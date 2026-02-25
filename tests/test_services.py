import json
import logging
from pytest import LogCaptureFixture
from typing import List, Dict, Any
from datetime import datetime
from src.services import calculate_cashback_by_category


def test_calculate_cashback_by_category_basic() -> None:
    """Базовый тест: одна категория с несколькими расходами."""
    data = [
        {"Дата операции": "01.12.2021", "Сумма операции": -99, "Категория": "Супермаркеты"},
        {"Дата операции": "08.12.2021", "Сумма операции": -135, "Категория": "Фастфуд"},
        {"Дата операции": "14.12.2021", "Сумма операции": -309, "Категория": "Супермаркеты"},
        {"Дата операции": "23.12.2021", "Сумма операции": 2000, "Категория": "Другое"},  # Доход игнорируется
    ]
    result_json = calculate_cashback_by_category(data, 2021, 12)
    expected = {"Супермаркеты": 4.08, "Фастфуд": 1.35}
    result_dict = json.loads(result_json)
    assert result_dict == expected


def test_calculate_cashback_by_category_empty() -> None:
    """Тест с пустыми данными."""
    data: List[Dict[str, Any]] = []
    result_json = calculate_cashback_by_category(data, 2021, 12)
    assert result_json == "{}"


def test_calculate_cashback_by_category_no_expenses() -> None:
    """Тест, где в месяце нет расходов."""
    data = [
        {"Дата операции": "16.12.2021", "Сумма операции": 453, "Категория": "Бонусы"},  # Доход
        {"Дата операции": "05.12.2021", "Сумма операции": 3500, "Категория": "Пополнения"},  # Доход
    ]
    result_json = calculate_cashback_by_category(data, 2021, 12)
    assert result_json == "{}"


def test_calculate_cashback_by_category_different_month() -> None:
    """Тест: транзакции другого месяца не учитываются."""
    data = [
        {"Дата операции": "18.11.2021", "Сумма операции": -200, "Категория": "Мобильная связь"},
        {"Дата операции": "25.12.2021", "Сумма операции": -3400, "Категория": "Развлечения"},
    ]
    result_json = calculate_cashback_by_category(data, 2021, 12)
    expected = {"Развлечения": 34.0}  # только декабрь
    result_dict = json.loads(result_json)
    assert result_dict == expected


def test_calculate_cashback_by_category_datetime_input() -> None:
    """Тест с передачей даты как объекта datetime."""
    data = [
        {"Дата операции": datetime(2021, 12, 10), "Сумма операции": -83, "Категория": "Фастфуд"},
    ]
    result_json = calculate_cashback_by_category(data, 2021, 12)
    expected = {"Фастфуд": 0.83}
    result_dict = json.loads(result_json)
    assert result_dict == expected


def test_calculate_cashback_by_category_missing_date(caplog: LogCaptureFixture) -> None:
    """Проверка пропуска транзакции без поля 'Дата операции'."""
    data = [{"Сумма операции": -100, "Категория": "Супермаркеты"}]
    with caplog.at_level(logging.WARNING):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    assert "Пропущена транзакция без поля 'Дата операции'" in caplog.text


def test_calculate_cashback_by_category_invalid_date_type(caplog: LogCaptureFixture) -> None:
    """Проверка обработки даты неподдерживаемого типа (например, число)."""
    data = [{"Дата операции": 12345, "Сумма операции": -100, "Категория": "Супермаркеты"}]
    with caplog.at_level(logging.WARNING):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    assert "Неподдерживаемый тип даты" in caplog.text


def test_calculate_cashback_by_category_missing_amount(caplog: LogCaptureFixture) -> None:
    """Проверка пропуска транзакции без поля 'Сумма операции'."""
    data = [{"Дата операции": "01.12.2021", "Категория": "Супермаркеты"}]
    with caplog.at_level(logging.DEBUG):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    assert "Пропущена транзакция без суммы" in caplog.text


def test_calculate_cashback_by_category_invalid_amount(caplog: LogCaptureFixture) -> None:
    """Проверка обработки некорректного значения суммы (не число)."""
    data = [{"Дата операции": "01.12.2021", "Сумма операции": "abc", "Категория": "Супермаркеты"}]
    with caplog.at_level(logging.WARNING):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    assert "Некорректное значение суммы" in caplog.text


def test_calculate_cashback_by_category_date_parse_error(caplog: LogCaptureFixture) -> None:
    """Проверка ошибки парсинга даты (неверный формат)."""
    data = [{"Дата операции": "2021-12-01", "Сумма операции": -100, "Категория": "Супермаркеты"}]  # формат ГГГГ-ММ-ДД
    with caplog.at_level(logging.ERROR):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    # Проверяем, что общая ошибка обработки транзакции залогирована
    assert "Ошибка обработки транзакции" in caplog.text


def test_calculate_cashback_by_category_missing_category(caplog: LogCaptureFixture) -> None:
    """Проверка пропуска транзакции без категории."""
    data = [{"Дата операции": "01.12.2021", "Сумма операции": -100}]
    with caplog.at_level(logging.DEBUG):
        result = calculate_cashback_by_category(data, 2021, 12)
    assert json.loads(result) == {}
    assert "Пропущена транзакция без категории" in caplog.text
