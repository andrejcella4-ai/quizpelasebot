from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def create_variant_keyboard(options: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for opt in options:
        builder.button(text=opt, callback_data=f'answer:{opt}')

    builder.adjust(2)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню с выбором типа игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Соло', callback_data='game:solo')
    builder.button(text='Каждый сам за себя', callback_data='game:dm')
    builder.button(text='Командная игра', callback_data='game:team')
    builder.adjust(1)
    return builder.as_markup()


def confirm_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения начала игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Начать игру', callback_data='game:solo:start')
    builder.adjust(1)
    return builder.as_markup()


def registration_dm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='Записаться', callback_data='reg:join')
    builder.adjust(1)
    return builder.as_markup()


def registration_team_keyboard(teams: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='Создать команду', callback_data='reg:create_team')
    for t in teams:
        builder.button(text=f'Вступить в {t}', callback_data=f'reg:join:{t}')
    builder.adjust(1)
    return builder.as_markup()
