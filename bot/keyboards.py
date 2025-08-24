from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def create_variant_keyboard(options: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for idx, opt in enumerate(options):
        builder.button(text=opt, callback_data=f'answer:{idx}')

    builder.adjust(2)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню с выбором типа игры"""
    builder = InlineKeyboardBuilder()

    builder.button(text='🏆 Соревнование', callback_data='game:dm')
    builder.button(text='👥 Кооперация', callback_data='game:team')

    builder.adjust(1)
    return builder.as_markup()


def private_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🤖 Соло', callback_data='game:solo')
    builder.adjust(1)
    return builder.as_markup()


def question_result_keyboard(include_finish: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text='👍', callback_data='like')
    builder.button(text='👎', callback_data='dislike')
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
    builder.button(text='✅Участвовать', callback_data='reg:join')
    builder.button(text='▶️Начать викторину', callback_data='reg:end')
    builder.button(text='🔙Отменить игру', callback_data='game:cancel')
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
