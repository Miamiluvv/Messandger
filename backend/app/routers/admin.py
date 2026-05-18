from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User, AccessRequest, Department, Division, ProfileChangeRequest
from app.models.chat import Chat, ChatMember
from app.services.auth import get_password_hash, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ('super_admin', 'admin'):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return current_user


# ===========================================================================
# УПРАВЛЕНИЕ ЗАПРОСАМИ НА ДОСТУП
# ===========================================================================

@router.get("/access-requests")
async def list_access_requests(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = select(AccessRequest)
    if status:
        query = query.where(AccessRequest.status == status)
    query = query.order_by(AccessRequest.created_at.desc())
    result = await db.execute(query)
    requests = result.scalars().all()
    return [{
        "id": str(r.id),
        "first_name": r.first_name,
        "last_name": r.last_name,
        "patronymic": r.patronymic,
        "email": r.email,
        "phone": r.phone,
        "department_id": str(r.department_id) if r.department_id else None,
        "division_id": str(r.division_id) if r.division_id else None,
        "position": r.position,
        "reason": r.reason,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in requests]


@router.post("/access-requests/{request_id}/approve")
async def approve_access_request(
    request_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    import uuid as uuid_mod
    result = await db.execute(select(AccessRequest).where(AccessRequest.id == uuid_mod.UUID(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Запрос уже обработан")

    # Создаем пользователя
    password = data.get("password", "Temp123!")
    user = User(
        email=req.email,
        password_hash=get_password_hash(password),
        first_name=req.first_name,
        last_name=req.last_name,
        patronymic=req.patronymic,
        phone=req.phone,
        department_id=req.department_id,
        division_id=req.division_id,
        position=req.position,
        role=data.get("role", "user"),
    )
    db.add(user)
    await db.flush()

    # Подписать на новостной канал
    news_result = await db.execute(select(Chat).where(Chat.is_news_channel == True))
    news_channel = news_result.scalar_one_or_none()
    if news_channel:
        member = ChatMember(chat_id=news_channel.id, user_id=user.id, role="readonly")
        db.add(member)

    # Создать "Избранное"
    saved_chat = Chat(chat_type="saved", name="Избранное", owner_id=user.id)
    db.add(saved_chat)
    await db.flush()
    saved_member = ChatMember(chat_id=saved_chat.id, user_id=user.id, role="owner")
    db.add(saved_member)

    # Обновить запрос
    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()

    return {"message": f"Пользователь {req.email} создан", "user_id": str(user.id), "password": password}


@router.post("/access-requests/{request_id}/reject")
async def reject_access_request(
    request_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    import uuid as uuid_mod
    result = await db.execute(select(AccessRequest).where(AccessRequest.id == uuid_mod.UUID(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    req.status = "rejected"
    req.reviewed_by = admin.id
    req.review_comment = data.get("comment", "")
    req.reviewed_at = datetime.utcnow()
    return {"message": "Запрос отклонён"}


# ===========================================================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ===========================================================================

@router.get("/users")
async def list_users(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = select(User)
    if q:
        query = query.where(
            (User.first_name.ilike(f"%{q}%")) |
            (User.last_name.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%"))
        )
    query = query.order_by(User.last_name, User.first_name).limit(100)
    result = await db.execute(query)
    users = result.scalars().all()
    return [{
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "patronymic": u.patronymic,
        "position": u.position,
        "role": u.role,
        "is_active": u.is_active,
        "is_blocked": u.is_blocked,
        "is_frozen": u.is_frozen,
        "department_id": str(u.department_id) if u.department_id else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    } for u in users]


@router.post("/users/create")
async def create_user(data: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    existing = await db.execute(select(User).where(User.email == data.get("email")))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже используется")

    password = data.get("password", "Temp123!")
    user = User(
        email=data["email"],
        password_hash=get_password_hash(password),
        first_name=data["first_name"],
        last_name=data["last_name"],
        patronymic=data.get("patronymic"),
        phone=data.get("phone"),
        department_id=data.get("department_id"),
        division_id=data.get("division_id"),
        position=data.get("position"),
        role=data.get("role", "user"),
    )
    db.add(user)
    await db.flush()

    # Подписать на новостной канал
    news_result = await db.execute(select(Chat).where(Chat.is_news_channel == True))
    news_channel = news_result.scalar_one_or_none()
    if news_channel:
        db.add(ChatMember(chat_id=news_channel.id, user_id=user.id, role="readonly"))

    # Создать "Избранное"
    saved_chat = Chat(chat_type="saved", name="Избранное", owner_id=user.id)
    db.add(saved_chat)
    await db.flush()
    db.add(ChatMember(chat_id=saved_chat.id, user_id=user.id, role="owner"))

    return {"message": "Пользователь создан", "user_id": str(user.id), "password": password}


@router.put("/users/{user_id}")
async def update_user(user_id: str, data: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    allowed_fields = ["first_name", "last_name", "patronymic", "position", "role", "department_id", "division_id", "phone"]
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    db.add(user)
    return {"message": "Пользователь обновлён"}


@router.post("/users/{user_id}/block")
async def block_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_blocked = True
    return {"message": "Пользователь заблокирован"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_blocked = False
    user.password_expires_at = datetime.utcnow() + timedelta(days=90)
    return {"message": "Пользователь разблокирован"}


@router.post("/users/{user_id}/freeze")
async def freeze_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_frozen = True
    return {"message": "Аккаунт заморожен"}


@router.post("/users/{user_id}/unfreeze")
async def unfreeze_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_frozen = False
    return {"message": "Аккаунт разморожен"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_active = False
    return {"message": "Пользователь удалён"}


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, data: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    new_password = data.get("password", "Temp123!")
    user.password_hash = get_password_hash(new_password)
    user.password_changed_at = datetime.utcnow()
    user.password_expires_at = datetime.utcnow() + timedelta(days=90)
    user.is_blocked = False
    return {"message": "Пароль сброшен", "password": new_password}


# ===========================================================================
# ЗАПРОСЫ НА ИЗМЕНЕНИЕ ПРОФИЛЯ
# ===========================================================================

@router.get("/profile-requests")
async def list_profile_requests(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(
        select(ProfileChangeRequest).where(ProfileChangeRequest.status == "pending").order_by(ProfileChangeRequest.created_at.desc())
    )
    requests = result.scalars().all()
    return [{
        "id": str(r.id),
        "user_id": str(r.user_id),
        "field_name": r.field_name,
        "old_value": r.old_value,
        "new_value": r.new_value,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in requests]


@router.post("/profile-requests/{request_id}/approve")
async def approve_profile_request(request_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(ProfileChangeRequest).where(ProfileChangeRequest.id == uuid_mod.UUID(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    # Применить изменение
    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        setattr(user, req.field_name, req.new_value)

    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    return {"message": "Изменение применено"}


@router.post("/profile-requests/{request_id}/reject")
async def reject_profile_request(request_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    import uuid as uuid_mod
    result = await db.execute(select(ProfileChangeRequest).where(ProfileChangeRequest.id == uuid_mod.UUID(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    return {"message": "Запрос отклонён"}
