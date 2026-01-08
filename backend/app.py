"""
Minimal FastAPI Application for Dashboard Generation

This is a simplified app that only includes the dashboard routes
for testing the new dashboard generation functionality.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys

from dotenv import load_dotenv

from utilities import create_simple_logger
from routes.auth import router as auth
from routes.database import router as database_router
from routes.dashboard import router as dashboard_router
import check_dependencies
import setup_admin_user

load_dotenv()
logger = create_simple_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    logger.info("=== Application Startup ===")

    # 1. Check dependencies
    logger.info("Running dependency checks...")
    dep_exit_code = check_dependencies.main()
    if dep_exit_code != 0:
        logger.error("Dependency checks failed. Exiting.")
        sys.exit(1)

    # 2. Setup admin user
    logger.info("Setting up admin user...")
    admin_exit_code = setup_admin_user.main()
    if admin_exit_code != 0:
        logger.error("Admin user setup failed. Exiting.")
        sys.exit(1)

    logger.info("Startup tasks completed successfully.")

    yield

    logger.info("Application shutting down...")


app = FastAPI(title="Dashboard Generation API", version="0.1.0", lifespan=lifespan)
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
