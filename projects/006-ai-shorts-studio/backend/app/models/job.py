from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.project import utcnow

ACTIVE_JOB_STATUSES = ("queued", "running")


class Job(Base):
    """시간이 걸리는 생성 작업. 요청과 완료 확인을 분리하고, 실패하면 재시도할 수 있다."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True, nullable=True)
    job_type: Mapped[str] = mapped_column(String(20))  # image, video, audio, render
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, running, succeeded, failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(50))
    provider_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="")  # 요청 시점의 프롬프트 (재시도에 그대로 사용)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scene = relationship("Scene", back_populates="jobs")
    assets = relationship("Asset", passive_deletes=True)
