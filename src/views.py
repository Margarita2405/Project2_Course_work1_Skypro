from datetime import datetime
from typing import Dict, Any, Optional
import logging
from src.utils import (
    get_time_greeting,
    load_user_settings,
    load_transactions,
    filter_transactions_by_date,
    process_card_date_with_spent,
    get_top_transactions,
    get_currency_rates,
    get_stock_prices,
)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Создание логгера с именем модуля
logger = logging.getLogger(__name__)


def main_view(input_datetime_str: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Главная функция, принимающую на вход строку с датой и временем в формате
    YYYY-MM-DD HH:MM:SS и возвращающая JSON-ответ."""
    try:
        # Извлекаем входную дату
        input_datetime = datetime.strptime(input_datetime_str, "%Y-%m-%d %H:%M:%S")

        # Получаем приветствие
        greeting = get_time_greeting(input_datetime)
        logger.info(f"Приветствие: {greeting} для времени {input_datetime_str}")

        # Загружаем пользовательские настройки
        settings = load_user_settings(file_path)
        logger.info(f"Загружены настройки: {settings}")

        # Загружаем транзакции
        df = load_transactions(file_path)

        # Фильтруем транзакции
        filtered_df = filter_transactions_by_date(df, input_datetime)

        # Проверяем, есть ли данные после фильтрации
        if filtered_df.empty:
            logger.warning("Нет транзакций за указанный период")
            return {
                "greeting": greeting,
                "cards": [],
                "top_transactions": [],
                "currency_rates": [],
                "stock_prices": [],
                "message": "Нет транзакций за указанный период",
            }

        # Обрабатываем данные по картам
        cards = process_card_date_with_spent(filtered_df)
        logger.info(f"Обработано {len(cards)} карт")

        # Получаем топ-транзакций
        top_transactions = get_top_transactions(filtered_df, 5)
        logger.info(f"Получено {len(top_transactions)} топ транзакций")

        # Получаем курс валют
        currency_rates = get_currency_rates(currencies=settings.get("user_currencies", ["USD", "EUR"]))
        logger.info(f"Получено {len(currency_rates)} курсов валют")

        # Получаем стоимость акций
        stock_prices = get_stock_prices(stocks=settings.get("user_stocks", ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]))
        logger.info(f"Получено {len(stock_prices)} стоимостей акций")

        # Формируем ответ
        response = {
            "greeting": greeting,
            "cards": cards,
            "top_transactions": top_transactions,
            "currency_rates": currency_rates,
            "stock_prices": stock_prices,
        }

        logger.info(f"Успешно сформирован ответ для даты {input_datetime_str}")
        return response

    except ValueError as e:
        logger.error(f"Ошибка извлечения даты {input_datetime_str}: {e}")
        return {"error": "Неверный формат даты. Используйте YYYY-MM-DD HH:MM:SS"}

    except Exception as e:
        logger.error(f"Ошибка при обработке запросов: {e}")
        return {"error": f"Внутренняя ошибка сервера: {str(e)}"}
