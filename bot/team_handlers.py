from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Dict

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from api_client import get_quiz_info
from keyboards import (
    main_menu_keyboard,
    registration_dm_keyboard,
    registration_team_keyboard,
    create_variant_keyboard
)

import ws_manager

from helpers import (
    format_dm_registration,
    format_team_registration,
    format_game_status,
    schedule_registration_end,
)
from static.answer_texts import TextStatics
from fsm import SoloGameStates, TeamGameStates

from static.choices import QuestionTypeChoices


router = Router(name="team_handlers")


# --------------------------------------------------------
# End game command (admin or any user)
# --------------------------------------------------------


@router.message(Command("end_game"))
async def manual_end_game(message: types.Message):
    chat_username = str(message.chat.id)

    active_key = _get_game_key_for_chat(message.chat.id)
    if not active_key:
        await message.answer("Сейчас нет активной игры.")
        return

    # Закрываем соединение и очищаем state
    chat_username, quiz_id_str = active_key.split("_", 1)
    await ws_manager.close_connection(chat_username, int(quiz_id_str))
    await message.answer("Игра принудительно завершена.")


# --------------------------------------------------------
# /game command – show current status or registration
# --------------------------------------------------------


@router.message(Command("game"))
async def show_game_status(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)

    if not game_key:
        await message.answer("Сейчас нет активной игры.")
        return

    game_state = ws_manager.get_state(game_key)

    text = format_game_status(game_state)
    await message.answer(text)


REGISTRATION_DURATION = 120  # seconds


async def _edit_or_send(message: types.Message, text: str, reply_markup: types.InlineKeyboardMarkup):
    """Utility: edit message if bot is author, else send new."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)


@router.callback_query(lambda c: c.data in {"game:dm", "game:team"})
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    """Callback after user selects DM or Team mode from main menu."""

    await callback.answer()

    if await ws_manager.get_state():
        await callback.message.answer(TextStatics.game_started_answer())
        return

    mode = "team" if callback.data == "game:team" else "dm"

    chat_username: str = str(callback.message.chat.id)

    # Запрашиваем актуальный квиз (как в соло-режиме)
    quiz_info = await get_quiz_info()
    quiz_id: int = quiz_info["id"]

    game_key = f"{chat_username}_{quiz_id}"

    # Инициализируем GameState
    game_state = ws_manager.get_state(game_key)
    game_state.mode = mode
    game_state.status = "reg"
    game_state.registration_ends_at = datetime.utcnow() + timedelta(seconds=REGISTRATION_DURATION)
    game_state.total_questions = quiz_info["amount_questions"]
    game_state.quiz_id = quiz_id

    # Открываем одно WS-соединение на игру (fire-and-forget)
    asyncio.create_task(get_connection(chat_username, quiz_id))

    # Build registration message
    if mode == "dm":
        reg_text = format_dm_registration(set(), REGISTRATION_DURATION)
        keyboard = registration_dm_keyboard()
    else:
        reg_text = format_team_registration({}, REGISTRATION_DURATION)
        keyboard = registration_team_keyboard([])

    # send initial reg message and keep message id
    sent_msg = await callback.message.answer(reg_text, reply_markup=keyboard)
    game_state.message_id = sent_msg.message_id  # type: ignore[attr-defined]

    # launch timer to edit
    async def on_expire():
        # Отправляем событие start_game в consumer
        connection = await ws_manager.get_connection(chat_username, quiz_id)
        await connection.send_json({"event": "start_game"})

        game_state.status = "playing"

        await callback.message.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=game_state.message_id,
            text="Регистрация завершена! Игра начинается…",
        )

    game_state.timer_task = await schedule_registration_end(
        game_state.registration_ends_at,
        on_expire,
    )

    await state.set_state(SoloGameStates.WAITING_CONFIRM)


# -------- регистрация участников / команд --------


@router.callback_query(lambda c: c.data == "reg:join")
async def reg_join_dm(callback: types.CallbackQuery):
    await callback.answer()

    chat_username = str(callback.message.chat.id)

    # Определяем активный quiz_id по сохранённому GameState
    active_key = next((k for k in ws_manager._state if k.startswith(chat_username)), None)  # type: ignore
    if not active_key:
        return

    game_state = ws_manager.get_state(active_key)

    if game_state.mode != "dm" or game_state.status != "reg":
        return

    username = callback.from_user.username or str(callback.from_user.id)
    game_state.players.add(username)

    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_dm_registration(game_state.players, seconds_left)

    await callback.message.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=game_state.message_id,
        text=updated_text,
        reply_markup=registration_dm_keyboard(),
    )


# ----------------- TEAM MODE callbacks -----------------


def _get_game_key_for_chat(chat_id: int) -> str | None:
    """Helper to find active game key by chat id."""
    chat_prefix = str(chat_id)
    for key in list(ws_manager._state.keys()):  # type: ignore[attr-defined]
        if key.startswith(chat_prefix):
            return key
    return None


@router.callback_query(lambda c: c.data == "reg:create_team")
async def create_team_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return

    game_state = ws_manager.get_state(game_key)
    if game_state.status != "reg" or game_state.mode != "team":
        return

    await callback.message.answer("Введите название новой команды:")
    await state.set_state(TeamGameStates.TEAM_CREATE_NAME)


@router.message(TeamGameStates.TEAM_CREATE_NAME)
async def team_name_entered(message: types.Message, state: FSMContext):
    team_name = message.text.strip()
    if not team_name:
        await message.answer("Название не может быть пустым. Введите ещё раз:")
        return

    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        await state.clear()
        return

    game_state = ws_manager.get_state(game_key)

    if team_name in game_state.teams:
        await message.answer("Такая команда уже существует. Введите другое название:")
        return

    username = message.from_user.username or str(message.from_user.id)
    game_state.teams[team_name] = [username]
    game_state.captains[team_name] = username

    # update message
    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_team_registration(game_state.teams, seconds_left)

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=game_state.message_id,
            text=updated_text,
            reply_markup=registration_team_keyboard(list(game_state.teams.keys())),
        )
    except Exception:
        pass

    # send to consumer
    connection = await ws_manager.get_connection(str(message.chat.id), game_state.quiz_id)
    await connection.send_json({
        "event": "registration_join",
        "username": username,
        "team_name": team_name,
    })

    await state.clear()


@router.callback_query(lambda c: c.data.startswith("reg:join:"))
async def join_team_callback(callback: types.CallbackQuery):
    await callback.answer()

    _, _, team_name = callback.data.partition(":join:")

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return

    game_state = ws_manager.get_state(game_key)

    if team_name not in game_state.teams:
        return

    username = callback.from_user.username or str(callback.from_user.id)

    # avoid duplicates
    if username in game_state.teams[team_name]:
        return

    game_state.teams[team_name].append(username)

    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_team_registration(game_state.teams, seconds_left)

    await callback.message.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=game_state.message_id,
        text=updated_text,
        reply_markup=registration_team_keyboard(list(game_state.teams.keys())),
    )

    # notify consumer
    connection = await ws_manager.get_connection(str(callback.message.chat.id), game_state.quiz_id)
    await connection.send_json({
        "event": "registration_join",
        "username": username,
        "team_name": team_name,
    })
