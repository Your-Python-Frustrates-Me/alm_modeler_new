"""
Модуль для анализа ликвидности.

Основные функции:
1. Гэп-анализ ликвидности по временным бакетам
2. Расчет кумулятивного гэпа
3. Расчет коэффициентов ликвидности (LCR, NSFR и т.д.)
4. Экспорт результатов в Excel

Бакеты используют контрактные сроки (maturity_date).
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging

from models.positions import (
    Position,
    InstrumentType,
    Currency,
)

logger = logging.getLogger(__name__)


class LiquidityGapAnalyzer:
    """
    Анализатор ликвидности.

    Выполняет гэп-анализ по временным бакетам на основе контрактных сроков погашения.

    Attributes:
        positions: Список позиций для анализа
        as_of_date: Дата анализа
        buckets: Определения временных бакетов
        fx_rates: Курсы валют для конвертации в базовую валюту
    """

    # Курсы валют к рублю (для конвертации)
    DEFAULT_FX_RATES = {
        Currency.RUB: Decimal('1.0'),
        Currency.USD: Decimal('95.0'),
        Currency.EUR: Decimal('105.0'),
        Currency.CNY: Decimal('13.0'),
    }

    def __init__(
        self,
        positions: List[Position],
        as_of_date: Optional[date] = None,
        fx_rates: Optional[Dict[Currency, Decimal]] = None,
        base_currency: Currency = Currency.RUB,
    ):
        """
        Инициализация анализатора.

        Args:
            positions: Список позиций для анализа
            as_of_date: Дата анализа (если None, используется текущая дата)
            fx_rates: Курсы валют (если None, используются дефолтные)
            base_currency: Базовая валюта для отчета
        """
        self.positions = positions
        self.as_of_date = as_of_date or date.today()
        self.fx_rates = fx_rates or self.DEFAULT_FX_RATES
        self.base_currency = base_currency

        # Определяем стандартные временные бакеты
        self.buckets = self._define_buckets()

        # Результаты анализа
        self.gap_df: Optional[pd.DataFrame] = None
        self.full_gap = None
        self.summary_df: Optional[pd.DataFrame] = None

        logger.info(f"Initialized LiquidityGapAnalyzer with {len(positions)} positions as of {self.as_of_date}")

    def _define_buckets(self) -> List[Tuple[str, int, Optional[int]]]:
        """
        Определяет временные бакеты для анализа.

        Returns:
            List of tuples: (bucket_name, days_from, days_to)
            days_to = None означает бесконечность
        """
        buckets = [
            ('Overnight', 0, 0),
            ('1-7 days', 1, 7),
            ('8-30 days', 8, 30),
            ('1-3 months', 31, 90),
            ('3-6 months', 91, 180),
            ('6-12 months', 181, 365),
            ('1-2 years', 366, 730),
            ('2-3 years', 731, 1095),
            ('3-5 years', 1096, 1825),
            ('5+ years', 1826, None),
        ]
        return buckets

    def _get_bucket(self, days_to_maturity: Optional[int]) -> str:
        """
        Определяет бакет для заданного количества дней до погашения.

        Args:
            days_to_maturity: Количество дней до погашения (None = perpetual)

        Returns:
            Название бакета
        """
        if days_to_maturity is None:
            return '5+ years'  # Perpetual instruments go to longest bucket

        for bucket_name, days_from, days_to in self.buckets:
            if days_to is None:
                if days_to_maturity >= days_from:
                    return bucket_name
            else:
                if days_from <= days_to_maturity <= days_to:
                    return bucket_name

        # Если не попало ни в один бакет (например, отрицательные дни)
        return 'Overdue'

    def _calculate_days_to_maturity(self, maturity_date: Optional[date]) -> Optional[int]:
        """
        Рассчитывает количество дней до погашения.

        Args:
            maturity_date: Дата погашения

        Returns:
            Количество дней (None для perpetual instruments)
        """
        if maturity_date is None:
            return None

        delta = maturity_date - self.as_of_date
        return delta.days

    def _convert_to_base_currency(self, amount: Decimal, currency: Currency) -> Decimal:
        """
        Конвертирует сумму в базовую валюту.

        Args:
            amount: Сумма в исходной валюте
            currency: Исходная валюта

        Returns:
            Сумма в базовой валюте
        """
        if currency == self.base_currency:
            return amount

        fx_rate = self.fx_rates.get(currency)
        if fx_rate is None:
            logger.warning(f"FX rate not found for {currency}, using 1.0")
            fx_rate = Decimal('1.0')

        return amount * fx_rate

    def _classify_position(self, position: Position) -> str:
        """
        Классифицирует позицию как актив или пассив.

        Args:
            position: Позиция

        Returns:
            'Asset' или 'Liability'
        """
        if position.instrument_type in [
            InstrumentType.LOAN_CORPORATE,
            InstrumentType.LOAN_RETAIL,
            InstrumentType.BOND,
        ]:
            return 'Asset'
        elif position.instrument_type in [
            InstrumentType.DEPOSIT_CORPORATE,
            InstrumentType.DEPOSIT_RETAIL,
        ]:
            return 'Liability'
        else:
            logger.warning(f"Unknown instrument type for classification: {position.instrument_type}")
            return 'Unknown'

    def calculate_gap(self) -> pd.DataFrame:
        """
        Рассчитывает гэп ликвидности по временным бакетам.

        Использует контрактные сроки погашения (maturity_date).

        Returns:
            DataFrame с гэпом по бакетам
        """
        logger.info("Calculating liquidity gap by buckets...")

        # Собираем данные по каждой позиции
        data = []
        for pos in self.positions:
            days_to_maturity = self._calculate_days_to_maturity(
                getattr(pos, 'maturity_date', None)
            )
            bucket = self._get_bucket(days_to_maturity)
            classification = self._classify_position(pos)
            amount_base = self._convert_to_base_currency(pos.amount, pos.currency)

            data.append({
                'position_id': pos.position_id,
                'instrument_type': pos.instrument_type.value if hasattr(pos.instrument_type, 'value') else pos.instrument_type,
                'currency': pos.currency.value if hasattr(pos.currency, 'value') else pos.currency,
                'amount': pos.amount,
                'amount_base': amount_base,
                'maturity_date': getattr(pos, 'maturity_date', None),
                'days_to_maturity': days_to_maturity,
                'bucket': bucket,
                'classification': classification,
            })

        df = pd.DataFrame(data)

        # Создаем сводную таблицу по бакетам
        pivot = df.pivot_table(
            values='amount_base',
            index='bucket',
            columns='classification',
            aggfunc='sum',
            fill_value=0
        )

        full_pivot = df.pivot_table(values='amount_base', index='bucket', columns='instrument_type', aggfunc='sum', fill_value=0)

        # Упорядочиваем бакеты
        bucket_order = [b[0] for b in self.buckets] + ['Overdue']
        pivot = pivot.reindex([b for b in bucket_order if b in pivot.index])
        full_pivot = full_pivot.reindex([b for b in bucket_order if b in pivot.index])

        # Добавляем колонки с расчетами
        if 'Asset' not in pivot.columns:
            pivot['Asset'] = 0
        if 'Liability' not in pivot.columns:
            pivot['Liability'] = 0
        if 'Asset' not in full_pivot.columns:
            full_pivot['Asset'] = 0
        if 'Liability' not in full_pivot.columns:
            full_pivot['Liability'] = 0

        pivot['Gap'] = pivot['Asset'] - pivot['Liability']
        pivot['Cumulative Gap'] = pivot['Gap'].cumsum()

        full_pivot['Gap'] = full_pivot['Asset'] - full_pivot['Liability']
        full_pivot['Cumulative Gap'] = full_pivot['Gap'].cumsum()

        # Добавляем строку Total
        total_row = pd.DataFrame({
            'Asset': [pivot['Asset'].sum()],
            'Liability': [pivot['Liability'].sum()],
            'Gap': [pivot['Gap'].sum()],
            'Cumulative Gap': [pivot['Cumulative Gap'].iloc[-1] if len(pivot) > 0 else 0],
        }, index=['TOTAL'])

        pivot = pd.concat([pivot, total_row])

        self.gap_df = pivot
        self.full_gap = full_pivot.T
        logger.info(f"Gap analysis completed for {len(bucket_order)} buckets")

        return pivot

    def calculate_summary_by_currency(self) -> pd.DataFrame:
        """
        Создает сводку по валютам и инструментам.

        Returns:
            DataFrame со сводкой
        """
        logger.info("Calculating summary by currency and instrument type...")

        data = []
        for pos in self.positions:
            classification = self._classify_position(pos)
            amount_base = self._convert_to_base_currency(pos.amount, pos.currency)

            data.append({
                'instrument_type': pos.instrument_type.value if hasattr(pos.instrument_type, 'value') else pos.instrument_type,
                'currency': pos.currency.value if hasattr(pos.currency, 'value') else pos.currency,
                'classification': classification,
                'amount': pos.amount,
                'amount_base': amount_base,
                'count': 1,
            })

        df = pd.DataFrame(data)

        # Группировка по типу инструмента и валюте
        summary = df.groupby(['classification', 'instrument_type', 'currency']).agg({
            'amount': 'sum',
            'amount_base': 'sum',
            'count': 'sum',
        }).reset_index()

        summary = summary.sort_values(['classification', 'instrument_type', 'currency'])

        self.summary_df = summary
        logger.info(f"Summary calculated: {len(summary)} rows")

        return summary

    def calculate_ratios(self) -> Dict[str, float]:
        """
        Рассчитывает основные коэффициенты ликвидности.

        Returns:
            Словарь с коэффициентами
        """
        if self.gap_df is None:
            self.calculate_gap()

        # Liquid assets (до 30 дней)
        liquid_buckets = ['Overnight', '1-7 days', '8-30 days']
        liquid_assets = sum(
            self.gap_df.loc[bucket, 'Asset']
            for bucket in liquid_buckets
            if bucket in self.gap_df.index
        )

        # Short-term liabilities (до 30 дней)
        st_liabilities = sum(
            self.gap_df.loc[bucket, 'Liability']
            for bucket in liquid_buckets
            if bucket in self.gap_df.index
        )

        # Total assets and liabilities
        total_assets = self.gap_df.loc['TOTAL', 'Asset']
        total_liabilities = self.gap_df.loc['TOTAL', 'Liability']

        ratios = {
            'liquid_assets': float(liquid_assets),
            'short_term_liabilities': float(st_liabilities),
            'liquidity_coverage_ratio': float(liquid_assets / st_liabilities) if st_liabilities > 0 else float('inf'),
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'gap_30d': float(sum(
                self.gap_df.loc[bucket, 'Gap']
                for bucket in liquid_buckets
                if bucket in self.gap_df.index
            )),
            'cumulative_gap_30d': float(sum(
                self.gap_df.loc[bucket, 'Gap']
                for bucket in liquid_buckets
                if bucket in self.gap_df.index
            )),
        }

        logger.info(f"Calculated ratios: LCR={ratios['liquidity_coverage_ratio']:.2f}, Gap 30d={ratios['gap_30d']:,.0f}")

        return ratios

    def export_to_excel(self, file_path: str):
        """
        Экспортирует результаты анализа в Excel файл.

        Args:
            file_path: Путь к файлу Excel для сохранения
        """
        logger.info(f"Exporting liquidity analysis to {file_path}...")

        # Убеждаемся что расчеты выполнены
        if self.gap_df is None:
            self.calculate_gap()
        if self.summary_df is None:
            self.calculate_summary_by_currency()

        # Рассчитываем коэффициенты
        ratios = self.calculate_ratios()

        # Создаем DataFrame для коэффициентов
        ratios_df = pd.DataFrame([
            {'Metric': 'Liquid Assets (0-30d)', 'Value': ratios['liquid_assets'], 'Unit': self.base_currency.value},
            {'Metric': 'Short-term Liabilities (0-30d)', 'Value': ratios['short_term_liabilities'], 'Unit': self.base_currency.value},
            {'Metric': 'Liquidity Coverage Ratio', 'Value': ratios['liquidity_coverage_ratio'], 'Unit': '%'},
            {'Metric': 'Gap 30 days', 'Value': ratios['gap_30d'], 'Unit': self.base_currency.value},
            {'Metric': 'Total Assets', 'Value': ratios['total_assets'], 'Unit': self.base_currency.value},
            {'Metric': 'Total Liabilities', 'Value': ratios['total_liabilities'], 'Unit': self.base_currency.value},
        ])

        # Создаем DataFrame с параметрами анализа
        params_df = pd.DataFrame([
            {'Parameter': 'As of Date', 'Value': str(self.as_of_date)},
            {'Parameter': 'Base Currency', 'Value': self.base_currency.value},
            {'Parameter': 'Number of Positions', 'Value': len(self.positions)},
            {'Parameter': 'Analysis Date', 'Value': str(date.today())},
        ])

        # Записываем в Excel
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Лист 1: Гэп по бакетам
            self.gap_df.to_excel(writer, sheet_name='Liquidity Gap')

            # Лист 2: Сводка по валютам
            self.summary_df.to_excel(writer, sheet_name='Summary by Currency', index=False)

            # Лист 3: Коэффициенты
            ratios_df.to_excel(writer, sheet_name='Ratios', index=False)

            # Лист 4: Параметры анализа
            params_df.to_excel(writer, sheet_name='Parameters', index=False)

            logger.info(f"Excel file saved with 4 sheets")

        logger.info(f"Successfully exported liquidity analysis to {file_path}")

    def print_gap_report(self):
        """Выводит отчет по гэпу ликвидности в консоль."""
        if self.gap_df is None:
            self.calculate_gap()

        print("\n" + "=" * 100)
        print("LIQUIDITY GAP ANALYSIS")
        print("=" * 100)
        print(f"As of Date: {self.as_of_date}")
        print(f"Base Currency: {self.base_currency.value}")
        print(f"Number of Positions: {len(self.positions)}")
        print("-" * 100)

        # Форматируем вывод
        print(f"\n{'Bucket':<20} {'Assets':>18} {'Liabilities':>18} {'Gap':>18} {'Cumulative Gap':>18}")
        print("-" * 100)

        for bucket in self.gap_df.index:
            row = self.gap_df.loc[bucket]
            print(f"{bucket:<20} {row['Asset']:>18,.0f} {row['Liability']:>18,.0f} {row['Gap']:>18,.0f} {row['Cumulative Gap']:>18,.0f}")

        print("=" * 100)

        # Выводим ключевые метрики
        ratios = self.calculate_ratios()
        print("\nKEY METRICS:")
        print(f"  Liquidity Coverage Ratio (LCR): {ratios['liquidity_coverage_ratio']:.2%}")
        print(f"  Gap 30 days: {ratios['gap_30d']:,.0f} {self.base_currency.value}")
        print(f"  Total Gap: {ratios['total_assets'] - ratios['total_liabilities']:,.0f} {self.base_currency.value}")
        print("=" * 100 + "\n")
