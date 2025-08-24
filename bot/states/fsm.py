from aiogram.fsm.state import StatesGroup, State


class SoloGameStates(StatesGroup):
    WAITING_CONFIRM = State()
    WAITING_ANSWER = State()
    WAITING_NEXT = State()
    WAITING_THEME = State()


class TeamGameStates(StatesGroup):
    TEAM_CREATE_NAME = State()
    TEAM_CHOOSE_CITY = State()
