import asyncio
import random
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states.fsm import SoloGameStates
from api_client import auth_player, get_quiz_info, get_questions
from keyboards import main_menu_keyboard, confirm_start_keyboard, create_variant_keyboard
from static.answer_texts import TextStatics
from helpers import schedule_question_timeout, fetch_question_and_cancel
from helpers import is_captain, get_team_of_player
from static.choices import QuestionTypeChoices


router = Router()


async def send_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get('current_index', 0)
    questions = data.get('questions', [])
    quiz_info = data.get('quiz_info', {})

    if index >= len(questions):
        correct = data.get('correct', 0)
        incorrect = data.get('incorrect', 0)
        await message.answer(TextStatics.get_single_game_answer(correct, incorrect))
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
        await message.answer(question_text, reply_markup=markup)
    else:
        await message.answer(question_text)

    task = schedule_question_timeout(time_limit, state, index, q, message, send_question)
    await state.update_data(timer_task=task)
    await state.set_state(SoloGameStates.WAITING_ANSWER)


@router.message(Command('start', 'menu'))
async def start_menu(message: types.Message):
    await message.answer(TextStatics.get_start_menu(), reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data == 'game:solo')
async def callback_solo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    if await state.get_state():
        await callback.answer("Игра уже идет! Сначала завершите предыдущую игру командой /end_game", show_alert=True)
        return

    # Authenticate player and fetch quiz data
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        username=callback.from_user.username,
        lang_code=callback.from_user.language_code
    )

    await state.update_data(token=token)
    quiz_info = await get_quiz_info('solo')

    await state.update_data(quiz_info=quiz_info)
    questions_data = await get_questions(token, quiz_info['id'])

    await state.update_data(questions=questions_data["questions"], current_index=0, correct=0, incorrect=0)

    start_text = TextStatics.get_solo_start_text(
        quiz_info['name'], quiz_info['amount_questions']
    )

    await callback.message.answer(
        start_text,
        reply_markup=confirm_start_keyboard()
    )

    await state.set_state(SoloGameStates.WAITING_CONFIRM)


@router.callback_query(SoloGameStates.WAITING_CONFIRM, lambda c: c.data == 'game:solo:start')
async def confirm_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Start the quiz
    await send_question(callback.message, state)


@router.message(Command('end_game'))
async def end_game(message: types.Message, state: FSMContext):
    # End current game: cancel timer, show results, clear state
    data = await state.get_data()

    task = data.get('timer_task')
    if task:
        task.cancel()

    correct = data.get('correct', 0)
    incorrect = data.get('incorrect', 0)
    # Send final results
    await message.answer(TextStatics.get_single_game_answer(correct, incorrect))
    # Clear FSM state to allow new games
    await state.clear()


@router.callback_query(SoloGameStates.WAITING_ANSWER, lambda c: c.data and c.data.startswith('answer:'))
async def answer_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    index, q = await fetch_question_and_cancel(state)

    if q is None:
        return

    data = await state.get_data()
    selected = callback.data.split(':', 1)[1]

    is_right = False
    if selected == q['correct_answer']:
        await callback.message.answer('✅ Правильно!')
        await state.update_data(correct=data.get('correct', 0) + 1)
        is_right = True
    else:
        await callback.message.answer(
            f'❌ Неправильно! Правильный ответ: {q["correct_answer"]}'
        )
        await state.update_data(incorrect=data.get('incorrect', 0) + 1)

    # send answer to consumer
    game_key = next(
        (
            k
            for k in ws_manager._state.keys()  # type: ignore[attr-defined]
            if k.startswith(str(callback.message.chat.id))
        ),
        None,
    )

    if game_key:
        chat_username, quiz_id_str = game_key.split('_', 1)
        connection = await ws_manager.get_connection(chat_username, int(quiz_id_str))
        await connection.send_json(
            {
                'event': 'answer_question',
                'username': callback.from_user.username or str(callback.from_user.id),
                'is_right': is_right,
            }
        )

    # update game state answer sets for /game
    if game_key:
        gs = ws_manager.get_state(game_key)
        if is_right:
            gs.answers_right.add(username := (callback.from_user.username or str(callback.from_user.id)))
        else:
            gs.answers_wrong.add(username := (callback.from_user.username or str(callback.from_user.id)))

    await state.update_data(current_index=index + 1)
    await send_question(callback.message, state)


@router.message(SoloGameStates.WAITING_ANSWER)
async def text_answer(message: types.Message, state: FSMContext):
    index, q = await fetch_question_and_cancel(state)

    if q is None:
        return

    data = await state.get_data()
    user_answer = message.text.strip()

    is_right = False

    if q['question_type'] == QuestionTypeChoices.TEXT:
        if user_answer.lower().strip() == q['correct_answer'].lower().strip():
            await message.answer('✅ Правильно!')
            await state.update_data(correct=data.get('correct', 0) + 1)
            is_right = True
        else:
            await message.answer(
                f'❌ Неправильно! Правильный ответ: {q["correct_answer"]}'
            )
            await state.update_data(incorrect=data.get('incorrect', 0) + 1)

        await state.update_data(current_index=index + 1)

        # send answer to consumer
        game_key = next(
            (
                k
                for k in ws_manager._state.keys()  # type: ignore
                if k.startswith(str(message.chat.id))
            ),
            None,
        )

        if game_key:
            gs = ws_get_state(game_key)
            if is_right:
                gs.answers_right.add(username := (message.from_user.username or str(message.from_user.id)))
            else:
                gs.answers_wrong.add(username := (message.from_user.username or str(message.from_user.id)))

        await send_question(message, state)
    else:
        await message.answer('Пожалуйста, выберите вариант ответа кнопкой ниже.')
