"""FinPilot API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import User
from app.routers import router
from app.seed_data import seed_demo
from app.services.bank import BankError

logger = logging.getLogger("finpilot")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.seed_on_start:
        db = SessionLocal()
        try:
            if db.query(User).count() == 0:
                seed_demo(db)
        finally:
            db.close()
    yield


app = FastAPI(title="FinPilot", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(BankError)
def bank_error_handler(_request: Request, exc: BankError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})


@app.exception_handler(Exception)
def unhandled_error(_request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.warning("request failed")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})
