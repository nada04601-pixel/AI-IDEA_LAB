from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config

config.load_env_file()  # 공급자·API 키 설정을 .env에서 읽는다 (다른 모듈보다 먼저)
from app.api import generation, projects, render, scenes
from app.db import init_db
from app.errors import install_error_handlers
from app.services.jobs import recover_interrupted_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(config.database_url())
    recover_interrupted_jobs()
    yield


app = FastAPI(title="AI Shorts Studio API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(projects.router)
app.include_router(scenes.router)
app.include_router(generation.router)
app.include_router(render.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
