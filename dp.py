import sqlite3


class Database:
    def __init__(self, db_name='users_data.db'):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                gender TEXT,
                age INTEGER,
                height INTEGER,
                weight REAL,
                activity_level TEXT,
                bmr REAL,
                daily_calories REAL,
                registration_date TEXT
            )
            ''')
            conn.commit()

    def _get_connection(self):
        """Возвращает соединение с базой данных"""
        return sqlite3.connect(self.db_name)

    def save_user_data(self, user_data: dict):
        """
        Сохраняет или обновляет данные пользователя

        :param user_data: Словарь с данными пользователя
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем существование пользователя
            cursor.execute(
                'SELECT user_id FROM users WHERE user_id = ?',
                (user_data['user_id'],)
            )
            exists = cursor.fetchone()

            if exists:
                # Обновляем данные
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
                    registration_date = ?
                WHERE user_id = ?
                ''', (
                    user_data['username'],
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data['gender'],
                    user_data['age'],
                    user_data['height'],
                    user_data['weight'],
                    user_data['activity_level'],
                    user_data['bmr'],
                    user_data['daily_calories'],
                    user_data['registration_date'],
                    user_data['user_id']
                ))
            else:
                # Вставляем новые данные
                cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, last_name, gender, age, 
                    height, weight, activity_level, bmr, daily_calories, registration_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['user_id'],
                    user_data['username'],
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data['gender'],
                    user_data['age'],
                    user_data['height'],
                    user_data['weight'],
                    user_data['activity_level'],
                    user_data['bmr'],
                    user_data['daily_calories'],
                    user_data['registration_date']
                ))

            conn.commit()

    def get_user_data(self, user_id: int) -> dict:
        """
        Получает данные пользователя по ID

        :param user_id: ID пользователя в Telegram
        :return: Словарь с данными пользователя или None, если не найден
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM users WHERE user_id = ?
            ''', (user_id,))

            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()

            if row:
                return dict(zip(columns, row))
            return None
