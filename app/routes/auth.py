"""Administrator login and logout browser routes."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import (
    authenticate_admin,
    create_authenticated_session,
    get_current_admin,
    logout_session,
    verify_csrf_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _login_template(request: Request, error: str | None = None) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "login.html", {"app_name": "InventoryHub", "error": error})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    try:
        get_current_admin(request, db)
    except HTTPException:
        return _login_template(request)
    return RedirectResponse(url="/", status_code=303)


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(min_length=1, max_length=64),
    password: str = Form(min_length=1, max_length=128),
    db: Session = Depends(get_db),
):
    admin = authenticate_admin(username, password, db)
    if admin is None:
        return _login_template(request, error="Invalid username or password.")
    create_authenticated_session(admin, request, db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
):
    get_current_admin(request, db)
    verify_csrf_token(request, csrf_token)
    logout_session(request, db)
    return RedirectResponse(url="/auth/login", status_code=303)
