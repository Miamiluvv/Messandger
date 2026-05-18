import os
import uuid as uuid_mod
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User, AccessRequest, Department, Division, ProfileChangeRequest
from app.models.chat import Chat, ChatMember
from app.services.auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory rate limit store: { key -> (failed_count, lock_until_dt) }
# Key combines email + client IP. Resets on successful login.
_login_attempts: dict = {}
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_MINUTES = 15
LOGIN_WINDOW_MINUTES = 15


def _rate_limit_key(email: str, request: Request) -> str:
    ip = request.client.host if request and request.client else "unknown"
    return f"{email.lower()}|{ip}"


def _check_rate_limit(key: str):
    rec = _login_attempts.get(key)
    if not rec:
        return
    fails, locked_until = rec
    now = datetime.utcnow()
    if locked_until and now < locked_until:
        remaining = int((locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Слишком много неудачных попыток входа. Попробуйте через {remaining} мин.",
        )


def _record_login_failure(key: str):
    rec = _login_attempts.get(key, (0, None))
    fails = rec[0] + 1
    locked_until = None
    if fails >= LOGIN_MAX_FAILS:
        locked_until = datetime.utcnow() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        fails = 0  # reset counter while locked
    _login_attempts[key] = (fails, locked_until)


def _reset_login_attempts(key: str):
    _login_attempts.pop(key, None)


# ===========================================================================
# ВХОД В СИСТЕМУ
# ===========================================================================

@router.post("/login")
async def login(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    email = data.get("email", "")
    password = data.get("password", "")

    rate_key = _rate_limit_key(email, request)
    _check_rate_limit(rate_key)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        _record_login_failure(rate_key)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт деактивирован")
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован. Обратитесь в Управление информатизации")
    if user.is_frozen:
        raise HTTPException(status_code=403, detail="Аккаунт заморожен. Обратитесь в Управление информатизации")

    # Проверка истечения пароля
    password_expired = False
    if user.password_expires_at and datetime.utcnow() > user.password_expires_at:
        password_expired = True

    _reset_login_attempts(rate_key)
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "password_expired": password_expired
    }


# ===========================================================================
# ЗАПРОС НА ДОСТУП (вместо регистрации)
# ===========================================================================

@router.post("/access-request")
async def create_access_request(data: dict, db: AsyncSession = Depends(get_db)):
    # Проверка что email не занят
    existing = await db.execute(select(User).where(User.email == data.get("email")))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    existing_req = await db.execute(
        select(AccessRequest).where(
            AccessRequest.email == data.get("email"),
            AccessRequest.status == "pending"
        )
    )
    if existing_req.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Запрос с таким email уже отправлен и ожидает рассмотрения")

    dept_id = data.get("department_id") or None
    div_id = data.get("division_id") or None

    request = AccessRequest(
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        patronymic=data.get("patronymic") or None,
        email=data.get("email", ""),
        phone=data.get("phone") or None,
        department_id=dept_id,
        division_id=div_id,
        position=data.get("position") or None,
        reason=data.get("reason") or None,
    )
    db.add(request)
    return {"message": "Запрос отправлен в Управление информатизации"}


@router.get("/departments")
async def get_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).where(Department.is_active == True))
    departments = result.scalars().all()
    return [{"id": str(d.id), "name": d.name, "short_name": d.short_name} for d in departments]


@router.get("/divisions/{department_id}")
async def get_divisions(department_id: str, db: AsyncSession = Depends(get_db)):
    import uuid as uuid_mod
    result = await db.execute(
        select(Division).where(Division.department_id == uuid_mod.UUID(department_id), Division.is_active == True)
    )
    divisions = result.scalars().all()
    return [{"id": str(d.id), "name": d.name, "short_name": d.short_name} for d in divisions]


# ===========================================================================
# ПРОФИЛЬ
# ===========================================================================

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dept = None
    if current_user.department_id:
        r = await db.execute(select(Department).where(Department.id == current_user.department_id))
        dept = r.scalar_one_or_none()
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "patronymic": current_user.patronymic,
        "avatar_url": current_user.avatar_url,
        "phone": current_user.phone,
        "department": dept.name if dept else None,
        "department_id": str(current_user.department_id) if current_user.department_id else None,
        "position": current_user.position,
        "role": current_user.role,
        "status": current_user.status,
        "password_expired": current_user.password_expired,
        "avatar_visibility": current_user.avatar_visibility or "all",
        "avatar_visibility_list": json.loads(current_user.avatar_visibility_list) if current_user.avatar_visibility_list else [],
    }


@router.put("/me/avatar")
async def update_avatar(data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    current_user.avatar_url = data.get("avatar_url")
    db.add(current_user)
    return {"message": "Аватар обновлён", "avatar_url": current_user.avatar_url}


@router.post("/me/avatar/upload")
async def upload_avatar(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ext = os.path.splitext(file.filename or "avatar.png")[1] or ".png"
    save_name = f"avatar_{current_user.id}_{uuid_mod.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(settings.UPLOAD_DIR, save_name)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    url = f"/uploads/{save_name}"
    current_user.avatar_url = url
    db.add(current_user)
    return {"message": "Аватар обновлён", "avatar_url": url}


@router.put("/me/avatar-visibility")
async def update_avatar_visibility(data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    visibility = data.get("visibility", "all")
    if visibility not in ("all", "contacts", "selected", "except"):
        raise HTTPException(status_code=400, detail="Неверный тип видимости")
    current_user.avatar_visibility = visibility
    user_ids = data.get("user_ids", [])
    current_user.avatar_visibility_list = json.dumps(user_ids) if user_ids else None
    db.add(current_user)
    return {"message": "Настройки видимости обновлены"}


@router.put("/me/password")
async def change_password(data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")

    current_user.password_hash = get_password_hash(new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.password_expires_at = datetime.utcnow() + timedelta(days=90)
    db.add(current_user)
    return {"message": "Пароль успешно изменён"}


@router.post("/me/request-name-change")
async def request_name_change(data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    field = data.get("field")  # first_name, last_name, patronymic
    new_value = data.get("new_value", "").strip()
    if field not in ("first_name", "last_name", "patronymic"):
        raise HTTPException(status_code=400, detail="Недопустимое поле")
    if not new_value:
        raise HTTPException(status_code=400, detail="Значение не может быть пустым")

    old_value = getattr(current_user, field, "")
    request = ProfileChangeRequest(
        user_id=current_user.id,
        field_name=field,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(request)
    return {"message": "Запрос на изменение отправлен в Управление информатизации"}


# ===========================================================================
# ПОИСК ПОЛЬЗОВАТЕЛЕЙ
# ===========================================================================

@router.get("/users")
async def search_users(q: str = "", db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(User).where(User.is_active == True, User.id != current_user.id)
    if q:
        query = query.where(
            (User.first_name.ilike(f"%{q}%")) |
            (User.last_name.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%")) |
            (User.position.ilike(f"%{q}%"))
        )
    query = query.limit(50)
    result = await db.execute(query)
    users = result.scalars().all()
    return [{
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "patronymic": u.patronymic,
        "avatar_url": u.avatar_url,
        "position": u.position,
        "role": u.role,
        "department_id": str(u.department_id) if u.department_id else None,
        "status": u.status,
    } for u in users]
