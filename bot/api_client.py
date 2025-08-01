import os
import aiohttp


BASE_URL = os.getenv('API_URL', 'http://localhost:8000')


async def auth_player(
    telegram_id: int,
    first_name: str,
    last_name: str,
    username: str = None,
    phone: str = None,
    lang_code: str = None
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


async def get_quiz_info(quiz_type: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BASE_URL}/quiz/game/{quiz_type}/') as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_questions(token: str, quiz_id: int) -> dict:
    headers = {'Authorization': f'Token {token}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{BASE_URL}/question/list/', params={'quiz_id': quiz_id}) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return {"questions": data}
