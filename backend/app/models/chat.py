import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text
from app.types import GUID
from sqlalchemy.orm import relationship

from app.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    chat_type = Column(String(20), nullable=False)  # private, group, channel, saved
    name = Column(String(200))
    description = Column(Text)
    avatar_url = Column(String(500))
    owner_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"))
    is_news_channel = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    show_deleted_label = Column(Boolean, default=True)  # False = hard delete, True = show "deleted"
    max_members = Column(Integer, default=1000)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("ChatMember", back_populates="chat", lazy="selectin", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", lazy="noload", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    chat_id = Column(GUID, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default="member")  # owner, admin, member, readonly
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_read_message_id = Column(GUID)
    notifications_enabled = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)

    chat = relationship("Chat", back_populates="members")
    user = relationship("User")
