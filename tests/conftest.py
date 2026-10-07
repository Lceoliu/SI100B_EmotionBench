from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(tempfile.mkdtemp(prefix="emotion-bench-tests-"))
TEST_CONFIG = TEST_ROOT / "config.yaml"
TEST_CONFIG.write_text(
    "\n".join(
        [
            "quota_per_day: 4",
            "max_params: 50_000_000",
            "max_weight_mb: 200",
            "eval_timeout_sec: 600",
            "num_classes: 7",
            "freeze_leaderboard: false",
            'final_pick_deadline: ""',
            "course:",
            "  name: SI100B",
            "  term: Test Term",
            "  email_domains: [shanghaitech.edu.cn]",
            "  tas: [{name: TA One, url: 'https://example.com/ta'}, {name: TA Two}]",
            "lectures:",
            "  - {title: Lab 1, detail: Basics, resource: lab1}",
            "resources:",
            "  - {id: lab1, title: Lab 1, filename: lab1.pdf}",
            "  - {id: student-kit, title: Kit, filename: kit.zip, media_type: application/zip}",
            "  - {id: escape, title: Escape, filename: ../../config.yaml}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
BASE_CONFIG = TEST_CONFIG.read_text(encoding="utf-8")

# app.env reads its paths and secrets at import time, so the environment must be
# in place before any test module imports it.
os.environ.update(
    {
        "APP_ENV": "test",
        "BENCH_ROOT": str(TEST_ROOT),
        "CONFIG_PATH": str(TEST_CONFIG),
        "DATABASE_URL": f"sqlite:///{TEST_ROOT / 'storage' / 'bench.db'}",
        "FRONTEND_DIST": str(TEST_ROOT / "frontend-dist"),
        "SECRET_KEY": "test-secret-key",
        "ADMIN_INITIAL_PASSWORD": "admin-test-password",
        "INVITE_CODE": "TEST-INVITE",
    }
)
(TEST_ROOT / "storage").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO_ROOT))

ADMIN_PASSWORD = os.environ["ADMIN_INITIAL_PASSWORD"]
INVITE_CODE = os.environ["INVITE_CODE"]


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": csrf_token,
        "X-Request-Nonce": uuid.uuid4().hex,
        "X-Request-Time": str(int(time.time() * 1000)),
    }


class ApiClient:
    """TestClient wrapper that carries the session cookie and CSRF token like the frontend."""

    def __init__(self, client) -> None:
        self.client = client
        self.csrf = client.get("/api/session").json()["csrf_token"]
        self.user: dict | None = None

    def get(self, path: str, **kwargs):
        return self.client.get(path, **kwargs)

    def send(self, method: str, path: str, **kwargs):
        headers = {**mutation_headers(self.csrf), **kwargs.pop("headers", {})}
        return self.client.request(method, path, headers=headers, **kwargs)

    def post(self, path: str, **kwargs):
        return self.send("POST", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.send("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.send("DELETE", path, **kwargs)

    def register(self, email: str, password: str = "student-password", display_name: str = "Student", invite_code: str = INVITE_CODE):
        response = self.client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": display_name, "invite_code": invite_code},
        )
        if response.status_code == 200:
            self.csrf = response.json()["csrf_token"]
            self.user = response.json()["user"]
        return response

    def login(self, email: str, password: str):
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        if response.status_code == 200:
            self.csrf = response.json()["csrf_token"]
            self.user = response.json()["user"]
        return response

    def set_group(self, group_name: str):
        response = self.patch("/api/me/profile", json={"display_name": self.user["display_name"], "group_name": group_name})
        assert response.status_code == 200, response.text
        self.user = response.json()["user"]
        return response

    def submit(self, model_bytes: bytes, *, mode: str = "public", input_size: int = 48, input_channels: int = 1, filename: str = "model.onnx"):
        return self.post(
            "/api/submissions",
            data={"mode": mode, "input_size": str(input_size), "input_channels": str(input_channels)},
            files={"package": (filename, model_bytes, "application/octet-stream")},
        )


def make_onnx(
    *,
    channels: int = 1,
    size: int = 48,
    num_classes: int = 7,
    batch: str | int = "N",
    input_dtype: int | None = None,
    output_shape: list | None = None,
    bias_class: int | None = None,
) -> bytes:
    """Build a tiny Flatten+Gemm classifier; with bias_class set it always predicts that class."""
    import numpy as np
    from onnx import TensorProto, helper, numpy_helper

    input_dtype = TensorProto.FLOAT if input_dtype is None else input_dtype
    features = channels * size * size
    weight = np.zeros((features, num_classes), dtype=np.float32)
    bias = np.zeros((num_classes,), dtype=np.float32)
    if bias_class is not None:
        bias[bias_class] = 1.0
    graph = helper.make_graph(
        [
            helper.make_node("Flatten", ["input"], ["flat"], axis=1),
            helper.make_node("Gemm", ["flat", "W", "B"], ["logits"]),
        ],
        "tiny-classifier",
        [helper.make_tensor_value_info("input", input_dtype, [batch, channels, size, size])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, output_shape or [batch, num_classes])],
        initializer=[numpy_helper.from_array(weight, "W"), numpy_helper.from_array(bias, "B")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    return model.SerializeToString()


@pytest.fixture
def extra_config():
    """Append YAML to the test config.yaml for one test."""

    def apply(text: str) -> None:
        TEST_CONFIG.write_text(BASE_CONFIG + text, encoding="utf-8")

    yield apply
    TEST_CONFIG.write_text(BASE_CONFIG, encoding="utf-8")


@pytest.fixture
def app_module():
    """Reset all persistent state and expose the backend modules under one namespace."""
    from types import SimpleNamespace

    from sqlalchemy import func, select

    from app import config, db, env, main, models, security, seed

    db.Base.metadata.drop_all(db.engine)
    for bucket in (security.DOWNLOAD_EVENTS, security.AUTH_EVENTS, security.MUTATION_NONCES):
        bucket.clear()
    for path in (env.SUBMISSION_ROOT, env.INDEX_ROOT, env.RESULTS_ROOT, TEST_ROOT / "data", TEST_ROOT / "logs"):
        shutil.rmtree(path, ignore_errors=True)
    return SimpleNamespace(
        app=main.app,
        env=env,
        SessionLocal=db.SessionLocal,
        Base=db.Base,
        engine=db.engine,
        User=models.User,
        Submission=models.Submission,
        Score=models.Score,
        InviteCode=models.InviteCode,
        set_setting=config.set_setting,
        ensure_admin_user=seed.ensure_admin_user,
        seed_initial_data=seed.seed_initial_data,
        RequestSizeLimitMiddleware=security.RequestSizeLimitMiddleware,
        AUTH_LIMIT_PER_MINUTE=env.AUTH_LIMIT_PER_MINUTE,
        SUBMISSION_ROOT=env.SUBMISSION_ROOT,
        select=select,
        func=func,
    )


@pytest.fixture
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client


@pytest.fixture
def make_api(app_module, client):
    from fastapi.testclient import TestClient

    def factory() -> ApiClient:
        # Separate cookie jars so several users can act in one test; startup already ran via `client`.
        return ApiClient(TestClient(app_module.app))

    return factory


@pytest.fixture
def admin(make_api) -> ApiClient:
    api = make_api()
    assert api.login("admin", ADMIN_PASSWORD).status_code == 200
    return api


@pytest.fixture
def student(make_api) -> ApiClient:
    api = make_api()
    assert api.register("alice@shanghaitech.edu.cn", display_name="Alice").status_code == 200
    api.set_group("A组")
    return api


@pytest.fixture
def make_student(make_api):
    def factory(name: str, group_name: str = "") -> ApiClient:
        api = make_api()
        assert api.register(f"{name.lower()}@shanghaitech.edu.cn", display_name=name).status_code == 200
        if group_name:
            api.set_group(group_name)
        return api

    return factory


def mark_passed(app_module, submission_id: int, score: float) -> None:
    with app_module.SessionLocal() as db:
        submission = db.get(app_module.Submission, submission_id)
        submission.status = "passed"
        submission.public_score = score
        db.commit()


def set_status(app_module, submission_id: int, status: str) -> None:
    with app_module.SessionLocal() as db:
        db.get(app_module.Submission, submission_id).status = status
        db.commit()
