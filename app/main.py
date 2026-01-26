"""FastAPI 入口."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.services.scheduler import init_scheduler
from app.web.routes import router as web_router


def create_app() -> FastAPI:
    """Create FastAPI app."""
    app = FastAPI(title="Makeup Bot")
    init_db()
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    init_scheduler(app)
    return app


app = create_app()


