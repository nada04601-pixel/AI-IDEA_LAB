from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import generation, projects, scenes
from app.db import init_db
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
app.include_router(projects.router)
app.include_router(scenes.router)
app.include_router(generation.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
