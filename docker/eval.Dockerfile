FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /eval
RUN addgroup --gid 1000 bench && adduser --disabled-password --gecos "" --uid 1000 --gid 1000 bench
COPY requirements-eval.txt /tmp/requirements-eval.txt
RUN pip install --timeout 180 --retries 10 -r /tmp/requirements-eval.txt
COPY sandbox/evaluate.py /evaluate.py
COPY scripts/gpu_smoke_test.py /gpu_smoke_test.py
USER 1000:1000
ENTRYPOINT ["python", "/evaluate.py"]
