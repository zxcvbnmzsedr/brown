from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db
from backend.routers import auth, assets, buckets, csv_export, groups, history, opening_positions, portfolio, prices, rebalance, transactions
from backend.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Brown API", version="0.2.0", lifespan=lifespan)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(buckets.router)
app.include_router(groups.router)
app.include_router(assets.router)
app.include_router(opening_positions.router)
app.include_router(transactions.router)
app.include_router(portfolio.router)
app.include_router(rebalance.router)
app.include_router(prices.router)
app.include_router(history.router)
app.include_router(csv_export.router)


@app.get("/")
def root():
    return {"name": "Brown API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
