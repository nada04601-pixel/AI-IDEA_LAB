from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)

# 기존 DB에 나중에 추가된 열. (테이블, 열, SQLite 열 정의) — 추가만 하고 삭제·변경은 하지 않는다.
# 스키마 변경이 이보다 복잡해지면 Alembic으로 옮긴다.
ADDED_COLUMNS = [
    ("projects", "script", "TEXT NOT NULL DEFAULT ''"),  # 2단계
]


def _add_missing_columns(eng: Engine) -> None:
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, column, ddl in ADDED_COLUMNS:
            if not insp.has_table(table):
                continue
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db(url: str) -> None:
    """엔진을 만들고, 없는 테이블은 생성하고, 이전 버전 DB에 빠진 열을 추가한다."""
    global engine
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SessionLocal.configure(bind=engine)
    from app.models import asset, job, project, scene  # noqa: F401  테이블 등록

    _add_missing_columns(engine)
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
