from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
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


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")  # 외래 키 제약을 실제로 지킨다
    cur.execute("PRAGMA journal_mode=WAL")  # 읽기와 쓰기가 서로 덜 막히게 한다
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


def init_db(url: str) -> None:
    """엔진을 만들고, 없는 테이블은 생성하고, 이전 버전 DB에 빠진 열을 추가한다."""
    global engine
    is_sqlite = url.startswith("sqlite")
    # 백그라운드 작업과 요청이 동시에 쓸 수 있으므로 잠금 대기 시간을 넉넉히 준다
    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    engine = create_engine(url, connect_args=connect_args)
    if is_sqlite:
        event.listen(engine, "connect", _sqlite_pragmas)
    SessionLocal.configure(bind=engine)
    from app.models import asset, job, project, scene  # noqa: F401  테이블 등록

    _add_missing_columns(engine)
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
