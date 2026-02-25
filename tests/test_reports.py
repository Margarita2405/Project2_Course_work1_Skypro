import pandas as pd
import json
import os
import tempfile
import shutil
from unittest.mock import patch
from pathlib import Path
from pytest import MonkeyPatch
from src.reports import spending_by_category, report_decorator


def test_spending_by_category_filter(sample_transactions: pd.DataFrame) -> None:
    """Проверка фильтрации по категории и дате."""
    result = spending_by_category(sample_transactions, "Супермаркеты", "2021-12-31")
    # Период: с 2021-10-01 по 2021-12-31 включительно
    # Подходят: 31.12.2021, 01.11.2021, 01.10.2021 -> 3 транзакции
    assert len(result) == 3
    assert all(result["Сумма операции"] < 0)


def test_spending_by_category_no_date(sample_transactions: pd.DataFrame) -> None:
    """Проверка работы без указания даты (используется текущая)."""
    with patch("src.reports.datetime") as mock_datetime:
        # Задаём фиксированное значение для datetime.now()
        mock_datetime.now.return_value = pd.Timestamp("2022-01-15")

        result = spending_by_category(sample_transactions, "Супермаркеты")

        # Ожидаемый период: 2021-10-15.. 2022-01-15
        # В sample_transactions подходят операции: 31.12.2021 и 01.11.2021 -> 2
        assert len(result) == 2
        assert all(result["Сумма операции"] < 0)


def test_decorator_default_filename(sample_transactions: pd.DataFrame) -> None:
    """Декоратор без параметра должен создать файл с именем по умолчанию."""
    # Создаем временную папку
    tmpdir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    os.chdir(tmpdir)

    try:

        @report_decorator()
        def test_func() -> pd.DataFrame:
            return spending_by_category(sample_transactions, "Супермаркеты", "2022-01-01")

        test_func()
        files = os.listdir(tmpdir)
        assert len(files) == 1
        filename = files[0]
        assert filename.startswith("report_") and filename.endswith(".json")

        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, list)
        assert len(data) == 3
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmpdir)  # удаляем временную папку


def test_decorator_custom_filename(
    sample_transactions: pd.DataFrame, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Декоратор с параметром должен сохранить отчёт в указанный файл."""
    # Создаем временную папку
    tmpdir = tempfile.mkdtemp()
    # Указываем путь к файлу во временной папке
    custom_file = os.path.join(tmpdir, "my_supermarket_report.json")

    try:

        @report_decorator(filename=custom_file)
        def test_func() -> pd.DataFrame:
            return spending_by_category(sample_transactions, "Супермаркеты", "2022-01-01")

        test_func()
        assert os.path.exists(custom_file)

        with open(custom_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        assert len(data) == 3
    finally:
        # Удаляем файл и папку
        os.remove(custom_file)
        os.rmdir(tmpdir)
