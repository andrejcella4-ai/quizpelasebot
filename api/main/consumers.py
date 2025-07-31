import asyncio
import random
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Quiz, Question, QuestionAnswer, TelegramPlayer
from django.core.cache import cache


class QuizConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        # Extract path parameters
        self.game_type = self.scope['url_route']['kwargs']['game_type']
        self.chat_username = self.scope['url_route']['kwargs']['chat_username']
        self.quiz_id = int(self.scope['url_route']['kwargs']['quiz_id'])

        self.group_name = f"quiz_{self.game_type}_{self.chat_username}_{self.quiz_id}"

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # In bot-managed connection we initialise containers
        self.players = set()
        self.teams = {}  # team_name -> list[str]
        self.captains = {}
        self.scores = {}
        self.answers_received = set()
        self.timer_task = None
        # Mapping when team mode: username -> team
        self.player_team = {}

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        event = content.get('event')
        if event == 'start_game':
            await self.start_game()
        elif event == 'answer_question':
            await self.handle_answer(content)
        elif event == 'registration_join':
            await self.registration_join(content)

    # Handlers for group events
    async def player_join(self, event):
        await self.send_json({'event': 'player_join', 'data': event['player']})

    async def game_start(self, event):
        await self.send_json({'event': 'game_start', 'data': {}})

    async def game_next_question(self, event):
        await self.send_json({
            'event': 'next_question',
            'data': {
                'new_question': event['new_question'],
                'previous_question': event.get('previous_question'),
                'leaderboard': event['leaderboard'],
            }
        })

    async def game_end(self, event):
        await self.send_json({'event': 'game_end', 'data': {'leaderboard': event['leaderboard']}})

    # Core game logic
    async def start_game(self):
        # Load quiz settings
        self.quiz = await sync_to_async(Quiz.objects.get)(id=self.quiz_id)
        # Gather all questions and pick random subset
        all_questions = await sync_to_async(lambda: list(Question.objects.all()))()
        random.shuffle(all_questions)
        self.questions = all_questions[:self.quiz.amount_questions]
        self.current_index = 0
        if self.game_type == 'team':
            # one score per team
            self.scores = {team: 0 for team in self.teams}
        else:
            self.scores = {u: 0 for u in self.players}
        self.answers_received = set()
        self.timer_task = None

        # Notify clients game has started
        await self.channel_layer.group_send(self.group_name, {'type': 'game.start'})
        # Send first question
        await self.send_next_question(previous_question=None)

    async def send_next_question(self, previous_question):
        # If quiz finished
        if self.current_index >= len(self.questions):
            leaderboard = [{'player': u, 'score': s} for u, s in self.scores.items()]
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'game.end', 'leaderboard': leaderboard}
            )
            return

        q = self.questions[self.current_index]
        # Build question payload
        if q.question_type == Question.QuestionTypeChoices.VARIANT:
            answers = await sync_to_async(
                lambda: list(QuestionAnswer.objects.filter(question=q).values('id', 'text'))
            )()
        else:
            answers = []

        new_q = {
            'id': q.id,
            'text': q.text,
            'type': q.question_type,
            'answers': answers,
            'time_to_answer': self.quiz.time_to_answer,
            'index': self.current_index + 1,
        }
        prev_data = None
        if previous_question:
            prev_data = {'id': previous_question.id, 'text': previous_question.text}

        leaderboard = [{'player': u, 'score': s} for u, s in self.scores.items()]

        # Broadcast next question to group
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'game.next_question',
                'new_question': new_q,
                'previous_question': prev_data,
                'leaderboard': leaderboard
            }
        )
        # Reset answers and start timer
        self.answers_received = set()
        self.timer_task = asyncio.create_task(self.question_timer())

    async def question_timer(self):
        try:
            await asyncio.sleep(self.quiz.time_to_answer)
            # Move to next question
            self.current_index += 1
            await self.send_next_question(previous_question=self.questions[self.current_index - 1])
        except asyncio.CancelledError:
            pass

    async def handle_answer(self, data):
        username = data.get('username')
        is_right = data.get('is_right', False)

        if username in self.answers_received:
            return

        # Validate for team mode: only captain's answers count
        if self.game_type == 'team':
            team_name = self.player_team.get(username)
            if not team_name or self.captains.get(team_name) != username:
                # Only captains' answers are accepted
                return

            if is_right:
                self.scores[team_name] = self.scores.get(team_name, 0) + 1
        else:
            if is_right:
                self.scores[username] = self.scores.get(username, 0) + 1

        self.answers_received.add(username)

        participants_count = len(self.teams) if self.game_type == 'team' else len(self.players)

        if len(self.answers_received) == participants_count:
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            self.current_index += 1
            await self.send_next_question(previous_question=self.questions[self.current_index - 1])

    async def registration_join(self, data):
        username = data.get('username')
        team_name = data.get('team_name')

        if self.game_type == 'team' and team_name:
            if team_name not in self.teams:
                self.teams[team_name] = []
            if username not in self.teams[team_name]:
                self.teams[team_name].append(username)
                self.player_team[username] = team_name
                if team_name not in self.captains:
                    self.captains[team_name] = username  # first member is captain
        else:
            self.players.add(username)

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'registration.update',
                'players': list(self.players),
                'teams': self.teams,
            },
        )

    # old Redis-based team management removed
