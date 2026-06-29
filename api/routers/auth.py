"""Auth endpoints: login, register (admin only), /me."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, UserRole
from api.auth import hash_password, verify_password, create_access_token
from api.deps import get_db, get_current_user, require_role, write_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "recruiter"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    await write_audit(db, actor_id=user.id, action="login", detail={"email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "role": user.role.value},
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Admin-only: create a new user."""
    try:
        role = UserRole(req.role)
    except ValueError:
        raise HTTPException(400, f"Invalid role '{req.role}'. Must be recruiter/approver/admin.")

    existing = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "A user with that email already exists")

    new_user = User(
        email=req.email.lower().strip(),
        hashed_password=hash_password(req.password),
        role=role,
        tenant_id=admin.tenant_id,
    )
    db.add(new_user)
    await db.flush()
    await write_audit(
        db,
        actor_id=admin.id,
        action="user.create",
        target_type="user",
        target_id=new_user.id,
        detail={"email": new_user.email, "role": role.value},
        tenant_id=admin.tenant_id,
    )
    return {"id": str(new_user.id), "email": new_user.email, "role": new_user.role.value}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "role": user.role.value}
