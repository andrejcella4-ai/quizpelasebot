from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from states.fsm import SoloGameStates
from states.local_state import GameState, get_game_state, _get_game_key_for_chat, _games_state
from static.answer_texts import TextStatics
from static.choices import QuestionTypeChoices
from keyboards import create_variant_keyboard


async def start_game_questions(callback: types.CallbackQuery, game_state: GameState):
    """Начать игру - показать первый вопрос."""
    if not game_state.questions:
        await show_final_results(callback.message.bot, callback.message.chat.id, game_state)
        return
    
    # Проверяем, что есть участники
    if game_state.mode == "dm":
        if not game_state.players:
            await callback.message.bot.send_message(callback.message.chat.id, "Игра не может начаться без участников!")
            # Очищаем состояние
            game_key = _get_game_key_for_chat(callback.message.chat.id)
            if game_key and game_key in _games_state:
                del _games_state[game_key]
            return
    else:
        if not game_state.teams:
            await callback.message.bot.send_message(callback.message.chat.id, "Игра не может начаться без команд!")
            # Очищаем состояние
            game_key = _get_game_key_for_chat(callback.message.chat.id)
            if game_key and game_key in _games_state:
                del _games_state[game_key]
            return
    
    # Инициализируем счет
    if game_state.mode == "dm":
        for player in game_state.players:
            game_state.scores[player] = 0
    else:
        for team in game_state.teams:
            game_state.scores[team] = 0
    
    await send_next_question(callback.message.bot, callback.message.chat.id, game_state)


async def send_next_question(bot, chat_id: int, game_state: GameState):
    """Отправить следующий вопрос."""
    if game_state.current_q_idx >= len(game_state.questions):
        # Игра окончена
        await show_final_results(bot, chat_id, game_state)
        return
    
    question = game_state.questions[game_state.current_q_idx]
    
    # Очищаем ответы на предыдущий вопрос
    game_state.answers_right.clear()
    game_state.answers_wrong.clear()
    
    text = TextStatics.format_question_text(
        game_state.current_q_idx + 1,
        question["text"],
        question.get("time_to_answer", 10),
    )

    if question["question_type"] == QuestionTypeChoices.VARIANT:
        # Собираем все варианты ответов
        options = question["wrong_answers"] + [question["correct_answer"]]
        import random
        random.shuffle(options)
        kb = create_variant_keyboard(options)
    else:
        kb = None

    sent_msg = await bot.send_message(chat_id, text, reply_markup=kb)
    game_state.current_question_msg_id = sent_msg.message_id
    
    # Запускаем таймер на вопрос
    async def on_timeout():
        try:
            # Отменяем таймер
            game_state.timer_task = None
            
            # Показываем что время вышло и правильный ответ
            current_question = game_state.questions[game_state.current_q_idx]
            result_text = f"⏰ Время вышло!\n📊 Правильный ответ: {current_question['correct_answer']}"
            
            await bot.send_message(chat_id, result_text)
            await move_to_next_question(bot, chat_id, game_state)
        except Exception as e:
            print(f"Ошибка в on_timeout: {e}")
            import traceback
            traceback.print_exc()
    
    timeout_seconds = question.get("time_to_answer", 10)
    game_state.timer_task = await schedule_question_timeout(
        timeout_seconds, on_timeout
    )


async def move_to_next_question(bot, chat_id: int, game_state: GameState):
    """Перейти к следующему вопросу или завершить игру."""
    game_state.current_q_idx += 1
    
    # Небольшая пауза перед следующим вопросом
    await asyncio.sleep(2)
    
    if game_state.current_q_idx >= len(game_state.questions):
        # Игра завершена
        await show_final_results(bot, chat_id, game_state)
    else:
        # Показываем следующий вопрос
        await send_next_question(bot, chat_id, game_state)


async def show_final_results(bot, chat_id: int, game_state: GameState):
    """Показать финальные результаты игры и завершить её."""
    if not game_state.scores:
        text = "Игра окончена! Никто не участвовал."
    else:
        # Сортируем по очкам
        sorted_scores = sorted(game_state.scores.items(), key=lambda x: x[1], reverse=True)
        lines = [f"{idx + 1}. {name} — {score}" for idx, (name, score) in enumerate(sorted_scores)]
        text = "🏆 Игра окончена!\n\n" + "\n".join(lines)
    
    await bot.send_message(chat_id, text)
    
    # Автоматически очищаем состояние после показа результатов
    game_key = _get_game_key_for_chat(chat_id)
    if game_key and game_key in _games_state:
        # Отменяем таймеры если есть
        if game_state.timer_task:
            game_state.timer_task.cancel()
        del _games_state[game_key]


async def process_answer(bot, chat_id: int, game_state: GameState, username: str, answer: str, callback: types.CallbackQuery | None = None):
    """Обработать ответ игрока."""
    if game_state.current_q_idx >= len(game_state.questions):
        return
    
    current_question = game_state.questions[game_state.current_q_idx]
    
    # Проверяем правильность ответа
    is_correct = False
    if current_question["question_type"] == QuestionTypeChoices.VARIANT:
        correct_answer = current_question["correct_answer"]
        is_correct = answer == correct_answer
    else:
        # Для текстовых вопросов сравниваем с правильным ответом
        correct_answer = current_question["correct_answer"].lower().strip()
        is_correct = answer.lower().strip() == correct_answer
    
    # Обновляем статистику
    if is_correct:
        game_state.answers_right.add(username)
        
        # Начисляем очки
        if game_state.mode == "dm":
            game_state.scores[username] = game_state.scores.get(username, 0) + 1
        else:
            # Находим команду игрока
            for team, members in game_state.teams.items():
                if username in members:
                    game_state.scores[team] = game_state.scores.get(team, 0) + 1
                    break
    else:
        game_state.answers_wrong.add(username)
    
    # Показываем индивидуальный результат игроку
    if callback:
        result_text = f"{'✅ Правильно!' if is_correct else '❌ Неправильно!'}"
        await callback.answer(result_text, show_alert=True)
    
    # Проверяем, ответили ли все игроки
    await check_if_all_answered(bot, chat_id, game_state)


async def check_if_all_answered(bot, chat_id: int, game_state: GameState):
    """Проверить, ответили ли все игроки на текущий вопрос."""
    total_answered = len(game_state.answers_right) + len(game_state.answers_wrong)
    
    if game_state.mode == "dm":
        # В DM режиме ждем всех зарегистрированных игроков
        total_players = len(game_state.players)
    else:
        # В Team режиме ждем ответов от всех команд (только капитаны отвечают)
        total_players = len(game_state.teams)
    
    if total_answered >= total_players:
        # Все ответили! Отменяем таймер и переходим дальше
        if game_state.timer_task:
            game_state.timer_task.cancel()
            game_state.timer_task = None
        
        # Показываем только правильный ответ
        current_question = game_state.questions[game_state.current_q_idx]
        result_text = f"📊 Правильный ответ: {current_question['correct_answer']}"
        
        await bot.send_message(chat_id, result_text)
        
        # Переходим к следующему вопросу
        await move_to_next_question(bot, chat_id, game_state)


async def schedule_question_timeout(timeout_seconds: int, on_timeout_callback) -> asyncio.Task:
    """Создать таймер для вопроса."""
    async def timer():
        try:
            await asyncio.sleep(timeout_seconds)
            await on_timeout_callback()
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


def format_dm_registration(players: set[str], time_left: int, quiz_name: str) -> str:
    players_text = "\n".join(f"— {p}" for p in players) or "—"
    return (
        f"Регистрация на игру ({quiz_name}). Старт через {time_left} сек.\n\n"
        f"Участники:\n{players_text}"
    )


def format_team_registration(teams: dict[str, list[str]], time_left: int, quiz_name: str) -> str:
    if not teams:
        teams_text = "—"
    else:
        parts = []
        for name, members in teams.items():
            users = ", ".join(members)
            parts.append(f"{name}: {users}")
        teams_text = "\n".join(parts)
    return (
        f"Регистрация командной игры ({quiz_name}). Старт через {time_left} сек.\n\n"
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
            return format_dm_registration(game_state.players, seconds_left, game_state.quiz_name)
        return format_team_registration(game_state.teams, seconds_left, game_state.quiz_name)

    if game_state.status == 'playing':
        lines = [f"🎮 Вопрос №{game_state.current_q_idx + 1} из {len(game_state.questions)}"]
        
        if question_text:
            lines.append(f"❓ {question_text}")
        
        # Показываем статистику ответов
        total_answered = len(game_state.answers_right) + len(game_state.answers_wrong)
        
        if game_state.mode == 'dm':
            total_players = len(game_state.players)
            lines.append(f"📊 Ответили: {total_answered}/{total_players}")
            
            if game_state.answers_right:
                lines.append(f"✅ Правильно: {', '.join(game_state.answers_right)}")
            if game_state.answers_wrong:
                lines.append(f"❌ Неправильно: {', '.join(game_state.answers_wrong)}")
            
            not_answered = [p for p in game_state.players if p not in game_state.answers_right and p not in game_state.answers_wrong]
            if not_answered:
                lines.append(f"⏳ Ждем ответа: {', '.join(not_answered)}")
        else:
            total_teams = len(game_state.teams)
            lines.append(f"📊 Команд ответили: {total_answered}/{total_teams}")
            
            correct_teams = []
            wrong_teams = []
            not_answered_teams = []
            
            for team_name in game_state.teams.keys():
                captain = game_state.captains.get(team_name)
                if captain in game_state.answers_right:
                    correct_teams.append(team_name)
                elif captain in game_state.answers_wrong:
                    wrong_teams.append(team_name)
                else:
                    not_answered_teams.append(team_name)
            
            if correct_teams:
                lines.append(f"✅ Правильно: {', '.join(correct_teams)}")
            if wrong_teams:
                lines.append(f"❌ Неправильно: {', '.join(wrong_teams)}")
            if not_answered_teams:
                lines.append(f"⏳ Ждем ответа: {', '.join(not_answered_teams)}")
        
        return '\n'.join(lines)

    return 'Игра завершена.'


# team game process


async def _edit_or_send(message: types.Message, text: str, reply_markup: types.InlineKeyboardMarkup):
    """Utility: edit message if bot is author, else send new."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)
