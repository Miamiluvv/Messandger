import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, data: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(user_id)

    async def send_to_users(self, user_ids: list, data: dict):
        for uid in user_ids:
            await self.send_to_user(uid, data)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "message":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "new_message",
                    "chat_id": data.get("chat_id"),
                    "message": data.get("message"),
                })

            elif event_type == "typing":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "typing",
                    "chat_id": data.get("chat_id"),
                    "user_id": user_id,
                })

            elif event_type == "stop_typing":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "stop_typing",
                    "chat_id": data.get("chat_id"),
                    "user_id": user_id,
                })

            elif event_type == "read":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "read",
                    "chat_id": data.get("chat_id"),
                    "user_id": user_id,
                })

            elif event_type == "call_signal":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "call_signal",
                    "call_id": data.get("call_id"),
                    "signal_type": data.get("signal_type"),
                    "signal": data.get("signal"),
                    "from_user": user_id,
                })

            elif event_type == "call_invite":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "call_invite",
                    "call_id": data.get("call_id"),
                    "call_type": data.get("call_type", "audio"),
                    "from_user": user_id,
                    "from_name": data.get("from_name", ""),
                    "from_avatar": data.get("from_avatar"),
                })

            elif event_type == "call_accept":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "call_accept",
                    "call_id": data.get("call_id"),
                    "from_user": user_id,
                })

            elif event_type == "call_reject":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "call_reject",
                    "call_id": data.get("call_id"),
                    "from_user": user_id,
                })

            elif event_type == "call_end":
                recipients = data.get("recipients", [])
                await manager.send_to_users(recipients, {
                    "type": "call_end",
                    "call_id": data.get("call_id"),
                    "from_user": user_id,
                })

    except WebSocketDisconnect:
        manager.disconnect(user_id)
