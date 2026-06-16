# Emotional Bench

Emotional Bench is a course-scale benchmark platform for face-emotion classification projects. Students upload a single ONNX model, the server validates the model contract, evaluates it in a Docker-based worker, and publishes leaderboard results. TA administrators can manage users, groups, submissions, deadlines, resources, and runtime status.

## Features

- FastAPI backend with SQLite persistence.
- React frontend for students and TA administrators.
- ONNX-only submissions with NCHW input validation.
- Public leaderboard, personal submission records, and detailed reports.
- Daily formal submission quota and separate test submissions.
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

Create `.env` on the server:

```text
SECRET_KEY=replace-with-a-long-random-secret
WEB_PORT=18080
SESSION_COOKIE_SECURE=0
```

Then start services:

```bash
docker compose up -d web
docker compose --profile worker up -d worker
docker compose up -d gpu-monitor
```

The backend reads `config.yaml` and persistent admin settings from SQLite. The frontend is served from `frontend/dist`.

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
