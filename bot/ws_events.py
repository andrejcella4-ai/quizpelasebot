"""WebSocket event dispatcher and handlers for game lifecycle."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot

from ws_manager import get_state, close_connection, register_event_handler
from helpers import (
    format_dm_registration,
    format_team_registration,
)
from keyboards import (
    registration_dm_keyboard,
    registration_team_keyboard,
    create_variant_keyboard,
)
from static.answer_texts import TextStatics
from static.choices import QuestionTypeChoices


async def handle_registration_update(game_key: str, payload: dict):
    game_state = get_state(game_key)

    if game_state.mode == "dm":
        game_state.players = set(payload.get("players", []))
    else:
        game_state.teams = payload.get("teams", {})

    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())

    if game_state.mode == "dm":
        text = format_dm_registration(game_state.players, seconds_left)
        kb = registration_dm_keyboard()
    else:
        text = format_team_registration(game_state.teams, seconds_left)
        kb = registration_team_keyboard(list(game_state.teams.keys()))

    bot = Bot.get_current()
    await bot.edit_message_text(
        chat_id=game_key.split("_", 1)[0],
        message_id=game_state.message_id,
        text=text,
        reply_markup=kb,
    )


async def handle_game_end(game_key: str, payload: dict):
    leaderboard = payload.get("leaderboard", [])
    lines = [f"{idx + 1}. {item['player']} — {item['score']}" for idx, item in enumerate(leaderboard)]
    text = "Игра окончена!\n" + "\n".join(lines)

    bot = Bot.get_current()
    await bot.send_message(game_key.split("_", 1)[0], text)

    chat_username, quiz_id_str = game_key.split("_", 1)
    await close_connection(chat_username, int(quiz_id_str))


async def handle_next_question(game_key: str, payload: dict):
    game_state = get_state(game_key)
    question = payload.get("new_question")
    if not question:
        return

    text = TextStatics.format_question_text(
        question.get("index", game_state.current_q_idx + 1),
        question["text"],
        question.get("time_to_answer", 10),
    )

    if question["type"] == QuestionTypeChoices.VARIANT:
        options = [a["text"] for a in question["answers"]]
        kb = create_variant_keyboard(options)
    else:
        kb = None

    bot = Bot.get_current()
    await bot.send_message(game_key.split("_", 1)[0], text, reply_markup=kb)
    game_state.current_q_idx += 1
    game_state.answers_right.clear()
    game_state.answers_wrong.clear()


_handler_map = {
    # from consumer via group_send type mapping to event (dots may appear)
    "registration_update": handle_registration_update,
    "registration.update": handle_registration_update,
    "game_end": handle_game_end,
    "game.end": handle_game_end,
    "game_start": handle_next_question,
    "game.start": handle_next_question,
    "next_question": handle_next_question,
    "game.next_question": handle_next_question,
}


async def process_ws_event(game_key: str, payload: dict):
    event = payload.get("event")
    handler = _handler_map.get(event)
    if handler:
        await handler(game_key, payload)


# Register dispatcher once when module imported
register_event_handler(process_ws_event) 