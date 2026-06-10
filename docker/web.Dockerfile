FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace
RUN addgroup --gid 1000 bench && adduser --disabled-password --gecos "" --uid 1000 --gid 1000 bench
COPY requirements-web.txt /tmp/requirements-web.txt
RUN python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/requirements-web.txt
USER 1000:1000
