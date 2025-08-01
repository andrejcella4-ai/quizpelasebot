from aiogram.fsm.state import StatesGroup, State


class SoloGameStates(StatesGroup):
    WAITING_CONFIRM = State()
    WAITING_ANSWER = State()


class TeamGameStates(StatesGroup):
    TEAM_CREATE_NAME = State()
