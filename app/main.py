"""FastAPI 入口."""
import os
from pathlib import Path
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
    # 只在 static 目录存在时才挂载静态文件
    static_dir = Path("static")
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/static", StaticFiles(directory="static"), name="static")
    init_scheduler(app)
    return app


app = create_app()


