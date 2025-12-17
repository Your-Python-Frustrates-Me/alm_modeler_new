from decimal import Decimal
"""
Unit тесты для классов балансовых инструментов.

Покрывают:
- Создание объектов
- Валидацию полей
- Расчет метрик (time to maturity, cash flows и т.д.)
- Конвертацию между форматами
"""

import pytest
from datetime import date, timedelta

import pandas as pd

from models.positions import (
    CorporateLoan,
    RetailLoan,
    CorporateDeposit,
    RetailDeposit,
    Currency,
    RateType,
    AssetQuality,
    RepricingFrequency,
    InstrumentType,
    create_position_from_dict,
    positions_to_dataframe,
    dataframe_to_positions,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def as_of_date():
    """Дата расчета для тестов"""
    return date(2024, 12, 1)


@pytest.fixture
def corporate_loan_data(as_of_date):
    """Базовые данные для корпоративного кредита"""
    return {
        'position_id': 'TEST_CORP_LOAN_001',
        'as_of_date': as_of_date,
        'balance_account': '45203',
        'currency': Currency.RUB,
        'amount': Decimal('10000000'),
        'start_date': date(2024, 1, 1),
        'maturity_date': date(2027, 1, 1),
        'rate': Decimal('0.15'),
        'rate_type': RateType.FIXED,
        'industry_sector': 'Manufacturing',
        'borrower_rating': 'BBB',
    }


@pytest.fixture
def retail_deposit_data(as_of_date):
    """Базовые данные для розничного депозита"""
    return {
        'position_id': 'TEST_RETAIL_DEP_001',
        'as_of_date': as_of_date,
        'balance_account': '42307',
        'currency': Currency.RUB,
        'amount': Decimal('500000'),
        'start_date': date(2022, 3, 15),
        'maturity_date': None,  # NMD
        'rate': Decimal('0.005'),
        'rate_type': RateType.FIXED,
        'is_demand_deposit': True,
        'product_type': 'current_account',
        'is_insured': True,
    }


# ============================================================================
# Тесты создания объектов
# ============================================================================

class TestObjectCreation:
    """Тесты создания объектов различных классов"""

    def test_create_corporate_loan(self, corporate_loan_data):
        """Создание корпоративного кредита с валидными данными"""
        loan = CorporateLoan(**corporate_loan_data)

        assert loan.position_id == 'TEST_CORP_LOAN_001'
        assert loan.amount == Decimal('10000000')
        assert loan.currency == Currency.RUB
        assert loan.instrument_type == InstrumentType.LOAN_CORPORATE
        assert loan.rate == Decimal('0.15')

    def test_create_retail_loan(self, as_of_date):
        """Создание розничного кредита (ипотека)"""
        loan = RetailLoan(
            position_id='TEST_RETAIL_LOAN_001',
            as_of_date=as_of_date,
            balance_account='45507',
            currency=Currency.RUB,
            amount=Decimal('3000000'),
            start_date=date(2020, 6, 1),
            maturity_date=date(2040, 6, 1),
            rate=Decimal('0.095'),
            product_type='mortgage',
            is_mortgage=True,
            loan_to_value=Decimal('0.67'),
        )

        assert loan.instrument_type == InstrumentType.LOAN_RETAIL
        assert loan.product_type == 'mortgage'
        assert loan.is_mortgage is True
        assert loan.loan_to_value == Decimal('0.67')

    def test_create_corporate_deposit(self, as_of_date):
        """Создание корпоративного депозита"""
        deposit = CorporateDeposit(
            position_id='TEST_CORP_DEP_001',
            as_of_date=as_of_date,
            balance_account='42301',
            currency=Currency.RUB,
            amount=Decimal('20000000'),
            start_date=date(2024, 9, 1),
            maturity_date=date(2025, 3, 1),
            rate=Decimal('0.14'),
            is_operational=False,
        )

        assert deposit.instrument_type == InstrumentType.DEPOSIT_CORPORATE
        assert deposit.amount == Decimal('20000000')
        assert deposit.is_operational is False

    def test_create_retail_deposit_nmd(self, retail_deposit_data):
        """Создание розничного депозита до востребования"""
        deposit = RetailDeposit(**retail_deposit_data)

        assert deposit.instrument_type == InstrumentType.DEPOSIT_RETAIL
        assert deposit.is_demand_deposit is True
        assert deposit.maturity_date is None
        assert deposit.product_type == 'current_account'


# ============================================================================
# Тесты валидации
# ============================================================================

class TestValidation:
    """Тесты валидации входных данных"""

    def test_zero_amount_raises_error(self, corporate_loan_data):
        """Нулевая сумма должна вызывать ошибку"""
        corporate_loan_data['amount'] = Decimal('0')

        with pytest.raises(ValueError, match='Amount cannot be zero'):
            CorporateLoan(**corporate_loan_data)

    def test_empty_position_id_raises_error(self, corporate_loan_data):
        """Пустой position_id должен вызывать ошибку"""
        corporate_loan_data['position_id'] = ''

        with pytest.raises(ValueError, match='Position ID cannot be empty'):
            CorporateLoan(**corporate_loan_data)

    def test_maturity_before_start_raises_error(self, corporate_loan_data):
        """maturity_date раньше start_date должен вызывать ошибку"""
        corporate_loan_data['maturity_date'] = date(2023, 1, 1)  # Раньше start_date

        with pytest.raises(ValueError, match='maturity_date .* must be after start_date'):
            CorporateLoan(**corporate_loan_data)

    def test_start_date_after_as_of_date_raises_error(self, corporate_loan_data):
        """start_date позже as_of_date должен вызывать ошибку"""
        corporate_loan_data['start_date'] = date(2025, 1, 1)  # Позже as_of_date

        with pytest.raises(ValueError, match='start_date .* cannot be after as_of_date'):
            CorporateLoan(**corporate_loan_data)

    def test_floating_rate_without_repricing_raises_error(self, corporate_loan_data):
        """Floating rate без repricing_frequency должен вызывать ошибку"""
        corporate_loan_data['rate_type'] = RateType.FLOATING
        # Нет repricing_frequency

        with pytest.raises(ValueError, match='floating rate requires repricing_frequency'):
            CorporateLoan(**corporate_loan_data)

    def test_negative_provision_raises_error(self, corporate_loan_data):
        """Отрицательные резервы должны вызывать ошибку"""
        corporate_loan_data['provision_amount'] = Decimal('-100')

        with pytest.raises(ValueError, match='Provision amount cannot be negative'):
            CorporateLoan(**corporate_loan_data)

    def test_mortgage_with_wrong_product_type_raises_error(self, as_of_date):
        """is_mortgage=True с неправильным product_type должен вызывать ошибку"""
        with pytest.raises(ValueError, match='is_mortgage flag requires product_type=mortgage'):
            RetailLoan(
                position_id='TEST',
                as_of_date=as_of_date,
                balance_account='45507',
                currency=Currency.RUB,
                amount=Decimal('3000000'),
                start_date=date(2020, 6, 1),
                maturity_date=date(2040, 6, 1),
                rate=Decimal('0.095'),
                product_type='consumer',  # Не mortgage!
                is_mortgage=True,  # Ошибка
            )

    def test_invalid_retail_product_type_raises_error(self, as_of_date):
        """Некорректный product_type для retail loan должен вызывать ошибку"""
        with pytest.raises(ValueError, match='product_type must be one of'):
            RetailLoan(
                position_id='TEST',
                as_of_date=as_of_date,
                balance_account='45507',
                currency=Currency.RUB,
                amount=Decimal('3000000'),
                start_date=date(2020, 6, 1),
                maturity_date=date(2040, 6, 1),
                rate=Decimal('0.095'),
                product_type='invalid_type',  # Неправильный тип
            )


# ============================================================================
# Тесты расчетных методов
# ============================================================================

class TestCalculationMethods:
    """Тесты методов расчета метрик"""

    def test_get_time_to_maturity_years(self, corporate_loan_data):
        """Расчет времени до погашения в годах"""
        loan = CorporateLoan(**corporate_loan_data)

        # as_of_date = 2024-12-01, maturity_date = 2027-01-01
        # Разница = ~2.08 года
        time_to_maturity = loan.get_time_to_maturity_years()

        assert time_to_maturity is not None
        assert isinstance(time_to_maturity, Decimal)
        assert Decimal('2.0') < time_to_maturity < Decimal('2.2')

    def test_get_time_to_maturity_for_nmd_returns_none(self, retail_deposit_data):
        """Для NMD без maturity_date должен возвращать None"""
        deposit = RetailDeposit(**retail_deposit_data)

        time_to_maturity = deposit.get_time_to_maturity_years()

        assert time_to_maturity is None

    def test_get_net_exposure(self, corporate_loan_data):
        """Расчет чистой экспозиции (с резервами)"""
        corporate_loan_data['provision_amount'] = Decimal('100000')
        loan = CorporateLoan(**corporate_loan_data)

        net_exposure = loan.get_net_exposure()

        assert net_exposure == Decimal('9900000')  # 10M - 100k

    def test_get_cash_flows_bullet_loan(self, corporate_loan_data):
        """Денежные потоки для bullet loan"""
        loan = CorporateLoan(**corporate_loan_data)

        cash_flows = loan.get_cash_flows()

        assert len(cash_flows) == 1
        assert cash_flows[0]['date'] == date(2027, 1, 1)
        assert cash_flows[0]['principal'] == Decimal('10000000')
        assert cash_flows[0]['interest'] > 0  # Есть проценты

    def test_get_cash_flows_deposit_negative(self, as_of_date):
        """Денежные потоки для депозита (отрицательные для пассивов)"""
        deposit = CorporateDeposit(
            position_id='TEST',
            as_of_date=as_of_date,
            balance_account='42301',
            currency=Currency.RUB,
            amount=Decimal('10000000'),
            start_date=date(2024, 9, 1),
            maturity_date=date(2025, 3, 1),
            rate=Decimal('0.10'),
        )

        cash_flows = deposit.get_cash_flows()

        assert len(cash_flows) == 1
        assert cash_flows[0]['principal'] < 0  # Отрицательный для пассива
        assert cash_flows[0]['interest'] < 0  # Отрицательный для пассива

    def test_get_cash_flows_nmd_returns_empty(self, retail_deposit_data):
        """Денежные потоки для NMD должны быть пустыми (генерируются AssumptionEngine)"""
        deposit = RetailDeposit(**retail_deposit_data)

        cash_flows = deposit.get_cash_flows()

        assert len(cash_flows) == 0


# ============================================================================
# Тесты конвертации между форматами
# ============================================================================

class TestConversion:
    """Тесты конвертации между dict/DataFrame и объектами"""

    def test_create_from_dict_corporate_loan(self, as_of_date):
        """Создание через factory функцию из dict"""
        data = {
            'position_id': 'TEST_001',
            'as_of_date': as_of_date,
            'instrument_type': 'loan_corporate',  # Строка
            'balance_account': '45203',
            'currency': 'RUB',
            'amount': Decimal('10000000'),
            'counterparty_type': 'corporate',
            'start_date': date(2024, 1, 1),
            'maturity_date': date(2027, 1, 1),
            'rate': Decimal('0.15'),
            'rate_type': 'fixed',
        }

        position = create_position_from_dict(data)

        assert isinstance(position, CorporateLoan)
        assert position.position_id == 'TEST_001'
        assert position.amount == Decimal('10000000')

    def test_create_from_dict_invalid_type_raises_error(self, as_of_date):
        """Неизвестный instrument_type должен вызывать ошибку"""
        data = {
            'position_id': 'TEST_001',
            'as_of_date': as_of_date,
            'instrument_type': 'invalid_type',
            'balance_account': '45203',
            'currency': 'RUB',
            'amount': Decimal('10000000'),
        }

        with pytest.raises(ValueError, match='Unknown instrument_type'):
            create_position_from_dict(data)

    def test_positions_to_dataframe(self, corporate_loan_data, retail_deposit_data):
        """Конвертация списка позиций в DataFrame"""
        positions = [
            CorporateLoan(**corporate_loan_data),
            RetailDeposit(**retail_deposit_data),
        ]

        df = positions_to_dataframe(positions)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'position_id' in df.columns
        assert 'amount' in df.columns
        assert 'instrument_type' in df.columns

    def test_dataframe_to_positions(self, corporate_loan_data, retail_deposit_data):
        """Конвертация DataFrame в список позиций"""
        positions_original = [
            CorporateLoan(**corporate_loan_data),
            RetailDeposit(**retail_deposit_data),
        ]

        df = positions_to_dataframe(positions_original)
        positions_back = dataframe_to_positions(df)

        assert len(positions_back) == 2
        assert isinstance(positions_back[0], CorporateLoan)
        assert isinstance(positions_back[1], RetailDeposit)
        assert positions_back[0].position_id == positions_original[0].position_id


# ============================================================================
# Тесты воспроизводимости
# ============================================================================

class TestReproducibility:
    """Тесты воспроизводимости расчетов"""

    def test_same_inputs_same_outputs(self, corporate_loan_data):
        """Одинаковые входы должны давать одинаковые выходы"""
        loan1 = CorporateLoan(**corporate_loan_data)
        loan2 = CorporateLoan(**corporate_loan_data)

        # Проверяем все ключевые метрики
        assert loan1.get_time_to_maturity_years() == loan2.get_time_to_maturity_years()
        assert loan1.get_net_exposure() == loan2.get_net_exposure()

        cf1 = loan1.get_cash_flows()
        cf2 = loan2.get_cash_flows()
        assert len(cf1) == len(cf2)
        for i in range(len(cf1)):
            assert cf1[i]['date'] == cf2[i]['date']
            assert cf1[i]['principal'] == cf2[i]['principal']
            assert cf1[i]['interest'] == cf2[i]['interest']

    def test_dict_roundtrip_preserves_data(self, corporate_loan_data):
        """Конвертация объект → dict → объект должна сохранять данные"""
        loan_original = CorporateLoan(**corporate_loan_data)

        # Конвертируем в dict и обратно
        loan_dict = loan_original.dict()
        loan_restored = create_position_from_dict(loan_dict)

        assert loan_restored.position_id == loan_original.position_id
        assert loan_restored.amount == loan_original.amount
        assert loan_restored.rate == loan_original.rate
        assert loan_restored.maturity_date == loan_original.maturity_date


# ============================================================================
# Тесты edge cases
# ============================================================================

class TestEdgeCases:
    """Тесты граничных случаев"""

    def test_maturity_on_as_of_date(self, corporate_loan_data):
        """Погашение в тот же день что и выдача (maturity_date == start_date)"""
        corporate_loan_data['maturity_date'] = corporate_loan_data['start_date']

        # Должно вызвать ошибку (maturity должен быть > start_date)
        with pytest.raises(ValueError, match='maturity_date .* must be after start_date'):
            CorporateLoan(**corporate_loan_data)

    def test_very_large_amount(self, corporate_loan_data):
        """Очень большая сумма (>1 трлн)"""
        corporate_loan_data['amount'] = Decimal('1000000000000')

        loan = CorporateLoan(**corporate_loan_data)

        assert loan.amount == Decimal('1000000000000')
        # Проверяем, что расчеты работают
        assert loan.get_time_to_maturity_years() is not None

    def test_zero_rate(self, corporate_loan_data):
        """Нулевая процентная ставка"""
        corporate_loan_data['rate'] = Decimal('0')

        loan = CorporateLoan(**corporate_loan_data)

        cash_flows = loan.get_cash_flows()
        assert cash_flows[0]['interest'] == 0

    def test_none_rate(self, corporate_loan_data):
        """Отсутствие процентной ставки (None)"""
        corporate_loan_data['rate'] = None

        loan = CorporateLoan(**corporate_loan_data)

        cash_flows = loan.get_cash_flows()
        assert cash_flows[0]['interest'] == 0

    def test_auto_insured_amount_for_retail_deposit(self, as_of_date):
        """Автоматический расчет insured_amount для retail deposit"""
        deposit = RetailDeposit(
            position_id='TEST',
            as_of_date=as_of_date,
            balance_account='42307',
            currency=Currency.RUB,
            amount=Decimal('2000000'),  # Больше лимита АСВ
            start_date=date(2023, 1, 1),
            rate=Decimal('0.05'),
            product_type='time_deposit',
            is_insured=True,
            # insured_amount не указываем
        )

        # Должно автоматически установиться в 1.4M (лимит АСВ)
        assert deposit.insured_amount == Decimal('1400000')
