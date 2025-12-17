"""
CSV Loader для загрузки балансовых позиций из CSV файлов.

Этот модуль:
1. Загружает данные из CSV в pandas DataFrame
2. Конвертирует DataFrame в объекты Position
3. Валидирует балансовые соотношения (Активы = Пассивы)
4. Поддерживает множественные валюты с конвертацией
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, datetime

from typing import List, Dict, Optional, Tuple
import logging
from decimal import Decimal

from models.positions import (
    Position,
    CorporateLoan,
    RetailLoan,
    CorporateDeposit,
    RetailDeposit,
    Bond,
    InstrumentType,
    create_position_from_dict,
)

logger = logging.getLogger(__name__)


class BalanceSheetLoader:
    """
    Loader для загрузки балансовых позиций из CSV.

    Основные функции:
    - Загрузка CSV с валидацией
    - Конвертация типов данных
    - Проверка баланса (Assets = Liabilities)
    - Статистика по валютам и типам инструментов
    """

    # Курсы валют к RUB (для примера, на 2024-12-01)
    # В production должны загружаться из внешнего источника
    FX_RATES_TO_RUB = {
        'RUB': Decimal('1.0'),
        'USD': Decimal('95.0'),
        'EUR': Decimal('105.0'),
        'CNY': Decimal('13.0'),
        'GBP': Decimal('120.0'),
    }

    def __init__(self, fx_rates: Optional[Dict[str, Decimal]] = None):
        """
        Инициализация loader.

        Args:
            fx_rates: Опциональные курсы валют к RUB.
                     Если не указаны, используются default курсы.
        """
        self.fx_rates = fx_rates or self.FX_RATES_TO_RUB
        self.positions: List[Position] = []
        self.df: Optional[pd.DataFrame] = None

    def load_from_csv(self, file_path: str) -> List[Position]:
        """
        Загружает позиции из CSV файла.

        Args:
            file_path: Путь к CSV файлу

        Returns:
            List[Position]: Список загруженных позиций

        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если данные невалидны
        """
        logger.info(f"Loading balance sheet from {file_path}")

        # Проверяем существование файла
        if not Path(file_path).exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Загружаем CSV
        self.df = pd.read_csv(file_path)
        logger.info(f"Loaded {len(self.df)} rows from CSV")

        # Конвертируем типы данных
        self._convert_datatypes()

        # Конвертируем в объекты Position
        self.positions = self._convert_to_positions()

        logger.info(f"Successfully created {len(self.positions)} position objects")

        return self.positions

    def _convert_datatypes(self):
        """Конвертирует типы данных DataFrame в нужные форматы"""

        # Даты
        date_columns = ['as_of_date', 'start_date', 'maturity_date', 'next_coupon_date']
        for col in date_columns:
            if col in self.df.columns:
                self.df[col] = pd.to_datetime(self.df[col], errors='coerce')
                # Конвертируем в date (не datetime)
                self.df[col] = self.df[col].apply(
                    lambda x: x.date() if pd.notna(x) else None
                )

        # Decimal числа (суммы)
        decimal_columns = [
            'amount', 'rate', 'provision_amount', 'collateral_value',
            'credit_limit', 'borrower_income', 'loan_to_value',
            'average_balance_30d', 'insured_amount', 'face_value',
            'coupon_rate', 'current_market_price', 'call_price', 'put_price'
        ]
        for col in decimal_columns:
            if col in self.df.columns:
                def safe_decimal(x):
                    if pd.isna(x) or str(x).strip() == '':
                        return None
                    try:
                        return Decimal(str(x))
                    except:
                        return None
                self.df[col] = self.df[col].apply(safe_decimal)

        # Integer числа
        int_columns = ['borrower_age', 'depositor_age']
        for col in int_columns:
            if col in self.df.columns:
                def safe_int(x):
                    if pd.isna(x) or str(x).strip() == '':
                        return None
                    try:
                        return int(float(x))
                    except:
                        return None
                self.df[col] = self.df[col].apply(safe_int)

        # Boolean
        bool_columns = [
            'is_syndicated', 'is_revolving', 'is_mortgage', 'is_operational',
            'is_insured', 'is_callable', 'is_puttable', 'is_investment_grade'
        ]
        for col in bool_columns:
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna(False).astype(bool)

        # String columns - ensure they are strings (pandas may auto-detect numeric strings as int)
        string_columns = [
            'balance_account', 'product_type', 'industry_sector', 'borrower_rating',
            'depositor_rating', 'depositor_segment', 'issuer', 'isin',
            'accounting_classification', 'credit_rating'
        ]
        for col in string_columns:
            if col in self.df.columns:
                def safe_string(x):
                    if pd.isna(x) or str(x).strip() == '':
                        return None
                    return str(x).strip()
                self.df[col] = self.df[col].apply(safe_string)

        logger.info("Data types converted successfully")

    def _convert_to_positions(self) -> List[Position]:
        """
        Конвертирует DataFrame в список объектов Position.

        Returns:
            List[Position]: Список позиций
        """
        positions = []
        errors = []

        for idx, row in self.df.iterrows():
            try:
                # Конвертируем строку в dict
                pos_dict = row.to_dict()

                # Убираем NaN/None значения, чтобы Pydantic использовал defaults
                # Также удаляем поля со значением None, чтобы не передавать их в модель
                pos_dict = {
                    k: v
                    for k, v in pos_dict.items()
                    if not (pd.isna(v) or v == '' or v is None)
                }

                # Создаем объект через factory функцию
                position = create_position_from_dict(pos_dict)
                positions.append(position)

            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                logger.error(f"Failed to convert row {idx}: {e}")

        if errors:
            logger.warning(f"Encountered {len(errors)} errors during conversion")
            for err in errors[:10]:  # Показываем первые 10 ошибок
                logger.warning(f"  {err}")

        return positions

    def verify_balance(self) -> Dict[str, any]:
        """
        Проверяет балансовое соотношение: Активы = Пассивы.

        Активы: кредиты (loans), облигации (bonds)
        Пассивы: депозиты (deposits)

        Returns:
            Dict со статистикой баланса
        """
        logger.info("Verifying balance sheet (Assets = Liabilities)")

        # Классифицируем инструменты
        assets = []
        liabilities = []

        for pos in self.positions:
            if pos.instrument_type in [
                InstrumentType.LOAN_CORPORATE,
                InstrumentType.LOAN_RETAIL,
                InstrumentType.BOND,
            ]:
                assets.append(pos)
            elif pos.instrument_type in [
                InstrumentType.DEPOSIT_CORPORATE,
                InstrumentType.DEPOSIT_RETAIL,
            ]:
                liabilities.append(pos)

        # Рассчитываем суммы по валютам
        assets_by_currency = self._sum_by_currency(assets)
        liabilities_by_currency = self._sum_by_currency(liabilities)

        # Конвертируем в RUB для общего баланса
        total_assets_rub = self._convert_to_rub(assets_by_currency)
        total_liabilities_rub = self._convert_to_rub(liabilities_by_currency)

        balance_diff = total_assets_rub - total_liabilities_rub
        is_balanced = abs(balance_diff) < Decimal('1')  # Допуск 1 руб

        result = {
            'is_balanced': is_balanced,
            'total_assets_rub': total_assets_rub,
            'total_liabilities_rub': total_liabilities_rub,
            'balance_difference_rub': balance_diff,
            'assets_by_currency': assets_by_currency,
            'liabilities_by_currency': liabilities_by_currency,
            'assets_count': len(assets),
            'liabilities_count': len(liabilities),
        }

        # Логируем результат
        if is_balanced:
            logger.info(f"✓ Balance sheet is BALANCED")
        else:
            logger.warning(f"✗ Balance sheet is UNBALANCED!")

        logger.info(f"  Total Assets:      {total_assets_rub:,.2f} RUB")
        logger.info(f"  Total Liabilities: {total_liabilities_rub:,.2f} RUB")
        logger.info(f"  Difference:        {balance_diff:,.2f} RUB")

        return result

    def _sum_by_currency(self, positions: List[Position]) -> Dict[str, Decimal]:
        """
        Суммирует позиции по валютам.

        Args:
            positions: Список позиций

        Returns:
            Dict[currency, total_amount]
        """
        result = {}

        for pos in positions:
            currency = str(pos.currency)
            if currency not in result:
                result[currency] = Decimal('0')
            result[currency] += pos.amount

        return result

    def _convert_to_rub(self, amounts_by_currency: Dict[str, Decimal]) -> Decimal:
        """
        Конвертирует суммы из разных валют в RUB.

        Args:
            amounts_by_currency: Dict[currency, amount]

        Returns:
            Decimal: Общая сумма в RUB
        """
        total_rub = Decimal('0')

        for currency, amount in amounts_by_currency.items():
            rate = self.fx_rates.get(currency, Decimal('1'))
            total_rub += amount * rate

        return total_rub

    def get_summary(self) -> pd.DataFrame:
        """
        Возвращает сводную таблицу по балансу.

        Returns:
            pd.DataFrame: Сводная таблица
        """
        if not self.positions:
            logger.warning("No positions loaded")
            return pd.DataFrame()

        summary_data = []

        for inst_type in InstrumentType:
            # Отбираем позиции данного типа
            type_positions = [
                p for p in self.positions
                if p.instrument_type == inst_type
            ]

            if not type_positions:
                continue

            # Группируем по валютам
            currency_amounts = self._sum_by_currency(type_positions)

            for currency, amount in currency_amounts.items():
                amount_rub = amount * self.fx_rates.get(currency, Decimal('1'))

                summary_data.append({
                    'instrument_type': inst_type.value,
                    'currency': currency,
                    'count': len([p for p in type_positions if str(p.currency) == currency]),
                    'amount': float(amount),
                    'amount_rub': float(amount_rub),
                })

        df = pd.DataFrame(summary_data)

        if not df.empty:
            # Сортируем
            df = df.sort_values(['instrument_type', 'currency'])

        return df

    def print_summary(self):
        """Печатает сводку по загруженным позициям"""

        print("\n" + "=" * 80)
        print("BALANCE SHEET SUMMARY")
        print("=" * 80)

        summary_df = self.get_summary()

        if summary_df.empty:
            print("No positions loaded")
            return

        # Группируем по типам инструментов
        print("\nBy Instrument Type and Currency:")
        print("-" * 80)

        for inst_type, group in summary_df.groupby('instrument_type'):
            print(f"\n{inst_type.upper()}:")
            for _, row in group.iterrows():
                print(f"  {row['currency']:3s}: {row['count']:3.0f} positions | "
                      f"{row['amount']:15,.0f} {row['currency']} | "
                      f"{row['amount_rub']:15,.0f} RUB")

        # Общие итоги
        print("\n" + "-" * 80)
        print("TOTALS:")

        total_by_type = summary_df.groupby('instrument_type').agg({
            'count': 'sum',
            'amount_rub': 'sum'
        }).reset_index()

        for _, row in total_by_type.iterrows():
            print(f"  {row['instrument_type']:20s}: {row['count']:3.0f} positions | "
                  f"{row['amount_rub']:15,.0f} RUB")

        # Баланс
        print("\n" + "=" * 80)
        balance_result = self.verify_balance()

        print(f"BALANCE CHECK:")
        print(f"  Assets:      {balance_result['total_assets_rub']:15,.2f} RUB")
        print(f"  Liabilities: {balance_result['total_liabilities_rub']:15,.2f} RUB")
        print(f"  Difference:  {balance_result['balance_difference_rub']:15,.2f} RUB")

        if balance_result['is_balanced']:
            print(f"  Status: ✓ BALANCED")
        else:
            print(f"  Status: ✗ UNBALANCED")

        print("=" * 80)


def load_balance_sheet(file_path: str) -> Tuple[List[Position], BalanceSheetLoader]:
    """
    Удобная функция для быстрой загрузки баланса.

    Args:
        file_path: Путь к CSV файлу

    Returns:
        Tuple[List[Position], BalanceSheetLoader]: Позиции и loader
    """
    loader = BalanceSheetLoader()
    positions = loader.load_from_csv(file_path)
    return positions, loader


if __name__ == "__main__":
    # Пример использования
    import sys

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Загружаем баланс
    csv_path = "data/sample/balance_sheet_2024-12-01.csv"

    loader = BalanceSheetLoader()
    positions = loader.load_from_csv(csv_path)

    # Печатаем сводку
    loader.print_summary()
