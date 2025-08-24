import asyncio
import os
import random
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states.fsm import SoloGameStates
from api_client import (
    auth_player,
    get_quiz_info,
    get_questions,
    get_quiz_list,
    player_game_end,
    player_leaderboard,
    player_update_notifications,
)
from keyboards import main_menu_keyboard, confirm_start_keyboard, create_variant_keyboard, private_menu_keyboard, question_result_keyboard, quiz_theme_keyboard, finish_quiz_keyboard
from static.answer_texts import TextStatics
from helpers import fetch_question_and_cancel, load_and_send_image
from static.choices import QuestionTypeChoices

from states.local_state import (
    get_game_state,
    _get_game_key_for_chat,
)
from helpers import move_to_next_question
from keyboards import notify_keyboard


router = Router()


def schedule_question_timeout_solo(delay: int, state: FSMContext, index: int, q: dict, message: types.Message, send_question_fn) -> asyncio.Task:
    async def timer():
        try:
            # Промежуточные уведомления на 30 и 10 секунд
            if delay > 30:
                await asyncio.sleep(delay - 30)
                curr_data = await state.get_data()
                if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                    await message.answer(TextStatics.time_left_30())
            
            if delay > 10:
                await asyncio.sleep(20)  # Дополнительные 20 секунд до 10 секунд остатка
                curr_data = await state.get_data()
                if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                    await message.answer(TextStatics.time_left_10())
            
            # Финальное ожидание до конца времени
            await asyncio.sleep(10)
            curr_data = await state.get_data()
            if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                # В соло показываем тот же подробный формат, но без списков участников
                result_text = TextStatics.dm_quiz_question_result_message(
                    right_answer=q["correct_answer"],
                    not_answered=[],
                    wrong_answers=[],
                    right_answers=[],
                )
                await message.answer(result_text, reply_markup=question_result_keyboard())
                await state.update_data(incorrect=curr_data.get('incorrect', 0) + 1)
                # Критично: после тайм-аута двигаем индекс на следующий вопрос
                await state.update_data(current_index=index + 1)
                await state.set_state(SoloGameStates.WAITING_NEXT)
        except asyncio.CancelledError:
            pass

    return asyncio.create_task(timer())


async def send_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get('current_index', 0)
    questions = data.get('questions', [])
    quiz_info = data.get('quiz_info', {})

    if index >= len(questions):
        correct = data.get('correct', 0)
        incorrect = data.get('incorrect', 0)
        # Сначала отправим результат на backend, чтобы получить актуальный стрик
        streak_suffix = ''
        try:
            system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
            points = correct * 10
            username = message.from_user.username or str(message.from_user.id)
            res = await player_game_end(username, points, system_token)
            streak = None
            if isinstance(res, dict):
                # Новый формат: {'updated': [{'username':..., 'streak':...}]}
                if 'streak' in res:
                    streak = res.get('streak')
                else:
                    updated = res.get('updated') or []
                    if updated:
                        streak = updated[0].get('streak')
            if streak is not None:
                streak_suffix = f"\n\n🔥 Ваш текущий стрик: {streak}\nПродолжайте играть каждый день, чтобы сохранить стрик! "
        except Exception:
            pass
        final_text = TextStatics.get_single_game_answer(correct, incorrect) + streak_suffix
        await message.answer(final_text)
        await state.clear()
        return

    q = questions[index]
    text = q['text']
    q_type = q['question_type']
    time_limit = quiz_info.get('time_to_answer', 10)

    question_text = TextStatics.format_question_text(index, text, time_limit)
    if q_type == QuestionTypeChoices.VARIANT:
        options = q['wrong_answers'] + [q['correct_answer']]
        random.shuffle(options)
        markup = create_variant_keyboard(options)
        await state.update_data(current_options=options)
        # Удаляем предыдущий вопрос
        if data.get('last_question_msg_id'):
            try:
                await message.bot.delete_message(message.chat.id, data['last_question_msg_id'])
            except Exception:
                pass
        # Проверяем, есть ли изображение в вопросе
        image_url = q.get("image_url")
        sent = await load_and_send_image(message.bot, message.chat.id, image_url, question_text, reply_markup=markup)
        await state.update_data(last_question_msg_id=sent.message_id)
    else:
        # Сброс попыток для текстового вопроса в соло
        await state.update_data(attempts_left=2)
        if data.get('last_question_msg_id'):
            try:
                await message.bot.delete_message(message.chat.id, data['last_question_msg_id'])
            except Exception:
                pass
        # Проверяем, есть ли изображение в вопросе
        image_url = q.get("image_url")
        sent = await load_and_send_image(message.bot, message.chat.id, image_url, question_text)
        await state.update_data(last_question_msg_id=sent.message_id)

    task = schedule_question_timeout_solo(time_limit, state, index, q, message, send_question)
    await state.update_data(timer_task=task)
    await state.set_state(SoloGameStates.WAITING_ANSWER)


@router.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    # Всегда показываем только приветствие
    username = message.from_user.username or str(message.from_user.id)
    await message.answer(TextStatics.get_start_message(username))


@router.message(Command('leaderboard'))
async def leaderboard_command(message: types.Message):
    token = await auth_player(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        username=message.from_user.username,
        lang_code=message.from_user.language_code,
    )
    data = await player_leaderboard(token)
    entries = data.get('entries', [])
    current = data.get('current') or {}

    def plural_day(n: int) -> str:
        n = abs(int(n))
        if n % 10 == 1 and n % 100 != 11:
            return 'день'
        if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
            return 'дня'
        return 'дней'

    pos = current.get('position') if isinstance(current, dict) else None
    total = current.get('total') if isinstance(current, dict) else None
    streak = current.get('streak') if isinstance(current, dict) else None

    lines: list[str] = []
    lines.append('🏆 Ваша статистика в общем рейтинге')
    if pos and total:
        lines.append('\n📊 Текущее место: ' + f"{pos}/{total}")
    else:
        lines.append('📊 Текущее место: —')
    if streak is not None:
        lines.append('🔥 Текущий стрик: ' + f"{streak} {plural_day(streak)}")
    lines.append('\n\n🏆 Топ-5 игроков:')

    for idx, e in enumerate(entries[:5], start=1):
        uname = e.get('username') or 'Без ника'
        xp = e.get('total_xp', 0)
        if idx == 1:
            prefix = '🥇'
        elif idx == 2:
            prefix = '🥈'
        elif idx == 3:
            prefix = '🥉'
        else:
            prefix = '🔹'
        lines.append(f"{prefix} {idx}. @{uname}: {xp} баллов")

    lines.append('\n\n💡 Как повысить свое место:')
    lines.append('- Участвуйте в викторинах')
    lines.append('- Правильно отвечайте на вопросы')
    lines.append('- Играйте каждый день для поддержания стрика')
    lines.append('- Выполняйте ежедневные задания')

    text = '\n'.join(lines)

    if message.chat.type != 'private':
        await message.answer('📊 Отправляю информацию о вашем месте в рейтинге в личные сообщения...')
        try:
            await message.bot.send_message(message.from_user.id, text)
        except Exception:
            await message.answer('Не могу написать вам в личные сообщения. Начните чат с ботом и повторите команду.')
    else:
        await message.answer(text)


@router.message(Command('menu'))
async def menu_command(message: types.Message, state: FSMContext):
    # Меню как в /quiz
    if message.chat.type == 'private':
        await message.answer(TextStatics.get_start_menu(), reply_markup=private_menu_keyboard())
    else:
        await message.answer(TextStatics.solo_quiz_start_message(), reply_markup=main_menu_keyboard())


@router.message(Command('quiz'))
async def quiz_command(message: types.Message, state: FSMContext):
    """Показывает меню выбора режима, как в JSON. В личке — только Соло."""
    if message.chat.type == 'private':
        await message.answer(TextStatics.get_start_menu(), reply_markup=private_menu_keyboard())
    else:
        await message.answer(TextStatics.solo_quiz_start_message(), reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data == 'game:solo')
async def callback_solo(callback: types.CallbackQuery, state: FSMContext):

    if await state.get_state():
        await callback.message.answer(TextStatics.game_already_running())
        return

    # Authenticate player and then предложим выбрать тему из всех соло-игр
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        username=callback.from_user.username,
        lang_code=callback.from_user.language_code
    )

    await state.update_data(token=token)
    quizzes = await get_quiz_list('solo')
    await state.update_data(available_solo_quizzes=quizzes)

    await callback.message.answer(
        TextStatics.theme_selection_solo(),
        reply_markup=quiz_theme_keyboard([(q.get('name', str(q.get('id'))), q.get('id')) for q in quizzes], prefix='solo_theme:')
    )
    await state.set_state(SoloGameStates.WAITING_THEME)


@router.callback_query(SoloGameStates.WAITING_THEME, lambda c: c.data and c.data.startswith('solo_theme:'))
async def choose_solo_theme(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    quizzes = data.get('available_solo_quizzes', [])
    selected_id_str = callback.data.split(':', 1)[1]
    try:
        selected_id = int(selected_id_str)
    except ValueError:
        return
    quiz = next((q for q in quizzes if q.get('id') == selected_id), None)
    if not quiz:
        return
    token = data.get('token')
    quiz_info = await get_quiz_info('solo', quiz_id=quiz['id'])
    questions_data = await get_questions(token, quiz_info['id'])
    await state.update_data(quiz_info=quiz_info, questions=questions_data['questions'], current_index=0, correct=0, incorrect=0, last_question_msg_id=None)

    start_text = TextStatics.get_solo_start_text(
        quiz_info['name'], quiz_info['amount_questions']
    )
    await callback.message.edit_text(start_text, reply_markup=confirm_start_keyboard())
    await state.set_state(SoloGameStates.WAITING_CONFIRM)


@router.callback_query(SoloGameStates.WAITING_CONFIRM, lambda c: c.data == 'game:solo:start')
async def confirm_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Start the quiz
    await send_question(callback.message, state)


@router.callback_query(SoloGameStates.WAITING_ANSWER, lambda c: c.data and c.data.startswith('answer:'))
async def answer_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    index, q = await fetch_question_and_cancel(state)

    if q is None:
        return

    data = await state.get_data()
    selected = callback.data.split(':', 1)[1]
    try:
        selected_idx = int(selected)
    except ValueError:
        selected_idx = -1
    options = (await state.get_data()).get('current_options') or (q['wrong_answers'] + [q['correct_answer']])
    is_correct = 0 <= selected_idx < len(options) and options[selected_idx] == q['correct_answer']
    username = callback.from_user.username or str(callback.from_user.id)
    if is_correct:
        # Формат результата как в DM, с указанием текущих баллов игрока
        totals = {username: (data.get('correct', 0) + 1) * 10}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=q["correct_answer"],
            not_answered=[],
            wrong_answers=[],
            right_answers=[username],
            totals=totals,
        )
        await callback.message.answer(result_text, reply_markup=question_result_keyboard())
        await state.update_data(correct=data.get('correct', 0) + 1)
    else:
        totals = {username: (data.get('correct', 0)) * 10}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=q["correct_answer"],
            not_answered=[],
            wrong_answers=[username],
            right_answers=[],
            totals=totals,
        )
        await callback.message.answer(result_text, reply_markup=question_result_keyboard())
        await state.update_data(incorrect=data.get('incorrect', 0) + 1)

    await state.update_data(current_index=index + 1)
    await state.set_state(SoloGameStates.WAITING_NEXT)


@router.callback_query(lambda c: c.data == 'finish_quiz')
async def finish_quiz_now(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    # cancel timer if running
    task = data.get('timer_task')
    if task:
        task.cancel()
    correct = data.get('correct', 0)
    incorrect = data.get('incorrect', 0)
    # Сразу кладем результат на backend, чтобы получить стрик, затем одним сообщением ответим
    streak_suffix = ''
    try:
        system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
        points = correct * 10
        username = callback.from_user.username or str(callback.from_user.id)
        res = await player_game_end(username, points, system_token)
        streak = None
        if isinstance(res, dict):
            if 'streak' in res:
                streak = res.get('streak')
            else:
                updated = res.get('updated') or []
                if updated:
                    streak = updated[0].get('streak')
        if streak is not None:
            streak_suffix = f"\n\n🔥 Ваш текущий стрик: {streak}\nПродолжайте играть каждый день, чтобы сохранить стрик! "
    except Exception:
        pass
    await callback.message.answer(TextStatics.get_single_game_answer(correct, incorrect) + streak_suffix)
    await state.clear()


@router.message(
    SoloGameStates.WAITING_ANSWER,
    lambda m: (m.text and (m.text.lower().startswith("/otvet") or m.text.lower().startswith("/answer"))) or 
    (m.reply_to_message is not None)
)
async def text_answer(message: types.Message, state: FSMContext):
    index, q = await fetch_question_and_cancel(state)

    if q is None:
        return

    data = await state.get_data()

    if message.reply_to_message:
        user_answer = message.text.strip()
    else:
        parts = message.text.strip().split(' ', maxsplit=1)
        if len(parts) <= 1 or not parts[1].strip():
            await message.answer(TextStatics.need_answer_text_after_command())
            return
        user_answer = parts[1].strip()

    if q['question_type'] != QuestionTypeChoices.TEXT:
        return

    # реализуем механику 2 попыток
    attempts_left = data.get('attempts_left', 2)
    if user_answer.lower().strip() == q['correct_answer'].lower().strip():
        # Показать DM-формат результата для соло
        username = message.from_user.username or str(message.from_user.id)
        totals = {username: (data.get('correct', 0) + 1) * 10}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=q["correct_answer"],
            not_answered=[],
            wrong_answers=[],
            right_answers=[username],
            totals=totals,
        )
        await message.answer(result_text, reply_markup=question_result_keyboard())
        await state.update_data(correct=data.get('correct', 0) + 1)
        await state.update_data(current_index=index + 1)
        await state.set_state(SoloGameStates.WAITING_NEXT)
    else:
        attempts_left -= 1
        if attempts_left <= 0:
            username = message.from_user.username or str(message.from_user.id)
            totals = {username: (data.get('correct', 0)) * 10}
            result_text = TextStatics.dm_quiz_question_result_message(
                right_answer=q["correct_answer"],
                not_answered=[],
                wrong_answers=[username],
                right_answers=[],
                totals=totals,
            )
            await message.answer(result_text, reply_markup=question_result_keyboard())
            await state.update_data(incorrect=data.get('incorrect', 0) + 1, current_index=index + 1)
            # Автопереход к следующему вопросу без ожидания кнопки
            await send_question(message, state)
        else:
            await state.update_data(attempts_left=attempts_left)
            await message.answer(TextStatics.dm_text_wrong_attempt(attempts_left, q["correct_answer"]))


@router.callback_query(lambda c: c.data == 'next_question' and c.message.chat.type == 'private')
async def next_question(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Обрабатываем этот хэндлер ТОЛЬКО в личных чатах (solo). В группах используется DM/Team хэндлер.
    if (await state.get_state()) != SoloGameStates.WAITING_NEXT:
        return
    # Запускаем отправку следующего вопроса как фоновую задачу, чтобы исключить гонки
    asyncio.create_task(send_question(callback.message, state))
    await state.set_state(SoloGameStates.WAITING_ANSWER)


@router.callback_query(lambda c: c.data == 'back')
async def go_back(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Возвращаемся к меню выбора режима
    if callback.message.chat.type == 'private':
        await callback.message.edit_text(TextStatics.get_start_menu(), reply_markup=private_menu_keyboard())
    else:
        await callback.message.edit_text(TextStatics.get_start_menu(), reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data in ('like', 'dislike'))
async def rate_question(callback: types.CallbackQuery):
    # Без лишних сообщений, как у оригинала — просто ответим на клик
    await callback.answer()


@router.callback_query(lambda c: c.data == 'notify:mute')
async def notify_mute(callback: types.CallbackQuery):
    await callback.answer()
    try:
        system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN', '')
        await player_update_notifications(callback.from_user.id, False, system_token)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer('🔕 Уведомления отключены.')
    except Exception:
        await callback.message.answer('Не удалось отключить уведомления. Попробуйте позже.')
