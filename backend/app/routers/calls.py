from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.call import Call, CallParticipant
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("/")
async def get_calls(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Call).join(CallParticipant).where(
            CallParticipant.user_id == current_user.id
        ).order_by(Call.created_at.desc()).limit(50)
    )
    calls = result.scalars().all()
    items = []
    for c in calls:
        items.append({
            "id": str(c.id),
            "chat_id": str(c.chat_id) if c.chat_id else None,
            "initiator_id": str(c.initiator_id),
            "call_type": c.call_type,
            "status": c.status,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
            "duration": c.duration,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "participants": [{
                "user_id": str(p.user_id),
                "is_muted": p.is_muted,
                "is_camera_off": p.is_camera_off,
                "is_screen_sharing": p.is_screen_sharing,
            } for p in c.participants]
        })
    return items


@router.post("/")
async def start_call(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    call = Call(
        chat_id=uuid_mod.UUID(data["chat_id"]) if data.get("chat_id") else None,
        initiator_id=current_user.id,
        call_type=data.get("call_type", "audio"),
        status="ringing",
        started_at=datetime.utcnow(),
    )
    db.add(call)
    await db.flush()

    # Добавить инициатора как участника
    db.add(CallParticipant(call_id=call.id, user_id=current_user.id, joined_at=datetime.utcnow()))

    # Добавить остальных участников
    for uid in data.get("participant_ids", []):
        db.add(CallParticipant(call_id=call.id, user_id=uuid_mod.UUID(uid)))

    return {"id": str(call.id), "status": "ringing"}


@router.post("/schedule")
async def schedule_call(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    from dateutil.parser import parse
    scheduled_at = parse(data["scheduled_at"]) if isinstance(data.get("scheduled_at"), str) else data.get("scheduled_at")

    call = Call(
        chat_id=uuid_mod.UUID(data["chat_id"]) if data.get("chat_id") else None,
        initiator_id=current_user.id,
        call_type=data.get("call_type", "audio"),
        status="scheduled",
        scheduled_at=scheduled_at,
    )
    db.add(call)
    await db.flush()

    for uid in data.get("participant_ids", []):
        db.add(CallParticipant(call_id=call.id, user_id=uuid_mod.UUID(uid)))

    return {"id": str(call.id), "status": "scheduled", "scheduled_at": scheduled_at.isoformat()}


@router.post("/{call_id}/join")
async def join_call(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(select(Call).where(Call.id == uuid_mod.UUID(call_id)))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Звонок не найден")

    # Проверить/добавить участника
    p_result = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == call.id, CallParticipant.user_id == current_user.id)
    )
    participant = p_result.scalar_one_or_none()
    if participant:
        participant.joined_at = datetime.utcnow()
        participant.left_at = None
    else:
        db.add(CallParticipant(call_id=call.id, user_id=current_user.id, joined_at=datetime.utcnow()))

    if call.status == "ringing":
        call.status = "active"
        call.started_at = datetime.utcnow()

    return {"status": "joined"}


@router.post("/{call_id}/leave")
async def leave_call(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == uuid_mod.UUID(call_id), CallParticipant.user_id == current_user.id)
    )
    participant = result.scalar_one_or_none()
    if participant:
        participant.left_at = datetime.utcnow()

    # Если все покинули — завершить
    call_result = await db.execute(select(Call).where(Call.id == uuid_mod.UUID(call_id)))
    call = call_result.scalar_one_or_none()
    if call:
        active_result = await db.execute(
            select(CallParticipant).where(
                CallParticipant.call_id == call.id,
                CallParticipant.joined_at != None,
                CallParticipant.left_at == None
            )
        )
        active = active_result.scalars().all()
        if len(active) == 0:
            call.status = "ended"
            call.ended_at = datetime.utcnow()
            if call.started_at:
                call.duration = int((call.ended_at - call.started_at).total_seconds())

    return {"status": "left"}


@router.post("/{call_id}/end")
async def end_call(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(select(Call).where(Call.id == uuid_mod.UUID(call_id)))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Звонок не найден")

    call.status = "ended"
    call.ended_at = datetime.utcnow()
    if call.started_at:
        call.duration = int((call.ended_at - call.started_at).total_seconds())
    return {"status": "ended"}


@router.post("/{call_id}/toggle-mute")
async def toggle_mute(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == uuid_mod.UUID(call_id), CallParticipant.user_id == current_user.id)
    )
    p = result.scalar_one_or_none()
    if p:
        p.is_muted = not p.is_muted
        return {"is_muted": p.is_muted}
    raise HTTPException(status_code=404, detail="Участник не найден")


@router.post("/{call_id}/toggle-camera")
async def toggle_camera(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == uuid_mod.UUID(call_id), CallParticipant.user_id == current_user.id)
    )
    p = result.scalar_one_or_none()
    if p:
        p.is_camera_off = not p.is_camera_off
        return {"is_camera_off": p.is_camera_off}
    raise HTTPException(status_code=404, detail="Участник не найден")


@router.post("/{call_id}/toggle-screen")
async def toggle_screen(call_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    result = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == uuid_mod.UUID(call_id), CallParticipant.user_id == current_user.id)
    )
    p = result.scalar_one_or_none()
    if p:
        p.is_screen_sharing = not p.is_screen_sharing
        return {"is_screen_sharing": p.is_screen_sharing}
    raise HTTPException(status_code=404, detail="Участник не найден")


@router.post("/{call_id}/add-participant")
async def add_participant(call_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as uuid_mod
    user_id = uuid_mod.UUID(data["user_id"])
    existing = await db.execute(
        select(CallParticipant).where(CallParticipant.call_id == uuid_mod.UUID(call_id), CallParticipant.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Участник уже в звонке")
    db.add(CallParticipant(call_id=uuid_mod.UUID(call_id), user_id=user_id))
    return {"message": "Участник добавлен"}
