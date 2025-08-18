from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from typing import Dict


# Глобальное состояние игр
_games_state: Dict[str, "GameState"] = {}


class GameModeChoices:
    solo = 'solo'
    team = 'team'
    dm = 'dm'


@dataclass
class GameState:
    mode: str  # 'dm' or 'team'
    players: set[str] = field(default_factory=set)
    teams: dict[str, list[str]] = field(default_factory=dict)
    captains: dict[str, str] = field(default_factory=dict)  # team -> captain username
    scores: dict[str, int] = field(default_factory=dict)  # player/team -> score
    team_id: int | None = None
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
    attempts_left_by_user: dict[str, int] = field(default_factory=dict)
    waiting_next: bool = False
    available_quizzes: list[dict] = field(default_factory=list)
    selected_quiz_name: str | None = None
    current_options: list[str] | None = None
    # --- anti-race / lifecycle flags ---
    question_token: int = 0  # increments on each new question
    question_result_sent: bool = False  # per-question result summary sent
    finished_sent: bool = False  # final results sent
    is_finishing: bool = False  # finalization in progress
    transition_lock: asyncio.Lock | None = None  # serializes transitions
    # snapshot of current question to avoid index races
    current_question_id: int | None = None
    current_correct_answer: str | None = None
    # prevent duplicate Next transitions
    next_in_progress: bool = False


def get_game_state(game_key: str) -> GameState:
    """Получить или создать состояние игры."""
    if game_key not in _games_state:
        _games_state[game_key] = GameState(mode="dm")
        # Инициализируем лок для переходов
        _games_state[game_key].transition_lock = asyncio.Lock()
    return _games_state[game_key]


def _get_game_key_for_chat(chat_id: int) -> str | None:
    """Helper to find active game key by chat id."""
    chat_prefix = str(chat_id)
    for key in list(_games_state.keys()):
        if key.startswith(chat_prefix):
            return key
    return None


REGISTRATION_DURATION = 20  # seconds