"""Downloadable course resources served from storage/resources."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import env

RESOURCE_MANIFEST = [
    {"id": "student-kit", "title": "代码框架与样本数据集", "filename": "si100b-bench-kit-v0.2.2.zip", "media_type": "application/zip"},
    {"id": "fer2013", "title": "FER2013 训练与测试数据集", "filename": "fer2013-train-test.zip", "media_type": "application/zip"},
    {"id": "lab1", "title": "Lab 1：环境配置与图像基础", "filename": "lab1.pdf"},
    {"id": "lab2", "title": "Lab 2：OpenCV 基本操作", "filename": "lab2.pdf"},
    {"id": "lab3", "title": "Lab 3：模型训练", "filename": "lab3.pdf"},
    {"id": "lab4", "title": "Lab 4：模型推理", "filename": "lab4.pdf"},
    {"id": "lab5", "title": "Lab 5：端到端流程", "filename": "lab5.pdf"},
    {"id": "lab6", "title": "Lab 6：Matplotlib 可视化", "filename": "lab6.pdf"},
    {"id": "lab7", "title": "Lab 7：数据标注的重要性", "filename": "lab7.pdf"},
    {"id": "lab8", "title": "Lab 8：扩展主题", "filename": "lab8.pdf"},
    {"id": "project-rules", "title": "项目评分完整规则", "filename": "face-emotion-project-rules.pdf"},
    {"id": "example-angry", "title": "公开样例：angry", "filename": "examples/angry.jpg", "media_type": "image/jpeg"},
    {"id": "example-disgust", "title": "公开样例：disgust", "filename": "examples/disgust.jpg", "media_type": "image/jpeg"},
    {"id": "example-fear", "title": "公开样例：fear", "filename": "examples/fear.jpg", "media_type": "image/jpeg"},
    {"id": "example-happy", "title": "公开样例：happy", "filename": "examples/happy.jpg", "media_type": "image/jpeg"},
    {"id": "example-neutral", "title": "公开样例：neutral", "filename": "examples/neutral.jpg", "media_type": "image/jpeg"},
    {"id": "example-sad", "title": "公开样例：sad", "filename": "examples/sad.jpg", "media_type": "image/jpeg"},
    {"id": "example-surprise", "title": "公开样例：surprise", "filename": "examples/surprise.jpg", "media_type": "image/jpeg"},
]


def resource_payload(item: dict[str, str]) -> dict[str, Any]:
    path = (env.RESOURCE_ROOT / item["filename"]).resolve()
    available = path.is_file() and env.RESOURCE_ROOT in path.parents
    return {
        "id": item["id"],
        "title": item["title"],
        "filename": item["filename"],
        "media_type": item.get("media_type", "application/pdf"),
        "available": available,
        "size": path.stat().st_size if available else 0,
        "download_url": f"/api/resources/{item['id']}/download" if available else None,
    }


def find_resource(resource_id: str) -> dict[str, str]:
    for item in RESOURCE_MANIFEST:
        if item["id"] == resource_id:
            return item
    raise HTTPException(status_code=404, detail="资源不存在。")
