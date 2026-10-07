"""FastAPI entry point.

Run locally:
    uvicorn backend.api.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers.auditor import router
from backend.api.routers.plans import router as plans_router

app = FastAPI(title="Ship Plan Compliance Auditor API", version="1.0.0")

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(router, prefix="/api")
app.include_router(plans_router, prefix="/api")
