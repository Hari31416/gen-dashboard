"""
Minimal FastAPI Application for Dashboard Generation

This is a simplified app that only includes the dashboard routes
for testing the new dashboard generation functionality.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from env import *
from utilities import create_simple_logger
from routes.auth import router as auth
from routes.database import router as database_router
from routes.dashboard import router as dashboard_router

load_dotenv()
logger = create_simple_logger(__name__)


app = FastAPI(title="Dashboard Generation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Core routes
app.include_router(auth)
app.include_router(database_router)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"message": "Dashboard Generation API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
