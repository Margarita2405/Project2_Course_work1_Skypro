import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Union, Optional
import pandas as pd
import requests
import os
from requests import JSONDecodeError
from requests.exceptions import RequestException, Timeout
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Создание логгера с именем модуля
logger = logging.getLogger(__name__)

# Получение API-ключа из переменных окружения
EXCHANGERATES_API_KEY = os.getenv("EXCHANGERATES_API_KEY")
EXCHANGERATES_URL = "https://api.apilayer.com/exchangerates_data/convert"
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
TWELVE_DATA_PRICE_URL = "https://api.twelvedata.com/price"


def get_time_greeting(input_datetime: datetime) -> str:
    """Функция определяет приветствие в зависимости от текущего времени суток и возвращает строку с приветствием."""
    # Извлекаем текущий час
    hour = input_datetime.hour

    if 5 <= hour < 12:
        return "Доброе утро"
    elif 12 <= hour < 17:
        return "Добрый день"
    elif 17 <= hour < 23:
        return "Добрый вечер"
    else:
        return "Доброй ночи"


def load_transactions(file_path: Optional[str] = None) -> pd.DataFrame:
    """Функция принимает путь к Excel-файлу, загружает транзакции и возвращает DataFrame."""
    # Если путь не передан, формируем путь к файлу в папке data
    if file_path is None:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(current_dir, "data", "operations.xlsx")

    try:
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл {file_path} не найден")

        # Читаем Excel-файл
        df = pd.read_excel(file_path, sheet_name="Отчет по операциям")

        # Преобразуем дату в datetime
        if "Дата операции" in df.columns:
            df["Дата операции"] = pd.to_datetime(df["Дата операции"], dayfirst=True)

        logger.info(f"Успешно загружено: {len(df)} транзакций")
        return df
    except Exception:
        logger.error("Ошибка при загрузке транзакций")
        raise


def filter_transactions_by_date(df: pd.DataFrame, end_date: datetime) -> pd.DataFrame:
    """Функция фильтрует транзакции с начала месяца по указанную дату и возвращает отфильтрованный DataFrame."""

    # Определяем начало месяца
    start_of_month = end_date.replace(day=1, hour=0, minute=0, second=0)

    # Фильтруем транзакции
    filtered_df = df[(df["Дата операции"] >= start_of_month) & (df["Дата операции"] <= end_date)]

    logger.info(f"Отфильтровано: {len(filtered_df)} транзакций с {start_of_month.date()} по {end_date.date()}")
    return filtered_df


def process_card_date_with_spent(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Функция обрабатывает данные по картам: последние 4 цифры карты, общая сумма расходов, кешбэк.
    Принимает DataFrame и возвращает список словарей с данными по картам."""
    # Создаем пустой новый список для данных по картам
    cards_data: List[Dict[str, Any]] = []

    # Проверяем, что есть столбец "Номер карты"
    card_column = None
    for col in ["Номер карты"]:
        if col in df.columns:
            card_column = col
            break

    if not card_column:
        logger.warning("Столбец с номером карты не найден")
        return cards_data

    # Проверяем, что есть столбец "Сумма операции"
    amount_column = None
    for col in ["Сумма операции", "Сумма платежа", "Сумма операции с округлением"]:
        if col in df.columns:
            amount_column = col
            break

    if not amount_column:
        logger.warning("Столбец с суммой не найден")
        return cards_data

    # Группируем по последним 4 цифрам карты
    df["last_digits"] = df[card_column].astype(str).str.replace("*", "").str[-4:]

    # Группируем данные по картам
    for card, group in df.groupby("last_digits"):
        # Суммируем только отрицательные значения (расходы)
        # Фильтруем отрицательные значения (расходы)
        negative_values = group[group[amount_column] < 0][amount_column]

        if negative_values.empty:
            total_spent = 0.0
        else:
            total_spent = abs(negative_values.sum())

        # Рассчитываем кешбэк (1 рубль на каждые 100 рублей)
        cashback = round(total_spent / 100, 2)

        cards_data.append({"last_digits": card, "total_spent": round(total_spent, 2), "cashback": cashback})
    return cards_data


def get_top_transactions(df: pd.DataFrame, top_n: int) -> List[Dict[str, Any]]:
    """Функция принимает DataFrame и возвращает список словарей с топ-n транзакциями по сумме платежа."""
    # Логируем начало функции
    logger.info(f"Поиск топ-{top_n} транзакций из {len(df)} записей")

    # Создаем пустой новый список для топ транзакций
    top_transactions: List[Dict[str, Any]] = []

    # Проверяем, что есть столбец "Дата платежа"
    date_column: Optional[str] = None
    for col in ["Дата операции"]:
        if col in df.columns:
            date_column = col
            break

    # Проверяем, что есть столбец "Сумма операции"
    amount_column: Optional[str] = None
    for col in ["Сумма операции", "Сумма платежа", "Сумма операции с округлением"]:
        if col in df.columns:
            amount_column = col
            break

    # Проверяем, что есть столбец "Категория"
    category_column: Optional[str] = None
    for col in ["Категория"]:
        if col in df.columns:
            category_column = col
            break

    # Проверяем, что есть столбец "Описание"
    description_column: Optional[str] = None
    for col in ["Описание"]:
        if col in df.columns:
            description_column = col
            break

    # Проверяем наличие обязательных столбцов
    if date_column is None or amount_column is None:
        logger.warning(
            f"Не все необходимые  столбцы найдены. Дата операции: {date_column}, Сумма операцмм {amount_column}"
        )
        logger.warning(f"Доступные столбцы {list(df.columns)}")
        return top_transactions

    # Создаем копию и преобразуем типы данных
    sorted_df = df.copy()

    sorted_df["abs_amount"] = sorted_df[amount_column].abs()
    sorted_df = sorted_df.sort_values("abs_amount", ascending=False).head(top_n)

    for index, row in sorted_df.iterrows():
        # Форматируем дату в строку
        date_value = row[date_column]
        try:
            date_str = date_value.strftime("%d.%m.%Y")
        except AttributeError:
            date_str = str(date_value)
        except Exception:
            date_str = "Дата не указана"

        # Для суммы убеждаемся, что это число
        amount_value = row[amount_column]
        try:
            amount = float(amount_value)
        except (ValueError, TypeError):
            amount = 0.0

        transaction = {
            "date": date_str,
            "amount": round(amount, 2),
            "category": str(row.get(category_column, "Не указана")) if category_column else "Не указана",
            "description": str(row.get(description_column, "")) if description_column else "",
        }
        top_transactions.append(transaction)

    return top_transactions


def get_currency_rates(currencies: List[str], base_currency: str = "RUB") -> List[Dict[str, Any]]:
    """Функция получает актуальные курсы валют относительно базовой валюты, по умолчанию "RUB" (российский рубль)
    через Exchange Rates Data API (apilayer.com)."""
    # Создаем новый пустой список для курсов валют
    currency_rates: List[Dict[str, Any]] = []

    # Проверяем наличие API-ключа
    if not EXCHANGERATES_API_KEY:
        logger.error("API-ключ для сервиса валют не задан. Проверьте свой .env файл.")
        return currency_rates

    logger.info(f"Запрос курсов для валют: {currencies} к базовой валюте {base_currency}")

    for currency in currencies:
        try:
            # Создаем заголовки запроса с API-ключом
            headers: Dict[str, str] = {"apikey": EXCHANGERATES_API_KEY}

            # Параметры запроса к API
            params: Dict[str, Union[str, float]] = {
                "from": currency,  # Валюта, которую конвертируем
                "to": base_currency,  # В какую валюту конвертируем
                "amount": 1,  # Курс за 1 единицу
            }

            # Выполнение GET запроса к API с таймаутом
            response = requests.get(EXCHANGERATES_URL, headers=headers, params=params, timeout=10)

            # Проверка статуса ответа
            response.raise_for_status()

            # Получение данных из ответа API в формате JSON
            data: Dict[str, Any] = response.json()

            # Проверка успешности запроса к API по полю success
            if data.get("success"):
                rate = data.get("result")
                if rate:
                    # Округляем до 4 знаков, так как курс 1 USD в RUB будет ~ 0,0010
                    currency_rates.append({"currency": currency, "rate": round(rate, 4)})
                    logger.debug(f"Получен курс {currency}: 1 {currency} = {rate} {base_currency}")
                else:
                    logger.warning(f"В ответе API для валюты {currency} отсутствует поле 'result'")
            else:
                # Обработка ошибки API
                error_info = data.get("error", {})
                logger.error(f"Ошибка API для валюты {currency}: {error_info.get('info', 'Unknown error')}")

        except Timeout:
            # Обработка ошибки времени ожидания запроса
            logger.error(f"Таймаут при запросе курса для валюты {currency}")
        except RequestException as e:
            # Обработка сетевых ошибок
            logger.error(f"Ошибка сети при запросе курса для валюты {currency}: {e}")
        except (KeyError, ValueError, TypeError) as e:
            # Обработка ошибок получения ответа
            logger.error(f"Ошибка обработки ответа API для валюты {currency}: {e}")

    logger.info(f"Успешно получено курсов: {len(currency_rates)} из {len(currencies)}")
    return currency_rates


def get_stock_prices(stocks: List[str]) -> List[Dict[str, Any]]:
    """Функция получает текущие цены на акции по их тикерам. Использует API Twelve Data. Возвращает список
    словарей, каждый из которых содержит 'stock' (тикер) и 'price' (текущая цена)."""
    # Создаем новый пустой список для цен на акции
    stock_prices: List[Dict[str, Any]] = []

    # Проверяем наличие API-ключа
    if not TWELVE_DATA_API_KEY:
        logger.error("API-ключ для Twelve Data не задан. Проверьте свой .env файл.")
        return stock_prices

    if not stocks:
        logger.warning("Получен пустой список акций для запроса цен")
        return stock_prices

    logger.info(f"Запрос цен для акций через Twelve Data: {stocks}")

    for symbol in stocks:
        try:
            # Параметры запроса к API
            params: Dict[str, Any] = {"symbol": symbol, "outputsize": 1, "apikey": TWELVE_DATA_API_KEY}

            # Выполнение GET запроса к API с таймаутом
            response = requests.get(TWELVE_DATA_PRICE_URL, params=params, timeout=10)

            # Проверка статуса ответа
            response.raise_for_status()

            # Получение данных из ответа API в формате JSON
            data: Dict[str, Any] = response.json()

            # Логируем ответ для отладки
            logger.debug(f"Ответ API для {symbol}: {data}")

            # Обрабатываем ответ API
            if "price" in data:
                price_str = data["price"]
                try:
                    price = float(price_str)
                    stock_prices.append({"stock": symbol, "price": round(price, 2)})
                    logger.debug(f"Получен цена {symbol}: ${price}")
                except ValueError:
                    logger.error(f"Невозможно преобразовать цену для {symbol} в число '{price_str}'")
            else:
                # Обработка ответа от API с ошибкой
                error_message = data.get("message", "Unknown error")
                logger.error(f"Ошибка API для акции {symbol}: {error_message}")

        except Timeout:
            # Обработка ошибки времени ожидания запроса
            logger.error(f"Таймаут при запросе цены для акции {symbol}")
        except RequestException as e:
            # Обработка сетевых ошибок
            logger.error(f"Ошибка сети при запросе цены для акции {symbol}: {e}")
        except (KeyError, ValueError, TypeError) as e:
            # Обработка ошибок получения ответа
            logger.error(f"Ошибка обработки ответа API для акции {symbol}: {e}")

    logger.info(f"Успешно получено цен: {len(stock_prices)} из {len(stocks)}")
    return stock_prices


def load_user_settings(file_path: Optional[str] = None) -> Dict[str, List[str]]:
    """Функция загружает пользовательские настройки из JSON-файла и возвращает словарь с настройками.
    В случае ошибки возвращает настройки по умолчанию."""

    # Указываем настройки по умолчанию
    default_settings = {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}

    # Если путь не передан, формируем путь по умолчанию
    if file_path is None:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(current_dir, "data", "user_settings.json")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Проверяем, что загруженные данные - словарь
        if not isinstance(data, dict):
            logger.warning(
                f"Загруженные данные из {file_path} не являются словарём. Используются значения по умолчанию."
            )
            return default_settings

        # Извлекаем и проверяем списки валют и акций
        currencies = data.get("user_currencies")
        stocks = data.get("user_stocks")

        if not isinstance(currencies, list):
            logger.warning(
                f"Ключ 'user_currencies' в {file_path} не является списком. Используются значения по умолчанию."
            )
            return default_settings

        if not isinstance(stocks, list):
            logger.warning(
                f"Ключ 'user_stocks' в {file_path} не является списком. Используются значения по умолчанию."
            )
            return default_settings

        logger.info(f"Настройки успешно загружены из {file_path}")
        return {"user_currencies": currencies, "user_stocks": stocks}

    except FileNotFoundError:
        logger.warning(f"Файл настроек {file_path} не найден. Используются значения по умолчанию.")
        return default_settings
    except JSONDecodeError as e:
        logger.error(f"Ошибка чтения JSON в файле {file_path}: {e}. Используются значения по умолчанию.")
        return default_settings
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке настроек: {e}. Используются значения по умолчанию.")
        return default_settings
