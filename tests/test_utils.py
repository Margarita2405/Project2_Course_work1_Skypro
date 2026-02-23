import pytest
import json
import logging
from datetime import datetime
import pandas as pd
from pytest import LogCaptureFixture
from requests.exceptions import Timeout, RequestException
from unittest.mock import patch, mock_open, MagicMock
from src.utils import (
    get_time_greeting,
    load_transactions,
    filter_transactions_by_date,
    process_card_date_with_spent,
    get_top_transactions,
    get_currency_rates,
    get_stock_prices,
    load_user_settings,
)


def test_get_time_greeting() -> None:
    """Тестирует фнункцию get_time_greeting. Проверяет правильность приветствия в зависимости от времени суток."""
    # Утро (5:00 - 11:59)
    assert get_time_greeting(datetime(2021, 3, 1, 10, 25, 0)) == "Доброе утро"
    # День (12:00 - 16:59)
    assert get_time_greeting(datetime(2021, 3, 1, 15, 8, 0)) == "Добрый день"
    # Вечер (17:00 - 22:59)
    assert get_time_greeting(datetime(2021, 3, 1, 20, 45, 0)) == "Добрый вечер"
    # Ночь (23:00 - 4:59)
    assert get_time_greeting(datetime(2021, 3, 1, 3, 15, 0)) == "Доброй ночи"


@patch("src.utils.pd.read_excel")
@patch("src.utils.os.path.exists")
def test_load_transactions(mock_exists: MagicMock, mock_read_excel: MagicMock) -> None:
    """Тестирует функцию load_transactions. Проверяет загрузку Excel-файла и возврат DataFrame. Мокирует
    pd.read_excel и os.path.exists."""
    # Настраиваем мок: файл существует
    mock_exists.return_value = True
    # Создаем тестовый DataFrame
    mock_df = pd.DataFrame({"Дата операции": ["01.03.2021"], "Сумма операции": [100]})
    mock_read_excel.return_value = mock_df
    # Вызываем функцию
    df = load_transactions()
    # Проверяем, что pd.read_excel был вызван
    mock_read_excel.assert_called_once()
    # Проверяем, что вернулся DataFrame с одной строкой
    assert len(df) == 1


def test_load_transactions_file_not_found() -> None:
    """Проверка, что при отсутствии файла выбрасывается FileNotFoundError."""
    with patch("src.utils.os.path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            load_transactions("fake_path.xlsx")


def test_load_transactions_invalid_excel(caplog: LogCaptureFixture) -> None:
    """Проверка обработки ошибки чтения Excel (например, повреждённый файл)."""
    with patch("src.utils.os.path.exists", return_value=True):
        with patch("src.utils.pd.read_excel", side_effect=Exception("Read error")):
            with pytest.raises(Exception, match="Read error"):
                load_transactions("some.xlsx")
    # Сама функция не логирует, исключение пробрасывается наружу


def test_filter_transactions_by_date() -> None:
    """Тестирует функцию filter_transactions_by_date. Проверяет фильтрацию записей с начала месяца по указанную
    дату."""
    # Исходный DataFrame с разными датами
    df = pd.DataFrame({"Дата операции": pd.to_datetime(["2021-12-01", "2021-12-15", "2021-12-20", "2021-11-30"])})
    end_date = datetime(2021, 12, 20)
    filtered = filter_transactions_by_date(df, end_date)

    # Должны остаться только записи декабря по 20 число включительно
    assert len(filtered) == 3
    assert all(filtered["Дата операции"] <= pd.Timestamp(end_date))
    assert all(filtered["Дата операции"] >= pd.Timestamp("2021-12-01"))


def test_process_card_date_with_spent() -> None:
    """Тестирует функцию process_card_date_with_spent. Проверяет корректность извлечения последних 4 цифр карты,
    суммирование расходов(только отрицательные значения) и расчета кешбэка."""
    # Тестовые данные: две карты, одна с двумя операциями
    df = pd.DataFrame(
        {
            "Номер карты": ["1234567890123456", "1234567890123456", "9876543210987654"],
            "Сумма операции": [1000, -500, -300],  # 1000 - доход (не учитывается)
        }
    )
    result = process_card_date_with_spent(df)

    # Должно быть две карты
    assert len(result) == 2

    # Первая карта: последние 4 цифры '3456', сумма расходов = 500.0, кешбэк = 5.0
    assert result[0]["last_digits"] == "3456"
    assert result[0]["total_spent"] == 500.0
    assert result[0]["cashback"] == 5.0

    # Вторая карта: последние 4 цифры '7654', сумма расходов = 300.0, кешбэк = 3.0
    assert result[1]["last_digits"] == "7654"
    assert result[1]["total_spent"] == 300.0
    assert result[1]["cashback"] == 3.0


def test_process_card_data_missing_card_column(caplog: LogCaptureFixture) -> None:
    """Проверка, что при отсутствии столбца 'Номер карты' возвращается пустой список и логируется предупреждение."""
    df = pd.DataFrame({"Сумма операции": [-100, -200]})
    with caplog.at_level(logging.WARNING):
        result = process_card_date_with_spent(df)
    assert result == []
    assert "Столбец с номером карты не найден" in caplog.text


def test_process_card_data_missing_amount_column(caplog: LogCaptureFixture) -> None:
    """Проверка, что при отсутствии столбца с суммой возвращается пустой список."""
    df = pd.DataFrame({"Номер карты": ["1234"], "Другое": [1]})
    with caplog.at_level(logging.WARNING):
        result = process_card_date_with_spent(df)
    assert result == []
    assert "Столбец с суммой не найден" in caplog.text


def test_process_card_data_no_expenses() -> None:
    """Проверка, что для карт без расходов (только доходы) total_spent = 0, cashback = 0."""
    df = pd.DataFrame(
        {"Номер карты": ["1234567890123456", "1234567890123456"], "Сумма операции": [1000, 500]}  # только доходы
    )
    result = process_card_date_with_spent(df)
    assert len(result) == 1
    assert result[0]["last_digits"] == "3456"
    assert result[0]["total_spent"] == 0.0
    assert result[0]["cashback"] == 0.0


def test_process_card_data_mixed_expenses() -> None:
    """Проверка корректного суммирования только расходов (отрицательных сумм)."""
    df = pd.DataFrame(
        {
            "Номер карты": ["1234567890123456", "1234567890123456", "9876543210987654", "9876543210987654"],
            "Сумма операции": [-100, -200, 500, -300],
        }
    )
    result = process_card_date_with_spent(df)
    # Первая карта: расходы -100 и -200, итого 300
    # Вторая карта: расход -300
    assert len(result) == 2
    # Сортируем для стабильности (last_digits могут идти в разном порядке)
    result_sorted = sorted(result, key=lambda x: x["last_digits"])
    assert result_sorted[0]["last_digits"] == "3456"
    assert result_sorted[0]["total_spent"] == 300.0
    assert result_sorted[0]["cashback"] == 3.0
    assert result_sorted[1]["last_digits"] == "7654"
    assert result_sorted[1]["total_spent"] == 300.0
    assert result_sorted[1]["cashback"] == 3.0


def test_get_top_transactions() -> None:
    """Тестирует функцию get_top_transactions. Проверяет сортировку по абсолютной сумме платежа и возврат топ-n
    записей."""
    # Создаем DataFrame с транзакциями разных сумм
    df = pd.DataFrame(
        {
            "Дата операции": ["15.12.2021", "20.12.2021", "10.12.2021", "05.12.2021", "25.12.2021"],
            "Сумма операции": [-1000, -500, -2000, -300, -150],
            "Категория": ["A", "B", "A", "C", "B"],
            "Описание": ["desc1", "desc2", "desc3", "desc4", "desc5"],
        }
    )

    # Запрашиваем топ-3 по абсолютной сумме
    result = get_top_transactions(df, 3)

    # Проверяем количество и порядок
    assert len(result) == 3
    assert result[0]["amount"] == -2000.0  # Самая большая сумма расходов
    assert result[1]["amount"] == -1000.0
    assert result[2]["amount"] == -500.0


def test_get_top_transactions_missing_optional_columns() -> None:
    """Проверка, что при отсутствии столбца 'Описание' возвращаются транзакции с пустым описанием."""
    df = pd.DataFrame(
        {
            "Дата операции": ["01.12.2021", "02.12.2021"],
            "Сумма операции": [-100, -200],
            "Категория": ["А", "Б"],
            # столбец 'Описание' отсутствует
        }
    )
    result = get_top_transactions(df, 2)
    assert len(result) == 2
    for t in result:
        assert "date" in t
        assert "amount" in t
        assert t["description"] == ""  # ожидаем пустую строку


def test_get_top_transactions_invalid_date_type() -> None:
    """Проверка обработки случая, когда значение даты не является datetime."""
    df = pd.DataFrame(
        {
            "Дата операции": ["не дата", "2021-12-01"],
            "Сумма операции": [-100, -200],
            "Категория": ["А", "Б"],
            "Описание": ["a", "b"],
        }
    )
    result = get_top_transactions(df, 2)
    assert len(result) == 2
    # Первая строка с наибольшей суммой (-200) -> дата '2021-12-01'
    assert result[0]["date"] == "2021-12-01"
    assert result[0]["amount"] == -200.0
    assert result[0]["category"] == "Б"
    assert result[0]["description"] == "b"
    # Вторая строка с меньшей суммой (-100) -> дата 'не дата'
    assert result[1]["date"] == "не дата"
    assert result[1]["amount"] == -100.0
    assert result[1]["category"] == "А"
    assert result[1]["description"] == "a"


@patch("src.utils.requests.get")
def test_get_currency_rates(mock_get: MagicMock) -> None:
    """Тестирует функцию get_currency_rates. Мокирует запрос к API и проверяет корректность получения ответа."""
    # Настраиваем мок-ответ от API
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True, "result": 73.21}  # Курс USD -> RUB
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Список валют для запроса
    currencies = ["USD", "EUR"]
    # Подменяем API-ключ, чтобы тест не зависел от .env файла
    with patch("src.utils.EXCHANGERATES_API_KEY", "test_key"):
        result = get_currency_rates(currencies, "RUB")

    # Проверяем, что запрос сделан для каждой валюты
    assert len(result) == 2
    # Проверяем результат
    assert result[0]["currency"] == "USD"
    assert result[0]["rate"] == 73.21
    assert result[1]["currency"] == "EUR"
    assert result[1]["rate"] == 73.21  # Мок возвращает одинаковый курс для обеих валют


def test_get_currency_rates_no_api_key(caplog: LogCaptureFixture) -> None:
    """Проверка, что при отсутствии API-ключа возвращается пустой список и логируется ошибка."""
    with patch("src.utils.EXCHANGERATES_API_KEY", None):
        with caplog.at_level(logging.ERROR):
            result = get_currency_rates(["USD", "EUR"])
    assert result == []
    assert "API-ключ для сервиса валют не задан" in caplog.text


def test_get_currency_rates_empty_list() -> None:
    """Проверка, что при пустом списке валют возвращается пустой список."""
    with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
        result = get_currency_rates([])
    assert result == []


def test_get_currency_rates_timeout(caplog: LogCaptureFixture) -> None:
    """Проверка обработки таймаута при запросе."""
    with patch("src.utils.requests.get", side_effect=Timeout):
        with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_currency_rates(["USD"])
    assert result == []
    assert "Таймаут при запросе курса для валюты USD" in caplog.text


def test_get_currency_rates_request_exception(caplog: LogCaptureFixture) -> None:
    """Проверка обработки сетевой ошибки."""
    with patch("src.utils.requests.get", side_effect=RequestException("Network error")):
        with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_currency_rates(["USD"])
    assert result == []
    assert "Ошибка сети при запросе курса для валюты USD" in caplog.text


def test_get_currency_rates_unsuccessful_response(caplog: LogCaptureFixture) -> None:
    """Проверка обработки ответа с success=False."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": False}
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
            with caplog.at_level(logging.WARNING):
                result = get_currency_rates(["USD"])
    assert result == []
    # Проверяем, что не было добавлено курса (пустой список)


def test_get_currency_rates_missing_result(caplog: LogCaptureFixture) -> None:
    """Проверка обработки ответа без поля 'result'."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True}  # нет result
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
            with caplog.at_level(logging.WARNING):
                result = get_currency_rates(["USD"])
    assert result == []
    assert "отсутствует none 'result'" in caplog.text or "отсутствует поле 'result'" in caplog.text


def test_get_currency_rates_key_error(caplog: LogCaptureFixture) -> None:
    """Проверка обработки KeyError при обработке ответа (например, неверная структура)."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"unexpected": "data"}
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.EXCHANGERATES_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_currency_rates(["USD"])
    assert result == []
    assert "Ошибка API для валюты USD" in caplog.text


@patch("src.utils.requests.get")
def test_get_stock_prices(mock_get: MagicMock) -> None:
    """Тестирует функцию get_stock_prices. Мокирует запрос к Twelve data API и проверяет корректность получения
    ответа."""
    # Настраиваем мок-ответ от API
    mock_response = MagicMock()
    mock_response.json.return_value = {"price": "150.12"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Список акций для запроса
    stocks = ["AAPL", "MSFT"]
    # Подменяем API-ключ, чтобы тест не зависел от .env файла
    with patch("src.utils.TWELVE_DATA_API_KEY", "test_key"):
        result = get_stock_prices(stocks)

    # Проверяем, что запрос сделан для каждого тикера
    assert len(result) == 2
    assert result[0]["stock"] == "AAPL"
    assert result[0]["price"] == 150.12
    assert result[1]["stock"] == "MSFT"
    assert result[1]["price"] == 150.12  # Мок возвращает одинаковую цену для всех тикеров


def test_get_stock_prices_no_api_key(caplog: LogCaptureFixture) -> None:
    """Проверка, что при отсутствии API-ключа возвращается пустой список."""
    with patch("src.utils.TWELVE_DATA_API_KEY", None):
        with caplog.at_level(logging.ERROR):
            result = get_stock_prices(["AAPL"])
    assert result == []
    assert "API-ключ для Twelve Data не задан" in caplog.text


def test_get_stock_prices_empty_list(caplog: LogCaptureFixture) -> None:
    """Проверка, что при пустом списке акций возвращается пустой список и предупреждение."""
    with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
        with caplog.at_level(logging.WARNING):
            result = get_stock_prices([])
    assert result == []
    assert "Получен пустой список акций для запроса цен" in caplog.text


def test_get_stock_prices_timeout(caplog: LogCaptureFixture) -> None:
    """Проверка обработки таймаута."""
    with patch("src.utils.requests.get", side_effect=Timeout):
        with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_stock_prices(["AAPL"])
    assert result == []
    assert "Таймаут при запросе цены для акции AAPL" in caplog.text


def test_get_stock_prices_request_exception(caplog: LogCaptureFixture) -> None:
    """Проверка обработки сетевой ошибки."""
    with patch("src.utils.requests.get", side_effect=RequestException("Network error")):
        with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_stock_prices(["AAPL"])
    assert result == []
    assert "Ошибка сети при запросе цены для акции AAPL" in caplog.text


def test_get_stock_prices_no_price_field(caplog: LogCaptureFixture) -> None:
    """Проверка ответа API без поля 'price'."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "error"}
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_stock_prices(["AAPL"])
    assert result == []
    assert "Ошибка API для акции AAPL" in caplog.text


def test_get_stock_prices_invalid_price(caplog: LogCaptureFixture) -> None:
    """Проверка, что если price не может быть преобразовано в float, записывается ошибка."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"price": "not a number"}
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_stock_prices(["AAPL"])
    assert result == []
    assert "Невозможно преобразовать цену для AAPL в число" in caplog.text


def test_get_stock_prices_key_error(caplog: LogCaptureFixture) -> None:
    """Проверка обработки KeyError при обработке ответа."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"unexpected": "data"}
    mock_response.raise_for_status.return_value = None
    with patch("src.utils.requests.get", return_value=mock_response):
        with patch("src.utils.TWELVE_DATA_API_KEY", "key"):
            with caplog.at_level(logging.ERROR):
                result = get_stock_prices(["AAPL"])
    assert result == []
    assert "Ошибка API для акции AAPL" in caplog.text


@patch("builtins.open", new_callable=mock_open, read_data="{}")
@patch("src.utils.json.load")
def test_load_user_settings(mock_json_load: MagicMock, mock_file: MagicMock) -> None:
    """Тестирует функцию load_user_settings. Проверяет чтение файла настроек и возврат словаря. При отсутствии
    файла или ошибке JSON должны возвращаться настройки по умолчанию."""
    # Случай успешной загрузки
    mock_json_load.return_value = {"user_currencies": ["USD"], "user_stocks": ["AAPL"]}
    with patch("src.utils.os.path.dirname") as mock_dirname:
        mock_dirname.return_value = "fake_dir"
        result = load_user_settings()

    # Проверяем, что вернулись загруженные настройки
    assert result == {"user_currencies": ["USD"], "user_stocks": ["AAPL"]}

    # Случай ошибки JSONDecodeError: мокируем исключение
    mock_json_load.side_effect = json.JSONDecodeError("Error", "", 0)
    with patch("src.utils.os.path.dirname") as mock_dirname:
        mock_dirname.return_value = "fake_dir"
        result = load_user_settings()

    # Должны вернуться настройки по умолчанию
    assert result == {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}


def test_load_user_settings_file_not_found(caplog: LogCaptureFixture) -> None:
    """Проверка возврата настроек по умолчанию при отсутствии файла."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        with patch("src.utils.os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "fake_dir"
            with caplog.at_level(logging.WARNING):
                result = load_user_settings()
    expected_default = {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    assert result == expected_default
    assert "Файл настроек" in caplog.text and "не найден" in caplog.text


def test_load_user_settings_invalid_format_currencies(caplog: LogCaptureFixture) -> None:
    """Проверка, что если user_currencies не список, возвращаются настройки по умолчанию."""
    mock_data = '{"user_currencies": "USD", "user_stocks": ["AAPL"]}'
    with patch("builtins.open", mock_open(read_data=mock_data)):
        with patch("src.utils.os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "fake_dir"
            with caplog.at_level(logging.WARNING):
                result = load_user_settings()
    expected_default = {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    assert result == expected_default
    assert "Ключ 'user_currencies' в" in caplog.text
    assert "не является списком" in caplog.text


def test_load_user_settings_invalid_format_stocks(caplog: LogCaptureFixture) -> None:
    """Проверка, что если user_stocks не список, возвращаются настройки по умолчанию."""
    mock_data = '{"user_currencies": ["USD"], "user_stocks": "AAPL"}'
    with patch("builtins.open", mock_open(read_data=mock_data)):
        with patch("src.utils.os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "fake_dir"
            with caplog.at_level(logging.WARNING):
                result = load_user_settings()
    expected_default = {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    assert result == expected_default
    assert "Ключ 'user_stocks' в" in caplog.text
    assert "не является списком" in caplog.text


def test_load_user_settings_unexpected_exception(caplog: LogCaptureFixture) -> None:
    """Проверка обработки любого другого исключения (например, PermissionError)."""
    with patch("builtins.open", side_effect=PermissionError("Access denied")):
        with patch("src.utils.os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "fake_dir"
            with caplog.at_level(logging.ERROR):
                result = load_user_settings()
    expected_default = {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    assert result == expected_default
    assert "Неожиданная ошибка при загрузке настроек" in caplog.text
