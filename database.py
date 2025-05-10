import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from config import Config
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name: str = 'fitness_bot.db'):
        """Инициализация базы данных"""
        self.db_name = db_name
        self._init_db()
        logger.info(f"Database initialized: {db_name}")

    def _init_db(self) -> None:
        """Создает таблицы, если они не существуют"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                gender TEXT CHECK(gender IN ('М', 'Ж')),
                age INTEGER CHECK(age BETWEEN 10 AND 120),
                height INTEGER CHECK(height BETWEEN 100 AND 250),
                weight REAL CHECK(weight BETWEEN 30 AND 300),
                activity_level TEXT,
                bmr REAL,
                daily_calories REAL,
                registration_date TEXT NOT NULL,
                last_update_date TEXT
            )
            ''')

            # Таблица приемов пищи
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                meal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                food_name TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL,
                fat REAL,
                carbs REAL,
                weight REAL NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            conn.commit()
            logger.debug("Database tables created/verified")

    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает соединение с базой данных"""
        return sqlite3.connect(self.db_name)

    def save_user_data(self, user_data: Dict[str, Any]) -> None:
        """
        Сохраняет или обновляет данные пользователя

        Args:
            user_data: {
                'user_id': int,
                'username': str,
                'first_name': str,
                'last_name': str,
                'gender': str,
                'age': int,
                'height': int,
                'weight': float,
                'activity_level': str,
                'bmr': float,
                'daily_calories': float,
                'registration_date': str
            }
        """
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем существование пользователя
            cursor.execute(
                'SELECT 1 FROM users WHERE user_id = ?',
                (user_data['user_id'],)
            )
            exists = cursor.fetchone()

            if exists:
                # Обновление данных
                cursor.execute('''
                UPDATE users SET
                    username = ?,
                    first_name = ?,
                    last_name = ?,
                    gender = ?,
                    age = ?,
                    height = ?,
                    weight = ?,
                    activity_level = ?,
                    bmr = ?,
                    daily_calories = ?,
                    last_update_date = ?
                WHERE user_id = ?
                ''', (
                    user_data.get('username'),
                    user_data['first_name'],
                    user_data.get('last_name'),
                    user_data['gender'],
                    user_data['age'],
                    user_data['height'],
                    user_data['weight'],
                    user_data['activity_level'],
                    user_data['bmr'],
                    user_data['daily_calories'],
                    current_date,
                    user_data['user_id']
                ))
                logger.info(f"User {user_data['user_id']} data updated")
            else:
                # Новая запись
                cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, last_name, gender, age,
                    height, weight, activity_level, bmr, daily_calories,
                    registration_date, last_update_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['user_id'],
                    user_data.get('username'),
                    user_data['first_name'],
                    user_data.get('last_name'),
                    user_data['gender'],
                    user_data['age'],
                    user_data['height'],
                    user_data['weight'],
                    user_data['activity_level'],
                    user_data['bmr'],
                    user_data['daily_calories'],
                    user_data.get('registration_date', current_date),
                    current_date
                ))
                logger.info(f"New user {user_data['user_id']} registered")

            conn.commit()

        # Получает данные пользователя

    def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM users WHERE user_id = ?
            ''', (user_id,))

            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()

            if row:
                user_data = dict(zip(columns, row))
                logger.debug(f"Retrieved data for user {user_id}")
                return user_data
            logger.debug(f"User {user_id} not found in database")
            return None

    def save_meal(self, user_id: int, food_data: Dict[str, Any]) -> None:
        """
        Сохраняет информацию о приеме пищи

        Args:
            user_id: ID пользователя
            food_data: {
                'food_name': str,
                'calories': float,
                'protein': float,
                'fat': float,
                'carbs': float,
                'weight': float
            }
        """
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO meals (
                user_id, food_name, calories, protein, fat, carbs, weight, date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                food_data['food_name'],
                food_data['calories'],
                food_data.get('protein'),
                food_data.get('fat'),
                food_data.get('carbs'),
                food_data['weight'],
                current_date
            ))
            conn.commit()
            logger.info(f"Meal saved for user {user_id}")

    def get_daily_nutrition(self, user_id: int, date: str = None) -> Dict[str, float]:
        """
        Получает суммарную информацию о питании за день

        Args:
            user_id: ID пользователя
            date: Дата в формате 'YYYY-MM-DD' (сегодня, если None)

        Returns:
            Словарь с суммарными значениями: {
                'calories': float,
                'protein': float,
                'fat': float,
                'carbs': float
            }
        """
        target_date = date or datetime.now().strftime('%Y-%m-%d')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT 
                SUM(calories) as calories,
                SUM(protein) as protein,
                SUM(fat) as fat,
                SUM(carbs) as carbs
            FROM meals 
            WHERE user_id = ? AND date LIKE ?
            ''', (user_id, f'{target_date}%'))

            result = cursor.fetchone()
            if result and result[0]:  # Проверяем, есть ли данные
                return {
                    'calories': result[0] or 0,
                    'protein': result[1] or 0,
                    'fat': result[2] or 0,
                    'carbs': result[3] or 0
                }
            return {
                'calories': 0,
                'protein': 0,
                'fat': 0,
                'carbs': 0
            }

    def get_user_meals(self, user_id: int, limit: int = 10) -> list:
        """Получает последние приемы пищи пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT food_name, calories, weight, date 
            FROM meals 
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ?
            ''', (user_id, limit))

            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
