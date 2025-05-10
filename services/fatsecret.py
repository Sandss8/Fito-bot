import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


class FatSecretAPI:
    @staticmethod
    def get_access_token():
        """Получение токена доступа"""
        url = "https://oauth.fatsecret.com/connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "scope": "basic",
            "client_id": Config.FATSECRET_CLIENT_ID,
            "client_secret": Config.FATSECRET_CLIENT_SECRET
        }

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            return token_data["access_token"]
        except Exception as e:
            logger.error(f"FatSecret API error: {e}")
            raise

    @staticmethod
    def search_food(query):
        """Поиск продуктов питания"""
        token = FatSecretAPI.get_access_token()
        url = "https://platform.fatsecret.com/rest/server.api"
        params = {
            "method": "foods.search",
            "search_expression": query,
            "format": "json"
        }
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Food search error: {e}")
            raise
