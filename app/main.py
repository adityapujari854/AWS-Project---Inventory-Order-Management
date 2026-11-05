"""FastAPI entry point for InventoryHub."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import Base, apply_development_schema_updates, engine, get_db
from app.models import admin, category, inventory, order, product, supplier  # noqa: F401 - registers SQLAlchemy models before table creation
from app.routes import auth as auth_routes
from app.routes import advisor as advisor_routes
from app.routes import categories as category_routes
from app.routes import inventory as inventory_routes
from app.routes import analytics as analytics_routes
from app.routes import orders as order_routes
from app.routes import products as product_routes
from app.routes import suppliers as supplier_routes
from app.security import get_current_admin

settings = get_settings()
APP_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = APP_DIRECTORY / "static"
TEMPLATE_DIRECTORY = APP_DIRECTORY / "templates"
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local development storage without applying schema changes in production."""
    if settings.environment.lower() != "production":
        Base.metadata.create_all(bind=engine)
        apply_development_schema_updates()
    else:
        logger.info("Production startup expects schema migrations to be applied before the application starts")
    logger.info("Application started in %s environment", settings.environment)
    yield
    logger.info("Application stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="inventoryhub_session",
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
app.state.templates = templates
app.include_router(auth_routes.router)
app.include_router(advisor_routes.router)
app.include_router(category_routes.router)
app.include_router(product_routes.router)
app.include_router(inventory_routes.router)
app.include_router(analytics_routes.router)
app.include_router(supplier_routes.router)
app.include_router(order_routes.router)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Render the initial dashboard shell."""
    try:
        admin_user = get_current_admin(request, db)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "app_name": settings.app_name,
            "admin_username": admin_user.username,
            "csrf_token": request.session["csrf_token"],
        },
    )


@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    """Render the protected product image-management page."""
    try:
        admin_user = get_current_admin(request, db)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "products.html",
        {
            "app_name": settings.app_name,
            "admin_username": admin_user.username,
            "csrf_token": request.session["csrf_token"],
        },
    )


@app.get("/advisor", response_class=HTMLResponse)
def advisor_page(request: Request, db: Session = Depends(get_db)):
    """Render the protected, read-only inventory-advisor page."""
    try:
        admin_user = get_current_admin(request, db)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "advisor.html",
        {"app_name": settings.app_name, "admin_username": admin_user.username, "csrf_token": request.session["csrf_token"]},
    )


def _operations_page(request: Request, db: Session, page: str, title: str):
    try:
        admin_user = get_current_admin(request, db)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(request, "operations.html", {"app_name": settings.app_name, "admin_username": admin_user.username, "csrf_token": request.session["csrf_token"], "page": page, "title": title})


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, db: Session = Depends(get_db)):
    return _operations_page(request, db, "inventory", "Inventory")


@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db)):
    return _operations_page(request, db, "orders", "Orders")


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_page(request: Request, db: Session = Depends(get_db)):
    return _operations_page(request, db, "suppliers", "Suppliers")


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    return _operations_page(request, db, "analytics", "Analytics")


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Health endpoint for local checks and eventual ALB target health checks."""
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures without exposing internal details to callers."""
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
