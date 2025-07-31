import asyncio
import json
from typing import Dict, Optional

import aiohttp
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from datetime import datetime, timedelta

load_dotenv()

# Unique key is f"{chat_username}_{quiz_id}"
_connections: Dict[str, "WSConnection"] = {}
_state = {}

# external async callback setter
_event_handler = None  # type: ignore


def register_event_handler(handler):
    """Called from other modules to subscribe on websocket events."""
    global _event_handler
    _event_handler = handler


_WS_BASE_URL = os.getenv("WS_BASE_URL", "ws://localhost:8000")
# Формируем адрес: <base>/ws/group-quiz/team/<chat>/<chat>/<quiz_id>/
WS_URL_TEMPLATE = _WS_BASE_URL + "/ws/group-quiz/team/{chat}/{quiz_id}/"  # requires trailing slash


@dataclass
class GameState:
    mode: str  # 'dm' or 'team'
    players: set[str] = field(default_factory=set)
    teams: dict[str, list[str]] = field(default_factory=dict)
    captains: dict[str, str] = field(default_factory=dict)  # team -> captain username
    current_q_idx: int = 0
    total_questions: int = 0
    answers_right: set[str] = field(default_factory=set)
    answers_wrong: set[str] = field(default_factory=set)
    status: str = 'reg'  # 'reg' | 'playing' | 'finished'
    registration_ends_at: datetime | None = None
    timer_task: asyncio.Task | None = None
    last_question_msg_id: int | None = None
    quiz_id: int | None = None


class WSConnection:
    def __init__(self, key: str, url: str):
        self.key = key
        self.url = url
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.listener_task: Optional[asyncio.Task] = None

    async def connect(self):
        if self.ws and not self.ws.closed:
            return
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(self.url)
        self.listener_task = asyncio.create_task(self._listener())

    async def _listener(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Dispatch to team_handlers
                    if _event_handler:
                        try:
                            await _event_handler(self.key, data)
                        except Exception as exc:
                            print(f"WS dispatch error for {self.key}: {exc}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        except Exception as e:
            print(f"WS listener error for {self.key}: {e}")
        finally:
            await self.close()

    async def send_json(self, payload: dict):
        if self.ws and not self.ws.closed:
            await self.ws.send_json(payload)

    async def close(self):
        if self.listener_task and not self.listener_task.done():
            self.listener_task.cancel()
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session:
            await self.session.close()


async def get_connection(chat_username: str, quiz_id: int) -> WSConnection:
    key = f"{chat_username}_{quiz_id}"
    if key not in _connections:
        url = WS_URL_TEMPLATE.format(chat=chat_username, quiz_id=quiz_id)
        conn = WSConnection(key, url)
        _connections[key] = conn
        await conn.connect()
    return _connections[key]


async def close_connection(chat_username: str, quiz_id: int):
    key = f"{chat_username}_{quiz_id}"
    conn = _connections.pop(key, None)
    if conn:
        await conn.close()
        gs = _state.pop(key, None)
        if gs and gs.timer_task and not gs.timer_task.done():
            gs.timer_task.cancel()


def get_state(key: str) -> GameState:
    if key not in _state:
        _state[key] = GameState(mode='dm')
    return _state[key]
 