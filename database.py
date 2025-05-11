# database.py

import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name: str = 'fitness_bot.db'):
        self.db_name = db_name
        self._init_db()
        logger.info(f"DB initialized: {db_name}")

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_name)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                gender TEXT CHECK(gender IN ('М','Ж')),
                age INTEGER CHECK(age BETWEEN 10 AND 120),
                height REAL CHECK(height BETWEEN 100 AND 250),
                weight REAL CHECK(weight BETWEEN 30 AND 300),
                activity_level TEXT,
                bmr REAL,
                daily_calories REAL,
                registration_date TEXT,
                last_update_date TEXT
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                meal_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL REFERENCES users(user_id),
                food_name TEXT    NOT NULL,
                calories  REAL    NOT NULL,
                protein   REAL,
                fat       REAL,
                carbs     REAL,
                weight    REAL    NOT NULL,
                date      TEXT    NOT NULL
            )''')
            conn.commit()

    def save_user_data(self, d: Dict[str, Any]) -> None:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE user_id=?", (d['user_id'],))
            if cur.fetchone():
                cur.execute('''
                UPDATE users SET
                    username=?, first_name=?, last_name=?,
                    gender=?, age=?, height=?, weight=?, activity_level=?,
                    bmr=?, daily_calories=?, last_update_date=?
                WHERE user_id=?
                ''', (
                    d.get('username'), d['first_name'], d.get('last_name'),
                    d['gender'], d['age'], d['height'], d['weight'], d.get('activity_level'),
                    d['bmr'], d['daily_calories'], now, d['user_id']
                ))
                logger.info(f"User {d['user_id']} updated")
            else:
                cur.execute('''
                INSERT INTO users VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    d['user_id'], d.get('username'), d['first_name'], d.get('last_name'),
                    d['gender'], d['age'], d['height'], d['weight'], d.get('activity_level'),
                    d['bmr'], d['daily_calories'], d.get('registration_date', now), now
                ))
                logger.info(f"User {d['user_id']} inserted")
            conn.commit()

    def save_meal(self, user_id: int, meal: Dict[str, Any]) -> None:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
            INSERT INTO meals (
                user_id, food_name, calories, protein, fat, carbs, weight, date
            ) VALUES (?,?,?,?,?,?,?,?)
            ''', (
                user_id, meal['food_name'], meal['calories'],
                meal.get('protein'), meal.get('fat'), meal.get('carbs'),
                meal['weight'], now
            ))
            conn.commit()
            logger.info(f"Meal for {user_id} saved")

    def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))

    def get_daily_nutrition(self, user_id: int, date: Optional[str] = None) -> Dict[str, float]:
        target = date or datetime.now().strftime('%Y-%m-%d')
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT
                COALESCE(SUM(calories),0),
                COALESCE(SUM(protein),0),
                COALESCE(SUM(fat),0),
                COALESCE(SUM(carbs),0)
            FROM meals
            WHERE user_id=? AND date LIKE ?
            ''', (user_id, f"{target}%"))
            cal, p, f, c = cur.fetchone()
            return {"calories": cal, "protein": p, "fat": f, "carbs": c}

    def get_user_meals(self, user_id: int, limit: int = 10) -> list[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT food_name, calories, weight, date
            FROM meals
            WHERE user_id=?
            ORDER BY date DESC
            LIMIT ?
            ''', (user_id, limit))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
