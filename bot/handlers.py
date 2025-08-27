import asyncio
import os
import random
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states.fsm import SoloGameStates
from api_client import (
    auth_player,
    get_quiz_list,
    player_game_end,
    player_leaderboard,
    player_update_notifications,
    get_rotated_questions_solo,
    get_bot_texts,
    get_configs,
)
from keyboards import main_menu_keyboard, confirm_start_keyboard, create_variant_keyboard, private_menu_keyboard, question_result_keyboard, quiz_theme_keyboard, finish_quiz_keyboard
from static.answer_texts import TextStatics
from static import answer_texts
from helpers import fetch_question_and_cancel, load_and_send_image, get_telethon_client
from static.choices import QuestionTypeChoices


router = Router()


def schedule_question_timeout_solo(delay: int, state: FSMContext, index: int, q: dict, message: types.Message, send_question_fn) -> asyncio.Task:
    async def timer():
        message_30 = None
        message_10 = None
        try:
            # Промежуточные уведомления на 30 и 10 секунд
            if delay > 30:
                await asyncio.sleep(delay - 30)
                curr_data = await state.get_data()
                if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                    message_30 = await message.answer(TextStatics.time_left_30())
            
            if delay > 10:
                await asyncio.sleep(20)  # Дополнительные 20 секунд до 10 секунд остатка
                curr_data = await state.get_data()
                if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                    message_10 = await message.answer(TextStatics.time_left_10())
            
            # Финальное ожидание до конца времени
            await asyncio.sleep(10)
            curr_data = await state.get_data()
            if (await state.get_state()) == SoloGameStates.WAITING_ANSWER and curr_data.get('current_index', 0) == index:
                # Проверяем, является ли это последним вопросом
                questions = curr_data.get('questions', [])
                is_last_question = (index + 1) >= len(questions)
                
                # В соло показываем тот же подробный формат, но без списков участников
                result_text = TextStatics.dm_quiz_question_result_message(
                    right_answer=q.get("correct_answers", [q["correct_answer"]])[0],
                    not_answered=[],
                    wrong_answers=[],
                    right_answers=[],
                    comment=q.get('comment', None),
                )
                await message.answer(result_text, reply_markup=question_result_keyboard(is_last_question=is_last_question))
                await state.update_data(incorrect=curr_data.get('incorrect', 0) + 1)
                # Критично: после тайм-аута двигаем индекс на следующий вопрос
                await state.update_data(current_index=index + 1)
                await state.set_state(SoloGameStates.WAITING_NEXT)
            
            # Удаляем уведомления о времени после завершения таймера
            if message_30:
                try:
                    await message.bot.delete_message(message.chat.id, message_30.message_id)
                except Exception:
                    pass
            if message_10:
                try:
                    await message.bot.delete_message(message.chat.id, message_10.message_id)
                except Exception:
                    pass

        except asyncio.CancelledError:
            # Удаляем уведомления о времени при отмене таймера (пользователь ответил)
            if message_30:
                try:
                    await message.bot.delete_message(message.chat.id, message_30.message_id)
                except Exception:
                    pass
            if message_10:
                try:
                    await message.bot.delete_message(message.chat.id, message_10.message_id)
                except Exception:
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
            points = correct
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


async def get_chat_member_usernames(bot, chat_id: int) -> list[str]:
    try:
        usernames = []

        async with get_telethon_client() as client:
            async for participant in client.iter_participants(chat_id):
                if participant.username and not participant.bot:
                    usernames.append(participant.username.lower())

        return usernames

    except Exception as e:
        for admin_user in os.getenv('ADMIN_USERS', '').split(' '):
            await bot.send_message(admin_user, f"Ошибка при получении списка участников чата с помощью Telethon: {e}")

        return []


@router.message(Command('stats'))
async def stats_command(message: types.Message):
    # Проверяем, что команда запущена в чате (не в ЛС)
    if message.chat.type == 'private':
        await message.answer(TextStatics.use_stats_in_group_chats())
        return

    token = await auth_player(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        username=message.from_user.username,
        lang_code=message.from_user.language_code,
    )

    # Получаем список username участников чата
    chat_usernames = await get_chat_member_usernames(message.bot, message.chat.id)

    # Получаем лидерборд среди участников этого чата
    data = await player_leaderboard(
        token,
        usernames=chat_usernames,
        current_user_username=str(message.from_user.username) or str(message.from_user.id)
    )
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
        lines.append(f'\n📊 Ваше место: {pos}/{total}')
    else:
        lines.append('\n📊 Ваше место: не найдено')

    if streak is not None:
        lines.append(f'🔥 Ваш стрик: {streak} {plural_day(streak)}')

    if entries:
        lines.append(f'\n\n🏆 Топ-5 участников чата ({len(entries)} чел.):')

        for idx, e in enumerate(entries, start=1):
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
    else:
        lines.append('\n\n❌ Среди участников чата нет зарегистрированных игроков.')

    lines.append('\n\n💡 Как повысить свое место:')
    lines.append('- Участвуйте в викторинах')
    lines.append('- Правильно отвечайте на вопросы')
    lines.append('- Играйте каждый день для поддержания стрика')

    text = '\n'.join(lines)
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

    # Authenticate player
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        username=callback.from_user.username,
        lang_code=callback.from_user.language_code
    )

    # Получаем первый квиз для настроек (время ответа и количество вопросов)
    quizzes = await get_quiz_list('solo')
    if not quizzes:
        await callback.message.answer("Нет доступных викторин для solo игр")
        return
    
    quiz = quizzes[0]  # Берем первый квиз для настроек
    
    # Получаем вопросы через новую ротационную систему
    system_token = os.getenv('SYSTEM_TOKEN')

    configs = await get_configs(system_token)
    amount_questions = int([config['value'] for config in configs if config['name'] == 'amount_questions_solo'][0])

    questions_data = await get_rotated_questions_solo(
        system_token=system_token,
        telegram_id=callback.from_user.id,
        size=amount_questions,
        time_to_answer=quiz['time_to_answer']
    )

    if not questions_data.get('questions'):
        await callback.message.answer("Нет доступных вопросов для solo игр")
        return
    
    await state.update_data(quiz_info=quiz, questions=questions_data['questions'], current_index=0, correct=0, incorrect=0, last_question_msg_id=None)

    start_text = TextStatics.get_solo_start_text(
        "Соло викторина", len(questions_data['questions'])
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
    
    # Проверяем, является ли это последним вопросом
    questions = data.get('questions', [])
    is_last_question = (index + 1) >= len(questions)
    
    if is_correct:
        # Формат результата как в DM, с указанием текущих баллов игрока
        totals = {username: (data.get('correct', 0) + 1)}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=q["correct_answer"],
            not_answered=[],
            wrong_answers=[],
            right_answers=[username],
            totals=totals,
            comment=q.get('comment', None),
        )
        await callback.message.answer(result_text, reply_markup=question_result_keyboard(is_last_question=is_last_question))
        await state.update_data(correct=data.get('correct', 0) + 1)
    else:
        totals = {username: (data.get('correct', 0))}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=q["correct_answer"],
            not_answered=[],
            wrong_answers=[username],
            right_answers=[],
            totals=totals,
            comment=q.get('comment', None),
        )
        await callback.message.answer(result_text, reply_markup=question_result_keyboard(is_last_question=is_last_question))
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
        points = correct
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

    # Проверяем, является ли это последним вопросом
    questions = data.get('questions', [])
    is_last_question = (index + 1) >= len(questions)

    # реализуем механику 2 попыток
    attempts_left = data.get('attempts_left', 2)
    correct_answers = [a.lower().strip() for a in q['correct_answers']]

    if user_answer.lower().strip() in correct_answers:
        # Показать DM-формат результата для соло
        username = message.from_user.username or str(message.from_user.id)
        totals = {username: (data.get('correct', 0) + 1)}
        result_text = TextStatics.dm_quiz_question_result_message(
            right_answer=user_answer,
            not_answered=[],
            wrong_answers=[],
            right_answers=[username],
            totals=totals,
            comment=q.get('comment', None),
        )
        await message.answer(result_text, reply_markup=question_result_keyboard(is_last_question=is_last_question))
        await state.update_data(correct=data.get('correct', 0) + 1)
        await state.update_data(current_index=index + 1)
        await state.set_state(SoloGameStates.WAITING_NEXT)
    else:
        attempts_left -= 1
        if attempts_left <= 0:
            username = message.from_user.username or str(message.from_user.id)
            totals = {username: (data.get('correct', 0))}
            result_text = TextStatics.dm_quiz_question_result_message(
                right_answer=q["correct_answers"][0],
                not_answered=[],
                wrong_answers=[username],
                right_answers=[],
                totals=totals,
                comment=q.get('comment', None),
            )
            await message.answer(result_text, reply_markup=question_result_keyboard(is_last_question=is_last_question))
            await state.update_data(incorrect=data.get('incorrect', 0) + 1, current_index=index + 1)
            # Автопереход к следующему вопросу без ожидания кнопки
            await send_question(message, state)
        else:
            await state.update_data(attempts_left=attempts_left)
            await message.answer(TextStatics.dm_text_wrong_attempt(attempts_left, q.get("correct_answers", [q["correct_answer"]])[0]))


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


@router.message(Command('help'))
async def help_command(message: types.Message):
    await message.answer(TextStatics.get_help_message())


@router.message(Command('update_texts'))
async def update_texts(message: types.Message):
    admin_users = os.getenv('ADMIN_USERS', '').split(' ')

    if str(message.from_user.id) not in admin_users:
        return

    answer_texts._current_bot_texts = {list(item.keys())[0]: list(item.values())[0] for item in get_bot_texts(os.getenv('BOT_TOKEN'))}
    await message.answer("Тексты обновлены")
