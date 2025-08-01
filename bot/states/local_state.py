from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from typing import Dict


# Глобальное состояние игр
_games_state: Dict[str, "GameState"] = {}


@dataclass
class GameState:
    mode: str  # 'dm' or 'team'
    players: set[str] = field(default_factory=set)
    teams: dict[str, list[str]] = field(default_factory=dict)
    captains: dict[str, str] = field(default_factory=dict)  # team -> captain username
    scores: dict[str, int] = field(default_factory=dict)  # player/team -> score
    current_q_idx: int = 0
    total_questions: int = 0
    answers_right: set[str] = field(default_factory=set)
    answers_wrong: set[str] = field(default_factory=set)
    status: str = 'reg'  # 'reg' | 'playing' | 'finished'
    registration_ends_at: datetime | None = None
    timer_task: asyncio.Task | None = None
    message_id: int | None = None
    quiz_id: int | None = None
    questions: list = field(default_factory=list)
    current_question_msg_id: int | None = None
    quiz_name: str | None = None


def get_game_state(game_key: str) -> GameState:
    """Получить или создать состояние игры."""
    if game_key not in _games_state:
        _games_state[game_key] = GameState(mode="dm")
    return _games_state[game_key]


def _get_game_key_for_chat(chat_id: int) -> str | None:
    """Helper to find active game key by chat id."""
    chat_prefix = str(chat_id)
    for key in list(_games_state.keys()):
        if key.startswith(chat_prefix):
            return key
    return None


REGISTRATION_DURATION = 20  # seconds