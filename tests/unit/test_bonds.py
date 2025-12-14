"""
Unit тесты для класса Bond.

Покрывают:
- Создание облигаций разных типов
- Валидацию параметров
- Расчет купонов и денежных потоков
- Расчет YTM
- Edge cases
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from models.positions import (
    Bond,
    BondType,
    CouponFrequency,
    Currency,
    RateType,
    InstrumentType,
    CounterpartyType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def as_of_date():
    """Дата расчета для тестов"""
    return date(2024, 12, 1)


@pytest.fixture
def government_bond_data(as_of_date):
    """Базовые данные для государственной облигации (ОФЗ)"""
    return {
        'position_id': 'BOND_OFZ_001',
        'as_of_date': as_of_date,
        'balance_account': '50105',
        'currency': Currency.RUB,
        'amount': Decimal('10000000'),  # 10 млн рублей (100 облигаций по 100k)
        'counterparty_type': CounterpartyType.GOVERNMENT,
        'start_date': date(2023, 1, 15),
        'maturity_date': date(2028, 1, 15),  # 5 лет
        'rate': Decimal('0.10'),  # Для облигаций это не используется напрямую
        'rate_type': RateType.FIXED,
        'bond_type': BondType.GOVERNMENT,
        'issuer': 'Минфин РФ',
        'face_value': Decimal('100000'),  # 100k номинал
        'coupon_rate': Decimal('0.08'),  # 8% годовых
        'coupon_frequency': CouponFrequency.SEMIANNUAL,
        'next_coupon_date': date(2025, 1, 15),
        'current_market_price': Decimal('98.5'),  # 98.5% от номинала
        'accounting_classification': 'HTM',
    }


@pytest.fixture
def corporate_bond_data(as_of_date):
    """Базовые данные для корпоративной облигации"""
    return {
        'position_id': 'BOND_CORP_001',
        'as_of_date': as_of_date,
        'balance_account': '50205',
        'currency': Currency.RUB,
        'amount': Decimal('5000000'),  # 5 млн (50 облигаций по 100k)
        'counterparty_type': CounterpartyType.CORPORATE,
        'start_date': date(2024, 6, 1),
        'maturity_date': date(2027, 6, 1),  # 3 года
        'rate': Decimal('0.12'),
        'rate_type': RateType.FIXED,
        'bond_type': BondType.CORPORATE,
        'issuer': 'Газпром',
        'isin': 'RU000A0JXP23',
        'face_value': Decimal('100000'),
        'coupon_rate': Decimal('0.12'),  # 12% годовых
        'coupon_frequency': CouponFrequency.QUARTERLY,
        'next_coupon_date': date(2025, 3, 1),
        'current_market_price': Decimal('102.3'),
        'credit_rating': 'BBB+',
        'accounting_classification': 'AFS',
    }


@pytest.fixture
def zero_coupon_bond_data(as_of_date):
    """Базовые данные для бескупонной облигации"""
    return {
        'position_id': 'BOND_ZERO_001',
        'as_of_date': as_of_date,
        'balance_account': '50105',
        'currency': Currency.USD,
        'amount': Decimal('1000000'),  # $1M номинал
        'counterparty_type': CounterpartyType.GOVERNMENT,
        'start_date': date(2022, 1, 1),
        'maturity_date': date(2027, 1, 1),  # 5 лет
        'rate': Decimal('0'),
        'rate_type': RateType.ZERO,
        'bond_type': BondType.GOVERNMENT,
        'issuer': 'US Treasury',
        'face_value': Decimal('1000000'),
        'coupon_rate': Decimal('0'),  # Бескупонная
        'coupon_frequency': CouponFrequency.ZERO,
        'purchase_price': Decimal('75.0'),  # Куплена с дисконтом
        'current_market_price': Decimal('85.0'),
        'accounting_classification': 'HTM',
    }


# ============================================================================
# Тесты создания объектов
# ============================================================================

class TestBondCreation:
    """Тесты создания объектов облигаций"""

    def test_create_government_bond(self, government_bond_data):
        """Создание государственной облигации (ОФЗ)"""
        bond = Bond(**government_bond_data)

        assert bond.position_id == 'BOND_OFZ_001'
        assert bond.instrument_type == InstrumentType.BOND
        assert bond.bond_type == BondType.GOVERNMENT
        assert bond.issuer == 'Минфин РФ'
        assert bond.face_value == Decimal('100000')
        assert bond.coupon_rate == Decimal('0.08')
        assert bond.coupon_frequency == CouponFrequency.SEMIANNUAL
        assert bond.accounting_classification == 'HTM'

    def test_create_corporate_bond(self, corporate_bond_data):
        """Создание корпоративной облигации"""
        bond = Bond(**corporate_bond_data)

        assert bond.bond_type == BondType.CORPORATE
        assert bond.issuer == 'Газпром'
        assert bond.isin == 'RU000A0JXP23'
        assert bond.coupon_frequency == CouponFrequency.QUARTERLY
        assert bond.credit_rating == 'BBB+'

    def test_create_zero_coupon_bond(self, zero_coupon_bond_data):
        """Создание бескупонной облигации"""
        bond = Bond(**zero_coupon_bond_data)

        assert bond.coupon_rate == Decimal('0')
        assert bond.coupon_frequency == CouponFrequency.ZERO
        assert bond.currency == Currency.USD


# ============================================================================
# Тесты валидации
# ============================================================================

class TestBondValidation:
    """Тесты валидации облигаций"""

    def test_callable_bond_requires_call_date(self, government_bond_data):
        """Callable облигация должна иметь call_date"""
        government_bond_data['is_callable'] = True
        # call_date не указан

        with pytest.raises(ValueError, match='Callable bond requires call_date'):
            Bond(**government_bond_data)

    def test_puttable_bond_requires_put_date(self, government_bond_data):
        """Puttable облигация должна иметь put_date"""
        government_bond_data['is_puttable'] = True
        # put_date не указан

        with pytest.raises(ValueError, match='Puttable bond requires put_date'):
            Bond(**government_bond_data)

    def test_negative_coupon_rate_raises_error(self, government_bond_data):
        """Отрицательная купонная ставка должна вызывать ошибку"""
        government_bond_data['coupon_rate'] = Decimal('-0.05')

        with pytest.raises(ValueError, match='Coupon rate cannot be negative'):
            Bond(**government_bond_data)

    def test_zero_coupon_bond_with_nonzero_rate_raises_error(self, zero_coupon_bond_data):
        """Zero-coupon облигация с ненулевой ставкой должна вызывать ошибку"""
        zero_coupon_bond_data['coupon_rate'] = Decimal('0.05')  # Не 0!

        with pytest.raises(ValueError, match='Zero-coupon bond must have coupon_rate = 0'):
            Bond(**zero_coupon_bond_data)

    def test_invalid_accounting_classification_raises_error(self, government_bond_data):
        """Некорректная accounting_classification должна вызывать ошибку"""
        government_bond_data['accounting_classification'] = 'INVALID'

        with pytest.raises(ValueError, match='accounting_classification must be one of HTM, AFS, HFT'):
            Bond(**government_bond_data)

    def test_accounting_classification_case_insensitive(self, government_bond_data):
        """accounting_classification должна быть case-insensitive"""
        government_bond_data['accounting_classification'] = 'htm'

        bond = Bond(**government_bond_data)

        assert bond.accounting_classification == 'HTM'


# ============================================================================
# Тесты расчетных методов
# ============================================================================

class TestBondCalculations:
    """Тесты методов расчета"""

    def test_get_number_of_bonds(self, government_bond_data):
        """Расчет количества облигаций в позиции"""
        bond = Bond(**government_bond_data)

        # amount = 10M, face_value = 100k => 100 облигаций
        num_bonds = bond.get_number_of_bonds()

        assert num_bonds == Decimal('100')

    def test_get_coupon_payment_amount_semiannual(self, government_bond_data):
        """Расчет суммы одного купона (полугодовые выплаты)"""
        bond = Bond(**government_bond_data)

        # face_value = 100k, coupon_rate = 8%, semiannual
        # Купон за 6 месяцев = 100k * 0.08 / 2 = 4k
        coupon = bond.get_coupon_payment_amount()

        assert coupon == Decimal('4000')

    def test_get_coupon_payment_amount_quarterly(self, corporate_bond_data):
        """Расчет суммы одного купона (квартальные выплаты)"""
        bond = Bond(**corporate_bond_data)

        # face_value = 100k, coupon_rate = 12%, quarterly
        # Купон за квартал = 100k * 0.12 / 4 = 3k
        coupon = bond.get_coupon_payment_amount()

        assert coupon == Decimal('3000')

    def test_get_coupon_payment_amount_zero_coupon(self, zero_coupon_bond_data):
        """Расчет купона для бескупонной облигации (должен быть 0)"""
        bond = Bond(**zero_coupon_bond_data)

        coupon = bond.get_coupon_payment_amount()

        assert coupon == Decimal('0')

    def test_get_cash_flows_zero_coupon_bond(self, zero_coupon_bond_data):
        """Денежные потоки для бескупонной облигации"""
        bond = Bond(**zero_coupon_bond_data)

        cash_flows = bond.get_cash_flows()

        # Только одна выплата: погашение номинала
        assert len(cash_flows) == 1
        assert cash_flows[0]['date'] == date(2027, 1, 1)
        assert cash_flows[0]['principal'] == Decimal('1000000')
        assert cash_flows[0]['interest'] == Decimal('0')
        assert cash_flows[0]['type'] == 'maturity'

    def test_get_cash_flows_coupon_bond(self, government_bond_data):
        """Денежные потоки для купонной облигации"""
        bond = Bond(**government_bond_data)

        cash_flows = bond.get_cash_flows()

        # Должны быть купоны + погашение номинала
        # Semiannual с 2025-01-15 до 2028-01-15 = ~6 купонов + погашение
        assert len(cash_flows) > 1

        # Первый поток - купон
        first_coupon = cash_flows[0]
        assert first_coupon['type'] == 'coupon'
        assert first_coupon['principal'] == Decimal('0')
        assert first_coupon['interest'] > 0

        # Последний поток - погашение номинала
        maturity_flow = cash_flows[-1]
        assert maturity_flow['type'] == 'maturity'
        assert maturity_flow['date'] == date(2028, 1, 15)
        assert maturity_flow['principal'] == Decimal('10000000')

    def test_get_yield_to_maturity(self, government_bond_data):
        """Расчет YTM (приблизительная формула)"""
        bond = Bond(**government_bond_data)

        ytm = bond.get_yield_to_maturity()

        # YTM должна быть больше купонной ставки, т.к. цена < номинала
        # current_market_price = 98.5% < 100%
        assert ytm is not None
        assert ytm > bond.coupon_rate  # YTM > 8%

    def test_get_yield_to_maturity_no_market_price(self, government_bond_data):
        """YTM без рыночной цены должна возвращать None"""
        government_bond_data['current_market_price'] = None
        bond = Bond(**government_bond_data)

        ytm = bond.get_yield_to_maturity()

        assert ytm is None

    def test_get_accrued_interest_explicit(self, government_bond_data):
        """НКД, если указан явно"""
        government_bond_data['accrued_interest'] = Decimal('1500')
        bond = Bond(**government_bond_data)

        nkd = bond.get_accrued_interest_amount()

        assert nkd == Decimal('1500')

    def test_get_accrued_interest_zero_coupon(self, zero_coupon_bond_data):
        """НКД для бескупонной облигации должен быть 0"""
        bond = Bond(**zero_coupon_bond_data)

        nkd = bond.get_accrued_interest_amount()

        assert nkd == Decimal('0')


# ============================================================================
# Тесты callable/puttable облигаций
# ============================================================================

class TestCallablePuttableBonds:
    """Тесты для облигаций с опциями отзыва/предъявления"""

    def test_create_callable_bond(self, government_bond_data):
        """Создание callable облигации"""
        government_bond_data['is_callable'] = True
        government_bond_data['call_date'] = date(2026, 1, 15)
        government_bond_data['call_price'] = Decimal('101.0')

        bond = Bond(**government_bond_data)

        assert bond.is_callable is True
        assert bond.call_date == date(2026, 1, 15)
        assert bond.call_price == Decimal('101.0')

    def test_create_puttable_bond(self, corporate_bond_data):
        """Создание puttable облигации"""
        corporate_bond_data['is_puttable'] = True
        corporate_bond_data['put_date'] = date(2026, 6, 1)
        corporate_bond_data['put_price'] = Decimal('100.0')

        bond = Bond(**corporate_bond_data)

        assert bond.is_puttable is True
        assert bond.put_date == date(2026, 6, 1)
        assert bond.put_price == Decimal('100.0')


# ============================================================================
# Тесты edge cases
# ============================================================================

class TestBondEdgeCases:
    """Тесты граничных случаев"""

    def test_bond_with_100_percent_market_price(self, government_bond_data):
        """Облигация торгуется по номиналу"""
        government_bond_data['current_market_price'] = Decimal('100.0')

        bond = Bond(**government_bond_data)

        # YTM должна быть примерно равна купонной ставке
        ytm = bond.get_yield_to_maturity()
        assert ytm is not None
        # Небольшая погрешность допустима
        assert abs(ytm - bond.coupon_rate) < Decimal('0.01')

    def test_bond_near_maturity(self, government_bond_data):
        """Облигация близка к погашению"""
        government_bond_data['maturity_date'] = date(2025, 1, 15)  # Через месяц

        bond = Bond(**government_bond_data)

        time_to_maturity = bond.get_time_to_maturity_years()
        assert time_to_maturity is not None
        assert time_to_maturity < Decimal('0.2')  # Меньше года

    def test_bond_with_fractional_number(self, government_bond_data):
        """Облигация с дробным количеством (например, 150.5 шт)"""
        government_bond_data['amount'] = Decimal('15050000')  # 150.5 облигаций

        bond = Bond(**government_bond_data)

        num_bonds = bond.get_number_of_bonds()
        assert num_bonds == Decimal('150.5')


# ============================================================================
# Интеграционные тесты
# ============================================================================

class TestBondIntegration:
    """Интеграционные тесты с другими компонентами"""

    def test_bond_in_positions_list(self, government_bond_data, corporate_bond_data):
        """Облигации в списке позиций с другими инструментами"""
        from models import positions_to_dataframe

        bond1 = Bond(**government_bond_data)
        bond2 = Bond(**corporate_bond_data)

        positions = [bond1, bond2]
        df = positions_to_dataframe(positions)

        assert len(df) == 2
        assert all(df['instrument_type'] == InstrumentType.BOND)
        assert bond1.position_id in df['position_id'].values
        assert bond2.position_id in df['position_id'].values

    def test_create_bond_from_dict(self, government_bond_data):
        """Создание облигации через factory функцию"""
        from models import create_position_from_dict

        government_bond_data['instrument_type'] = 'bond'

        bond = create_position_from_dict(government_bond_data)

        assert isinstance(bond, Bond)
        assert bond.bond_type == BondType.GOVERNMENT
        assert bond.issuer == 'Минфин РФ'
