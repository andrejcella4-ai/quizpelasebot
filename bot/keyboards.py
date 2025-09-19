from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def create_variant_keyboard(options: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Максимальная длина для кнопки в 2 колонки (примерно 20 символов)
    MAX_LENGTH_FOR_TWO_COLUMNS = 20
    
    for idx, opt in enumerate(options):
        builder.button(text=opt, callback_data=f'answer:{idx}')
    
    # Если есть кнопки с длинным текстом, размещаем их в одну колонку
    has_long_text = any(len(opt) > MAX_LENGTH_FOR_TWO_COLUMNS for opt in options)
    
    if has_long_text:
        builder.adjust(1)  # Все кнопки в одну колонку
    else:
        builder.adjust(2)  # По 2 кнопки в ряд
    
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню с выбором типа игры"""
    builder = InlineKeyboardBuilder()

    builder.button(text='🎯 Соревнование', callback_data='game:dm')
    builder.button(text='🤝 Командный', callback_data='game:team')

    builder.adjust(1)
    return builder.as_markup()


def private_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🤖 Соло', callback_data='game:solo')
    builder.adjust(1)
    return builder.as_markup()


def question_result_keyboard(include_finish: bool = True, is_last_question: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text='👍', callback_data='like')
    builder.button(text='👎', callback_data='dislike')

    if is_last_question:
        builder.button(text='Узнать результаты игры', callback_data='next_question')
    else:
        builder.button(text='➡️ Следующий вопрос', callback_data='next_question')

    if include_finish:
        builder.button(text='🏁 Завершить викторину', callback_data='finish_quiz')
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(2, 1)

    return builder.as_markup()


def quiz_registration_dm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='Участвовать', callback_data='reg:join')
    builder.button(text='🔙Отмена', callback_data='cancel')

    builder.adjust(1)
    return builder.as_markup()


def quiz_theme_keyboard(themes: list[tuple[str, int]], prefix: str = 'theme_id:') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for theme_name, theme_id in themes:
        builder.button(text=theme_name, callback_data=f'{prefix}{theme_id}')

    builder.button(text='🔙Назад', callback_data='back')

    builder.adjust(1)
    return builder.as_markup()


def team_plans_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in plans:
        text = p.get('quiz_name') or f"Квиз #{p.get('quiz')}"
        builder.button(text=text, callback_data=f"plan_team:{p.get('id')}")
    builder.button(text='🔙Назад', callback_data='back')
    builder.adjust(1)
    return builder.as_markup()


def team_start_game_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для начала командной игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text='🚀 Начать игру', callback_data='team:start_game')
    builder.button(text='❌ Отменить', callback_data='cancel:team')
    builder.adjust(1)
    return builder.as_markup()


def confirm_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения начала игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Начать игру', callback_data='game:solo:start')
    builder.adjust(1)
    return builder.as_markup()


def finish_quiz_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🏁 Завершить викторину', callback_data='finish_quiz')
    builder.adjust(1)
    return builder.as_markup()


def registration_dm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='✅ Участвовать', callback_data='reg:join')
    builder.button(text='▶️ Начать игру', callback_data='reg:end')
    builder.button(text='🔙 Отменить игру', callback_data='game:cancel')
    builder.adjust(1)
    return builder.as_markup()


def cancel_game_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🔙Отменить игру', callback_data='game:cancel')
    builder.adjust(1)
    return builder.as_markup()


def registration_team_keyboard(teams: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='Создать команду', callback_data='reg:create_team')
    for t in teams:
        builder.button(text=f'Вступить в {t}', callback_data=f'reg:join:{t}')
    builder.adjust(1)
    return builder.as_markup()


def team_registration_keyboard(team_name: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🚀 Начать игру', callback_data='team:start_early')
    builder.button(text='🛑 Отменить игру', callback_data='game:cancel')
    builder.adjust(1)
    return builder.as_markup()


def skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='Пропустить', callback_data='team:skip_city')
    builder.adjust(1)
    return builder.as_markup()


def notify_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🔕 Не напоминать', callback_data='notify:mute')
    builder.adjust(1)
    return builder.as_markup()


def new_chat_welcome_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для приветствия в новом чате"""
    builder = InlineKeyboardBuilder()
    builder.button(text='ℹ️ Помощь', callback_data='help')
    builder.adjust(1)
    return builder.as_markup()


def existing_chat_welcome_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для приветствия в существующем чате"""
    builder = InlineKeyboardBuilder()
    builder.button(text='🎮 Начать игру', callback_data='quizplease')
    builder.button(text='ℹ️ Помощь', callback_data='help')
    builder.adjust(1)
    return builder.as_markup()


def city_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора города"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Пропустить', callback_data='team:skip_city')
    builder.adjust(1)
    return builder.as_markup()


def game_finished_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для окончания игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text='🎯 Играть оффлайн', url='https://quizplease.ru/schedule?utm_source=tgbot&utm_medium=tgmessage&utm_campaign=tgmessages')
    builder.adjust(1)
    return builder.as_markup()


def no_planned_games_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура когда нет запланированных игр"""
    builder = InlineKeyboardBuilder()
    builder.button(text='🔔 Напомнить', callback_data='notify:enable')
    builder.button(text='🎯 Соревнование', callback_data='game:dm')
    builder.adjust(1)
    return builder.as_markup()
