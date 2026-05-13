from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.db import init_db
from server.routers import accounts, admin, auth, catalog, portfolio, transactions, user_assets
from server.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Brown API", version="1.0.0", lifespan=lifespan)

default_cors_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5175",
]
env_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origins = list(dict.fromkeys([*default_cors_origins, *env_cors_origins]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(catalog.router)
app.include_router(portfolio.router)
app.include_router(accounts.router)
app.include_router(user_assets.router)
app.include_router(transactions.router)


@app.get("/")
def root():
    return {"name": "Brown API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
