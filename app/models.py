from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="student")
    group_name: Mapped[str] = mapped_column(String(120), default="")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    submit_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    leaderboard_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(24), default="public", index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    package_path: Mapped[str] = mapped_column(Text)
    model_format: Mapped[str] = mapped_column(String(24), default="onnx")
    input_size: Mapped[int] = mapped_column(Integer, default=224)
    input_channels: Mapped[int] = mapped_column(Integer, default=3)
    onnx_input_name: Mapped[str] = mapped_column(String(255), default="")
    onnx_opset: Mapped[int] = mapped_column(Integer, default=0)
    model_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    param_count: Mapped[int] = mapped_column(Integer, default=0)
    weight_mb: Mapped[float] = mapped_column(Float, default=0.0)
    public_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Legacy columns from the removed private split and final-pick feature. They stay mapped
    # because existing databases declare final_pick NOT NULL without a server default.
    private_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    realworld_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_pick: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="submissions")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    split: Mapped[str] = mapped_column(String(24), index=True)
    macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    confusion_json: Mapped[str] = mapped_column(Text, default="[]")
    per_class_json: Mapped[str] = mapped_column(Text, default="{}")
    predictions_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
