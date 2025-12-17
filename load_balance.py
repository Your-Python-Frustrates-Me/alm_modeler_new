"""
Скрипт для загрузки и анализа баланса из CSV.
"""

import sys
import logging
from data.loaders.csv_loader import BalanceSheetLoader

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

if __name__ == "__main__":
    # Путь к файлу баланса
    csv_path = "data/sample/balance_sheet_2024-12-01.csv"

    print("Loading balance sheet from CSV...\n")

    # Создаем loader
    loader = BalanceSheetLoader()

    # Загружаем позиции
    positions = loader.load_from_csv(csv_path)

    # Печатаем сводку
    loader.print_summary()

    print(f"\n\nTotal positions loaded: {len(positions)}")
