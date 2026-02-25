import json
import os
import pandas as pd
from typing import List, Dict, Any
from src.views import main_view
from src.utils import load_transactions
from src.services import calculate_cashback_by_category
from src.reports import spending_by_category
from src.reports import report_decorator


if __name__ == "__main__":
    # Формируем путь к файлу в папке data
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(current_dir, "data", "operations.xlsx")

    test_date = "2021-12-21 14:30:00"

    # Проверяем существование файла
    if not os.path.exists(file_path):
        print(f"Файл не найден по пути: {file_path}")
        # Завершаем выполнение, если файла нет
        exit(1)

    result: Any = main_view(test_date, file_path)
    print(json.dumps(result, ensure_ascii=False, indent=4))

    # Загружаем транзакции
    df: pd.DataFrame = load_transactions(file_path)

    # Приводим имена колонок к строке, чтобы ключи словарей были строками
    df.columns = df.columns.astype(str)

    # Преобразуем DataFrame в список словарей с гарантией строковых ключей
    transactions: List[Dict[str, Any]] = [
        {str(key): value for key, value in record.items()} for record in df.to_dict(orient="records")
    ]

    # Вычисляем кешбэк
    result_json = calculate_cashback_by_category(transactions, 2021, 12)
    print(result_json)

    # Настройка отображения результата для pandas
    # Показывать все столбцы
    pd.set_option("display.max_columns", None)
    # Ширина консоли
    pd.set_option("display.width", None)

    # Получение отчета по категории "Супермаркеты" за последние 3 месяца от 31.12.2021
    result_df: pd.DataFrame = spending_by_category(df, "Супермаркеты", "2021-12-31")
    print(result_df)

    # Использование декоратора для автоматического сохранения в JSON
    @report_decorator(filename="supermarkets.json")
    def get_report() -> pd.DataFrame:
        return spending_by_category(df, "Супермаркеты")
