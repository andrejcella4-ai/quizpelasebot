from states.local_state import GameModeChoices


class TextStatics:
    game_started_answer = 'Игра уже начата. Сначала завершите теущую игру, овтетив на все вопросы или завершите её досрочно, командой /end_game\n\n'

    @staticmethod
    def get_single_game_answer(right_answers: int, wrong_answers: int) -> str:
        xp = right_answers * 10
        return (
            "🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡\n\n"
            "🏆 Результаты раунда:\n"
            f"✅ Правильных ответов: {right_answers}\n"
            f"❌ Неправильных: {wrong_answers}\n"
            f"⭐ Баллы: {xp} баллов\n\n"
            "👇 Что дальше?\n\n"
            "🎮 Для начала новой игры используйте команду /quiz"
        )

    @staticmethod
    def game_started_answer() -> str:
        return 'Игра уже начата. Сначала завершите предыдущую игру командой /end_game'

    @staticmethod
    def get_start_menu() -> str:
        return (
            "🎮 Выберите режим игры:\n\n"
            "🤖 Соло - индивидуальная игра с ботом, персонализированные вопросы"
        )

    @staticmethod
    def get_solo_start_text(name: str, amount: int) -> str:
        """
        Возвращает единый текст для начала соло-игры: правила и вводную информацию.
        """
        return (
            "Правила одиночной игры:\n"
            "1. У вас есть ограниченное время на каждый вопрос.\n"
            "2. Ответьте на вопрос до конца таймера, иначе он засчитается неверным.\n"
            "3. В конце вы увидите статистику правильных и неверных ответов.\n\n"
            f"Вы выбрали соло-игру «{name}». Всего вопросов: {amount}.\n"
            "Нажмите на кнопку ниже, чтобы начать игру."
        )

    @staticmethod
    def get_question_result_text(wrong_answers: list[str], right_answers: list[str]) -> str:
        text = f"""
		⌛️ Время вышло!

		✅ Правильный ответ: Закон Паскаля

		📊 Ответы участников:

        """

        if wrong_answers:
            text += f"❌ Неправильно ответили: {wrong_answers}\n"
        if right_answers:
            text += f"✅ Правильно ответили: {right_answers}\n"

        return text

    @staticmethod
    def get_select_theme_text(mode: str) -> str:
        if mode == GameModeChoices.solo:
            theme = "🤖 Соло"
        elif mode == GameModeChoices.team:
            theme = "👥 Команда"
        elif mode == GameModeChoices.dm:
            theme = "👥 Кажд"
        else:
            pass

    # ---- New helpers to ensure все тексты приходят отсюда ----

    @staticmethod
    def game_already_running() -> str:
        return '🎮 В этом чате уже идет викторина.\nДля начала новой викторины сначала завершите текущую с помощью команды /stop'

    @staticmethod
    def need_create_team_first() -> str:
        return (
            'В этом чате пока нет команды.\n'
            'Напиши название команды ответом на это сообщение, чтобы зарегистрировать свою команду в общей рейтинге и начать игру!'
        )

    @staticmethod
    def need_team_name_hint() -> str:
        return 'Укажите название команды после команды. Пример: /create_team МояКоманда'

    @staticmethod
    def team_created_success(team_name: str) -> str:
        return f'Команда "{team_name}" успешно создана!\n'

    @staticmethod
    def team_created_success_before_game(team_name: str) -> str:
        return f'Команда "{team_name}" успешно создана!\nТеперь можете выбрать командный режим игры!'

    @staticmethod
    def team_create_error() -> str:
        return 'Ошибка при создании команды!'

    @staticmethod
    def team_registration_start(team_name: str, seconds: int, captain_username: str) -> str:
        return f"""
🎮 Стартуем! "{team_name}" — поехали!\n
📝 Как играть:\n
• Обсуждаете вопрос всей командой\n
• Капитан (@a_glinsky) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /ответ ваш_ответ\n
• Очки начисляются всей команде\n
• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n
Готовность {seconds} сек. ⏳ Удачи, команда! 🧠💪
        """

    @staticmethod
    def team_game_starts() -> str:
        return 'Командная игра начинается!'

    @staticmethod
    def outdated_question() -> str:
        return 'Этот вопрос уже неактуален!'

    @staticmethod
    def no_players_cannot_start() -> str:
        return 'Игра не может начаться без участников!'

    @staticmethod
    def no_teams_cannot_start() -> str:
        return 'Игра не может начаться без команд!'

    @staticmethod
    def time_is_up_with_answer(right_answer: str) -> str:
        return (
            "⌛️ Время вышло!\n\n"
            f"✅ Правильный ответ: {right_answer}\n\n"
            "📊 Ответы участников:"
        )

    @staticmethod
    def show_right_answer_only(right_answer: str) -> str:
        return f'✅ Правильный ответ: {right_answer}'

    @staticmethod
    def correct_inline_hint() -> str:
        return '✅ Правильно!'

    @staticmethod
    def incorrect_inline_hint() -> str:
        return '❌ Неправильно!'

    @staticmethod
    def team_quiz_finished_no_scores() -> str:
        return '🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\nКоманда не набрала очков.'

    @staticmethod
    def team_quiz_finished_with_scores(team_name: str, score: int) -> str:
        return (
            '🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\n'
            '🏆 Результаты раунда:\n'
            f'👥 Команда "{team_name}": {score} баллов\n\n'
            '👇 Что дальше?\n\n'
            '🎮 Для начала новой игры используйте команду /menu'
        )

    @staticmethod
    def no_participants_game_finished() -> str:
        return 'Игра окончена! Никто не участвовал.'

    @staticmethod
    def dm_quiz_finished_with_scores(lines: str) -> str:
        return '🏆 Игра окончена!\n\n' + lines

    @staticmethod
    def dm_quiz_finished_full(
        sorted_scores: list[tuple[str, int]],
        registered_count: int,
        participants_total_points: int | None = None,
        players_totals: list[tuple[str, int]] | None = None,
    ) -> str:
        if not sorted_scores:
            results = "—"
            participated = 0
        else:
            result_lines = []
            for idx, (name, score) in enumerate(sorted_scores, start=1):
                prefix = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else "🔹"))
                handle = f"@{name}"
                result_lines.append(f"{prefix} {idx}. {handle}: {score * 10} баллов")
            results = "\n".join(result_lines)
            participated = len(sorted_scores)
        percent = int(round((participated / registered_count) * 100)) if registered_count else 0
        if players_totals:
            totals_sorted = sorted(players_totals, key=lambda x: x[1], reverse=True)
            totals_lines = []
            for idx, (name, total_points) in enumerate(totals_sorted, start=1):
                handle = f"@{name}"
                totals_lines.append(f"{idx}. {handle}: {total_points} баллов")
            stats_block = "📊 Общие баллы участников:\n" + "\n".join(totals_lines)
        elif participants_total_points is not None:
            stats_block = f"💰 Сумма баллов участников: {participants_total_points}"
        else:
            stats_block = f"👥 Участвовало: {participated} из {registered_count} зарегистрированных ({percent}%)"
        return (
            "🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\n"
            "🏆 Результаты раунда:\n"
            f"{results}\n"
            "👇 Что дальше?\n\n\n"
            f"{stats_block}\n"
            "🎮 Для начала новой игры используйте команду /quiz"
        )

    @staticmethod
    def dm_text_wrong_attempt(attempts_remaining: int, right_answer: str) -> str:
        if attempts_remaining == 1:
            return '❌ Неправильный ответ! Осталась 1 попытка'
        else:
            return f'❌ Неправильный ответ! Попыток больше нет.\n✅ Правильный ответ: {right_answer}\n\nПереходим к следующему вопросу...'

    @staticmethod
    def dm_registration_open(seconds: int, quiz_name: str) -> str:
        return (
            f'📝 Регистрация на игру ("{quiz_name}") открыта!\n\n'
            f'⏳ До завершения регистрации: {seconds} сек.'
        )

    @staticmethod
    def dm_registration_updated(players: list[str], seconds_left: int, quiz_name: str) -> str:
        players_text = '\n'.join(f'— @{p}' for p in players) or '—'
        return (
            f'Регистрация на игру ("{quiz_name}"). Старт через {seconds_left} сек.\n\n'
            f'Участники:\n{players_text}'
        )

    @staticmethod
    def dm_registration_message(usernames: list[str], seconds_left: int) -> str:
        participants_text = ''
        for i, username in enumerate(usernames):
            participants_text += f"{i+1}. @{username}\n"
        return (
            "📝 Регистрация на игру открыта!\n\n"
            f"👥 Участники ({max(1, len(usernames))}):\n{participants_text}\n"
            "Если хочешь участвовать в этом раунде — просто нажми кнопку ниже.\n"
            f"⏳ У тебя есть {seconds_left} секунд, чтобы вступить в игру! \n\n"
            "Чем больше участников — тем интереснее баттл! 🎯\n"
            "👇 Жми, если готов(а) сражаться за баллы и славу! 🧠⚡️"
        )

    @staticmethod
    def dm_select_theme_message() -> str:
        return """
🎯 Мы начинаем игру...

Впереди один раунд и шесть вопросов! За каждый правильный ответ — +10 баллов в копилку.

👇 Итак, тема для раунда:
        """

    @staticmethod
    def theme_selected_start(name: str, amount: int) -> str:
        return f"""
🎯 Категория "{name}" — принял!
Будет жарко 🔥 — {amount} вопросов, 10 баллов за каждый правильный ответ.

Скоро начнём! 🧠⚡️
        """

    @staticmethod
    def canceled() -> str:
        return 'Игра отменена.'

    @staticmethod
    def stopped_quiz() -> str:
        return '🛑 Викторина остановлена.\nДля начала новой используйте команду /quiz'

    @staticmethod
    def time_left_30() -> str:
        return '⚠️ Осталось 30 секунд!'

    @staticmethod
    def time_left_10() -> str:
        return '⚠️ Осталось 10 секунд!'

    @staticmethod
    def please_choose_variant() -> str:
        return 'Пожалуйста, выберите вариант ответа кнопкой ниже.'

    @staticmethod
    def no_active_game() -> str:
        return '🛑 В этом чате нет активной викторины.'

    @staticmethod
    def game_not_running() -> str:
        return 'Игра не идет!'

    @staticmethod
    def captain_only_can_answer() -> str:
        return 'Отвечать может только капитан команды!'

    @staticmethod
    def already_answered() -> str:
        return 'Вы уже ответили на этот вопрос!'

    @staticmethod
    def only_registered_can_answer() -> str:
        return 'Только зарегистрированные участники могут отвечать в этом раунде. Нажмите «Участвую» перед началом.'

    @staticmethod
    def need_answer_text_after_command() -> str:
        return 'Нужно написать ответ после команды. Пример: /otvet ваш_ответ'

    @staticmethod
    def theme_selection_solo() -> str:
        return '📚 Выберите категорию викторины (режим: 🤖 Соло):'

    @staticmethod
    def get_start_message(username: str):
        return (
            f"👋 Привет, @{username}!\n\n"
            "Я бот для проведения викторин в Telegram.\n\n"
            "🎮 Чтобы начать новую викторину, используйте команду /quiz\n"
            "📊 Для просмотра статистики используйте команду /stats\n"
            "Для подробной информации используйте команду /help"
        )

    @staticmethod
    def solo_quiz_start_message():
        return (
            "🎮 Погнали! Выберите режим, в котором хотите играть:\n\n"
            "🏆 Соревнование — каждый сам за себя! Кто наберёт больше всех очков, тот и чемпион 💪\n\n"
            "👥 Командный режим — квиз для всей команды! Каждый день — новая викторина: обсуждаете вместе, отвечаете вместе, побеждаете вместе!\n\n"
            "👇 Жмите кнопку и вперёд к знаниям! 🧠⚡️"
        )


    @staticmethod
    def dm_quiz_start_message():
        return """
        🎯 Мы начинаем игру...

        Впереди один раунд и шесть вопросов! За каждый правильный ответ — +10 баллов в копилку.

        👇 Итак, тема для раунда:
        """

    @staticmethod
    def dm_quiz_after_start_message(question_amount: int):
        return f"""
        🎯 Категория "Обо всем" — принял!
        Будет жарко 🔥 — {question_amount} вопросов, 10 баллов за каждый правильный ответ.

        Скоро начнём! 🧠⚡️
        """

    @staticmethod
    def dm_quiz_question_result_message(
        right_answer: str,
        not_answered: list[str],
        wrong_answers: list[str],
        right_answers: list[str],
        totals: dict[str, int] | None = None,
    ) -> str:
        blocks = []
        if right_answers:
            # Добавляем ": +10 баллов" к каждому и общий счет в скобках
            def _fmt_right(name: str) -> str:
                if totals and name in totals:
                    return f"{name}: +10 баллов ({totals[name]})"
                return f"{name}: +10 баллов"
            rights = "\n".join([_fmt_right(name) for name in right_answers])
            blocks.append(f"✅ Правильно ответили:\n{rights}")
        if wrong_answers:
            def _fmt_wrong(name: str) -> str:
                if totals and name in totals:
                    return f"{name} ({totals[name]})"
                return name
            wrongs = "\n".join([_fmt_wrong(name) for name in wrong_answers])
            blocks.append(f"❌ Неправильно ответили:\n{wrongs}")
        if not_answered:
            na = "\n".join(not_answered)
            blocks.append(f"⏳ Не успели ответить:\n{na}")

        details = ("\n\n".join(blocks)) if blocks else ""
        return (
            "⌛️ Время вышло!\n\n"
            f"✅ Правильный ответ: {right_answer}\n\n"
            "📊 Ответы участников:\n\n"
            f"{details}".rstrip()
        )

    @staticmethod
    def dm_quiz_question_template(text: str, timer: int, current_q_idx: int) -> str:
        return f"""
Вопрос №{current_q_idx}
🧠  {text}

⏱ ТАЙМЕР: {timer} сек
        """

    @staticmethod
    def team_quiz_question_template(current_q_idx: int, username: str, text: str, timer: int) -> str:
        return TextStatics.dm_quiz_question_template(text, timer, current_q_idx) + f"""
💡 {username}, отвечай командами /otvet и /answer или просто ответь на это сообщение
📝 У вас 2 попытки
        """

    @staticmethod
    def team_quiz_question_right_answer(username: str, xp: int) -> str:
        return f"🎉 Правильный ответ от {username}! +{xp} баллов всей команде"

    @staticmethod
    def team_start_message(team_name: str, username: str) -> str:
        return f"""
        🎮 Стартуем! "Командная викторина #01" — поехали!

        📝 Как играть:

        • Обсуждаете вопрос всей командой

        • Капитан ({username}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /otvet ваш_ответ

        • Очки начисляются всей команде

        • 2 балла за правильный ответ с первой попытки и 1 балл — со второй

        Время пошло! ⏳ Удачи, команда! 🧠💪
        """

    @staticmethod
    def team_prep_message(quiz_name: str, captain_username: str | None, seconds: int) -> str:
        captain = f"@{captain_username}" if captain_username and not captain_username.startswith('@') else (captain_username or '')
        return (
            f"🎮 Стартуем! \"{quiz_name}\" — поехали!\n\n"
            f"📝 Как играть:\n\n"
            f"• Обсуждаете вопрос всей командой\n\n"
            f"• Капитан ({captain}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /ответ ваш_ответ\n\n"
            f"• Очки начисляются всей команде\n\n"
            f"• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n\n"
            f"⏳ Подготовка: {seconds} сек"
        )

    @staticmethod
    def team_prep_message_started(quiz_name: str, captain_username: str | None) -> str:
        captain = f"@{captain_username}" if captain_username and not captain_username.startswith('@') else (captain_username or '')
        return (
            f"🎮 Стартуем! \"{quiz_name}\" — поехали!\n\n"
            f"📝 Как играть:\n\n"
            f"• Обсуждаете вопрос всей командой\n\n"
            f"• Капитан ({captain}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /ответ ваш_ответ\n\n"
            f"• Очки начисляются всей команде\n\n"
            f"• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n\n"
            f"Время пошло! ⏳ Удачи, команда! 🧠💪"
        )

    @staticmethod
    def team_quiz_question_wrong_answer(attempts_remaining: int, right_answer: str) -> str:
        if attempts_remaining == 1:
            return f"❌ Неправильный ответ!\n осталась 1 попытка"
        else:
            return f"❌ Неправильный ответ! Попыток больше нет.\n✅ Правильный ответ: {right_answer}\n\nПереходим к следующему вопросу..."

    @staticmethod
    def get_registration_dm_message(usernames: list[str]) -> str:
        participants_text = ''

        for i, username in enumerate(usernames):
            participants_text += f"{i+1}. @{username}\n"
        
        return f"""
        📝 Регистрация на игру открыта!

        👥 Участники (1):
        {participants_text}

        Если хочешь участвовать в этом раунде — просто нажми кнопку ниже.
        ⏳ У тебя есть 60 секунд, чтобы вступить в игру! 

        Чем больше участников — тем интереснее баттл! 🎯
        👇 Жми, если готов(а) сражаться за баллы и славу! 🧠⚡️
        """

    @staticmethod
    def format_question_text(index: int, text: str, time_limit: int) -> str:
        # Формат вопроса как в примерах JSON
        return TextStatics.dm_quiz_question_template(text, time_limit, index).strip()
    
    @staticmethod
    def get_solo_intro(name: str, amount: int) -> str:
        return (
            f"Вы выбрали соло-игру «{name}». Всего вопросов: {amount}.\n"
            "Нажмите на кнопку ниже, чтобы начать игру."
        )
