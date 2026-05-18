import uuid as uuid_mod
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.chat import Chat, ChatMember
from app.models.message import Message, MessageAttachment, Reaction
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("/")
async def get_chats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Chat).join(ChatMember).where(ChatMember.user_id == current_user.id).order_by(Chat.updated_at.desc())
    )
    chats = result.scalars().all()
    items = []
    for chat in chats:
        # Получить последнее сообщение
        msg_result = await db.execute(
            select(Message).where(Message.chat_id == chat.id, Message.is_deleted == False)
            .order_by(Message.created_at.desc()).limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()

        # Непрочитанные
        my_member = next((m for m in chat.members if m.user_id == current_user.id), None)
        unread = 0
        if my_member and my_member.last_read_message_id:
            unread_result = await db.execute(
                select(Message).where(
                    Message.chat_id == chat.id,
                    Message.created_at > (
                        select(Message.created_at).where(Message.id == my_member.last_read_message_id).scalar_subquery()
                    ),
                    Message.sender_id != current_user.id,
                    Message.is_deleted == False
                )
            )
            unread = len(unread_result.scalars().all())

        members_data = []
        for m in chat.members:
            u_result = await db.execute(select(User).where(User.id == m.user_id))
            u = u_result.scalar_one_or_none()
            if u:
                members_data.append({
                    "user_id": str(u.id),
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "avatar_url": u.avatar_url,
                    "status": u.status,
                    "role": m.role,
                })

        last_message_data = None
        if last_msg:
            sender_result = await db.execute(select(User).where(User.id == last_msg.sender_id))
            sender = sender_result.scalar_one_or_none()
            last_message_data = {
                "id": str(last_msg.id),
                "content": last_msg.content,
                "sender_name": f"{sender.first_name} {sender.last_name}" if sender else "",
                "created_at": last_msg.created_at.isoformat() if last_msg.created_at else None,
                "message_type": last_msg.message_type,
            }

        items.append({
            "id": str(chat.id),
            "chat_type": chat.chat_type,
            "name": chat.name,
            "description": chat.description,
            "avatar_url": chat.avatar_url,
            "is_news_channel": chat.is_news_channel,
            "show_deleted_label": chat.show_deleted_label,
            "members": members_data,
            "last_message": last_message_data,
            "unread_count": unread,
            "is_pinned": my_member.is_pinned if my_member else False,
        })

    return items


@router.post("/")
async def create_chat(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    chat_type = data.get("chat_type", "private")
    name = data.get("name")
    member_ids = data.get("member_ids", [])

    # Для приватного чата проверяем существующий
    if chat_type == "private" and len(member_ids) == 1:
        other_id = uuid_mod.UUID(member_ids[0])
        existing = await db.execute(
            select(Chat).join(ChatMember).where(
                Chat.chat_type == "private",
                ChatMember.user_id == current_user.id
            )
        )
        for chat in existing.scalars().all():
            member_ids_in_chat = [m.user_id for m in chat.members]
            if other_id in member_ids_in_chat and current_user.id in member_ids_in_chat and len(member_ids_in_chat) == 2:
                return {"id": str(chat.id), "existing": True}

    chat = Chat(
        chat_type=chat_type,
        name=name,
        owner_id=current_user.id,
    )
    db.add(chat)
    await db.flush()

    # Добавить создателя
    db.add(ChatMember(chat_id=chat.id, user_id=current_user.id, role="owner"))

    # Добавить участников
    for uid in member_ids:
        uid_parsed = uuid_mod.UUID(uid)
        if uid_parsed != current_user.id:
            role = "member"
            if chat_type == "channel":
                role = "readonly"
            elif chat_type == "group":
                u_result = await db.execute(select(User).where(User.id == uid_parsed))
                u = u_result.scalar_one_or_none()
                if u and u.role in ("head", "deputy_head"):
                    role = "admin"
            db.add(ChatMember(chat_id=chat.id, user_id=uid_parsed, role=role))

    return {"id": str(chat.id), "existing": False}


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    # Проверить членство
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")

    result = await db.execute(
        select(Message).where(Message.chat_id == cid, Message.is_scheduled == False)
        .order_by(Message.created_at.desc()).limit(limit).offset(offset)
    )
    messages = list(reversed(result.scalars().all()))

    # Compute read status: a message is "read" if every other chat member has
    # last_read_message_id pointing to a message at or after this one.
    members_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id != current_user.id)
    )
    other_members = members_result.scalars().all()
    # Build a set of message IDs already read by every other member
    if other_members and messages:
        # For each other member, find index of their last_read in this messages list
        msg_ids_in_order = [m.id for m in messages]
        msg_index = {mid: i for i, mid in enumerate(msg_ids_in_order)}
        # Smallest index across all other members (everyone has read up to here)
        min_idx = len(msg_ids_in_order)  # default: no one has read anything visible
        for m in other_members:
            if m.last_read_message_id and m.last_read_message_id in msg_index:
                min_idx = min(min_idx, msg_index[m.last_read_message_id])
            else:
                min_idx = -1
                break
        read_by_all = set(msg_ids_in_order[: min_idx + 1]) if min_idx >= 0 else set()
    else:
        read_by_all = set()

    items = []
    for msg in messages:
        sender_result = await db.execute(select(User).where(User.id == msg.sender_id))
        sender = sender_result.scalar_one_or_none()

        reply_data = None
        if msg.reply_to:
            reply_sender_result = await db.execute(select(User).where(User.id == msg.reply_to.sender_id))
            reply_sender = reply_sender_result.scalar_one_or_none()
            reply_data = {
                "id": str(msg.reply_to.id),
                "content": msg.reply_to.content,
                "sender_name": f"{reply_sender.first_name} {reply_sender.last_name}" if reply_sender else "",
            }

        attachments_data = [{
            "id": str(a.id),
            "file_name": a.file_name,
            "file_url": a.file_url,
            "file_size": a.file_size,
            "file_type": a.file_type,
            "thumbnail_url": a.thumbnail_url,
        } for a in msg.attachments]

        reactions_data = [{
            "id": str(r.id),
            "emoji": r.emoji,
            "user_id": str(r.user_id),
        } for r in msg.reactions]

        poll_data = None
        if msg.message_type == "poll" and msg.poll:
            poll = msg.poll
            opts = []
            for opt in poll.options:
                opts.append({
                    "id": str(opt.id),
                    "text": opt.option_text,
                    "vote_count": len(opt.votes),
                    "voted_by_me": any(v.user_id == current_user.id for v in opt.votes),
                    "voters": [] if poll.is_anonymous else [str(v.user_id) for v in opt.votes],
                })
            poll_data = {
                "id": str(poll.id),
                "question": poll.question,
                "is_anonymous": poll.is_anonymous,
                "is_multiple_choice": poll.is_multiple_choice,
                "closes_at": poll.closes_at.isoformat() if poll.closes_at else None,
                "options": opts,
                "total_votes": sum(o["vote_count"] for o in opts),
            }

        items.append({
            "id": str(msg.id),
            "chat_id": str(msg.chat_id),
            "sender_id": str(msg.sender_id),
            "sender_name": f"{sender.first_name} {sender.last_name}" if sender else "",
            "sender_avatar": sender.avatar_url if sender else None,
            "content": msg.content,
            "message_type": msg.message_type,
            "reply_to": reply_data,
            "is_edited": msg.is_edited,
            "is_deleted": msg.is_deleted,
            "is_pinned": msg.is_pinned,
            "attachments": attachments_data,
            "reactions": reactions_data,
            "poll": poll_data,
            "is_read": msg.id in read_by_all,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return items


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")
    if member.role == "readonly":
        raise HTTPException(status_code=403, detail="У вас нет прав на отправку сообщений в этот канал")

    message = Message(
        chat_id=cid,
        sender_id=current_user.id,
        content=data.get("content"),
        message_type=data.get("message_type", "text"),
        reply_to_id=uuid_mod.UUID(data["reply_to_id"]) if data.get("reply_to_id") else None,
        scheduled_at=data.get("scheduled_at"),
        is_scheduled=bool(data.get("scheduled_at")),
    )
    db.add(message)
    await db.flush()

    # Обновить last_read
    member.last_read_message_id = message.id

    # Обновить chat.updated_at
    chat_result = await db.execute(select(Chat).where(Chat.id == cid))
    chat = chat_result.scalar_one_or_none()
    if chat:
        chat.updated_at = datetime.utcnow()

    return {
        "id": str(message.id),
        "chat_id": str(message.chat_id),
        "sender_id": str(message.sender_id),
        "sender_name": f"{current_user.first_name} {current_user.last_name}",
        "sender_avatar": current_user.avatar_url,
        "content": message.content,
        "message_type": message.message_type,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "is_edited": False,
        "is_deleted": False,
        "attachments": [],
        "reactions": [],
        "reply_to": None,
    }


@router.put("/{chat_id}/messages/{message_id}")
async def edit_message(chat_id: str, message_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Message).where(Message.id == uuid_mod.UUID(message_id), Message.sender_id == current_user.id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    message.content = data.get("content", message.content)
    message.is_edited = True
    return {"message": "Обновлено"}


@router.delete("/{chat_id}/messages/{message_id}")
async def delete_message(chat_id: str, message_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    result = await db.execute(
        select(Message).where(Message.id == uuid_mod.UUID(message_id), Message.sender_id == current_user.id)
    )
    message = result.scalar_one_or_none()
    if not message:
        # Проверяем: может админ чата удаляет чужое сообщение
        member_result = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
        )
        member = member_result.scalar_one_or_none()
        if not member or member.role not in ("owner", "admin"):
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        result2 = await db.execute(select(Message).where(Message.id == uuid_mod.UUID(message_id)))
        message = result2.scalar_one_or_none()
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")

    # Определяем тип удаления
    chat_result = await db.execute(select(Chat).where(Chat.id == cid))
    chat = chat_result.scalar_one_or_none()

    # В каналах и избранном — всегда hard delete
    hard_delete = False
    if chat and (chat.chat_type in ("channel", "saved") or chat.is_news_channel):
        hard_delete = True
    elif chat and not chat.show_deleted_label:
        hard_delete = True

    if hard_delete:
        await db.delete(message)
    else:
        message.is_deleted = True
        message.content = None

    return {"message": "Удалено", "hard_delete": hard_delete}


@router.post("/{chat_id}/read")
async def mark_read(chat_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if member and data.get("message_id"):
        member.last_read_message_id = uuid_mod.UUID(data["message_id"])
    return {"ok": True}


@router.post("/{chat_id}/upload")
async def upload_file(
    chat_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member or member.role == "readonly":
        raise HTTPException(status_code=403, detail="Нет прав")

    # Сохранить файл
    file_id = str(uuid_mod.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    save_name = f"{file_id}{ext}"
    save_path = os.path.join(settings.UPLOAD_DIR, save_name)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    file_url = f"/uploads/{save_name}"
    file_size = len(content)
    file_type = file.content_type or "application/octet-stream"

    # Определить тип сообщения
    msg_type = "file"
    fname = file.filename or save_name
    if file_type.startswith("image"):
        msg_type = "image"
    elif file_type.startswith("video"):
        msg_type = "video"
    elif file_type.startswith("audio"):
        msg_type = "voice" if fname.startswith("voice_") else "audio"

    # Контент: для медиа не показываем имя файла
    display_content = None if msg_type in ("image", "video", "voice", "audio") else fname

    # Создать сообщение с вложением
    message = Message(
        chat_id=cid,
        sender_id=current_user.id,
        content=display_content,
        message_type=msg_type,
    )
    db.add(message)
    await db.flush()

    attachment = MessageAttachment(
        message_id=message.id,
        file_name=file.filename or save_name,
        file_url=file_url,
        file_size=file_size,
        file_type=file_type,
    )
    db.add(attachment)
    await db.flush()

    member.last_read_message_id = message.id
    chat_result = await db.execute(select(Chat).where(Chat.id == cid))
    chat_obj = chat_result.scalar_one_or_none()
    if chat_obj:
        chat_obj.updated_at = datetime.utcnow()

    return {
        "id": str(message.id),
        "chat_id": str(message.chat_id),
        "sender_id": str(message.sender_id),
        "sender_name": f"{current_user.first_name} {current_user.last_name}",
        "sender_avatar": current_user.avatar_url,
        "content": display_content,
        "message_type": msg_type,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "is_edited": False,
        "is_deleted": False,
        "attachments": [{
            "id": str(attachment.id),
            "file_name": attachment.file_name,
            "file_url": attachment.file_url,
            "file_size": attachment.file_size,
            "file_type": attachment.file_type,
            "thumbnail_url": None,
        }],
        "reactions": [],
        "reply_to": None,
    }


@router.post("/{chat_id}/members")
async def add_members(chat_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member or member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Нет прав на добавление участников")

    chat_result = await db.execute(select(Chat).where(Chat.id == cid))
    chat_obj = chat_result.scalar_one_or_none()

    added = []
    for uid in data.get("user_ids", []):
        uid_parsed = uuid_mod.UUID(uid)
        existing = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == uid_parsed)
        )
        if existing.scalar_one_or_none():
            continue
        role = "member"
        if chat_obj:
            if chat_obj.chat_type == "channel" and not chat_obj.is_news_channel:
                role = "readonly"
            elif chat_obj.chat_type == "group":
                u_result = await db.execute(select(User).where(User.id == uid_parsed))
                u = u_result.scalar_one_or_none()
                if u and u.role in ("head", "deputy_head"):
                    role = "admin"
        db.add(ChatMember(chat_id=cid, user_id=uid_parsed, role=role))
        added.append(uid)

    return {"added": added, "count": len(added)}


@router.delete("/{chat_id}/members/{user_id}")
async def remove_member(chat_id: str, user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member or member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Нет прав")

    target = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == uuid_mod.UUID(user_id))
    )
    target_member = target.scalar_one_or_none()
    if target_member:
        await db.delete(target_member)
    return {"message": "Участник удалён"}


@router.put("/{chat_id}/settings")
async def update_chat_settings(chat_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member or member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Нет прав")

    chat_result = await db.execute(select(Chat).where(Chat.id == cid))
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    if "name" in data:
        chat.name = data["name"]
    if "description" in data:
        chat.description = data["description"]
    if "show_deleted_label" in data:
        chat.show_deleted_label = data["show_deleted_label"]

    return {"message": "Настройки обновлены"}


@router.post("/{chat_id}/messages/{message_id}/reactions")
async def toggle_reaction(
    chat_id: str, message_id: str, data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mid = uuid_mod.UUID(message_id)
    emoji = data.get("emoji", "")
    if not emoji:
        raise HTTPException(status_code=400, detail="Укажите эмодзи")

    existing = await db.execute(
        select(Reaction).where(
            Reaction.message_id == mid,
            Reaction.user_id == current_user.id,
            Reaction.emoji == emoji
        )
    )
    reaction = existing.scalar_one_or_none()
    if reaction:
        await db.delete(reaction)
        return {"action": "removed", "emoji": emoji}
    else:
        r = Reaction(message_id=mid, user_id=current_user.id, emoji=emoji)
        db.add(r)
        await db.flush()
        return {"action": "added", "emoji": emoji, "id": str(r.id)}


@router.get("/{chat_id}/messages/scheduled")
async def list_scheduled_messages(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return all scheduled (not yet sent) messages of the current user in this chat."""
    cid = uuid_mod.UUID(chat_id)
    result = await db.execute(
        select(Message).where(
            Message.chat_id == cid,
            Message.sender_id == current_user.id,
            Message.is_scheduled == True,
        ).order_by(Message.scheduled_at.asc())
    )
    items = []
    for msg in result.scalars().all():
        items.append({
            "id": str(msg.id),
            "content": msg.content,
            "message_type": msg.message_type,
            "scheduled_at": msg.scheduled_at.isoformat() if msg.scheduled_at else None,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
    return items


@router.delete("/{chat_id}/messages/scheduled/{message_id}")
async def cancel_scheduled_message(
    chat_id: str, message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Message).where(
            Message.id == uuid_mod.UUID(message_id),
            Message.sender_id == current_user.id,
            Message.is_scheduled == True,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Запланированное сообщение не найдено")
    await db.delete(msg)
    return {"ok": True}


@router.post("/{chat_id}/messages/schedule")
async def schedule_message(
    chat_id: str, data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cid = uuid_mod.UUID(chat_id)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == cid, ChatMember.user_id == current_user.id)
    )
    member = member_check.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")

    from dateutil.parser import parse
    scheduled_at = parse(data["scheduled_at"]) if isinstance(data.get("scheduled_at"), str) else data.get("scheduled_at")

    message = Message(
        chat_id=cid,
        sender_id=current_user.id,
        content=data.get("content"),
        message_type="text",
        scheduled_at=scheduled_at,
        is_scheduled=True,
    )
    db.add(message)
    await db.flush()

    return {
        "id": str(message.id),
        "chat_id": str(message.chat_id),
        "content": message.content,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "is_scheduled": True,
    }
