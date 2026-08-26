"""FastAPI entry point for InventoryHub."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import Base, engine

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local tables now; models will be added in later phases."""
    Base.metadata.create_all(bind=engine)
    logger.info("Application started in %s environment", settings.environment)
    yield
    logger.info("Application stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Render the initial dashboard shell."""
    return templates.TemplateResponse(request, "dashboard.html", {"app_name": settings.app_name})


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Health endpoint for local checks and eventual ALB target health checks."""
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures without exposing internal details to callers."""
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

