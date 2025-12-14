"""
Модели балансовых инструментов для ALM калькулятора.

Этот модуль содержит иерархию классов для представления балансовых позиций:
- Базовый класс Position
- Абстрактный класс BalanceSheetInstrument
- Специализированные классы для кредитов и депозитов (ЮЛ/ФЛ)
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Enums для типизации
# ============================================================================

class InstrumentType(str, Enum):
    """Типы финансовых инструментов"""
    LOAN_CORPORATE = "loan_corporate"
    LOAN_RETAIL = "loan_retail"
    DEPOSIT_CORPORATE = "deposit_corporate"
    DEPOSIT_RETAIL = "deposit_retail"
    BOND = "bond"
    EQUITY = "equity"
    CASH = "cash"
    OTHER = "other"


class CounterpartyType(str, Enum):
    """Типы контрагентов"""
    CORPORATE = "corporate"
    RETAIL = "retail"
    BANK = "bank"
    GOVERNMENT = "government"
    OTHER = "other"


class Currency(str, Enum):
    """Валюты"""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    CNY = "CNY"
    GBP = "GBP"


class RateType(str, Enum):
    """Типы процентных ставок"""
    FIXED = "fixed"
    FLOATING = "floating"
    ZERO = "zero"


class RepricingFrequency(str, Enum):
    """Частота пересмотра ставки (для floating)"""
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class AssetQuality(str, Enum):
    """Качество актива (для кредитов)"""
    STANDARD = "standard"
    WATCH = "watch"
    SUBSTANDARD = "substandard"
    DOUBTFUL = "doubtful"
    LOSS = "loss"


# ============================================================================
# Базовый класс Position
# ============================================================================

class Position(BaseModel):
    """
    Базовый класс для представления любой балансовой позиции.

    Содержит минимальный набор атрибутов, общих для всех инструментов.
    Все специализированные классы наследуются от него.

    Attributes:
        position_id: Уникальный идентификатор позиции (из КХД)
        as_of_date: Дата, на которую снят баланс
        instrument_type: Тип инструмента
        balance_account: Балансовый счет (по плану счетов банка)
        currency: Валюта позиции
        amount: Балансовая стоимость (в валюте позиции)
        counterparty_type: Тип контрагента
        metadata: Дополнительные метаданные (для расширяемости)
    """

    position_id: str = Field(..., description="Уникальный ID позиции")
    as_of_date: date = Field(..., description="Дата расчета")
    instrument_type: InstrumentType = Field(..., description="Тип инструмента")
    balance_account: str = Field(..., description="Балансовый счет")
    currency: Currency = Field(..., description="Валюта")
    amount: Decimal = Field(..., description="Сумма в валюте позиции")
    counterparty_type: CounterpartyType = Field(..., description="Тип контрагента")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные данные")

    @field_validator('amount')
    @classmethod
    def amount_must_be_nonzero(cls, v):
        """Сумма позиции не может быть нулевой"""
        if v == 0:
            raise ValueError('Amount cannot be zero')
        return v

    @field_validator('position_id')
    @classmethod
    def position_id_must_be_nonempty(cls, v):
        """ID позиции не может быть пустым"""
        if not v or not v.strip():
            raise ValueError('Position ID cannot be empty')
        return v.strip()

    class Config:
        frozen = False  # Позволяем модификацию (для применения assumptions)
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
        }


# ============================================================================
# Абстрактный класс BalanceSheetInstrument
# ============================================================================

class BalanceSheetInstrument(Position, ABC):
    """
    Абстрактный базовый класс для балансовых инструментов с процентными ставками.

    Расширяет Position добавлением атрибутов для инструментов с денежными потоками:
    - Даты (начало, погашение, репрайсинг)
    - Процентные ставки
    - Амортизация

    Все кредиты и депозиты наследуются от этого класса.
    """

    start_date: date = Field(..., description="Дата выдачи/открытия")
    maturity_date: Optional[date] = Field(None, description="Дата погашения (None для бессрочных)")

    rate: Optional[Decimal] = Field(None, description="Процентная ставка (годовых, в долях: 0.10 = 10%)")
    rate_type: RateType = Field(default=RateType.FIXED, description="Тип ставки")
    repricing_date: Optional[date] = Field(None, description="Дата следующего пересмотра ставки")
    repricing_frequency: Optional[RepricingFrequency] = Field(None, description="Частота репрайсинга")

    # Флаги для специальных инструментов
    is_amortizing: bool = Field(default=False, description="Есть ли амортизация основного долга")
    amortization_schedule: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="График амортизации [{date, principal, interest}, ...]"
    )

    @model_validator(mode='after')
    def validate_dates(self):
        """Валидация логики дат"""
        if self.start_date and self.as_of_date and self.start_date > self.as_of_date:
            raise ValueError(f'start_date ({self.start_date}) cannot be after as_of_date ({self.as_of_date})')

        if self.maturity_date and self.start_date and self.maturity_date <= self.start_date:
            raise ValueError(f'maturity_date ({self.maturity_date}) must be after start_date ({self.start_date})')

        if self.repricing_date and self.as_of_date and self.repricing_date < self.as_of_date:
            raise ValueError(f'repricing_date ({self.repricing_date}) cannot be before as_of_date ({self.as_of_date})')

        return self

    @model_validator(mode='after')
    def validate_rate_logic(self):
        """Валидация логики процентных ставок"""
        if self.rate_type == RateType.FLOATING:
            if not self.repricing_frequency:
                raise ValueError('floating rate requires repricing_frequency')
            if not self.repricing_date:
                raise ValueError('floating rate requires repricing_date')

        return self

    @abstractmethod
    def get_cash_flows(self, scenario: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Возвращает денежные потоки по инструменту.

        Args:
            scenario: Опциональный сценарий (стресс, behavioral assumptions и т.д.)

        Returns:
            List[Dict]: Список денежных потоков с полями:
                - date: дата платежа
                - principal: выплата основного долга
                - interest: выплата процентов
                - total: total = principal + interest
        """
        pass

    @abstractmethod
    def get_effective_maturity(self) -> Optional[date]:
        """
        Возвращает эффективную дату погашения с учетом behavioral assumptions.

        Для обычных инструментов = maturity_date.
        Для NMD (бессрочных депозитов) может быть рассчитана условная дата.

        Returns:
            Optional[date]: Эффективная дата погашения
        """
        pass

    def get_time_to_maturity_years(self) -> Optional[Decimal]:
        """
        Рассчитывает время до погашения в годах (для duration расчетов).

        Returns:
            Optional[Decimal]: Время в годах или None если нет maturity_date
        """
        effective_maturity = self.get_effective_maturity()
        if not effective_maturity:
            return None

        days = (effective_maturity - self.as_of_date).days
        return Decimal(days) / Decimal(365)

    def get_time_to_repricing_years(self) -> Optional[Decimal]:
        """
        Рассчитывает время до следующего репрайсинга в годах (для IRR gap analysis).

        Returns:
            Optional[Decimal]: Время в годах или None если нет repricing_date
        """
        if not self.repricing_date:
            return None

        days = (self.repricing_date - self.as_of_date).days
        return Decimal(days) / Decimal(365)


# ============================================================================
# Кредиты
# ============================================================================

class LoanBase(BalanceSheetInstrument):
    """
    Базовый класс для кредитов (общая логика для ЮЛ и ФЛ).

    Добавляет специфичные для кредитов атрибуты:
    - Качество актива
    - Резервы
    - Обеспечение
    - Early repayment опции
    """

    asset_quality: AssetQuality = Field(default=AssetQuality.STANDARD, description="Качество актива")
    provision_amount: Decimal = Field(default=Decimal(0), description="Сумма резервов (РВПС)")
    collateral_value: Optional[Decimal] = Field(None, description="Стоимость обеспечения")

    # Early repayment (досрочное погашение)
    allows_early_repayment: bool = Field(default=True, description="Возможно ли досрочное погашение")
    early_repayment_penalty: Optional[Decimal] = Field(None, description="Штраф за досрочное погашение (%)")

    # Behavioral assumptions (будут применены извне через AssumptionEngine)
    behavioral_prepayment_rate: Optional[Decimal] = Field(
        None,
        description="Модельная ставка досрочного погашения (CPR/SMM)"
    )

    @field_validator('provision_amount')
    @classmethod
    def provision_cannot_be_negative(cls, v):
        if v < 0:
            raise ValueError('Provision amount cannot be negative')
        return v

    def get_net_exposure(self) -> Decimal:
        """Возвращает чистую экспозицию (amount - provision)"""
        return self.amount - self.provision_amount

    def get_effective_maturity(self) -> Optional[date]:
        """
        Для кредитов эффективная дата = contractual maturity.

        Behavioral assumptions (prepayment) применяются через AssumptionEngine,
        который создаст новые synthetic позиции с adjusted maturity.
        """
        return self.maturity_date

    def get_cash_flows(self, scenario: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Базовая реализация денежных потоков для кредита.

        Простой случай: bullet loan (погашение в maturity_date).
        Для amortizing loans переопределяется в подклассах.

        Args:
            scenario: Опциональные сценарные параметры (для стресс-тестов)

        Returns:
            List[Dict]: Денежные потоки
        """
        if not self.maturity_date:
            logger.warning(f"Loan {self.position_id} has no maturity_date, cannot generate cash flows")
            return []

        cash_flows = []

        # Если есть график амортизации, используем его
        if self.is_amortizing and self.amortization_schedule:
            for payment in self.amortization_schedule:
                if payment['date'] >= self.as_of_date:
                    cash_flows.append({
                        'date': payment['date'],
                        'principal': Decimal(payment['principal']),
                        'interest': Decimal(payment['interest']),
                        'total': Decimal(payment['principal']) + Decimal(payment['interest'])
                    })
        else:
            # Bullet loan: principal в maturity, проценты можно рассчитать
            if self.rate:
                # Упрощение: считаем проценты за весь период до погашения
                time_to_maturity = self.get_time_to_maturity_years()
                if time_to_maturity:
                    interest = self.amount * self.rate * time_to_maturity
                else:
                    interest = Decimal(0)
            else:
                interest = Decimal(0)

            cash_flows.append({
                'date': self.maturity_date,
                'principal': self.amount,
                'interest': interest,
                'total': self.amount + interest
            })

        return cash_flows


class CorporateLoan(LoanBase):
    """
    Кредиты юридическим лицам.

    Особенности:
    - Обычно крупные суммы
    - Часто имеют floating rate
    - Могут иметь сложные структуры (синдицированные, револьверные)
    - Меньше prepayment risk по сравнению с retail
    """

    instrument_type: Literal[InstrumentType.LOAN_CORPORATE] = InstrumentType.LOAN_CORPORATE
    counterparty_type: Literal[CounterpartyType.CORPORATE] = CounterpartyType.CORPORATE

    # Специфичные для корпоративных кредитов поля
    industry_sector: Optional[str] = Field(None, description="Отрасль заемщика")
    borrower_rating: Optional[str] = Field(None, description="Внутренний рейтинг заемщика")
    is_syndicated: bool = Field(default=False, description="Синдицированный кредит")
    is_revolving: bool = Field(default=False, description="Револьверный кредит")

    # Для revolving credit: лимит и используемая часть
    credit_limit: Optional[Decimal] = Field(None, description="Лимит для револьверного кредита")

    @model_validator(mode='after')
    def validate_revolving_logic(self):
        """Валидация для револьверных кредитов"""
        if self.is_revolving and not self.credit_limit:
            raise ValueError('Revolving loan requires credit_limit')

        return self


class RetailLoan(LoanBase):
    """
    Кредиты физическим лицам.

    Особенности:
    - Обычно фиксированные ставки
    - Высокий prepayment risk (особенно ипотека)
    - Большое количество однородных позиций (можно группировать)
    - Важна сегментация по продуктам
    """

    instrument_type: Literal[InstrumentType.LOAN_RETAIL] = InstrumentType.LOAN_RETAIL
    counterparty_type: Literal[CounterpartyType.RETAIL] = CounterpartyType.RETAIL

    # Специфичные для розничных кредитов поля
    product_type: str = Field(..., description="Тип продукта: mortgage, consumer, auto, credit_card")
    borrower_age: Optional[int] = Field(None, description="Возраст заемщика")
    borrower_income: Optional[Decimal] = Field(None, description="Доход заемщика")

    # Для ипотеки
    is_mortgage: bool = Field(default=False, description="Ипотечный кредит")
    loan_to_value: Optional[Decimal] = Field(None, description="LTV ratio (для ипотеки)")

    @field_validator('product_type')
    @classmethod
    def validate_product_type(cls, v):
        """Валидация допустимых типов retail продуктов"""
        allowed_types = {'mortgage', 'consumer', 'auto', 'credit_card', 'other'}
        if v.lower() not in allowed_types:
            raise ValueError(f'product_type must be one of {allowed_types}')
        return v.lower()

    @model_validator(mode='after')
    def validate_mortgage_logic(self):
        """Валидация для ипотечных кредитов"""
        if self.is_mortgage and self.product_type != 'mortgage':
            raise ValueError('is_mortgage flag requires product_type=mortgage')

        return self


# ============================================================================
# Депозиты
# ============================================================================

class DepositBase(BalanceSheetInstrument):
    """
    Базовый класс для депозитов (общая логика для ЮЛ и ФЛ).

    Депозиты = пассивы банка, поэтому amount обычно положительный.

    Ключевые особенности:
    - Могут быть срочными (maturity_date) или до востребования (demand)
    - Для demand депозитов критичны behavioral assumptions
    - Обычно есть возможность досрочного изъятия (с штрафом или без)
    """

    is_demand_deposit: bool = Field(default=False, description="Депозит до востребования (NMD)")
    allows_early_withdrawal: bool = Field(default=True, description="Возможно ли досрочное изъятие")
    early_withdrawal_penalty: Optional[Decimal] = Field(None, description="Штраф за досрочное изъятие (%)")

    # Interest capitalization
    interest_capitalization: bool = Field(default=False, description="Капитализация процентов")

    # Behavioral assumptions
    behavioral_runoff_rate: Optional[Decimal] = Field(
        None,
        description="Модельная ставка оттока (для NMD)"
    )
    behavioral_core_portion: Optional[Decimal] = Field(
        None,
        description="Устойчивая часть депозита (для NMD)"
    )

    def get_effective_maturity(self) -> Optional[date]:
        """
        Для срочных депозитов = contractual maturity.
        Для NMD эффективная дата рассчитывается через AssumptionEngine.
        """
        return self.maturity_date

    def get_cash_flows(self, scenario: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Денежные потоки для депозита.

        Для срочных: principal + interest в maturity_date.
        Для NMD: потоки определяются через behavioral assumptions.

        Args:
            scenario: Опциональные сценарные параметры

        Returns:
            List[Dict]: Денежные потоки (отрицательные для пассивов)
        """
        cash_flows = []

        # Для demand депозитов без maturity_date возвращаем пустой список
        # (денежные потоки будут созданы AssumptionEngine на основе behavioral model)
        if self.is_demand_deposit and not self.maturity_date:
            logger.debug(f"Deposit {self.position_id} is NMD, cash flows will be generated by AssumptionEngine")
            return []

        if not self.maturity_date:
            return []

        # Для срочных депозитов
        if self.rate:
            time_to_maturity = self.get_time_to_maturity_years()
            if time_to_maturity:
                interest = self.amount * self.rate * time_to_maturity
            else:
                interest = Decimal(0)
        else:
            interest = Decimal(0)

        # Пассивы = отток денег, поэтому отрицательные значения
        cash_flows.append({
            'date': self.maturity_date,
            'principal': -self.amount,  # Отрицательное для пассива
            'interest': -interest,      # Отрицательное для пассива
            'total': -(self.amount + interest)
        })

        return cash_flows


class CorporateDeposit(DepositBase):
    """
    Депозиты юридических лиц.

    Особенности:
    - Обычно крупные суммы
    - Более волатильные чем retail (чувствительны к ставкам)
    - Операционные остатки (на расчетных счетах) могут быть устойчивыми
    """

    instrument_type: Literal[InstrumentType.DEPOSIT_CORPORATE] = InstrumentType.DEPOSIT_CORPORATE
    counterparty_type: Literal[CounterpartyType.CORPORATE] = CounterpartyType.CORPORATE

    # Специфичные для корпоративных депозитов поля
    is_operational: bool = Field(default=False, description="Операционный остаток (расчетный счет)")
    industry_sector: Optional[str] = Field(None, description="Отрасль вкладчика")
    depositor_rating: Optional[str] = Field(None, description="Внутренний рейтинг вкладчика")

    # Для operational balances может быть важна средняя величина
    average_balance_30d: Optional[Decimal] = Field(None, description="Средний остаток за 30 дней")
    average_balance_90d: Optional[Decimal] = Field(None, description="Средний остаток за 90 дней")


class RetailDeposit(DepositBase):
    """
    Депозиты физических лиц.

    Особенности:
    - Более стабильные чем corporate (особенно застрахованные вклады)
    - Важна сегментация по продуктам (срочные, до востребования, накопительные)
    - Behavioral assumptions критичны для demand deposits
    """

    instrument_type: Literal[InstrumentType.DEPOSIT_RETAIL] = InstrumentType.DEPOSIT_RETAIL
    counterparty_type: Literal[CounterpartyType.RETAIL] = CounterpartyType.RETAIL

    # Специфичные для розничных депозитов поля
    product_type: str = Field(..., description="Тип продукта: savings, time_deposit, current_account")
    is_insured: bool = Field(default=True, description="Участвует в системе страхования вкладов")
    insured_amount: Optional[Decimal] = Field(None, description="Застрахованная сумма")

    depositor_age: Optional[int] = Field(None, description="Возраст вкладчика")
    depositor_segment: Optional[str] = Field(None, description="Сегмент клиента: mass, affluent, private")

    @field_validator('product_type')
    @classmethod
    def validate_product_type(cls, v):
        """Валидация допустимых типов retail продуктов"""
        allowed_types = {'savings', 'time_deposit', 'current_account', 'other'}
        if v.lower() not in allowed_types:
            raise ValueError(f'product_type must be one of {allowed_types}')
        return v.lower()

    @model_validator(mode='after')
    def validate_insurance_logic(self):
        """Валидация логики страхования вкладов"""
        if self.is_insured and self.insured_amount is None and self.amount:
            # Автоматически устанавливаем insured_amount = min(amount, 1.4M RUB)
            # 1.4M RUB = лимит АСВ в России
            max_insurance = Decimal('1400000')
            self.insured_amount = min(self.amount, max_insurance)

        return self


# ============================================================================
# Вспомогательные функции
# ============================================================================

def create_position_from_dict(data: Dict[str, Any]) -> Position:
    """
    Factory функция для создания объекта позиции из словаря.

    Автоматически определяет нужный класс на основе instrument_type.

    Args:
        data: Словарь с данными позиции (например, строка из DataFrame)

    Returns:
        Position: Экземпляр соответствующего класса

    Raises:
        ValueError: Если instrument_type неизвестен
    """
    instrument_type = data.get('instrument_type')

    if not instrument_type:
        raise ValueError('instrument_type is required')

    # Маппинг типов на классы
    class_mapping = {
        InstrumentType.LOAN_CORPORATE: CorporateLoan,
        InstrumentType.LOAN_RETAIL: RetailLoan,
        InstrumentType.DEPOSIT_CORPORATE: CorporateDeposit,
        InstrumentType.DEPOSIT_RETAIL: RetailDeposit,
    }

    # Если передана строка, конвертируем в enum
    if isinstance(instrument_type, str):
        try:
            instrument_type = InstrumentType(instrument_type)
        except ValueError:
            raise ValueError(f'Unknown instrument_type: {instrument_type}')

    position_class = class_mapping.get(instrument_type)
    if not position_class:
        raise ValueError(f'No class mapping for instrument_type: {instrument_type}')

    return position_class(**data)


def positions_to_dataframe(positions: List[Position]) -> 'pd.DataFrame':
    """
    Конвертирует список позиций в pandas DataFrame.

    Args:
        positions: Список объектов Position

    Returns:
        pd.DataFrame: DataFrame с позициями
    """
    import pandas as pd

    data = [pos.dict() for pos in positions]
    return pd.DataFrame(data)


def dataframe_to_positions(df: 'pd.DataFrame') -> List[Position]:
    """
    Конвертирует pandas DataFrame в список позиций.

    Args:
        df: DataFrame с позициями

    Returns:
        List[Position]: Список объектов Position
    """
    import pandas as pd
    import numpy as np

    positions = []
    for _, row in df.iterrows():
        pos_dict = row.to_dict()

        # Заменяем NaN на None для Optional полей
        pos_dict = {k: (None if isinstance(v, float) and np.isnan(v) else v)
                    for k, v in pos_dict.items()}

        position = create_position_from_dict(pos_dict)
        positions.append(position)

    return positions
