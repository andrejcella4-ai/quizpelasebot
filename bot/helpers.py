from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from fsm import SoloGameStates


def schedule_question_timeout(delay: int, state: FSMContext, index: int, q: dict, message: types.Message, send_question_fn) -> asyncio.Task:
    async def timer():
        try:
            await asyncio.sleep(delay)
            curr_data = await state.get_data()
            if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                await message.answer(f'Время вышло! Правильный ответ: {q["correct_answer"]}')
                await state.update_data(incorrect=curr_data.get('incorrect', 0) + 1, current_index=index + 1)
                await send_question_fn(message, state)
        except asyncio.CancelledError:
            pass
    return asyncio.create_task(timer())


async def fetch_question_and_cancel(state: FSMContext) -> tuple[int, dict] | tuple[None, None]:
    data = await state.get_data()
    index = data.get('current_index', 0)
    questions = data.get('questions', [])

    if index >= len(questions):
        return None, None

    q = questions[index]
    task = data.get('timer_task')

    if task:
        task.cancel()

    return index, q


async def schedule_registration_end(ends_at: datetime, on_expire):
    """Возвращает task, который спит до конца регистрации и затем вызывает on_expire()."""

    async def _sleep():
        try:
            delay = max(0, (ends_at - datetime.utcnow()).total_seconds())
            await asyncio.sleep(delay)
            await on_expire()
        except asyncio.CancelledError:
            pass

    return asyncio.create_task(_sleep())


def format_dm_registration(players: set[str], time_left: int) -> str:
    players_text = "\n".join(f"— {p}" for p in players) or "—"
    return (
        f"Регистрация на игру (DM). Старт через {time_left} сек.\n\n"
        f"Участники:\n{players_text}"
    )


def format_team_registration(teams: dict[str, list[str]], time_left: int) -> str:
    if not teams:
        teams_text = "—"
    else:
        parts = []
        for name, members in teams.items():
            users = ", ".join(members)
            parts.append(f"{name}: {users}")
        teams_text = "\n".join(parts)
    return (
        f"Регистрация командной игры. Старт через {time_left} сек.\n\n"
        f"Команды:\n{teams_text}"
    )


def get_team_of_player(username: str, game_state) -> str | None:
    for team_name, members in game_state.teams.items():
        if username in members:
            return team_name
    return None


def is_captain(username: str, game_state) -> bool:
    team = get_team_of_player(username, game_state)
    if not team:
        return False
    return game_state.captains.get(team) == username


def format_game_status(game_state, question_text: str | None = None) -> str:
    """Return human-readable status of current game."""
    if game_state.status == 'reg':
        seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
        if game_state.mode == 'dm':
            return format_dm_registration(game_state.players, seconds_left)
        return format_team_registration(game_state.teams, seconds_left)

    if game_state.status == 'playing':
        lines = [f"Сейчас вопрос №{game_state.current_q_idx + 1}"]
        if question_text:
            lines.append(question_text)
        if game_state.mode == 'dm':
            lines.append('Ответили правильно: ' + ', '.join(game_state.answers_right))
            lines.append('Ответили неправильно: ' + ', '.join(game_state.answers_wrong))
        else:
            lines.append('Команды:')
            for team, members in game_state.teams.items():
                lines.append(f"{team}: {', '.join(members)}")
        return '\n'.join(lines)

    return 'Игра завершена.'
