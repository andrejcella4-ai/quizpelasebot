import os
import time

from api_client import get_bot_texts


time.sleep(5)
_current_bot_texts = {list(item.keys())[0]: list(item.values())[0] for item in get_bot_texts(os.getenv('BOT_TOKEN'))}


def _t(key: str, default: str, **params) -> str:
    """Возвращает текст из _current_bot_texts по ключу с безопасным фолбеком.

    Ожидаем структуру: { key: { 'unformatted_text': '...' } }
    Поддерживается подстановка плейсхолдеров через str.format(**params).
    """
    try:
        source = _current_bot_texts or {}
        # Если вдруг это корутина/не-словарь — игнорируем и используем default
        if not isinstance(source, dict):
            raise TypeError("texts source is not a dict")
        raw = source.get(key) or {}
        text = raw.get('unformatted_text') if isinstance(raw, dict) else None
        text = text or default
    except Exception:
        text = default
    try:
        return text.format(**params) if params else text
    except Exception:
        # На случай несовпадения плейсхолдеров
        return text


def plural_points(n: int) -> str:
    """Возвращает правильное склонение слова 'балл'"""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return 'балл'
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return 'балла'
    return 'баллов'


class TextStatics:

    @staticmethod
    def get_single_game_answer(right_answers: int, wrong_answers: int) -> str:
        xp = right_answers
        default = (
            "🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡\n\n"
            "🏆 Результаты раунда:\n"
            "✅ Правильных ответов: {right_answers}\n"
            "❌ Неправильных: {wrong_answers}\n"
            "⭐ Баллы: {xp} баллов\n\n"
            "👇 Что дальше?\n\n"
            "🎮 Для начала новой игры используйте команду /quiz"
        )
        return _t(
            'single_game_answer',
            default,
            right_answers=right_answers,
            wrong_answers=wrong_answers,
            xp=xp,
        )

    @staticmethod
    def get_start_menu() -> str:
        default = (
            "🎮 Выберите режим игры:\n\n"
            "🤖 Соло - индивидуальная игра с ботом, персонализированные вопросы"
        )
        return _t('start_menu', default)

    @staticmethod
    def get_solo_start_text(name: str, amount: int) -> str:
        """
        Возвращает единый текст для начала соло-игры: правила и вводную информацию.
        """
        default = (
            "Правила одиночной игры:\n"
            "1. У вас есть ограниченное время на каждый вопрос.\n"
            "2. Ответьте на вопрос до конца таймера, иначе он засчитается неверным.\n"
            "3. В конце вы увидите статистику правильных и неверных ответов.\n\n"
            "Вы выбрали соло-игру «{name}». Всего вопросов: {amount}.\n"
            "Нажмите на кнопку ниже, чтобы начать игру."
        )
        return _t('solo_start_text', default, name=name, amount=amount)

    @staticmethod
    def game_already_running() -> str:
        return _t(
            'game_already_running',
            '🎮 В этом чате уже идет викторина.\nДля начала новой викторины сначала завершите текущую с помощью команды /stop'
        )

    @staticmethod
    def need_create_team_first() -> str:
        default = (
            'В этом чате пока нет команды.\n'
            'Напиши название команды ответом на это сообщение, чтобы зарегистрировать свою команду в общей рейтинге и начать игру!'
        )
        return _t('need_create_team_first', default)

    @staticmethod
    def team_created_success(team_name: str) -> str:
        return _t('team_created_success', 'Команда "{team_name}" успешно создана!\n', team_name=team_name)

    @staticmethod
    def team_create_error() -> str:
        return _t('team_create_error', 'Ошибка при создании команды!')

    @staticmethod
    def leaderboard_private_chat_error() -> str:
        default = "Команда /leaderboard работает только в групповых чатах с командами."
        return _t('leaderboard_private_chat_error', default)

    @staticmethod
    def leaderboard_api_error() -> str:
        default = "Не удалось получить рейтинг команд. Возможно, команда не зарегистрирована в этом чате."
        return _t('leaderboard_api_error', default)

    @staticmethod
    def leaderboard_message(entries: list, current_team_info: dict = None) -> str:
        """Формирует полное сообщение командного рейтинга"""
        lines = []
        
        # Заголовок
        header_default = "📈 Командный рейтинг — вот как сейчас обстоят дела:"
        header = _t('leaderboard_header', header_default)
        lines.append(header)
        lines.append('')
        
        # Топ команд
        medals = ['🥇', '🥈', '🥉']
        for idx, entry in enumerate(entries[:10], start=1):
            team_name = entry.get('username', 'Неизвестная команда')
            team_scores = entry.get('total_scores', 0)
            points_word = plural_points(team_scores)
            
            if idx <= 3:
                emoji = medals[idx-1]
            else:
                emoji = f"{idx}."
            
            entry_default = "{emoji} {team_name} — {team_scores} {points_word}"
            entry_text = _t('leaderboard_entry', entry_default, 
                          emoji=emoji, team_name=team_name, team_scores=team_scores, points_word=points_word)
            lines.append(entry_text)
        
        # Информация о текущей команде
        if current_team_info:
            lines.append('')
            team_name = "Ваша команда"
            team_scores = current_team_info.get('total_scores', 0)
            team_rank = current_team_info.get('position', '—')
            total_teams = current_team_info.get('total', 0)
            points_word = plural_points(team_scores)
            
            current_default = "🔹 {team_name} — {team_scores} {points_word} (место {team_rank} из {total_teams})"
            current_text = _t('leaderboard_current_team', current_default,
                            team_name=team_name, team_scores=team_scores, points_word=points_word,
                            team_rank=team_rank, total_teams=total_teams)
            lines.append(current_text)
        
        # Мотивирующий текст
        lines.append('')
        footer_default = (
            "🔥 Ещё пара удачных дней — и вы подниметесь выше!\n"
            "Продолжайте играть каждый день, чтобы занимать топовые места 💪\n\n"
            "🍻 А ещё лучше сыграть вживую — приходите на \"Квиз, плиз!\" в вашем городе!\n\n"
            "Живое общение, юмор и много вопросов — будет классно! Регистрация как обычно на quizplease.ru"
        )
        footer = _t('leaderboard_footer', footer_default)
        lines.append(footer)
        
        return '\n'.join(lines)

    @staticmethod
    def outdated_question() -> str:
        return _t('outdated_question', 'Этот вопрос уже неактуален!')

    @staticmethod
    def no_players_cannot_start() -> str:
        return _t('no_players_cannot_start', 'Игра не может начаться без участников!')

    @staticmethod
    def no_teams_cannot_start() -> str:
        return _t('no_teams_cannot_start', 'Игра не может начаться без команд!')

    @staticmethod
    def show_right_answer_only(right_answer: str, comment: str | None = None) -> str:
        comment_block = f"\n\nКомментарий: {comment}" if comment else ""
        return _t('show_right_answer_only', '✅ Правильный ответ: {right_answer}{comment_block}', 
                  right_answer=right_answer, comment_block=comment_block)

    @staticmethod
    def correct_inline_hint() -> str:
        return _t('correct_inline_hint', '✅ Правильно!')

    @staticmethod
    def incorrect_inline_hint() -> str:
        return _t('incorrect_inline_hint', '❌ Неправильно!')

    @staticmethod
    def team_quiz_finished_no_scores() -> str:
        return _t('team_quiz_finished_no_scores', '🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\nКоманда не набрала очков.')

    @staticmethod
    def team_quiz_finished_with_scores(team_name: str, score: int) -> str:
        default = (
            '🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\n'
            '🏆 Результаты раунда:\n'
            '👥 Команда "{team_name}": {score} баллов\n\n'
            '👇 Что дальше?\n\n'
            '🎮 Для начала новой игры используйте команду /menu'
        )
        return _t('team_quiz_finished_with_scores', default, team_name=team_name, score=score)

    @staticmethod
    def no_participants_game_finished() -> str:
        return _t('no_participants_game_finished', 'Игра окончена! Никто не участвовал.')

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
                result_lines.append(f"{prefix} {idx}. {handle}: {score} баллов")
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
        default = (
            "🏁 Викторина завершена! Спасибо за игру — это было мощно! ⚡️\n\n"
            "🏆 Результаты раунда:\n"
            "{results}\n"
            "👇 Что дальше?\n\n\n"
            "{stats_block}\n"
            "🎮 Для начала новой игры используйте команду /quiz"
        )
        return _t('dm_quiz_finished_full', default, results=results, stats_block=stats_block)

    @staticmethod
    def dm_text_wrong_attempt(attempts_remaining: int, right_answer: str, comment: str | None = None) -> str:
        if attempts_remaining == 1:
            return _t('dm_text_wrong_attempt_1', '❌ Неправильный ответ! Осталась 1 попытка')
        else:
            comment_block = f"\n\nКомментарий: {comment}" if comment else ""
            return _t(
                'dm_text_wrong_attempt_0',
                '❌ Неправильный ответ! Попыток больше нет.\n✅ Правильный ответ: {right_answer}{comment_block}\n\nПереходим к следующему вопросу...',
                right_answer=right_answer,
                comment_block=comment_block
            )

    @staticmethod
    def dm_registration_message(usernames: list[str], seconds_left: int) -> str:
        participants_text = ''
        for i, username in enumerate(usernames):
            participants_text += f"{i+1}. @{username}\n"
        default = (
            "📝 Регистрация на игру открыта!\n\n"
            "Если хочешь участвовать в этом раунде — просто нажми кнопку ниже.\n"
            "⏳ У тебя есть {seconds_left} секунд, чтобы вступить в игру! \n\n"
            "👥 Участники ({count}):\n{participants}\n"
            "Чем больше участников — тем интереснее баттл! 🎯\n"
            "👇 Жми, если готов(а) сражаться за баллы и славу! 🧠⚡️"
        )
        return _t(
            'dm_registration_message',
            default,
            count=max(1, len(usernames)),
            participants=participants_text,
            seconds_left=seconds_left,
        )

    @staticmethod
    def dm_select_theme_message() -> str:
        default = (
            "🎯 Мы начинаем игру...\n\n"
            "Впереди один раунд и шесть вопросов! За каждый правильный ответ — +1 балл в копилку.\n\n"
            "👇 Итак, тема для раунда:"
        )
        return _t('dm_select_theme_message', default)

    @staticmethod
    def theme_selected_start(name: str, amount: int) -> str:
        default = (
            "🎯 Категория \"{name}\" — принял!\n"
            "Будет жарко 🔥 — {amount} вопросов, 1 балл за каждый правильный ответ.\n\n"
            "Скоро начнём! 🧠⚡️"
        )
        return _t('theme_selected_start', default, name=name, amount=amount)

    @staticmethod
    def canceled() -> str:
        return _t('canceled', 'Игра отменена.')

    @staticmethod
    def stopped_quiz() -> str:
        return _t('stopped_quiz', '🛑 Викторина остановлена.\nДля начала новой используйте команду /quiz')

    @staticmethod
    def time_left_30() -> str:
        return _t('time_left_30', '⚠️ Осталось 30 секунд!')

    @staticmethod
    def time_left_10() -> str:
        return _t('time_left_10', '⚠️ Осталось 10 секунд!')

    @staticmethod
    def no_active_game() -> str:
        return _t('no_active_game', '🛑 В этом чате нет активной викторины.')

    @staticmethod
    def game_not_running() -> str:
        return _t('game_not_running', 'Игра не идет!')

    @staticmethod
    def captain_only_can_answer(username: str) -> str:
        default = f"Отвечать может только капитан команды! (@{username})"
        return _t('captain_only_can_answer_with_username', default, username=username)

    @staticmethod
    def already_answered() -> str:
        return _t('already_answered', 'Вы уже ответили на этот вопрос!')

    @staticmethod
    def only_registered_can_answer() -> str:
        return _t('only_registered_can_answer', 'Только зарегистрированные участники могут отвечать в этом раунде. Нажмите «Участвую» перед началом.')

    @staticmethod
    def need_answer_text_after_command() -> str:
        return _t('need_answer_text_after_command', 'Нужно написать ответ после команды. Пример: /otvet ваш_ответ')

    @staticmethod
    def theme_selection_solo() -> str:
        return _t('theme_selection_solo', '📚 Выберите категорию викторины (режим: 🤖 Соло):')

    @staticmethod
    def get_start_message(captain: str):
        default = (
            "👋 Всем привет! \n\n"
            "Я — официальный бот от Квиз, плиз! в Telegram 💥\n"
            "Могу устроить вам соревнование между собой и ежедневно задавать вам вопросы, как команде (да, всё как в настоящем Квиз, плиз!)\n\n"
            "Прежде чем мы начнём — давайте познакомимся!\n\n"
            "📝 {captain}, напиши название команды вашего чата в ответ на это сообщение — и погнали! 💥"
        )
        return _t('get_start_message', default, captain=captain)

    @staticmethod
    def solo_quiz_start_message():
        default = (
            "🎮 Погнали! Выберите режим, в котором хотите играть:\n\n"
            "🏆 Соревнование — каждый сам за себя! Кто наберёт больше всех очков, тот и чемпион 💪\n\n"
            "👥 Командный режим — квиз для всей команды! Каждый день — новая викторина: обсуждаете вместе, отвечаете вместе, побеждаете вместе!\n\n"
            "👇 Жмите кнопку и вперёд к знаниям! 🧠⚡️"
        )
        return _t('solo_quiz_start_message', default)


    @staticmethod
    def dm_quiz_start_message():
        default = (
            "🎯 Мы начинаем игру...\n\n"
            "Впереди один раунд и шесть вопросов! За каждый правильный ответ — +1 балл в копилку.\n\n"
            "👇 Итак, тема для раунда:"
        )
        return _t('dm_quiz_start_message', default)

    @staticmethod
    def dm_quiz_after_start_message(question_amount: int):
        default = (
            "🎯 Категория \"Обо всем\" — принял!\n"
            "Будет жарко 🔥 — {question_amount} вопросов, 1 балл за каждый правильный ответ.\n\n"
            "Скоро начнём! 🧠⚡️"
        )
        return _t('dm_quiz_after_start_message', default, question_amount=question_amount)

    @staticmethod
    def dm_quiz_question_result_message(
        right_answer: str,
        not_answered: list[str],
        wrong_answers: list[str],
        right_answers: list[str],
        totals: dict[str, int] | None = None,
        comment: str | None = None,
    ) -> str:
        blocks = []
        if right_answers:
            def _fmt_right(name: str) -> str:
                if totals and name in totals:
                    return f"{name}: +1 балл ({totals[name]})"
                return f"{name}: +1 балл"
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
        comment_block = f"\n\nКомментарий: {comment}" if comment else ""
        default = (
            "⌛️ Время вышло!\n\n"
            "✅ Правильный ответ: {right_answer}{comment_block}\n\n"
            "📊 Ответы участников:\n\n"
            "{details}"
        )
        return _t(
            'dm_quiz_question_result_message',
            default,
            right_answer=right_answer,
            details=details.rstrip(),
            comment_block=comment_block
        )

    @staticmethod
    def dm_quiz_question_template(text: str, timer: int, current_q_idx: int) -> str:
        default = (
            "Вопрос №{current_q_idx}\n"
            "🧠  {text}\n\n"
            "⏱ ТАЙМЕР: {timer} сек"
        )
        return _t('dm_quiz_question_template', default, text=text, timer=timer, current_q_idx=current_q_idx)

    @staticmethod
    def team_quiz_question_template(current_q_idx: int, username: str, text: str, timer: int) -> str:
        base = TextStatics.dm_quiz_question_template(text, timer, current_q_idx)
        default_suffix = (
            "\n💡 {username}, отвечай командами /otvet и /answer или просто ответь на это сообщение\n"
            "📝 У вас 2 попытки"
        )
        return base + _t('team_quiz_question_suffix', default_suffix, username=username)

    @staticmethod
    def team_quiz_question_right_answer(username: str, xp: int) -> str:
        return _t('team_quiz_question_right_answer', '🎉 Правильный ответ от {username}! +{xp} баллов всей команде', username=username, xp=xp)

    @staticmethod
    def team_start_message(team_name: str, username: str) -> str:
        default = (
            "🎮 Стартуем! \"Командная викторина #01\" — поехали!\n\n"
            "📝 Как играть:\n\n"
            "• Обсуждаете вопрос всей командой\n\n"
            "• Капитан ({username}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /otvet ваш_ответ\n\n"
            "• Баллы начисляются всей команде\n\n"
            "• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n\n"
            "Время пошло! ⏳ Удачи, команда! 🧠💪"
        )
        return _t('team_start_message', default, username=username, team_name=team_name)

    @staticmethod
    def team_prep_message(quiz_name: str, captain_username: str | None, seconds: int) -> str:
        captain = f"@{captain_username}" if captain_username and not captain_username.startswith('@') else (captain_username or '')
        default = (
            "🎮 Стартуем! \"{quiz_name}\" — поехали!\n\n"
            "📝 Как играть:\n\n"
            "• Обсуждаете вопрос всей командой\n\n"
            "• Капитан ({captain}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /ответ ваш_ответ\n\n"
            "• Баллы начисляются всей команде\n\n"
            "• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n\n"
            "⏳ Подготовка: {seconds} сек"
        )
        return _t('team_prep_message', default, quiz_name=quiz_name, captain=captain, seconds=seconds)

    @staticmethod
    def team_prep_message_started(quiz_name: str, captain_username: str | None) -> str:
        captain = f"@{captain_username}" if captain_username and not captain_username.startswith('@') else (captain_username or '')
        default = (
            "🎮 Стартуем! \"{quiz_name}\" — поехали!\n\n"
            "📝 Как играть:\n\n"
            "• Обсуждаете вопрос всей командой\n\n"
            "• Капитан ({captain}) сдаёт ваш ответ ответом на сообщение с вопросом или через команду /ответ ваш_ответ\n\n"
            "• Баллы начисляются всей команде\n\n"
            "• 2 балла за правильный ответ с первой попытки и 1 балл — со второй\n\n"
            "Время пошло! ⏳ Удачи, команда! 🧠💪"
        )
        return _t('team_prep_message_started', default, quiz_name=quiz_name, captain=captain)

    @staticmethod
    def team_quiz_question_wrong_answer(attempts_remaining: int, right_answer: str, comment: str | None = None) -> str:
        if attempts_remaining == 1:
            return _t('team_quiz_question_wrong_answer_1', '❌ Неправильный ответ!\n осталась 1 попытка')
        else:
            comment_block = f"\n\nКомментарий: {comment}" if comment else ""
            return _t(
                'team_quiz_question_wrong_answer_0',
                '❌ Неправильный ответ! Попыток больше нет.\n✅ Правильный ответ: {right_answer}{comment_block}\n\nПереходим к следующему вопросу...',
                right_answer=right_answer,
                comment_block=comment_block
            )

    @staticmethod
    def get_registration_dm_message(usernames: list[str]) -> str:
        participants_text = ''

        for i, username in enumerate(usernames):
            participants_text += f"{i+1}. @{username}\n"
        
        default = (
            "📝 Регистрация на игру открыта!\n\n"
            "👥 Участники ({count}):\n{participants}\n\n"
            "Если хочешь участвовать в этом раунде — просто нажми кнопку ниже.\n"
            "⏳ У тебя есть 60 секунд, чтобы вступить в игру! \n\n"
            "Чем больше участников — тем интереснее баттл! 🎯\n"
            "👇 Жми, если готов(а) сражаться за баллы и славу! 🧠⚡️"
        )
        return _t('get_registration_dm_message', default, count=len(usernames) or 1, participants=participants_text)

    @staticmethod
    def format_question_text(index: int, text: str, time_limit: int) -> str:
        # Формат вопроса как в примерах JSON
        return TextStatics.dm_quiz_question_template(text, time_limit, index).strip()
    
    @staticmethod
    def get_solo_intro(name: str, amount: int) -> str:
        default = (
            "Вы выбрали соло-игру «{name}». Всего вопросов: {amount}.\n"
            "Нажмите на кнопку ниже, чтобы начать игру."
        )
        return _t('get_solo_intro', default, name=name, amount=amount)

    @staticmethod
    def need_choose_city(team: str, captain: str) -> str:
        default = (
            "📍 {team} — отличное название! Теперь давайте определим, откуда вы.\n\n"
            "В каком городе вы играете?\n"
            "{captain} напиши название города в ответ на это сообщение. Можно без уточнений.\n\n"
            "Даже если вы играете онлайн — всё равно выберите свой город, чтобы попасть в локальные рейтинги 🏆"
        )
        return _t('need_choose_city', default, team=team, captain=captain)

    @staticmethod
    def city_not_found(captain: str) -> str:
        default = (
            "🤔 Кажется, я не нашёл такой город в списке. Может, была опечатка?\n\n"
            "{captain}, попробуй написать ещё раз, в ответ на это сообщение — или нажми 'Пропустить', если хочешь указать его позже.\n\n"
            "Но с городом будет интереснее — попадёте в локальные рейтинги! 🏆"
        )
        return _t('city_not_found', default, captain=captain)


    @staticmethod
    def get_help_message() -> str:
        default = (
            "ℹ️ Квиз, плиз! Мистер Бот\n\n"
            "Бот создан для того, чтобы вы играли в \"Квиз, плиз!\" прямо в Telegram — быстро, весело и с пользой для мозга 🧠⚡\n\n"
            "📌 Основные команды:\n\n"
            "🎮 /quiz — начать новую игру\n\n"
            "🛑 /stop — остановить текущую игру\n\n"
            "📊 /leaderboard — рейтинги игроков и команды\n\n"
            "❓ /help — это сообщение\n\n"
            "🧠 Как отвечать на вопросы:\n\n"
            "В соревновании или 1-1 с ботом — жмите кнопки с вариантами\n\n"
            "В командном режиме — отвечая на сообщение с вопросом\n\n"
            "✨ Как начисляется XP:\n\n"
            "Соревнование или 1-1 с ботом — 10 очков каждому за правильный ответ\n\n"
            "Командный режим — 2 балла команде за правильный ответ с первой попытки и 1 балл - со второй\n\n"
            "Бот продолжает развиваться — зовите друзей, играйте каждый день и прокачивайтесь вместе! 🚀"
        )
        return _t('get_help_message', default)

    @staticmethod
    def question_transition_delay() -> str:
        default = (
            "⏱️ Следующий вопрос появится через 3 секунды"
        )
        return _t('question_transition_delay', default)
