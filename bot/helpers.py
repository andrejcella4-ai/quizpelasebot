from __future__ import annotations
import os
import traceback
from pathlib import Path

import asyncio
from datetime import datetime
import pytz

from aiogram import types
from aiogram.fsm.context import FSMContext
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from states.fsm import SoloGameStates
from states.local_state import GameState, get_game_state, _get_game_key_for_chat, _games_state
from static.answer_texts import TextStatics
from static.choices import QuestionTypeChoices
from keyboards import create_variant_keyboard, question_result_keyboard, game_finished_keyboard
from api_client import players_game_end_bulk, team_game_end, auth_player, create_team, get_players_total_points, get_players_chat_points


async def load_and_send_image(bot, chat_id: int, image_url: str, text: str, reply_markup=None):
    """Загружает изображение с локального диска и отправляет его с текстом."""
    if not image_url:
        # Если нет изображения, отправляем только текст
        return await bot.send_message(chat_id, text, reply_markup=reply_markup)

    try:
        # Получаем директорию для медиа файлов из переменных окружения или используем по умолчанию
        media_root = os.getenv('MEDIA_ROOT', '')

        # Убираем ведущий слэш из image_url, если он есть, чтобы Path правильно объединил пути
        clean_image_url = image_url.lstrip('/')
        file_path = Path(media_root) / clean_image_url

        # Проверяем, что файл существует
        if file_path.exists() and file_path.is_file():
            # Читаем файл с диска
            with open(file_path, 'rb') as image_file:
                image_data = image_file.read()

            # Определяем имя файла
            filename = file_path.name

            # Отправляем изображение с текстом как caption
            return await bot.send_photo(
                chat_id=chat_id,
                photo=types.BufferedInputFile(image_data, filename=filename),
                caption=text,
                reply_markup=reply_markup
            )
        else:
            print(f"Файл изображения не найден: {file_path}")
            # Если файл не найден, отправляем только текст
            return await bot.send_message(chat_id, text, reply_markup=reply_markup)

    except Exception as e:
        print(f"Ошибка при чтении изображения {image_url}: {e}")
        # В случае ошибки отправляем только текст
        return await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def start_game_questions(callback: types.CallbackQuery, game_state: GameState):
    """Начать игру - показать первый вопрос."""
    if not game_state.questions:
        await finalize_game(callback.message.bot, callback.message.chat.id, game_state)
        return

    # Удаляем сообщения регистрации и подготовки сразу при начале игры
    try:
        for mid in getattr(game_state, 'registration_message_ids', []) or []:
            try:
                await callback.message.bot.delete_message(callback.message.chat.id, mid)
            except Exception:
                pass
        game_state.registration_message_ids = []
        
        # Удаляем основное сообщение регистрации/подготовки
        if game_state.message_id:
            try:
                await callback.message.bot.delete_message(callback.message.chat.id, game_state.message_id)
            except Exception:
                pass
            game_state.message_id = None
    except Exception:
        pass

    # Проверяем, что есть участники
    if game_state.mode == "dm":
        if not game_state.players:
            await callback.message.bot.send_message(callback.message.chat.id, TextStatics.no_players_cannot_start())
            # Очищаем состояние
            game_key = _get_game_key_for_chat(callback.message.chat.id)
            if game_key and game_key in _games_state:
                del _games_state[game_key]
            return
    else:
        if not game_state.teams:
            await callback.message.bot.send_message(callback.message.chat.id, TextStatics.no_teams_cannot_start())
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
        await finalize_game(bot, chat_id, game_state)
        return
    
    question = game_state.questions[game_state.current_q_idx]
    
    # Очищаем ответы на предыдущий вопрос
    game_state.answers_right.clear()
    game_state.answers_wrong.clear()
    
    # Очищаем лайки/дизлайки для нового вопроса
    game_state.question_likes.clear()
    game_state.question_dislikes.clear()
    
    # Формируем текст вопроса. Для командных открытых вопросов добавляем подсказку про команды и 2 попытки
    if game_state.mode == "team" and question["question_type"] == QuestionTypeChoices.TEXT:
        # Берем капитана (одного, исходя из текущей модели одной команды на чат)
        try:
            captain_username = list(game_state.captains.values())[0]
        except Exception:
            captain_username = None
        mention = f"@{captain_username}" if captain_username and not captain_username.startswith("@") else (captain_username or "")
        text = TextStatics.team_quiz_question_template(
            current_q_idx=game_state.current_q_idx + 1,
            username=mention,
            text=question["text"],
            timer=question.get("time_to_answer", 120),
            total_questions=game_state.total_questions,
        )
    else:
        text = TextStatics.format_question_text(
            game_state.current_q_idx + 1,
            question["text"],
            question.get("time_to_answer", 120),
            game_state.total_questions,
        )

    if question["question_type"] == QuestionTypeChoices.VARIANT:
        # Собираем все варианты ответов
        options = question["wrong_answers"] + [question["correct_answer"]]
        import random
        random.shuffle(options)
        kb = create_variant_keyboard(options)
        # Сохраняем порядок вариантов для корректной интерпретации индекса
        game_state.current_options = options
    else:
        kb = None

    # Увеличим токен вопроса и сбросим флаги
    game_state.question_token += 1
    token = game_state.question_token
    game_state.question_result_sent = False
    # Сохраним снимок правильного ответа/идентификатора
    try:
        game_state.current_correct_answer = question.get("correct_answers", [question["correct_answer"]])[0]
    except Exception:
        game_state.current_correct_answer = None
    
    # Сохраняем ID текущего вопроса для лайков/дизлайков
    game_state.current_question_id = question.get("id")

    # Удаляем предыдущее сообщение с вопросом и гасим предыдущий таймер
    if game_state.current_question_msg_id:
        if game_state.timer_task:
            try:
                game_state.timer_task.cancel()
            except Exception:
                pass
            game_state.timer_task = None

        await bot.delete_message(chat_id, game_state.current_question_msg_id)

    try:
        # Проверяем, есть ли изображение в вопросе
        image_url = question.get("image_url")
        sent_msg = await load_and_send_image(bot, chat_id, image_url, text, reply_markup=kb)
    except asyncio.CancelledError as e:
        print("send_next_question: CancelledError; state=", game_state.status, "q_idx=", game_state.current_q_idx)
        return
    except Exception as e:
        print("send_next_question: send_message failed:", type(e).__name__, e)
        import traceback; traceback.print_exc()
        return

    game_state.current_question_msg_id = sent_msg.message_id
    # Инициализируем контейнер для последующего удаления вспомогательных сообщений
    if not hasattr(game_state, 'cleanup_message_ids'):
        game_state.cleanup_message_ids = []
    game_state.waiting_next = False
    game_state.attempts_left_by_user.clear()
    # Сбрасываем списки ответов для следующего вопроса
    game_state.answers_right.clear()
    game_state.answers_wrong.clear()
    
    # Запускаем таймер на вопрос
    async def on_timeout():
        try:
            # Атомарная секция: проверяем актуальность и помечаем результат выведенным
            if game_state.transition_lock is None:
                game_state.transition_lock = asyncio.Lock()
            should_send_dm = False
            should_advance_team = False
            if token != game_state.question_token or game_state.is_finishing or game_state.status != "playing":
                return
            async with game_state.transition_lock:
                if token != game_state.question_token or game_state.is_finishing or game_state.status != "playing":
                    return
                if game_state.question_result_sent:
                    return
                # Отменяем таймер
                if game_state.timer_task:
                    game_state.timer_task = None

                game_state.question_result_sent = True
                if game_state.mode == "team":
                    should_advance_team = True
                    # Отправляем сообщение о таймауте для командного режима
                    correct_answer = question.get("correct_answers", [game_state.current_correct_answer])[0]
                    comment = question.get('comment', None)
                    earned_xp = 0  # При таймауте команда не получает очков
                    timeout_text = TextStatics.team_timeout_message(correct_answer, comment, earned_xp)
                    
                    # Проверяем, является ли это последним вопросом
                    is_last_question = (game_state.current_q_idx + 1) >= len(game_state.questions)
                    _sent = await bot.send_message(chat_id, timeout_text, reply_markup=question_result_keyboard(include_finish=False, is_last_question=is_last_question))
                    try:
                        game_state.cleanup_message_ids.append(_sent.message_id)
                    except Exception:
                        pass
                else:
                    game_state.waiting_next = True
                    should_send_dm = True

            # Для команд результат уже отправлен выше, переходим к следующему вопросу
            if game_state.mode == "team":
                game_state.waiting_next = True
                return

            if should_send_dm:
                right_list = sorted(list(game_state.answers_right))
                wrong_list = sorted(list(game_state.answers_wrong))
                not_answered_list = [p for p in sorted(list(game_state.players)) if p not in game_state.answers_right and p not in game_state.answers_wrong]
                totals = {u: int(game_state.scores.get(u, 0)) for u in set(right_list + wrong_list)}
                
                # Проверяем, является ли это последним вопросом
                is_last_question = (game_state.current_q_idx + 1) >= len(game_state.questions)
                
                result_text = TextStatics.dm_quiz_question_result_message(
                    right_answer=question.get("correct_answers", [game_state.current_correct_answer])[0],
                    not_answered=not_answered_list,
                    wrong_answers=wrong_list,
                    right_answers=right_list,
                    totals=totals,
                    comment=question.get('comment', None),
                )
                _sent = await bot.send_message(chat_id, result_text, reply_markup=question_result_keyboard(include_finish=False, is_last_question=is_last_question))
                try:
                    game_state.cleanup_message_ids.append(_sent.message_id)
                except Exception:
                    pass
                # Явно включаем фазу ожидания Next (на случай гонок)
                game_state.waiting_next = True
                game_state.question_result_sent = True
        except Exception as e:
            print(f"Ошибка в on_timeout: {e}")
            traceback.print_exc()
    
    timeout_seconds = question.get("time_to_answer", 120)
    game_state.timer_task = await schedule_question_timeout(
        timeout_seconds, on_timeout, bot, chat_id, game_state=game_state, token=token
    )


async def move_to_next_question(bot, chat_id: int, game_state: GameState):
    """Перейти к следующему вопросу или завершить игру."""
    # Если финализация началась, не двигаем вопросы
    if game_state.is_finishing or game_state.status != "playing":
        return
    # Инвалидация токена, чтобы старые таймеры точно не сработали на старом вопросе
    try:
        game_state.question_token += 1
    except Exception:
        pass
    game_state.current_q_idx += 1
    
    # Небольшая пауза перед следующим вопросом
    await asyncio.sleep(1)

    # Удаляем вспомогательные сообщения, ответы пользователей и предыдущий вопрос
    try:
        # Удаляем вспомогательные сообщения (результаты, таймеры)
        for mid in getattr(game_state, 'cleanup_message_ids', []) or []:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
        game_state.cleanup_message_ids = []
        
        # Удаляем ответы пользователей (если бот имеет права админа)
        for mid in getattr(game_state, 'user_answer_message_ids', []) or []:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass  # Нет прав или сообщение уже удалено
        game_state.user_answer_message_ids = []
        
        # Удаляем предыдущий вопрос
        if game_state.current_question_msg_id:
            try:
                await bot.delete_message(chat_id, game_state.current_question_msg_id)
            except Exception:
                pass
            game_state.current_question_msg_id = None
    except Exception:
        pass
    
    if game_state.current_q_idx >= len(game_state.questions):
        # Игра завершена
        await finalize_game(bot, chat_id, game_state)
    else:
        # Показываем следующий вопрос
        await send_next_question(bot, chat_id, game_state)


async def show_final_results(bot, chat_id: int, game_state: GameState):
    """Сформировать текст финальных результатов без очистки состояния."""
    if game_state.mode == "team":
        # Командный режим – особый формат
        if not game_state.scores:
            text = TextStatics.team_quiz_finished_no_scores()
        else:
            team_name, score = next(iter(game_state.scores.items()))
            text = TextStatics.team_quiz_finished_with_scores(team_name, score)
    else:
        # DM: отправляем результаты на backend (без вывода стриков в тексте)
        if not game_state.scores:
            text = TextStatics.no_participants_game_finished()
        else:
            sorted_scores = sorted(game_state.scores.items(), key=lambda x: x[1], reverse=True)
            participants_total_points = None
            players_totals = None
            try:
                system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
                usernames = list(game_state.players)
                if usernames and system_token:
                    api_items = await get_players_chat_points(usernames, chat_id, system_token)
                    # api_items: list of {username, points}
                    players_totals = []
                    for item in api_items:
                        if isinstance(item, dict):
                            uname = item.get('username')
                            total = int(item.get('points', 0))
                            if uname:
                                players_totals.append((uname, total))
                    participants_total_points = sum(total for _, total in players_totals) if players_totals else 0
            except Exception:
                participants_total_points = None
                players_totals = None
            text = TextStatics.dm_quiz_finished_full(
                sorted_scores,
                registered_count=len(game_state.players),
                participants_total_points=participants_total_points,
                players_totals=players_totals,
            )
    return text


async def finalize_game(bot, chat_id: int, game_state: GameState):
    """Единая финализация игры: отмена таймеров, отправка на бэкенд, один финальный месседж, очистка состояния."""
    # Не допускаем повторной финализации
    if game_state.finished_sent or game_state.is_finishing:
        return
    game_state.is_finishing = True
    try:
        # Отменить активный таймер
        if game_state.timer_task:
            try:
                game_state.timer_task.cancel()
            except Exception:
                pass
            game_state.timer_task = None

        # Отправка результатов на backend
        if game_state.mode == "team":
            try:
                system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
                team_points = 0
                if game_state.scores:
                    team_points = list(game_state.scores.values())[0]
                if game_state.team_id is not None:
                    await team_game_end(game_state.team_id, team_points, game_state.plan_team_quiz_id, system_token)
            except Exception:
                pass
        else:
            try:
                if game_state.scores:
                    system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
                    results = [
                        {'username': username, 'points': int(score), 'chat_id': int(chat_id)}
                        for username, score in game_state.scores.items()
                    ]
                    await players_game_end_bulk(results, system_token)
            except Exception:
                pass

        # Сформировать текст и отправить ровно один раз
        if game_state.finished_sent:
            return
        final_text = await show_final_results(bot, chat_id, game_state)
        game_state.finished_sent = True
        await bot.send_message(chat_id, final_text, reply_markup=game_finished_keyboard())
        # Очистка всех сообщений после окончания игры
        try:
            # Удаляем вспомогательные сообщения результатов
            for mid in getattr(game_state, 'cleanup_message_ids', []) or []:
                try:
                    await bot.delete_message(chat_id, mid)
                except Exception:
                    pass
            game_state.cleanup_message_ids = []
            
            # Удаляем оставшиеся ответы пользователей
            for mid in getattr(game_state, 'user_answer_message_ids', []) or []:
                try:
                    await bot.delete_message(chat_id, mid)
                except Exception:
                    pass  # Нет прав или сообщение уже удалено
            game_state.user_answer_message_ids = []
            
            # Удаляем текущий вопрос
            if game_state.current_question_msg_id:
                try:
                    await bot.delete_message(chat_id, game_state.current_question_msg_id)
                except Exception:
                    pass
                game_state.current_question_msg_id = None
        except Exception:
            pass
    finally:
        # Очистить состояние
            game_key = _get_game_key_for_chat(chat_id)
            if not game_key:
                return
            game_state = get_game_state(game_key)
            if game_state and game_state.timer_task:
                try:
                    game_state.timer_task.cancel()
                except Exception:
                    pass
            if game_key in _games_state:
                del _games_state[game_key]


async def process_answer(bot, chat_id: int, game_state: GameState, username: str, answer: str, callback: types.CallbackQuery | None = None):
    """Обработать ответ игрока."""
    if game_state.is_finishing or game_state.status != "playing":
        if callback:
            await callback.answer()
        return
    if game_state.current_q_idx >= len(game_state.questions):
        if callback:
            await callback.answer()
        return

    current_question = game_state.questions[game_state.current_q_idx]

    # Проверяем правильность ответа
    is_correct = False

    if current_question["question_type"] == QuestionTypeChoices.TEXT:
        print("current_question", current_question)

    correct_answers = [a.lower().strip() for a in current_question["correct_answers"]]
    is_correct = answer.lower().strip() in correct_answers

    # Инициализируем попытки для пользователя/капитана (для TEXT вопросов)
    if current_question["question_type"] == QuestionTypeChoices.TEXT and username not in game_state.attempts_left_by_user:
        game_state.attempts_left_by_user[username] = 2

    # Обновляем статистику и Баллы
    if is_correct:
        game_state.answers_right.add(username)
        # Подсчет очков с учетом попыток для TEXT
        if current_question["question_type"] == QuestionTypeChoices.TEXT:
            attempts_left = game_state.attempts_left_by_user.get(username, 2)
            gain = 2 if attempts_left == 2 else 1
        else:
            gain = 1

        if game_state.mode == "dm":
            # В DM считаем количество правильных ответов (по 1 балл в отображении)
            game_state.scores[username] = game_state.scores.get(username, 0) + 1
        elif game_state.mode == "team":
            for team, _ in game_state.teams.items():
                game_state.scores[team] = game_state.scores.get(team, 0) + gain
                break

        # Ответ правильный
        if game_state.mode == "team":
            # В командном режиме: сразу показываем правильный ответ и переходим к следующему вопросу
            try:
                if game_state.timer_task:
                    game_state.timer_task.cancel()
                    game_state.timer_task = None
            except Exception:
                pass

            # Проверяем, является ли это последним вопросом
            is_last_question = (game_state.current_q_idx + 1) >= len(game_state.questions)

            game_state.waiting_next = True
            _sent = await bot.send_message(
                chat_id,
                TextStatics.show_right_answer_only(current_question.get("correct_answers", [game_state.current_correct_answer])[0], current_question.get('comment', None), gain),
                reply_markup=question_result_keyboard(include_finish=False, is_last_question=is_last_question)
            )
            try:
                game_state.cleanup_message_ids.append(_sent.message_id)
            except Exception:
                pass
            return
        else:
            # DM режим — просто ответим на клик
            if callback:
                await callback.answer(TextStatics.correct_inline_hint())
    else:
        # Неправильный ответ
        if current_question["question_type"] == QuestionTypeChoices.TEXT:
            game_state.attempts_left_by_user[username] = game_state.attempts_left_by_user.get(username, 2) - 1
            attempts_left = game_state.attempts_left_by_user[username]

            # Сообщаем пользователю об оставшихся попытках
            earned_scores = 0  # При неправильном ответе команда не получает очков
            wrong_text = TextStatics.team_quiz_question_wrong_answer(
                attempts_left,
                current_question.get("correct_answers", [current_question["correct_answer"]])[0],
                current_question.get('comment', None),
                earned_scores
            ) if game_state.mode == "team" else TextStatics.dm_text_wrong_attempt(
                attempts_left,
                current_question.get("correct_answers", [current_question["correct_answer"]])[0],
                current_question.get('comment', None)
            )

            # Если попыток больше нет
            if attempts_left <= 0:
                # Отмечаем пользователя как ответившего неправильно окончательно
                game_state.answers_wrong.add(username)
                if game_state.mode == "team":
                    # В командном режиме — сразу к следующему вопросу
                    if game_state.timer_task:
                        game_state.timer_task.cancel()
                        game_state.timer_task = None

                    # Проверяем, является ли это последним вопросом
                    is_last_question = (game_state.current_q_idx + 1) >= len(game_state.questions)
                    
                    game_state.waiting_next = True
                    _sent = await bot.send_message(chat_id, wrong_text, reply_markup=question_result_keyboard(include_finish=False, is_last_question=is_last_question))
                    try:
                        game_state.cleanup_message_ids.append(_sent.message_id)
                    except Exception:
                        pass
                    return
                # В DM режиме — ждём остальных через общий механизм
            else:
                _sent = await bot.send_message(chat_id, wrong_text)
                try:
                    game_state.cleanup_message_ids.append(_sent.message_id)
                except Exception:
                    pass
        else:
            # Для вариантов — сразу отмечаем как неправильный
            game_state.answers_wrong.add(username)
            if callback:
                await callback.answer(TextStatics.incorrect_inline_hint())

    # Проверяем, ответили ли все (для dm ждём всех, для team — капитанов)
    await check_if_all_answered(bot, chat_id, game_state)


async def check_if_all_answered(bot, chat_id: int, game_state: GameState):
    """Проверить, ответили ли все игроки на текущий вопрос."""
    if game_state.is_finishing or game_state.status != "playing":
        return
    total_answered = len(game_state.answers_right) + len(game_state.answers_wrong)
    current_question = game_state.questions[game_state.current_q_idx]

    if game_state.mode == "dm":
        # В DM режиме ждем всех зарегистрированных игроков
        total_players = len(game_state.players)
    else:
        # В Team режиме ждем ответов от всех команд (только капитаны отвечают)
        total_players = len(game_state.teams)
    
    if total_answered >= total_players:
        # Атомарно закрываем вопрос, чтобы не было дублей
        if game_state.transition_lock is None:
            game_state.transition_lock = asyncio.Lock()
        should_send_dm = False
        should_advance_team = False
        async with game_state.transition_lock:
            if game_state.is_finishing or game_state.status != "playing":
                return
            if game_state.question_result_sent:
                return
            # Все ответили — отменим таймер
            if game_state.timer_task:
                try:
                    game_state.timer_task.cancel()
                except Exception:
                    pass
                game_state.timer_task = None
            game_state.question_result_sent = True
            if game_state.mode == "team":
                should_advance_team = True
            else:
                game_state.waiting_next = True
                should_send_dm = True

        if game_state.mode == "team":
            # В командном режиме не отправляем дополнительное сообщение когда все ответили
            # Результат покажет таймер или будет показан при переходе к следующему вопросу
            return

        if should_send_dm:
            right_list = sorted(list(game_state.answers_right))
            wrong_list = sorted(list(game_state.answers_wrong))
            not_answered_list = [p for p in sorted(list(game_state.players)) if p not in game_state.answers_right and p not in game_state.answers_wrong]
            totals = {u: int(game_state.scores.get(u, 0)) for u in set(right_list + wrong_list)}
            
            # Проверяем, является ли это последним вопросом
            is_last_question = (game_state.current_q_idx + 1) >= len(game_state.questions)
            
            result_text = TextStatics.dm_quiz_question_result_message(
                right_answer=current_question.get('correct_answers', [game_state.current_correct_answer])[0],
                not_answered=not_answered_list,
                wrong_answers=wrong_list,
                right_answers=right_list,
                totals=totals,
                comment=current_question.get('comment', None),
            )
            _sent = await bot.send_message(chat_id, result_text, reply_markup=question_result_keyboard(include_finish=False, is_last_question=is_last_question))
            try:
                game_state.cleanup_message_ids.append(_sent.message_id)
            except Exception:
                pass


async def question_transition_delay(bot, chat_id: int, game_state: GameState, delay: int = 3):
    sent = await bot.send_message(chat_id, TextStatics.question_transition_delay())
    await asyncio.sleep(delay)
    await bot.delete_message(chat_id, sent.message_id)

    await move_to_next_question(bot, chat_id, game_state)
    game_state.next_in_progress = False


async def schedule_question_timeout(timeout_seconds: int, on_timeout_callback, bot=None, chat_id=None, game_state: GameState | None = None, token: int | None = None) -> asyncio.Task:
    """Создать таймер для вопроса с промежуточными уведомлениями.

    Старые/неактуальные таймеры подавляются проверкой game_state/token.
    """
    message_30 = None
    message_10 = None

    def cancelled() -> bool:
        if not game_state:
            return False
        if game_state.is_finishing or game_state.status != "playing":
            return True
        if token is not None and token != game_state.question_token:
            return True
        return False

    async def timer():
        nonlocal message_30, message_10
        try:
            # Промежуточные уведомления на 30 и 10 секунд
            if timeout_seconds > 30 and bot and chat_id:
                await asyncio.sleep(timeout_seconds - 30)
                if not cancelled():
                    try:
                        message_30 = await bot.send_message(chat_id, TextStatics.time_left_30())
                    except Exception:
                        pass
            
            if timeout_seconds > 10 and bot and chat_id:
                await asyncio.sleep(20)  # Дополнительные 20 секунд до 10 секунд остатка
                if not cancelled():
                    try:
                        message_10 = await bot.send_message(chat_id, TextStatics.time_left_10())
                    except Exception:
                        pass
            
            # Финальное ожидание до конца времени
            await asyncio.sleep(10)

            if message_30 and bot is not None and chat_id is not None:
                try:
                    await bot.delete_message(chat_id, message_30.message_id)
                except Exception:
                    pass
            if message_10 and bot is not None and chat_id is not None:
                try:
                    await bot.delete_message(chat_id, message_10.message_id)
                except Exception:
                    pass

            if not cancelled():
                await on_timeout_callback()
        except asyncio.CancelledError:
            if message_30 and bot is not None and chat_id is not None:
                try:
                    await bot.delete_message(chat_id, message_30.message_id)
                except Exception:
                    pass
            if message_10 and bot is not None and chat_id is not None:
                try:
                    await bot.delete_message(chat_id, message_10.message_id)
                except Exception:
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
        lines = [f"🎮 Вопрос №{game_state.current_q_idx + 1} из {game_state.total_questions}"]
        
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


async def create_team_helper(
    team_name: str, message: types.Message, captain_user: types.User, city: str | None = None
):
    # Auth player to get token
    token = await auth_player(
        telegram_id=captain_user.id,
        first_name=captain_user.first_name,
        last_name=captain_user.last_name or "",
        username=captain_user.username,
        phone=None,
        lang_code=captain_user.language_code,
    )

    chat_username = message.chat.username or str(message.chat.id)
    try:
        await create_team(token, chat_username, team_name, captain_user.id, city)
        return True
    except Exception as e:
        print(e)
        await message.answer(TextStatics.team_create_error())
        return False


def get_today_games_avaliable(plans: list[dict]) -> list[dict]:
    current_moscow_time = datetime.now(pytz.timezone('Europe/Moscow'))

    return [
        p for p in plans if (
            # Преобразуем строку в datetime с timezone, учитывая что DRF возвращает строку с часовым поясом
            p['always_active'] == True or ((plan_datetime := datetime.fromisoformat(p['scheduled_datetime'])) <= current_moscow_time and
            plan_datetime.date() == current_moscow_time.date())
        )
    ]


def get_nearest_game_avaliable(plans: list[dict]) -> dict | None:
    if not plans:
        return None

    filtered_plans = [p for p in plans if p['always_active'] == False]
    nearest = sorted(filtered_plans, key=lambda x: datetime.fromisoformat(x['scheduled_datetime']))

    return nearest[0] if nearest else None


async def stop_quiz(message: types.Message, state: FSMContext):

    if message.chat.type == 'private':
        data = await state.get_data()
        task = data.get('timer_task')
        if task:
            try:
                task.cancel()
            except Exception:
                pass
        await state.clear()
        await message.answer(TextStatics.stopped_quiz())
        return

    # GROUP (dm/team): удаляем игру из _games_state
    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        await message.answer(TextStatics.no_active_game())
        return
    game_state = get_game_state(game_key)
    if game_state and game_state.timer_task:
        try:
            game_state.timer_task.cancel()
        except Exception:
            pass
    if game_key in _games_state:
        del _games_state[game_key]
    await message.answer(TextStatics.stopped_quiz())
