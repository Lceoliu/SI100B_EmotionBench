# Emotional Bench

Emotional Bench is a course-scale benchmark platform for face-emotion classification projects. Students upload a single ONNX model, the server validates the model contract, evaluates it in a Docker-based worker, and publishes leaderboard results. TA administrators can manage users, groups, submissions, deadlines, resources, and runtime status.

## Features

- FastAPI backend with SQLite persistence.
- React frontend for students and TA administrators.
- ONNX-only submissions with NCHW input validation.
- Group grading: one leaderboard ranking each group by the best formal submission of its members.
- Students see their own best score, their group's best score and rank, and the group's remaining daily quota.
- Daily formal-submission quota per group; test submissions are unlimited and unscored. Students must set a group name before formal submissions.
- Server-side evaluation failures are recorded as system errors that do not use up quota, and TAs can re-run them.
- Docker Compose deployment with web, worker, and GPU monitor services.
- Student kit for local training, ONNX export, and devset checks.

## Repository Layout

```text
app/          FastAPI application and database models
worker/       evaluation queue worker
sandbox/      isolated model evaluation code
frontend/     React source
student_kit/  downloadable student code framework source
scripts/      data preparation, deployment, and monitoring scripts
docker/       Dockerfiles
```

Runtime data, submitted models, datasets, downloaded resource bundles, generated frontend builds, and evaluation results are intentionally ignored by git.

## Deployment

Create `.env` next to `docker-compose.yml` on the server:

```text
SECRET_KEY=replace-with-a-long-random-secret
ADMIN_INITIAL_PASSWORD=replace-with-a-strong-password
HOST_BENCH_ROOT=/absolute/path/to/this/checkout
INVITE_CODE=replace-with-this-term-invite-code
WEB_PORT=18080
SESSION_COOKIE_SECURE=0
```

| Variable | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | yes | Signs session cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `ADMIN_INITIAL_PASSWORD` | first start | Password for the `admin` account when it is created (at least 8 characters). Change it from the web console after logging in. |
| `HOST_BENCH_ROOT` | yes | Absolute host path of this checkout. The worker mounts submissions and data from it into evaluation containers. |
| `INVITE_CODE` | no | Seeded once as a registration invite. Manage further invites in the TA console; deleting an invite there is permanent. |
| `APP_ENV` | no | Defaults to `prod` in Compose, which refuses to start without the secrets above. |
| `SESSION_COOKIE_SECURE` | no | Set to `1` when the site is served over HTTPS. |
| `FORWARDED_ALLOW_IPS` | no | IPs of a reverse proxy allowed to set `X-Forwarded-For` (default `127.0.0.1`). If nginx on the host proxies to the container, set this to the Docker network gateway, otherwise every client shares one rate-limit bucket. |
| `ADMIN_RESET_PASSWORD_ON_STARTUP` | no | Set to `1` for one restart to reset the admin password to `ADMIN_INITIAL_PASSWORD`. |

Then start services:

```bash
docker compose up -d web
docker compose --profile eval build eval-image
docker compose --profile worker up -d worker
docker compose up -d gpu-monitor
```

The backend reads `config.yaml` and persistent admin settings from SQLite. The frontend is served from `frontend/dist`.

Before each semester, edit the `course`, `lectures` and `resources` sections of `config.yaml`: course name and term, allowed registration email domains, instructors and TAs, course links, lab cards, and the files served from `storage/resources/`. Restarting is not required; the values are read per request.

Evaluation data lives outside git:

```text
data/final/images/ + data/final/labels.csv    leaderboard set (falls back to data/public/)
data/dryrun/images/ + data/dryrun/labels.csv  sample set for test-mode submissions
```

`scripts/build_preprocess_cache.py` precomputes model inputs per input size, `scripts/build_student_kit.py` packages the student kit into `storage/resources/`, and `scripts/install_backup_cron.sh` installs a daily SQLite backup.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest

cd frontend && npm ci && npm run build
```

## Student Submission Contract

The platform accepts a single `.onnx` file.

- Layout: NCHW.
- Batch dimension: dynamic.
- Channels: `1` or `3`.
- Spatial size: `48`, `64`, `96`, `112`, `160`, or `224`.
- Output: `[B, 7]` logits.
- Class order: `angry`, `disgust`, `fear`, `happy`, `neutral`, `sad`, `surprise`.
- External ONNX data files are rejected.

## License

Licensed under Apache-2.0. See `LICENSE`.
