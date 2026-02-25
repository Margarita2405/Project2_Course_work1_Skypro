import json
import sys
from datetime import datetime
import logging
from typing import List, Dict, Any


# Настройка логирования
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="%(asctime)s - %(levelname)s - %(message)s")

# Создание логгера с именем модуля
logger = logging.getLogger(__name__)


def calculate_cashback_by_category(data: List[Dict[str, Any]], year: int, month: int) -> str:
    """Функция анализирует транзакции за указанный месяц и год и вычисляет потенциальный кешбэк по каждой
    категории. Возвращает JSON-строку с анализом, сколько на каждой категории можно заработать кешбэка в
    указанном месяце года."""

    logger.info(f"Запуск расчета кешбэка для {year} - {month:02d}")

    # Создаем словарь для накопления расходов по категориям
    expenses_by_category: Dict[str, float] = {}

    for transaction in data:
        try:
            # Извлекаем дату операции
            date_operation = transaction.get("Дата операции")
            if date_operation is None:
                logger.warning("Пропущена транзакция без поля 'Дата операции'")
                continue

            # Преобразуем дату в объект datetime
            if isinstance(date_operation, datetime):
                dt = date_operation
            elif isinstance(date_operation, str):
                # Пытаемся преобразовать строку в объект datetime в формате DD.MM.YYY
                dt = datetime.strptime(date_operation, "%d.%m.%Y")
            else:
                logger.warning(f"Неподдерживаемый тип даты: {type(date_operation)}")
                continue

            # Проверяем, соответсвует ли дата заданному году и месяцу
            if dt.year != year or dt.month != month:
                continue

            # Получаем сумму операции
            amount_raw = transaction.get("Сумма операции")
            if amount_raw is None:
                logger.debug("Пропущена транзакция без суммы")
                continue

            # Приводим сумму к числу
            try:
                amount = float(amount_raw)
            except (ValueError, TypeError):
                logger.warning(f"Некорректное значение суммы: {amount_raw}")
                continue

            # Учитываем только расходы (отрицательные суммы)
            if amount >= 0:
                continue

            # Получаем категорию
            category = transaction.get("Категория")
            if category is None:
                logger.debug("Пропущена транзакция без категории")
                continue

            # Накопление расходов (берём абсолютное значение)
            expenses_by_category[category] = expenses_by_category.get(category, 0.0) + abs(amount)

        except Exception as e:
            logger.error(f"Ошибка обработки транзакции: {e}", exc_info=True)

    # Вычисляем кешбэк для каждой категории (1 рубль на каждые 100 рублей)
    cashback_by_category = {category: round(expenses / 100, 2) for category, expenses in expenses_by_category.items()}

    # Логируем результат
    logger.info(f"Рассчитан кешбэк по категориям: {cashback_by_category}")

    # Возвращаем JSON-строку
    return json.dumps(cashback_by_category, ensure_ascii=False, indent=4)
