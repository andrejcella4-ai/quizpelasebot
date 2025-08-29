import os
import aiohttp
from typing import Optional, Dict, List
import requests


BASE_URL = os.getenv('API_URL', 'http://localhost:8000')


async def auth_player(
    telegram_id: int,
    first_name: str,
    last_name: str,
    username: str | None = None,
    phone: str | None = None,
    lang_code: str | None = None,
) -> str:
    payload = {
        'telegram_id': telegram_id,
        'first_name': first_name,
        'last_name': last_name,
        'username': username,
        'phone': phone,
        'lang_code': lang_code,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{BASE_URL}/auth/player/', json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data['token']


async def player_game_end(username: str | None, points: int, system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        payload = {'username': username, 'points': points}
        async with session.post(f'{BASE_URL}/player/game-end/', json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def players_game_end_bulk(results: list[dict], system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/player/game-end/', json={'results': results}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def team_game_end(team_id: int, points: int, plan_team_quiz_id: int, system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/team/game-end/{team_id}/', json={'points': points, 'plan_team_quiz_id': plan_team_quiz_id}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def player_update_notifications(telegram_id: int, notification_is_on: bool, system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.patch(f'{BASE_URL}/player/{telegram_id}/', json={'notification_is_on': notification_is_on}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def list_plan_team_quizzes(chat_username: str, token: str) -> list[dict]:
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/game/plan-game/list/{chat_username}/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def player_leaderboard(token: str, usernames: List[str] = None, current_user_username: str | None = None) -> dict:
    """Получить лидерборд игроков. Если usernames указан, то только среди этих пользователей."""
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        if usernames and current_user_username:
            # POST запрос с списком username
            payload = {'usernames': usernames, 'current_user_username': current_user_username}
            async with session.post(f'{BASE_URL}/player/leaderboard/', json=payload) as resp:
                resp.raise_for_status()
                return await resp.json()
        else:
            # GET запрос для общего лидерборда
            async with session.get(f'{BASE_URL}/player/leaderboard/') as resp:
                resp.raise_for_status()
                return await resp.json()


async def team_leaderboard(token: str, chat_username: str) -> dict:
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/team/leaderboard/{chat_username}/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_notify_list() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BASE_URL}/player/notify-list/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_quiz_info(quiz_type: str, quiz_id: int | None = None) -> dict:
    params = {}
    if quiz_id is not None:
        params["quiz_id"] = quiz_id
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BASE_URL}/quiz/game/{quiz_type}/', params=params) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_questions(token: str, quiz_id: int) -> dict:
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/question/list/', params={'quiz_id': quiz_id}) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return {"questions": data}


async def get_quiz_list(quiz_type: str) -> List[Dict]:
    """Получить список всех квизов заданного типа."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BASE_URL}/quiz/list/{quiz_type}/') as resp:
            resp.raise_for_status()
            data = await resp.json()
            # ожидаем список словарей с полями id, name, description...
            return data


# --- Team -----------------------------------------------------------

async def create_team(token: str, chat_username: str, name: str, player_id: int, city: str | None = None) -> dict:
    """Create a team and return its JSON representation."""
    headers = {'Authorization': f'Token {token}'}
    payload = {
        'name': name,
        'city': city,
        'chat_username': chat_username,
        'player_id': player_id,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/teams/', json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_team(token: str, chat_username: str) -> Optional[Dict]:
    """Return team JSON or None if not exists."""
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/team/{chat_username}/') as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json()


async def get_players_total_points(usernames: list[str], system_token: str) -> list[dict]:
    """Возвращает список {username, total_xp} по списку usernames."""
    headers = {'Authorization': f'Token {system_token}'}
    payload = {'usernames': usernames}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/player/list/total-points/', json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


def get_bot_texts(system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    response = requests.get(f'{BASE_URL}/bot-texts/', headers=headers)
    response.raise_for_status()

    return response.json()


async def get_rotated_questions_solo(system_token: str, telegram_id: int, size: int, time_to_answer: int = 10) -> dict:
    """Получить вопросы для solo игры с ротацией"""
    headers = {'Authorization': f'Token {system_token}'}
    payload = {
        'use_type': 'solo',
        'context_id': telegram_id,
        'size': size,
        'time_to_answer': time_to_answer
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/question/rotated/', json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_rotated_questions_dm(system_token: str, chat_id: int, size: int, time_to_answer: int = 10) -> dict:
    """Получить вопросы для dm игры с ротацией"""
    headers = {'Authorization': f'Token {system_token}'}
    payload = {
        'use_type': 'dm',
        'context_id': chat_id,
        'size': size,
        'time_to_answer': time_to_answer
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/question/rotated/', json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_configs(system_token: str) -> list[dict]:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/configs/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def question_like(question_id: int, token: str) -> dict:
    """Поставить лайк вопросу"""
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/question/{question_id}/like/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def question_dislike(question_id: int, token: str) -> dict:
    """Поставить дизлайк вопросу"""
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/question/{question_id}/dislike/') as resp:
            resp.raise_for_status()
            return await resp.json()
