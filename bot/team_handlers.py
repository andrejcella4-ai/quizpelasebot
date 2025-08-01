from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from api_client import get_quiz_info, get_questions, auth_player
from keyboards import (
    main_menu_keyboard,
    registration_dm_keyboard,
    registration_team_keyboard,
    create_variant_keyboard
)

from helpers import (
    start_game_questions,
    process_answer,
    format_dm_registration,
    format_team_registration,
    format_game_status,
    schedule_registration_end,
)
from states.local_state import (
    GameState,
    get_game_state,
    _get_game_key_for_chat,
    _games_state,
    REGISTRATION_DURATION,
)
from static.answer_texts import TextStatics
from states.fsm import SoloGameStates, TeamGameStates
from static.choices import QuestionTypeChoices


router = Router(name="team_handlers")


# --------------------------------------------------------
# End game command (admin or any user)
# --------------------------------------------------------

@router.message(Command("end_game"))
async def manual_end_game(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        await message.answer("Сейчас нет активной игры.")
        return

    game_state = get_game_state(game_key)
    
    # Отменяем таймеры
    if game_state.timer_task:
        game_state.timer_task.cancel()
    
    # Показываем результаты
    if not game_state.scores:
        text = "Игра окончена! Никто не участвовал."
    else:
        # Сортируем по очкам
        sorted_scores = sorted(game_state.scores.items(), key=lambda x: x[1], reverse=True)
        lines = [f"{idx + 1}. {name} — {score}" for idx, (name, score) in enumerate(sorted_scores)]
        text = "🏆 Игра окончена!\n\n" + "\n".join(lines)
    
    await message.bot.send_message(message.chat.id, text)
    
    # Очищаем состояние
    del _games_state[game_key]
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

    game_state = get_game_state(game_key)
    text = format_game_status(game_state)
    await message.answer(text)


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

    # Проверяем есть ли уже активная игра
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if game_key:
        game_state = get_game_state(game_key)
        if game_state.status == "playing":
            await callback.answer("Игра уже идет! Дождитесь её завершения.", show_alert=True)
            return

    if await state.get_state():
        await callback.answer("Игра уже идет! Сначала завершите предыдущую игру командой /end_game", show_alert=True)
        return

    mode = "team" if callback.data == "game:team" else "dm"
    chat_username: str = str(callback.message.chat.id)

    # Авторизуем игрока для получения токена
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name or "",
        username=callback.from_user.username,
        phone=None,
        lang_code=callback.from_user.language_code
    )

    # Запрашиваем актуальный квиз
    quiz_info = await get_quiz_info(mode)
    quiz_id: int = quiz_info["id"]

    game_key = f"{chat_username}_{quiz_id}"

    # Инициализируем GameState
    game_state = get_game_state(game_key)
    game_state.mode = mode
    game_state.status = "reg"
    game_state.registration_ends_at = datetime.utcnow() + timedelta(seconds=REGISTRATION_DURATION)
    game_state.total_questions = quiz_info["amount_questions"]
    game_state.quiz_id = quiz_id
    game_state.quiz_name = quiz_info["name"]

    # Получаем вопросы заранее
    questions_data = await get_questions(token, quiz_id)
    game_state.questions = questions_data["questions"]

    # Build registration message
    if mode == "dm":
        reg_text = format_dm_registration(set(), REGISTRATION_DURATION, quiz_info["name"])
        keyboard = registration_dm_keyboard()
    else:
        reg_text = format_team_registration({}, REGISTRATION_DURATION, quiz_info["name"])
        keyboard = registration_team_keyboard([])

    # send initial reg message and keep message id
    sent_msg = await callback.message.answer(reg_text, reply_markup=keyboard)
    game_state.message_id = sent_msg.message_id

    # launch timer to start game
    async def on_expire():
        try:
            game_state.status = "playing"
            
            await callback.message.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=game_state.message_id,
                text="Регистрация завершена! Игра начинается…",
            )
            
            # Начинаем игру - показываем первый вопрос
            await start_game_questions(callback, game_state)
        except Exception as e:
            print(f"Ошибка в on_expire: {e}")
            import traceback
            traceback.print_exc()

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
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return

    game_state = get_game_state(game_key)

    if game_state.mode != "dm" or game_state.status != "reg":
        return

    username = callback.from_user.username or str(callback.from_user.id)
    game_state.players.add(username)

    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_dm_registration(game_state.players, seconds_left, game_state.quiz_name)

    await callback.message.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=game_state.message_id,
        text=updated_text,
        reply_markup=registration_dm_keyboard(),
    )


# ----------------- TEAM MODE callbacks -----------------

@router.callback_query(lambda c: c.data == "reg:create_team")
async def create_team_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return

    game_state = get_game_state(game_key)
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

    game_state = get_game_state(game_key)

    if team_name in game_state.teams:
        await message.answer("Такая команда уже существует. Введите другое название:")
        return

    username = message.from_user.username or str(message.from_user.id)
    game_state.teams[team_name] = [username]
    game_state.captains[team_name] = username

    # update message
    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_team_registration(game_state.teams, seconds_left, game_state.quiz_name)

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=game_state.message_id,
            text=updated_text,
            reply_markup=registration_team_keyboard(list(game_state.teams.keys())),
        )
    except Exception:
        pass

    await state.clear()


@router.callback_query(lambda c: c.data.startswith("reg:join:"))
async def join_team_callback(callback: types.CallbackQuery):
    await callback.answer()

    _, _, team_name = callback.data.partition(":join:")

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return

    game_state = get_game_state(game_key)

    if team_name not in game_state.teams:
        return

    username = callback.from_user.username or str(callback.from_user.id)

    # avoid duplicates
    if username in game_state.teams[team_name]:
        return

    game_state.teams[team_name].append(username)

    seconds_left = int((game_state.registration_ends_at - datetime.utcnow()).total_seconds())
    updated_text = format_team_registration(game_state.teams, seconds_left, game_state.quiz_name)

    await callback.message.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=game_state.message_id,
        text=updated_text,
        reply_markup=registration_team_keyboard(list(game_state.teams.keys())),
    )


# -------- обработка ответов во время игры --------

@router.callback_query(lambda c: c.data.startswith("answer:") and _get_game_key_for_chat(c.message.chat.id))
async def answer_variant_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    
    game_state = get_game_state(game_key)
    if game_state.status != "playing":
        return
    
    # Проверяем что это текущий вопрос (не старый)
    if callback.message.message_id != game_state.current_question_msg_id:
        await callback.answer("Этот вопрос уже неактуален!", show_alert=True)
        return
    
    username = callback.from_user.username or str(callback.from_user.id)
    
    # Проверяем права на ответ
    if game_state.mode == "team":
        # В командном режиме может отвечать только капитан
        user_team = None
        for team, members in game_state.teams.items():
            if username in members:
                user_team = team
                break
        
        if not user_team or game_state.captains.get(user_team) != username:
            await callback.answer("Отвечать может только капитан команды!", show_alert=True)
            return
    
    # Проверяем, что игрок еще не отвечал
    if username in game_state.answers_right or username in game_state.answers_wrong:
        await callback.answer("Вы уже ответили на этот вопрос!", show_alert=True)
        return
    
    # Получаем ответ
    _, variant_text = callback.data.split(":", 1)
    await process_answer(
        callback.message.bot, 
        callback.message.chat.id, 
        game_state, 
        username, 
        variant_text,
        callback
    )


@router.message(lambda m: m.chat and _get_game_key_for_chat(m.chat.id) and get_game_state(_get_game_key_for_chat(m.chat.id)).status == "playing")
async def answer_text_message(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        return
    
    game_state = get_game_state(game_key)
    
    # Проверяем, что это текстовый вопрос
    if game_state.current_q_idx >= len(game_state.questions):
        return
    
    current_question = game_state.questions[game_state.current_q_idx]
    if current_question["question_type"] != QuestionTypeChoices.TEXT:
        return
    
    username = message.from_user.username or str(message.from_user.id)
    
    # Проверяем права на ответ в командном режиме
    if game_state.mode == "team":
        user_team = None
        for team, members in game_state.teams.items():
            if username in members:
                user_team = team
                break
        
        if not user_team or game_state.captains.get(user_team) != username:
            return
    
    # Проверяем, что игрок еще не отвечал
    if username in game_state.answers_right or username in game_state.answers_wrong:
        await message.answer("Вы уже ответили на этот вопрос!")
        return
    
    await process_answer(
        message.bot, 
        message.chat.id, 
        game_state, 
        username, 
        message.text.strip(),
    )
