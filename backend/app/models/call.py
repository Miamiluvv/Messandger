import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from app.types import GUID
from sqlalchemy.orm import relationship

from app.database import Base


class Call(Base):
    __tablename__ = "calls"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    chat_id = Column(GUID, ForeignKey("chats.id", ondelete="SET NULL"))
    initiator_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    call_type = Column(String(10), nullable=False)  # audio, video
    status = Column(String(20), default="ringing")  # ringing, active, ended, missed, declined, scheduled
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    initiator = relationship("User")
    chat = relationship("Chat")
    participants = relationship("CallParticipant", back_populates="call", lazy="selectin", cascade="all, delete-orphan")


class CallParticipant(Base):
    __tablename__ = "call_participants"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    call_id = Column(GUID, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True))
    left_at = Column(DateTime(timezone=True))
    is_muted = Column(Boolean, default=False)
    is_camera_off = Column(Boolean, default=False)
    is_screen_sharing = Column(Boolean, default=False)

    call = relationship("Call", back_populates="participants")
    user = relationship("User")
