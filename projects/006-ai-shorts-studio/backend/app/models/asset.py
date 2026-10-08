from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.project import utcnow


class Asset(Base):
    """생성된 파일 하나. 재생성해도 지우지 않고 version을 올려 이력을 남긴다."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True, nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(20))  # image, video, audio, subtitle, render
    version: Mapped[int] = mapped_column(Integer, default=1)
    file_path: Mapped[str] = mapped_column(String(500))  # storage 폴더 기준 상대 경로
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    cost_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scene = relationship("Scene", back_populates="assets")
