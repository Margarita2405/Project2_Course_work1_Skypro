from datetime import datetime
import pandas as pd
from unittest.mock import patch
from src.views import main_view


def test_main_view_success() -> None:
    """Тестирует успешное выполнение главной функции main_view. Проверяет кооректный вызов всех функций
    (загрузка транзакций, настроек пользователя, фильтрация, обработка карт, получение топ-транзакций,
    курсов валют, цен акций), структуру возвращаемого JSON-ответа, отсутствие ключа 'error' в ответе."""
    # Тестовые данные
    test_date = "2021-12-21 14:30:00"

    # Создаем мок-данные для транзакций
    mock_df = pd.DataFrame(
        {"Дата операции": [datetime(2021, 12, 15)], "Номер карты": ["1234"], "Сумма операции": [-1000]}
    )

    # Создаем отдельную копию DataFrame для имитации результата фильтрации
    mock_filtered_df = mock_df.copy()

    # Мок-результаты для транзакций
    mock_cards = [{"last_digits": "1234", "total_spent": 1000.0, "cashback": 10.0}]
    mock_top = [{"date": "15.12.2021", "amount": -1000.0, "category": "Test", "description": ""}]
    mock_currencies = [{"currency": "USD", "rate": 73.21}]
    mock_stocks = [{"stock": "AAPL", "price": 150.12}]
    mock_settings = {"user_currencies": ["USD"], "user_stocks": ["AAPL"]}

    # Мокирование всех внешних функций
    with (
        patch("src.views.get_time_greeting") as mock_greeting,
        patch("src.views.load_user_settings") as mock_load_settings,
        patch("src.views.load_transactions") as mock_load_trans,
        patch("src.views.filter_transactions_by_date") as mock_filter,
        patch("src.views.process_card_date_with_spent") as mock_cards_func,
        patch("src.views.get_top_transactions") as mock_top_func,
        patch("src.views.get_currency_rates") as mock_currency_func,
        patch("src.views.get_stock_prices") as mock_stock_func,
    ):

        # Настройка возвращаемых значений моков
        mock_greeting.return_value = "Добрый день"
        mock_load_settings.return_value = mock_settings
        mock_load_trans.return_value = mock_df
        mock_filter.return_value = mock_filtered_df
        mock_cards_func.return_value = mock_cards
        mock_top_func.return_value = mock_top
        mock_currency_func.return_value = mock_currencies
        mock_stock_func.return_value = mock_stocks

        # Вызов тестируемой функции
        result = main_view(test_date)

        # Проверки
        assert result["greeting"] == "Добрый день"
        assert result["cards"] == mock_cards
        assert result["top_transactions"] == mock_top
        assert result["currency_rates"] == mock_currencies
        assert result["stock_prices"] == mock_stocks
        assert "error" not in result

        # Проверяем, что все моки были вызваны
        mock_greeting.assert_called_once()
        mock_load_settings.assert_called_once()
        mock_load_trans.assert_called_once()
        mock_filter.assert_called_once_with(mock_df, datetime(2021, 12, 21, 14, 30, 0))
        mock_cards_func.assert_called_once_with(mock_filtered_df)
        mock_top_func.assert_called_once_with(mock_filtered_df, 5)
        mock_currency_func.assert_called_once_with(currencies=mock_settings["user_currencies"])
        mock_stock_func.assert_called_once_with(stocks=mock_settings["user_stocks"])


def test_main_view_invalid_date() -> None:
    """Тестирует обработку некорректного формата входной даты. Проверяет, что при передаче строки, не
    соответствующей формату YYYY-MM-DD HH:MM:SS, возвращается словарь с ключом 'error' и сообщением об ошибке."""
    # Дата без времени -не полный формат
    invalid_date = "2021-12-21"

    # Вызов тестируемой функции
    result = main_view(invalid_date)

    # Проверяем результат
    assert "error" in result
    assert "Неверный формат даты" in result["error"]


def test_main_view_empty_transactions() -> None:
    """Тестирует сценарий, когда после фильтрации за указанный период нет транзакций.
    Должен вернуться ответ с пустыми списками и сообщением."""
    # Тестовые данные
    test_date = "2021-12-21 14:30:00"

    # Пустой DataFrame после фильтрации
    mock_df = pd.DataFrame({"Дата операции": []})
    mock_filtered_df = pd.DataFrame()
    mock_settings = {"user_currencies": ["USD"], "user_stocks": ["AAPL"]}

    # Мокирование функций main_view
    with (
        patch("src.views.get_time_greeting", return_value="Добрый день"),
        patch("src.views.load_user_settings", return_value=mock_settings),
        patch("src.views.load_transactions", return_value=mock_df),
        patch("src.views.filter_transactions_by_date", return_value=mock_filtered_df),
        patch("src.views.process_card_date_with_spent") as mock_cards,
        patch("src.views.get_top_transactions") as mock_top,
        patch("src.views.get_currency_rates") as mock_currency,
        patch("src.views.get_stock_prices") as mock_stock,
    ):

        # Вызов тестируемой функции
        result = main_view(test_date)

        # Проверяем, что функции обработки данных не вызывались, так как транзакции отсутствуют (пустой filtered_df)
        #
        mock_cards.assert_not_called()
        mock_top.assert_not_called()
        mock_currency.assert_not_called()
        mock_stock.assert_not_called()

        # Проверяем структуру ответа
        assert result["cards"] == []
        assert result["top_transactions"] == []
        assert result["currency_rates"] == []
        assert result["stock_prices"] == []
        assert "message" in result
        assert "Нет транзакций" in result["message"]


def test_main_view_exception_handling() -> None:
    """Тестирует, что любое необработанное исключение внутри try
    перехватывается и возвращается словарь с ошибкой и сообщением."""
    # Тестовые данные
    test_date = "2021-12-21 14:30:00"

    # Имитируем ошибку в одном из вызовов (например, get_time_greeting)
    with patch("src.views.get_time_greeting", side_effect=Exception("Test error")):
        result = main_view(test_date)

        # Проверки
        assert "error" in result
        assert "Внутренняя ошибка сервера" in result["error"]
        assert "Test error" in result["error"]
