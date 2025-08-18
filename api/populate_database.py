#!/usr/bin/env python
"""
Скрипт для заполнения базы данных вопросами и тематическими квизами
"""

import os
import sys
import django
from django.db import transaction

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botapi.settings')
django.setup()

from main.models import Topic, Question, QuestionAnswer, Quiz


def create_topics():
    """Создание тем для вопросов"""
    topics_data = [
        {
            'name': 'История России',
            'description': 'Вопросы по истории России от древности до современности'
        },
        {
            'name': 'География',
            'description': 'Вопросы по географии мира, стран и регионов'
        },
        {
            'name': 'Наука и технологии',
            'description': 'Вопросы по физике, химии, биологии и современным технологиям'
        },
        {
            'name': 'Литература',
            'description': 'Вопросы по мировой и русской литературе'
        },
        {
            'name': 'Кино и музыка',
            'description': 'Вопросы по кинематографу, музыке и поп-культуре'
        },
        {
            'name': 'Спорт',
            'description': 'Вопросы по различным видам спорта и спортивным событиям'
        },
        {
            'name': 'Кулинария',
            'description': 'Вопросы о кухнях мира, продуктах и способах приготовления'
        },
        {
            'name': 'Искусство',
            'description': 'Вопросы по живописи, архитектуре и другим видам искусства'
        }
    ]
    
    topics = {}
    for topic_data in topics_data:
        topic, created = Topic.objects.get_or_create(
            name=topic_data['name'],
            defaults={'description': topic_data['description']}
        )
        topics[topic.name] = topic
        if created:
            print(f"Создана тема: {topic.name}")
    
    return topics


def create_questions(topics):
    """Создание вопросов с ответами"""
    questions_data = [
        # История России
        {
            'text': 'В каком году была основана Москва?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['История России'],
            'answers': [
                {'text': '1147', 'is_right': True},
                {'text': '1240', 'is_right': False},
                {'text': '1380', 'is_right': False},
                {'text': '1480', 'is_right': False}
            ]
        },
        {
            'text': 'Кто был первым императором России?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['История России'],
            'answers': [
                {'text': 'Петр I', 'is_right': True},
                {'text': 'Иван Грозный', 'is_right': False},
                {'text': 'Екатерина II', 'is_right': False},
                {'text': 'Александр I', 'is_right': False}
            ]
        },
        {
            'text': 'В каком году произошла Куликовская битва?',
            'question_type': 'variant',
            'difficulty': 3,
            'topics': ['История России'],
            'answers': [
                {'text': '1380', 'is_right': True},
                {'text': '1240', 'is_right': False},
                {'text': '1480', 'is_right': False},
                {'text': '1612', 'is_right': False}
            ]
        },
        
        # География
        {
            'text': 'Какая самая длинная река в мире?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['География'],
            'answers': [
                {'text': 'Нил', 'is_right': True},
                {'text': 'Амазонка', 'is_right': False},
                {'text': 'Янцзы', 'is_right': False},
                {'text': 'Миссисипи', 'is_right': False}
            ]
        },
        {
            'text': 'Столица Австралии?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['География'],
            'answers': [
                {'text': 'Канберра', 'is_right': True},
                {'text': 'Сидней', 'is_right': False},
                {'text': 'Мельбурн', 'is_right': False},
                {'text': 'Брисбен', 'is_right': False}
            ]
        },
        {
            'text': 'Сколько океанов на Земле?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['География'],
            'answers': [
                {'text': '5', 'is_right': True},
                {'text': '4', 'is_right': False},
                {'text': '6', 'is_right': False},
                {'text': '7', 'is_right': False}
            ]
        },
        
        # Наука и технологии
        {
            'text': 'Химический символ золота?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Наука и технологии'],
            'answers': [
                {'text': 'Au', 'is_right': True},
                {'text': 'Ag', 'is_right': False},
                {'text': 'Fe', 'is_right': False},
                {'text': 'Cu', 'is_right': False}
            ]
        },
        {
            'text': 'Кто изобрел телефон?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['Наука и технологии'],
            'answers': [
                {'text': 'Александр Белл', 'is_right': True},
                {'text': 'Томас Эдисон', 'is_right': False},
                {'text': 'Никола Тесла', 'is_right': False},
                {'text': 'Гульельмо Маркони', 'is_right': False}
            ]
        },
        {
            'text': 'Сколько костей в теле взрослого человека?',
            'question_type': 'variant',
            'difficulty': 3,
            'topics': ['Наука и технологии'],
            'answers': [
                {'text': '206', 'is_right': True},
                {'text': '200', 'is_right': False},
                {'text': '212', 'is_right': False},
                {'text': '198', 'is_right': False}
            ]
        },
        
        # Литература
        {
            'text': 'Кто написал "Войну и мир"?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Литература'],
            'answers': [
                {'text': 'Лев Толстой', 'is_right': True},
                {'text': 'Федор Достоевский', 'is_right': False},
                {'text': 'Александр Пушкин', 'is_right': False},
                {'text': 'Антон Чехов', 'is_right': False}
            ]
        },
        {
            'text': 'В каком году родился Уильям Шекспир?',
            'question_type': 'variant',
            'difficulty': 3,
            'topics': ['Литература'],
            'answers': [
                {'text': '1564', 'is_right': True},
                {'text': '1550', 'is_right': False},
                {'text': '1570', 'is_right': False},
                {'text': '1580', 'is_right': False}
            ]
        },
        
        # Кино и музыка
        {
            'text': 'В каком году вышел первый фильм "Звездные войны"?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['Кино и музыка'],
            'answers': [
                {'text': '1977', 'is_right': True},
                {'text': '1975', 'is_right': False},
                {'text': '1980', 'is_right': False},
                {'text': '1973', 'is_right': False}
            ]
        },
        {
            'text': 'Кто поет песню "Bohemian Rhapsody"?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['Кино и музыка'],
            'answers': [
                {'text': 'Queen', 'is_right': True},
                {'text': 'The Beatles', 'is_right': False},
                {'text': 'Led Zeppelin', 'is_right': False},
                {'text': 'Pink Floyd', 'is_right': False}
            ]
        },
        
        # Спорт
        {
            'text': 'В каком году состоялся первый чемпионат мира по футболу?',
            'question_type': 'variant',
            'difficulty': 3,
            'topics': ['Спорт'],
            'answers': [
                {'text': '1930', 'is_right': True},
                {'text': '1926', 'is_right': False},
                {'text': '1934', 'is_right': False},
                {'text': '1928', 'is_right': False}
            ]
        },
        {
            'text': 'Сколько игроков в баскетбольной команде на площадке?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Спорт'],
            'answers': [
                {'text': '5', 'is_right': True},
                {'text': '6', 'is_right': False},
                {'text': '4', 'is_right': False},
                {'text': '7', 'is_right': False}
            ]
        },
        
        # Кулинария
        {
            'text': 'Из какой страны родом пицца?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Кулинария'],
            'answers': [
                {'text': 'Италия', 'is_right': True},
                {'text': 'Испания', 'is_right': False},
                {'text': 'Греция', 'is_right': False},
                {'text': 'Франция', 'is_right': False}
            ]
        },
        {
            'text': 'Какой основной ингредиент суши?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Кулинария'],
            'answers': [
                {'text': 'Рис', 'is_right': True},
                {'text': 'Рыба', 'is_right': False},
                {'text': 'Водоросли', 'is_right': False},
                {'text': 'Овощи', 'is_right': False}
            ]
        },
        
        # Искусство
        {
            'text': 'Кто написал "Мону Лизу"?',
            'question_type': 'variant',
            'difficulty': 1,
            'topics': ['Искусство'],
            'answers': [
                {'text': 'Леонардо да Винчи', 'is_right': True},
                {'text': 'Микеланджело', 'is_right': False},
                {'text': 'Рафаэль', 'is_right': False},
                {'text': 'Боттичелли', 'is_right': False}
            ]
        },
        {
            'text': 'В каком стиле написана картина "Звездная ночь"?',
            'question_type': 'variant',
            'difficulty': 2,
            'topics': ['Искусство'],
            'answers': [
                {'text': 'Постимпрессионизм', 'is_right': True},
                {'text': 'Импрессионизм', 'is_right': False},
                {'text': 'Экспрессионизм', 'is_right': False},
                {'text': 'Кубизм', 'is_right': False}
            ]
        },
        
        # Текстовые вопросы
        {
            'text': 'Назовите столицу Японии',
            'question_type': 'text',
            'difficulty': 1,
            'topics': ['География'],
            'answers': [
                {'text': 'Токио', 'is_right': True}
            ]
        },
        {
            'text': 'Какой химический элемент обозначается символом H?',
            'question_type': 'text',
            'difficulty': 1,
            'topics': ['Наука и технологии'],
            'answers': [
                {'text': 'Водород', 'is_right': True}
            ]
        },
        {
            'text': 'Назовите автора романа "Преступление и наказание"',
            'question_type': 'text',
            'difficulty': 2,
            'topics': ['Литература'],
            'answers': [
                {'text': 'Достоевский', 'is_right': True},
                {'text': 'Федор Достоевский', 'is_right': True}
            ]
        }
        ,
        # Дополнительные текстовые вопросы для командного квиза (до 6 шт.)
        {
            'text': 'Назовите столицу Франции',
            'question_type': 'text',
            'difficulty': 1,
            'topics': ['География'],
            'answers': [
                {'text': 'Париж', 'is_right': True}
            ]
        },
        {
            'text': 'Сколько планет в Солнечной системе?',
            'question_type': 'text',
            'difficulty': 1,
            'topics': ['Наука и технологии'],
            'answers': [
                {'text': '8', 'is_right': True},
                {'text': 'восемь', 'is_right': True}
            ]
        },
        {
            'text': 'Кто написал поэму "Евгений Онегин"?',
            'question_type': 'text',
            'difficulty': 1,
            'topics': ['Литература'],
            'answers': [
                {'text': 'Александр Пушкин', 'is_right': True},
                {'text': 'Пушкин', 'is_right': True}
            ]
        }
    ]
    
    questions = []
    for q_data in questions_data:
        question, created = Question.objects.get_or_create(
            text=q_data['text'],
            defaults={
                'question_type': q_data['question_type'],
                'difficulty': q_data['difficulty']
            }
        )
        
        if created:
            # Добавляем темы
            for topic_name in q_data['topics']:
                question.topics.add(topics[topic_name])
            
            # Создаем ответы
            for answer_data in q_data['answers']:
                QuestionAnswer.objects.create(
                    text=answer_data['text'],
                    is_right=answer_data['is_right'],
                    question=question
                )
            
            questions.append(question)
            print(f"Создан вопрос: {question.text[:50]}...")
    
    return questions


def create_quizzes(questions):
    """Создание РОВНО трёх квизов под задачу:
    - 1 соло (5 вопросов, ВСЕ с вариантами)
    - 1 DM (6 вопросов, ВСЕ с вариантами)
    - 1 командный (6 вопросов, ВСЕ с открытым ответом)
    """

    quizzes = []

    # 1) Соло: 5 вопросов с вариантами
    solo_variant_qs = list(Question.objects.filter(question_type='variant')[:5])
    if solo_variant_qs and len(solo_variant_qs) >= 5:
        solo_quiz, created = Quiz.objects.get_or_create(
            name='Соло: Обо всем (варианты)',
            defaults={
                'description': '5 вопросов с вариантами ответов',
                'quiz_type': 'solo',
                'amount_questions': 5,
                'time_to_answer': 60,
            }
        )
        if created:
            for q in solo_variant_qs[:5]:
                solo_quiz.questions.add(q)
            quizzes.append(solo_quiz)
            print(f"Создан квиз: {solo_quiz.name} (5 вопросов)")
        else:
            quizzes.append(solo_quiz)

    # 2) DM: 6 вопросов с вариантами
    dm_variant_qs = list(Question.objects.filter(question_type='variant')[5:11])
    # если в срезе меньше 6, возьмем первые 6
    if len(dm_variant_qs) < 6:
        dm_variant_qs = list(Question.objects.filter(question_type='variant')[:6])
    if dm_variant_qs and len(dm_variant_qs) >= 6:
        dm_quiz, created = Quiz.objects.get_or_create(
            name='DM: Обо всем (варианты)',
            defaults={
                'description': '6 вопросов с вариантами ответов',
                'quiz_type': 'dm',
                'amount_questions': 6,
                'time_to_answer': 60,
            }
        )
        if created:
            for q in dm_variant_qs[:6]:
                dm_quiz.questions.add(q)
            quizzes.append(dm_quiz)
            print(f"Создан квиз: {dm_quiz.name} (6 вопросов)")
        else:
            quizzes.append(dm_quiz)

    # 3) Командный: 6 вопросов с открытым ответом
    team_text_qs = list(Question.objects.filter(question_type='text')[:6])
    if team_text_qs and len(team_text_qs) >= 6:
        team_quiz, created = Quiz.objects.get_or_create(
            name='Командный: Открытые вопросы',
            defaults={
                'description': '6 открытых вопросов для командного режима',
                'quiz_type': 'team',
                'amount_questions': 6,
                'time_to_answer': 120,
            }
        )
        if created:
            for q in team_text_qs[:6]:
                team_quiz.questions.add(q)
            quizzes.append(team_quiz)
            print(f"Создан квиз: {team_quiz.name} (6 вопросов)")
        else:
            quizzes.append(team_quiz)

    return quizzes


@transaction.atomic
def main():
    """Основная функция для заполнения базы данных"""
    print("Начинаем заполнение базы данных...")
    
    # Создаем темы
    print("\n1. Создание тем...")
    topics = create_topics()
    
    # Создаем вопросы
    print("\n2. Создание вопросов...")
    questions = create_questions(topics)
    
    # Создаем квизы
    print("\n3. Создание квизов...")
    quizzes = create_quizzes(questions)
    
    print(f"\n✅ Заполнение завершено!")
    print(f"📊 Статистика:")
    print(f"   - Тем: {len(topics)}")
    print(f"   - Вопросов: {len(questions)}")
    print(f"   - Квизов: {len(quizzes)}")
    
    # Выводим информацию о созданных квизах
    print(f"\n🎯 Созданные квизы:")
    for quiz in quizzes:
        print(f"   • {quiz.name} ({quiz.quiz_type}) - {quiz.questions.count()} вопросов")


if __name__ == '__main__':
    main() 