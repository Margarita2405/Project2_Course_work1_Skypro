import json
import logging
import pandas as pd
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Any


# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Создание логгера с именем модуля
logger = logging.getLogger(__name__)


def report_decorator(filename: Optional[str] = None) -> Callable:
    """Декоратор для функций-отчетов, который записывает результат работы функции в JSON-файл."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)

            # Определяем имя файла
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"report_{timestamp}.json"
            else:
                file_name = filename

            try:
                if isinstance(result, pd.DataFrame):
                    # Преобразуем DataFrame в JSON-строку
                    json_data = result.to_json(
                        orient="records", date_format="iso", force_ascii=False, default_handler=str
                    )
                elif isinstance(result, (dict, list)):
                    # Если результат - словарь или список, преобразуем Python-объект в JSON-строку
                    json_data = json.dumps(result, ensure_ascii=False, indent=4, default=str)
                else:
                    # Если результат - любой другой тип
                    json_data = json.dumps({"result": str(result)}, ensure_ascii=False, indent=4)

                with open(file_name, "w", encoding="utf-8") as file:
                    file.write(json_data)
                logger.info(f"Отчет сохранен в файл: {file_name}")

            except Exception as e:
                logger.error(f"Ошибка при сохранении отчета в {file_name}: {e}")

            return result

        return wrapper

    return decorator


def spending_by_category(transactions: pd.DataFrame, category: str, date: Optional[str] = None) -> pd.DataFrame:
    """Функция возвращает траты по заданной категории за последние три месяца от указанной даты."""

    # Создаем копию, чтобы не изменять исходный DataFrame
    df = transactions.copy()

    # Проверяем наличие обязательных столбцов
    required_columns = ["Дата операции", "Категория", "Сумма операции"]
    for column in required_columns:
        if column not in df.columns:
            raise KeyError(f"В данных отсутствует обязательный столбец '{column}'")

    # Преобразование столбца даты
    df["date_dt"] = pd.to_datetime(df["Дата операции"], format="%d.%m.%Y %H:%M:%S", dayfirst=True, errors="coerce")

    # Удаляем строки с NaT (некорректные даты)
    df = df.dropna(subset=["date_dt"])

    # Определение конечной даты отчета
    if date is None:
        end_date = datetime.now()
    else:
        end_date = pd.to_datetime(date)

    # Вычисляем дату, которая была ровно 3 месяца назад от конечной даты отчета (end_date)
    start_date = end_date - pd.DateOffset(months=3)

    # Для фильтрации используем строго меньше начала следующего дня
    end_of_date = end_date + pd.DateOffset(days=1)

    # Фильтруем транзакции
    filtered_df = (
        (df["Категория"] == category)
        & (df["date_dt"] >= start_date)
        & (df["date_dt"] < end_of_date)
        & (df["Сумма операции"] < 0)  # учитываем только расходы
    )

    result = df.loc[filtered_df].copy()
    logger.info(
        f"Найдено: {len(result)} транзакций по каждой категории '{category}' "
        f" за период с {start_date.date()} по {end_date.date()}"
    )

    # Возвращаем ключевые столбцы
    columns_to_return = ["Дата операции", "Категория", "Сумма операции"]
    # Добавляем опциональные, если они присутствуют
    optional_columns = ["Валюта операции", "Описание", "МСС"]
    for column in optional_columns:
        if column in result.columns:
            columns_to_return.append(column)

    return result[columns_to_return]
