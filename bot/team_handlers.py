from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, date

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from api_client import get_quiz_info, get_questions, auth_player, create_team, get_team, get_quiz_list, team_game_end, list_plan_team_quizzes
from keyboards import (
    main_menu_keyboard,
    registration_dm_keyboard,
    create_variant_keyboard,
    quiz_theme_keyboard,
    team_registration_keyboard,
    team_plans_keyboard,
)

from helpers import (
    start_game_questions,
    process_answer,
    format_game_status,
    schedule_registration_end,
    move_to_next_question,
    show_final_results,
    finalize_game,
    create_team_helper,
    get_today_games_avaliable,
    get_nearest_game_avaliable,
)
from states.local_state import (
    get_game_state,
    _get_game_key_for_chat,
    _games_state,
    REGISTRATION_DURATION,
)
from static.answer_texts import TextStatics
from states.fsm import SoloGameStates
from static.choices import QuestionTypeChoices
from states.fsm import TeamGameStates


router = Router(name="team_handlers")


# --------------------------------------------------------
# End game command (admin or any user)
# --------------------------------------------------------

@router.message(Command("end_game"))
async def manual_end_game(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        await message.answer(TextStatics.no_active_game())
        return

    game_state = get_game_state(game_key)
    
    # Отменяем таймеры
    if game_state.timer_task:
        game_state.timer_task.cancel()
    # Унифицированное завершение игры
    await finalize_game(message.bot, message.chat.id, game_state)


@router.message(Command("stop"))
async def stop_game_team(message: types.Message, state: FSMContext):
    """Остановить текущую викторину: SOLO (private) очищаем FSM, GROUP (dm/team) удаляем из _games_state."""
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


# --------------------------------------------------------
# /game command – show current status or registration
# --------------------------------------------------------

@router.message(Command("game"))
async def show_game_status(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)

    if not game_key:
        await message.answer(TextStatics.no_active_game())
        return

    game_state = get_game_state(game_key)
    text = format_game_status(game_state)
    await message.answer(text)


@router.message(Command("create_team"))
async def create_team_command(message: types.Message, state: FSMContext):
    """Create a team for this chat."""
    # Expect /create_team <team name>
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(TextStatics.need_team_name_hint())
        return
    team_name = parts[1].strip()

    # Auth player to get token
    token = await auth_player(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name or "",
        username=message.from_user.username,
        phone=None,
        lang_code=message.from_user.language_code,
    )

    chat_username = message.chat.username or str(message.chat.id)
    try:
        await create_team(token, chat_username, team_name, message.from_user.id)
        await message.answer(TextStatics.team_created_success(team_name))
    except Exception as e:
        print(e)
        await message.answer(TextStatics.team_create_error())


@router.message(TeamGameStates.TEAM_CREATE_NAME)
async def create_team_name(message: types.Message, state: FSMContext):
    create_team_message_id = (await state.get_data()).get("create_team_message_id")
    send_from_user_id = (await state.get_data()).get("send_from_user_id")

    if not message.reply_to_message:
        return

    if create_team_message_id == message.reply_to_message.message_id and send_from_user_id == message.from_user.id:
        if not message.text.strip():
            await message.answer(TextStatics.no_text_in_team_name())
            return

        await message.bot.delete_message(message.chat.id, create_team_message_id)

        await create_team_helper(message.text.strip(), message)

        await state.clear()


@router.callback_query(lambda c: c.data in {"game:dm", "game:team"})
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    """Callback after user selects DM or Team mode from main menu."""
    await callback.answer()

    # Проверяем есть ли уже активная игра
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if game_key:
        game_state = get_game_state(game_key)
        if game_state.status == "playing":
            await callback.message.answer(TextStatics.game_already_running())
            return

    mode = "team" if callback.data == "game:team" else "dm"
    chat_username: str = callback.message.chat.username or str(callback.message.chat.id)

    # Авторизуем игрока для получения токена
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name or "",
        username=callback.from_user.username,
        phone=None,
        lang_code=callback.from_user.language_code
    )

    # Если это командный режим, убедимся, что команда существует
    if mode == "team":
        team_data = await get_team(token, chat_username)
        if team_data is None:
            await state.set_state(TeamGameStates.TEAM_CREATE_NAME)
            create_team_message = await callback.message.answer(TextStatics.need_create_team_first())
            await state.update_data(create_team_message_id=create_team_message.message_id)
            await state.update_data(send_from_user_id=callback.from_user.id)
            return

    # Для командного режима проверим наличие плана на сегодня
    if mode == "team":
        plans = await list_plan_team_quizzes()
        today_games_avaliable = get_today_games_avaliable(plans)
        nearest_game_avaliavle = get_nearest_game_avaliable(plans)

        if not plans:
            await callback.message.answer("📆 Нет запланированной викторины в режиме кооперации на ближайшие дни.")
            return

        if not today_games_avaliable and nearest_game_avaliavle:
            # Преобразуем строку datetime в объект datetime и форматируем для России
            scheduled_datetime = datetime.fromisoformat(nearest_game_avaliavle['scheduled_datetime'].replace('Z', '+00:00'))
            formatted_datetime = scheduled_datetime.strftime("%d.%m.%Y %H:%M")
            await callback.message.answer(f"📆 Ближайшая викторина в режиме кооперации: {nearest_game_avaliavle['quiz_name']} @ {formatted_datetime}")
            return

        if not today_games_avaliable:
            return

        quizzes = today_games_avaliable
    else:
        # Запрашиваем список квизов выбранного типа
        quizzes = await get_quiz_list(mode)

    # Временно используем chat.id как ключ до выбора темы
    game_key = f"{callback.message.chat.id}_pending"
    game_state = get_game_state(game_key)
    game_state.mode = mode
    game_state.status = "reg"
    game_state.registration_ends_at = datetime.utcnow() + timedelta(seconds=REGISTRATION_DURATION)
    game_state.available_quizzes = quizzes
    game_state.quiz_id = None
    game_state.quiz_name = None

    # Пока вопросы не загружаем до выбора темы
    game_state.questions = []

    if mode == "dm":
        # ------ старая логика регистрации DM ------
        # Формируем текст регистрации как в примере
        reg_text = TextStatics.dm_registration_message(list(game_state.players), REGISTRATION_DURATION)
        keyboard = registration_dm_keyboard()

        sent_msg = await callback.message.answer(reg_text, reply_markup=keyboard)
        game_state.message_id = sent_msg.message_id

        async def on_expire():
            try:
                # Завершили регистрацию — предлагаем выбрать тему
                await callback.message.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=game_state.message_id,
                    text=TextStatics.dm_select_theme_message(),
                    reply_markup=quiz_theme_keyboard([(q.get("name", str(q.get("id"))), q.get("id")) for q in game_state.available_quizzes])
                )
            except Exception as e:
                print(f"Ошибка в on_expire: {e}")
                import traceback
                traceback.print_exc()

        game_state.timer_task = await schedule_registration_end(
            game_state.registration_ends_at,
            on_expire,
        )
        await state.set_state(SoloGameStates.WAITING_CONFIRM)
    else:
        # ----- Командный режим с таймером регистрации -----
        team_name = team_data["name"] if team_data else "Команда"
        game_state.teams = {team_name: [team_data.get("captain_username") if team_data else None]}
        game_state.captains = {team_name: team_data.get("captain_username") if team_data else None}
        try:
            game_state.team_id = team_data.get("id") if team_data else None
        except Exception:
            game_state.team_id = None
        
        # Показываем сообщение о выборе плана/темы
        await callback.message.answer("📆 Выберите запланированную викторину:", reply_markup=team_plans_keyboard(game_state.available_quizzes))
        
        # Таймер подготовки здесь не запускаем, запустим после выбора плана
        await state.set_state(SoloGameStates.WAITING_CONFIRM)


# -------- досрочный старт командной игры --------

@router.callback_query(lambda c: c.data == "team:start_early")
async def start_team_game_early(callback: types.CallbackQuery, state: FSMContext):
    """Досрочно начать командную игру."""
    await callback.answer()
    
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    
    game_state = get_game_state(game_key)
    if game_state.status != "reg" or game_state.mode != "team":
        return
    
    # Отменяем таймер регистрации
    if game_state.timer_task:
        game_state.timer_task.cancel()
        game_state.timer_task = None
    
    # Загружаем вопросы для командной игры (если план ещё не выбран — предложим выбор)
    token = await auth_player(
        telegram_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name or "",
        username=callback.from_user.username,
        phone=None,
        lang_code=callback.from_user.language_code,
    )
    if not game_state.quiz_id:
        # показать выбор планов
        await callback.message.edit_text(
            "📆 Выберите запланированную викторину:",
            reply_markup=team_plans_keyboard(game_state.available_quizzes),
        )
        return
    # Показать сообщение подготовки (без мгновенного старта)
    prep_text = TextStatics.team_prep_message(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0], REGISTRATION_DURATION)
    # Сохраним message_id для последующего редактирования
    try:
        await callback.message.edit_text(prep_text)
        game_state.message_id = callback.message.message_id
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            game_state.message_id = callback.message.message_id
        else:
            sent = await callback.message.answer(prep_text)
            game_state.message_id = sent.message_id
    
    # Через REGISTRATION_DURATION секунд стартуем (как on_expire)
    async def _delayed_start():
        try:
            token = await auth_player(
                telegram_id=callback.from_user.id,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name or "",
                username=callback.from_user.username,
                phone=None,
                lang_code=callback.from_user.language_code,
            )
            quiz_info = await get_quiz_info("team", quiz_id=game_state.quiz_id)
            questions_data = await get_questions(token, quiz_info["id"])
            game_state.questions = questions_data["questions"]
            game_state.total_questions = len(game_state.questions)
            game_state.status = "playing"
            # Редактируем исходное сообщение подготовки
            try:
                await callback.message.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=game_state.message_id,
                    text=TextStatics.team_prep_message_started(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0])
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    await callback.message.answer(TextStatics.team_prep_message_started(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0]))
            await start_game_questions(callback, game_state)
        except Exception:
            pass
    
    game_state.timer_task = await schedule_registration_end(datetime.utcnow() + timedelta(seconds=REGISTRATION_DURATION), _delayed_start)


# --- Выбор плана командной игры ---
@router.callback_query(lambda c: c.data.startswith("plan_team:"))
async def choose_team_plan(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    game_state = get_game_state(game_key)
    if game_state.mode != "team" or game_state.status not in {"reg"}:
        return
    plan_id_str = callback.data.split(":", 1)[1]
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        return
    # Найдем план
    plan = next((p for p in game_state.available_quizzes if p.get("id") == plan_id), None)
    if not plan:
        return
    # Из плана берем quiz id
    game_state.quiz_id = plan.get("quiz")
    game_state.quiz_name = plan.get("quiz_name") or str(game_state.quiz_id)

    # Показать сообщение подготовки с таймером
    prep_text = TextStatics.team_prep_message(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0], REGISTRATION_DURATION)
    try:
        await callback.message.edit_text(prep_text)
        game_state.message_id = callback.message.message_id
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            game_state.message_id = callback.message.message_id
        else:
            sent = await callback.message.answer(prep_text)
            game_state.message_id = sent.message_id
    
    # По истечении подготовки загрузим вопросы и начнём
    async def _delayed_start_after_choose():
        try:
            token = await auth_player(
                telegram_id=callback.from_user.id,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name or "",
                username=callback.from_user.username,
                phone=None,
                lang_code=callback.from_user.language_code,
            )
            quiz_info = await get_quiz_info("team", quiz_id=game_state.quiz_id)
            questions_data = await get_questions(token, quiz_info["id"])
            game_state.questions = questions_data["questions"]
            game_state.total_questions = len(game_state.questions)
            game_state.status = "playing"
            try:
                await callback.message.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=game_state.message_id,
                    text=TextStatics.team_prep_message_started(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0])
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    await callback.message.answer(TextStatics.team_prep_message_started(game_state.quiz_name or "Командная викторина", list(game_state.captains.values())[0]))
            await start_game_questions(callback, game_state)
        except Exception:
            pass
    game_state.timer_task = await schedule_registration_end(datetime.utcnow() + timedelta(seconds=REGISTRATION_DURATION), _delayed_start_after_choose)


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
    updated_text = TextStatics.dm_registration_message(list(game_state.players), seconds_left)

    await callback.message.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=game_state.message_id,
        text=updated_text,
        reply_markup=registration_dm_keyboard(),
    )


# --- Завершение регистрации DM вручную ---
@router.callback_query(lambda c: c.data == "reg:end")
async def reg_end_dm(callback: types.CallbackQuery):
    await callback.answer()

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    game_state = get_game_state(game_key)
    if game_state.mode != "dm" or game_state.status != "reg":
        return

    # Отменяем таймер регистрации
    if game_state.timer_task:
        game_state.timer_task.cancel()
        game_state.timer_task = None

    try:
        await callback.message.edit_text(
            TextStatics.dm_select_theme_message(),
            reply_markup=quiz_theme_keyboard([(q.get("name", str(q.get("id"))), q.get("id")) for q in game_state.available_quizzes])
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# -------- обработка ответов во время игры --------

@router.callback_query(lambda c: c.data.startswith("answer:") and _get_game_key_for_chat(c.message.chat.id))
async def answer_variant_callback(callback: types.CallbackQuery):

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        await callback.answer(TextStatics.no_active_game())
        return

    game_state = get_game_state(game_key)
    if game_state.status != "playing":
        await callback.answer(TextStatics.game_not_running())
        return

    # Проверяем что это текущий вопрос (не старый)
    if callback.message.message_id != game_state.current_question_msg_id:
        await callback.answer(TextStatics.outdated_question())
        return

    username = callback.from_user.username or str(callback.from_user.id)
    
    # Проверяем права на ответ
    if game_state.mode == "team":
        # В командном режиме может отвечать только капитан

        if list(game_state.captains.values())[0] != username:
            await callback.answer(TextStatics.captain_only_can_answer())
            return
    else:
        # DM: только зарегистрированные игроки
        if username not in game_state.players:
            await callback.answer(TextStatics.only_registered_can_answer())
            return

    # Проверяем, что игрок еще не отвечал
    if username in game_state.answers_right or username in game_state.answers_wrong:
        await callback.answer(TextStatics.already_answered())
        return

    # Получаем индекс выбранного варианта и маппим его в текст
    _, variant_idx_str = callback.data.split(":", 1)
    try:
        variant_idx = int(variant_idx_str)
    except ValueError:
        await callback.answer(TextStatics.incorrect_inline_hint())
        return

    options = game_state.current_options or []
    if not options:
        # fallback на формирование из вопроса, если по какой-то причине не сохранилось
        current_question = game_state.questions[game_state.current_q_idx]
        options = current_question["wrong_answers"] + [current_question["correct_answer"]]
    if variant_idx < 0 or variant_idx >= len(options):
        await callback.answer(TextStatics.incorrect_inline_hint())
        return
    variant_text = options[variant_idx]
    await process_answer(
        callback.message.bot, 
        callback.message.chat.id, 
        game_state, 
        username, 
        variant_text,
        callback
    )


# --- Выбор темы DM после регистрации ---
@router.callback_query(lambda c: c.data.startswith("theme_id:"))
async def choose_theme_dm(callback: types.CallbackQuery):
    await callback.answer()

    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    game_state = get_game_state(game_key)
    # Сериализуем старт DM-игры на этапе выбора темы, чтобы не было дублей
    if game_state.transition_lock is None:
        game_state.transition_lock = asyncio.Lock()
    async with game_state.transition_lock:
        if game_state.mode != "dm" or game_state.status != "reg":
            return

        selected_id_str = callback.data.split(":", 1)[1]
        try:
            selected_id = int(selected_id_str)
        except ValueError:
            return
        # Найдем квиз по id
        quiz = next((q for q in game_state.available_quizzes if q.get("id") == selected_id), None)
        if not quiz:
            return

        game_state.quiz_id = quiz["id"]
        game_state.quiz_name = quiz.get("name")

        # Загрузим вопросы
        token = await auth_player(
            telegram_id=callback.from_user.id,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name or "",
            username=callback.from_user.username,
            phone=None,
            lang_code=callback.from_user.language_code
        )

        questions_data = await get_questions(token, game_state.quiz_id)
        game_state.questions = questions_data["questions"]
        game_state.total_questions = len(game_state.questions)
        game_state.status = "playing"

        # Безопасно редактируем сообщение (игнорируем "message is not modified")
        try:
            await callback.message.edit_text(
                TextStatics.theme_selected_start(game_state.quiz_name or str(selected_id), game_state.total_questions)
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

    # Стартуем вопросы (вне lock)
    await start_game_questions(callback, game_state)


@router.message(
    lambda m:
    m.chat
    and _get_game_key_for_chat(m.chat.id)
    and get_game_state(_get_game_key_for_chat(m.chat.id)).status == "playing"
    and (
        (m.text and (m.text.startswith("/otvet") or m.text.startswith("/answer")))
        or (m.reply_to_message is not None)
    )
)
async def answer_text_message(message: types.Message):
    game_key = _get_game_key_for_chat(message.chat.id)
    if not game_key:
        return
    
    game_state = get_game_state(game_key)
    
    # Если это ответ-реплай, убеждаемся, что он к текущему вопросу
    if message.reply_to_message is not None:
        # current_question_msg_id должен быть уже установлен send_next_question()
        if game_state.current_question_msg_id is None or message.reply_to_message.message_id != game_state.current_question_msg_id:
            return

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
    # В DM пускаем отвечать только зарегистрированных игроков
    if game_state.mode == "dm" and username not in game_state.players:
        await message.answer(TextStatics.only_registered_can_answer())
        return
    if username in game_state.answers_right or username in game_state.answers_wrong:
        await message.answer(TextStatics.already_answered())
        return
    
    raw_text = (message.text or "").strip()
    if raw_text.startswith("/otvet") or raw_text.startswith("/answer"):
        parts = raw_text.split(" ", maxsplit=1)
        if len(parts) <= 1 or not parts[1].strip():
            await message.answer(TextStatics.need_answer_text_after_command())
            return
        user_answer = parts[1].strip()
    else:
        user_answer = raw_text

    await process_answer(
        message.bot,
        message.chat.id,
        game_state,
        username,
        user_answer,
    )


# --- Переход к следующему вопросу по кнопке ---
@router.callback_query(lambda c: c.data == "next_question")
async def next_question_dm_team(callback: types.CallbackQuery):
    await callback.answer()
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    game_state = get_game_state(game_key)
    # Игру могли завершать
    if game_state.is_finishing or game_state.status != "playing":
        return
    # В DM/Team переходим далее только если выведен результат вопроса (ожидаем next)
    # Защищаемся от одновременных кликов через lock
    if game_state.transition_lock is None:
        game_state.transition_lock = asyncio.Lock()
    async with game_state.transition_lock:
        if game_state.is_finishing or game_state.status != "playing":
            return
        # Разрешаем переход, если мы действительно на этапе после вывода результата
        if not (game_state.waiting_next or game_state.question_result_sent):
            return
        # Двойная защита от дублей: флаг на период перехода
        if getattr(game_state, 'next_in_progress', False):
            return
        game_state.next_in_progress = True
        # Снимаем ожидание и помечаем, что результат уже отправлен, чтобы второй клик ничего не делал
        game_state.waiting_next = False
        game_state.question_result_sent = True
    # Переходим к следующему вопросу (вне lock), как отдельная задача чтобы исключить блокировки и гонки
    asyncio.create_task(move_to_next_question(callback.message.bot, callback.message.chat.id, game_state))
    # Сбросим флаг после фактического выхода на следующий вопрос
    game_state.next_in_progress = False


# --- Отмена игры кнопкой ---
@router.callback_query(lambda c: c.data == "game:cancel")
async def cancel_game_callback(callback: types.CallbackQuery):
    await callback.answer()
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        return
    game_state = get_game_state(game_key)
    if game_state.timer_task:
        game_state.timer_task.cancel()
    try:
        del _games_state[game_key]
    except Exception:
        pass
    await callback.message.answer(TextStatics.canceled())


# --- Завершить игру кнопкой (DM/Team в группах) ---
@router.callback_query(lambda c: c.data == "finish_quiz")
async def finish_quiz_group(callback: types.CallbackQuery):
    await callback.answer()
    # Только для групповых чатов: dm и team
    if callback.message.chat.type == 'private':
        return
    game_key = _get_game_key_for_chat(callback.message.chat.id)
    if not game_key:
        await callback.message.answer(TextStatics.no_active_game())
        return
    game_state = get_game_state(game_key)
    # отменяем таймер
    if game_state.timer_task:
        try:
            game_state.timer_task.cancel()
        except Exception:
            pass
        game_state.timer_task = None
    # Унифицированное завершение игры
    from helpers import finalize_game
    await finalize_game(callback.message.bot, callback.message.chat.id, game_state)
