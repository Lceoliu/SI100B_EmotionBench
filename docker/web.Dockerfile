FROM docker.m.daocloud.io/library/node:20-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install
COPY frontend/ ./
RUN npm run build

FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /workspace
RUN addgroup --gid 1000 bench && adduser --disabled-password --gecos "" --uid 1000 --gid 1000 bench
COPY requirements-web.txt /tmp/requirements-web.txt
RUN python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/requirements-web.txt
COPY --from=frontend /frontend/dist /app/frontend/dist
USER 1000:1000
