import os
import aiohttp
from typing import Optional, Dict, List

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


async def team_game_end(team_id: int, points: int, system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(f'{BASE_URL}/team/game-end/{team_id}/', json={'points': points}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def player_update_notifications(telegram_id: int, notification_is_on: bool, system_token: str) -> dict:
    headers = {'Authorization': f'Token {system_token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.patch(f'{BASE_URL}/player/{telegram_id}/', json={'notification_is_on': notification_is_on}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def list_plan_team_quizzes() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BASE_URL}/game/plan-game/list/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def player_leaderboard(token: str) -> dict:
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/player/leaderboard/') as resp:
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

async def create_team(token: str, chat_username: str, name: str, player_id: int) -> dict:
    """Create a team and return its JSON representation."""
    headers = {'Authorization': f'Token {token}'}
    payload = {
        'name': name,
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
