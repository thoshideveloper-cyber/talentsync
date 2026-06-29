"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient

from db.models import User

pytestmark = pytest.mark.asyncio


async def test_login_success(admin_client: AsyncClient, admin_user: User):
    """Admin client fixture implies login succeeded."""
    resp = await admin_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == admin_user.email
    assert data["role"] == "admin"


async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "email": "admin@test.local", "password": "wrong"
    })
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "email": "nobody@test.local", "password": "pass"
    })
    assert resp.status_code == 401


async def test_protected_without_token(client: AsyncClient):
    """Unauthenticated requests to protected endpoints return 401 or 403."""
    resp = await client.get("/api/records")
    assert resp.status_code in (401, 403)


async def test_me_returns_current_user(recruiter_client: AsyncClient):
    resp = await recruiter_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "recruiter"


async def test_register_by_admin(admin_client: AsyncClient):
    resp = await admin_client.post("/api/auth/register", json={
        "email": "new_recruiter@test.local",
        "password": "newpass123",
        "role": "recruiter",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new_recruiter@test.local"
    assert data["role"] == "recruiter"


async def test_register_duplicate_email(admin_client: AsyncClient):
    await admin_client.post("/api/auth/register", json={
        "email": "dup@test.local", "password": "p", "role": "recruiter"
    })
    resp = await admin_client.post("/api/auth/register", json={
        "email": "dup@test.local", "password": "p", "role": "recruiter"
    })
    assert resp.status_code == 409


async def test_register_invalid_role(admin_client: AsyncClient):
    resp = await admin_client.post("/api/auth/register", json={
        "email": "x@test.local", "password": "p", "role": "superuser"
    })
    assert resp.status_code == 400


async def test_recruiter_cannot_register(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/auth/register", json={
        "email": "z@test.local", "password": "p", "role": "recruiter"
    })
    assert resp.status_code == 403
