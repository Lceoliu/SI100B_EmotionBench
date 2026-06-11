FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:/usr/local/lib/python3.12/site-packages/nvidia/cufft/lib:/usr/local/lib/python3.12/site-packages/nvidia/curand/lib:/usr/local/lib/python3.12/site-packages/nvidia/cusolver/lib:/usr/local/lib/python3.12/site-packages/nvidia/cusparse/lib:/usr/local/lib/python3.12/site-packages/nvidia/nccl/lib:/usr/local/lib/python3.12/site-packages/nvidia/nvtx/lib:/usr/local/lib/python3.12/site-packages/nvidia/nvjitlink/lib

WORKDIR /eval
RUN addgroup --gid 1000 bench && adduser --disabled-password --gecos "" --uid 1000 --gid 1000 bench
COPY requirements-eval.txt /tmp/requirements-eval.txt
RUN pip install --timeout 180 --retries 10 -r /tmp/requirements-eval.txt
COPY sandbox/evaluate.py /evaluate.py
COPY sandbox/transforms.py /transforms.py
COPY scripts/gpu_smoke_test.py /gpu_smoke_test.py
USER 1000:1000
ENTRYPOINT ["python", "/evaluate.py"]
