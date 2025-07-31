

class TextStatics:
    game_started_answer = 'Игра уже начата. Сначала завершите теущую игру, овтетив на все вопросы или завершите её досрочно, командой /end_game\n\n'

    @staticmethod
    def get_single_game_answer(right_answers: int, wrong_answers: int) -> str:
        return f"Игра окончена! Правильных ответов: {right_answers}, Неправильных: {wrong_answers}"

    @staticmethod
    def game_started_answer() -> str:
        return 'Игра уже начата. Сначала завершите предыдущую игру командой /end_game'

    @staticmethod
    def get_start_menu() -> str:
        return "Выберите тип игры:"

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
    def format_question_text(index: int, text: str, time_limit: int) -> str:
        return f"<b>Вопрос {index+1} (Время: {time_limit} сек):</b> {text}"
    
    @staticmethod
    def get_solo_intro(name: str, amount: int) -> str:
        return (
            f"Вы выбрали соло-игру «{name}». Всего вопросов: {amount}.\n"
            "Нажмите на кнопку ниже, чтобы начать игру."
        )
