"""SQLite 작업 기록. 작업 상태, 업로드 결과(중복 방지), 성과 지표를 저장한다."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    topic_id TEXT,
    topic TEXT,
    difficulty TEXT,
    source TEXT,
    seed INTEGER,
    status TEXT NOT NULL,
    puzzle_path TEXT,
    video_path TEXT,
    video_sha256 TEXT,
    duration REAL,
    title TEXT,
    description TEXT,
    tags TEXT,
    review_flags TEXT,
    error TEXT,
    attempts INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS uploads (
    job_id TEXT PRIMARY KEY,
    video_sha256 TEXT UNIQUE,
    youtube_id TEXT,
    privacy TEXT,
    upload_status TEXT,
    processing_status TEXT,
    uploaded_at TEXT,
    last_checked TEXT
);
CREATE TABLE IF NOT EXISTS stats (
    youtube_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER
);
"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class JobDB:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ----- jobs -----
    def create_job(self, job_id: str, **fields: Any) -> None:
        ts = now()
        data = {"job_id": job_id, "created_at": ts, "updated_at": ts, "status": "created", **fields}
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        self.conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", list(data.values()))
        self.conn.commit()

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        for k, v in list(fields.items()):
            if isinstance(v, (list, dict)):
                fields[k] = json.dumps(v, ensure_ascii=False)
        fields["updated_at"] = now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE jobs SET {sets} WHERE job_id = ?", [*fields.values(), job_id])
        self.conn.commit()

    def get_job(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_topic_ids(self, limit: int = 10) -> list[str]:
        rows = self.conn.execute(
            "SELECT topic_id FROM jobs WHERE status NOT IN ('failed') "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["topic_id"] for r in rows if r["topic_id"]]

    def topic_use_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT topic_id, COUNT(*) AS n FROM jobs WHERE status NOT IN ('failed') GROUP BY topic_id"
        ).fetchall()
        return {r["topic_id"]: r["n"] for r in rows}

    def recent_titles(self, limit: int = 50) -> list[str]:
        rows = self.conn.execute(
            "SELECT title FROM jobs WHERE title IS NOT NULL ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["title"] for r in rows]

    def jobs_ready_to_upload(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT j.* FROM jobs j LEFT JOIN uploads u ON u.job_id = j.job_id "
            "WHERE j.status = 'ready' AND u.job_id IS NULL ORDER BY j.created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    # ----- uploads (중복 방지) -----
    def find_upload(self, job_id: str | None = None, sha256: str | None = None) -> dict | None:
        row = None
        if job_id:
            row = self.conn.execute("SELECT * FROM uploads WHERE job_id = ?", (job_id,)).fetchone()
        if row is None and sha256:
            row = self.conn.execute("SELECT * FROM uploads WHERE video_sha256 = ?", (sha256,)).fetchone()
        return dict(row) if row else None

    def record_upload(self, job_id: str, sha256: str, youtube_id: str, privacy: str,
                      upload_status: str, processing_status: str | None = None) -> None:
        ts = now()
        self.conn.execute(
            "INSERT OR REPLACE INTO uploads (job_id, video_sha256, youtube_id, privacy, upload_status, "
            "processing_status, uploaded_at, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, sha256, youtube_id, privacy, upload_status, processing_status, ts, ts),
        )
        self.conn.commit()

    def update_upload_status(self, youtube_id: str, upload_status: str, processing_status: str | None) -> None:
        self.conn.execute(
            "UPDATE uploads SET upload_status = ?, processing_status = ?, last_checked = ? WHERE youtube_id = ?",
            (upload_status, processing_status, now(), youtube_id),
        )
        self.conn.commit()

    def list_uploads(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM uploads ORDER BY uploaded_at").fetchall()]

    # ----- stats -----
    def add_stats(self, youtube_id: str, views: int | None, likes: int | None, comments: int | None) -> None:
        self.conn.execute(
            "INSERT INTO stats (youtube_id, fetched_at, view_count, like_count, comment_count) VALUES (?, ?, ?, ?, ?)",
            (youtube_id, now(), views, likes, comments),
        )
        self.conn.commit()

    def export_csv(self, path: Path) -> int:
        rows = self.conn.execute(
            "SELECT j.job_id, j.created_at, j.topic, j.difficulty, j.source, j.status, j.duration, j.title, "
            "u.youtube_id, u.privacy, u.upload_status, u.uploaded_at, "
            "(SELECT view_count FROM stats s WHERE s.youtube_id = u.youtube_id ORDER BY fetched_at DESC LIMIT 1) AS views, "
            "(SELECT like_count FROM stats s WHERE s.youtube_id = u.youtube_id ORDER BY fetched_at DESC LIMIT 1) AS likes "
            "FROM jobs j LEFT JOIN uploads u ON u.job_id = j.job_id ORDER BY j.created_at"
        ).fetchall()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if rows:
                w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(list(r))
        return len(rows)
