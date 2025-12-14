"""
Примеры использования классов балансовых инструментов.

Этот файл демонстрирует:
1. Создание различных типов позиций
2. Работу с валидацией
3. Расчет денежных потоков
4. Конвертацию между dict/DataFrame и объектами
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List
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
    create_position_from_dict,
    positions_to_dataframe,
    dataframe_to_positions
)


# ============================================================================
# Пример 1: Создание корпоративного кредита
# ============================================================================

def example_corporate_loan():
    """Создание корпоративного кредита с floating rate"""

    print("=" * 80)
    print("ПРИМЕР 1: Корпоративный кредит (floating rate)")
    print("=" * 80)

    loan = CorporateLoan(
        position_id="LOAN_CORP_001",
        as_of_date=date(2024, 12, 1),
        balance_account="45203",
        currency=Currency.RUB,
        amount=Decimal("50000000"),  # 50 млн рублей

        start_date=date(2024, 1, 15),
        maturity_date=date(2027, 1, 15),  # 3 года

        rate=Decimal("0.16"),  # 16% годовых
        rate_type=RateType.FLOATING,
        repricing_date=date(2025, 1, 15),  # Следующий репрайсинг через месяц
        repricing_frequency=RepricingFrequency.QUARTERLY,

        asset_quality=AssetQuality.STANDARD,
        provision_amount=Decimal("500000"),  # 1% резервы
        collateral_value=Decimal("60000000"),

        industry_sector="Manufacturing",
        borrower_rating="BB+",
        is_syndicated=False,
        is_revolving=False,
    )

    print(f"\nID позиции: {loan.position_id}")
    print(f"Сумма: {loan.amount:,.0f} {loan.currency}")
    print(f"Ставка: {loan.rate * 100:.2f}% ({loan.rate_type})")
    print(f"Погашение: {loan.maturity_date}")
    print(f"Следующий репрайсинг: {loan.repricing_date} ({loan.repricing_frequency})")
    print(f"Чистая экспозиция: {loan.get_net_exposure():,.0f} {loan.currency}")
    print(f"Время до погашения: {loan.get_time_to_maturity_years():.2f} лет")
    print(f"Время до репрайсинга: {loan.get_time_to_repricing_years():.2f} лет")

    # Денежные потоки
    cash_flows = loan.get_cash_flows()
    print(f"\nДенежные потоки (bullet loan):")
    for cf in cash_flows:
        print(f"  {cf['date']}: Principal={cf['principal']:,.0f}, Interest={cf['interest']:,.0f}, Total={cf['total']:,.0f}")

    return loan


# ============================================================================
# Пример 2: Создание розничного кредита (ипотека)
# ============================================================================

def example_retail_mortgage():
    """Создание ипотечного кредита с амортизацией"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 2: Розничный кредит (ипотека с амортизацией)")
    print("=" * 80)

    # Упрощенный график амортизации (в реальности рассчитывается по формулам аннуитета)
    amortization_schedule = [
        {'date': date(2025, 1, 1), 'principal': 50000, 'interest': 12000},
        {'date': date(2025, 2, 1), 'principal': 50500, 'interest': 11500},
        {'date': date(2025, 3, 1), 'principal': 51000, 'interest': 11000},
        # ... остальные платежи
    ]

    loan = RetailLoan(
        position_id="LOAN_RETAIL_001",
        as_of_date=date(2024, 12, 1),
        balance_account="45507",
        currency=Currency.RUB,
        amount=Decimal("3000000"),  # 3 млн рублей

        start_date=date(2020, 6, 1),
        maturity_date=date(2040, 6, 1),  # 20 лет

        rate=Decimal("0.095"),  # 9.5% годовых
        rate_type=RateType.FIXED,

        asset_quality=AssetQuality.STANDARD,
        provision_amount=Decimal("30000"),
        collateral_value=Decimal("4500000"),  # Квартира

        product_type="mortgage",
        is_mortgage=True,
        loan_to_value=Decimal("0.67"),  # LTV = 67%

        borrower_age=35,
        borrower_income=Decimal("150000"),

        allows_early_repayment=True,
        early_repayment_penalty=Decimal("0.01"),  # 1% штраф

        is_amortizing=True,
        amortization_schedule=amortization_schedule,
    )

    print(f"\nID позиции: {loan.position_id}")
    print(f"Продукт: {loan.product_type} (LTV={loan.loan_to_value * 100:.0f}%)")
    print(f"Сумма: {loan.amount:,.0f} {loan.currency}")
    print(f"Ставка: {loan.rate * 100:.2f}% (фиксированная)")
    print(f"Срок: {loan.start_date} - {loan.maturity_date}")
    print(f"Амортизация: {'Да' if loan.is_amortizing else 'Нет'}")
    print(f"Обеспечение: {loan.collateral_value:,.0f} {loan.currency}")

    # Денежные потоки
    cash_flows = loan.get_cash_flows()
    print(f"\nПервые 3 платежа по графику амортизации:")
    for cf in cash_flows[:3]:
        print(f"  {cf['date']}: Principal={cf['principal']:,.0f}, Interest={cf['interest']:,.0f}, Total={cf['total']:,.0f}")

    return loan


# ============================================================================
# Пример 3: Создание корпоративного депозита (срочный)
# ============================================================================

def example_corporate_deposit():
    """Создание срочного корпоративного депозита"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 3: Корпоративный депозит (срочный)")
    print("=" * 80)

    deposit = CorporateDeposit(
        position_id="DEP_CORP_001",
        as_of_date=date(2024, 12, 1),
        balance_account="42301",
        currency=Currency.RUB,
        amount=Decimal("20000000"),  # 20 млн рублей

        start_date=date(2024, 9, 1),
        maturity_date=date(2025, 3, 1),  # 6 месяцев

        rate=Decimal("0.14"),  # 14% годовых
        rate_type=RateType.FIXED,

        is_demand_deposit=False,
        allows_early_withdrawal=True,
        early_withdrawal_penalty=Decimal("0.02"),  # 2% штраф
        interest_capitalization=False,

        is_operational=False,
        industry_sector="Retail Trade",
        depositor_rating="A",
    )

    print(f"\nID позиции: {deposit.position_id}")
    print(f"Сумма: {deposit.amount:,.0f} {deposit.currency}")
    print(f"Ставка: {deposit.rate * 100:.2f}%")
    print(f"Срок: {deposit.start_date} - {deposit.maturity_date}")
    print(f"Время до погашения: {deposit.get_time_to_maturity_years():.2f} лет")

    # Денежные потоки (отрицательные для пассивов)
    cash_flows = deposit.get_cash_flows()
    print(f"\nДенежные потоки (отток для банка):")
    for cf in cash_flows:
        print(f"  {cf['date']}: Principal={cf['principal']:,.0f}, Interest={cf['interest']:,.0f}, Total={cf['total']:,.0f}")

    return deposit


# ============================================================================
# Пример 4: Создание розничного депозита (до востребования / NMD)
# ============================================================================

def example_retail_demand_deposit():
    """Создание депозита до востребования (NMD - Non-Maturing Deposit)"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 4: Розничный депозит до востребования (NMD)")
    print("=" * 80)

    deposit = RetailDeposit(
        position_id="DEP_RETAIL_001",
        as_of_date=date(2024, 12, 1),
        balance_account="42307",
        currency=Currency.RUB,
        amount=Decimal("500000"),  # 500 тыс рублей

        start_date=date(2022, 3, 15),
        maturity_date=None,  # Бессрочный (до востребования)

        rate=Decimal("0.005"),  # 0.5% годовых (символическая ставка)
        rate_type=RateType.FIXED,

        is_demand_deposit=True,
        allows_early_withdrawal=True,
        early_withdrawal_penalty=None,  # Нет штрафа
        interest_capitalization=False,

        product_type="current_account",
        is_insured=True,
        insured_amount=Decimal("500000"),  # Полностью застрахован

        depositor_age=42,
        depositor_segment="mass",
    )

    print(f"\nID позиции: {deposit.position_id}")
    print(f"Продукт: {deposit.product_type} (до востребования)")
    print(f"Сумма: {deposit.amount:,.0f} {deposit.currency}")
    print(f"Застрахованная сумма: {deposit.insured_amount:,.0f} {deposit.currency}")
    print(f"Дата погашения: {'Нет (NMD)' if not deposit.maturity_date else deposit.maturity_date}")

    # Для NMD денежные потоки будут рассчитаны через AssumptionEngine
    cash_flows = deposit.get_cash_flows()
    if not cash_flows:
        print(f"\nДенежные потоки: будут рассчитаны AssumptionEngine на основе behavioral model")
        print(f"  (например, core portion 70%, avg maturity 3 года)")

    return deposit


# ============================================================================
# Пример 5: Работа с массивом позиций и DataFrame
# ============================================================================

def example_bulk_operations():
    """Работа с множеством позиций через pandas DataFrame"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 5: Массовые операции с позициями (DataFrame)")
    print("=" * 80)

    # Создаем набор позиций
    positions = [
        CorporateLoan(
            position_id=f"CORP_LOAN_{i}",
            as_of_date=date(2024, 12, 1),
            balance_account="45203",
            currency=Currency.RUB,
            amount=Decimal(10000000 + i * 1000000),
            start_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            rate=Decimal("0.15"),
            rate_type=RateType.FIXED,
            industry_sector="Manufacturing" if i % 2 == 0 else "Services",
            borrower_rating="BBB",
        )
        for i in range(5)
    ]

    positions.extend([
        RetailDeposit(
            position_id=f"RETAIL_DEP_{i}",
            as_of_date=date(2024, 12, 1),
            balance_account="42307",
            currency=Currency.RUB,
            amount=Decimal(100000 + i * 50000),
            start_date=date(2023, 1, 1),
            maturity_date=None if i % 2 == 0 else date(2025, 12, 1),
            rate=Decimal("0.01"),
            rate_type=RateType.FIXED,
            is_demand_deposit=(i % 2 == 0),
            product_type="current_account" if i % 2 == 0 else "time_deposit",
            is_insured=True,
        )
        for i in range(5)
    ])

    # Конвертируем в DataFrame
    df = positions_to_dataframe(positions)

    print(f"\nСоздано позиций: {len(df)}")
    print(f"\nПервые 5 строк DataFrame:")
    print(df[['position_id', 'instrument_type', 'amount', 'currency', 'maturity_date']].head())

    # Группировка по типам инструментов
    print(f"\nСтатистика по типам инструментов:")
    summary = df.groupby('instrument_type')['amount'].agg(['count', 'sum', 'mean'])
    print(summary)

    # Фильтрация: только кредиты
    loans_df = df[df['instrument_type'].str.contains('loan')]
    print(f"\nТолько кредиты: {len(loans_df)} позиций")
    print(f"Общая сумма кредитов: {loans_df['amount'].sum():,.0f} RUB")

    # Конвертируем обратно в объекты
    positions_back = dataframe_to_positions(df)
    print(f"\nКонвертировано обратно в объекты: {len(positions_back)} позиций")

    return df, positions


# ============================================================================
# Пример 6: Валидация и обработка ошибок
# ============================================================================

def example_validation_errors():
    """Демонстрация работы валидации"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 6: Валидация и обработка ошибок")
    print("=" * 80)

    # Ошибка 1: Нулевая сумма
    print("\n1. Попытка создать позицию с нулевой суммой:")
    try:
        loan = CorporateLoan(
            position_id="INVALID_001",
            as_of_date=date(2024, 12, 1),
            balance_account="45203",
            currency=Currency.RUB,
            amount=Decimal("0"),  # Ошибка!
            start_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            rate=Decimal("0.15"),
        )
    except ValueError as e:
        print(f"   [ERROR] Ошибка валидации: {e}")

    # Ошибка 2: maturity_date раньше start_date
    print("\n2. Попытка создать позицию с некорректными датами:")
    try:
        loan = CorporateLoan(
            position_id="INVALID_002",
            as_of_date=date(2024, 12, 1),
            balance_account="45203",
            currency=Currency.RUB,
            amount=Decimal("1000000"),
            start_date=date(2027, 1, 1),  # Позже maturity!
            maturity_date=date(2024, 1, 1),  # Ошибка!
            rate=Decimal("0.15"),
        )
    except ValueError as e:
        print(f"   [ERROR] Ошибка валидации: {e}")

    # Ошибка 3: Floating rate без repricing_frequency
    print("\n3. Попытка создать floating rate без repricing_frequency:")
    try:
        loan = CorporateLoan(
            position_id="INVALID_003",
            as_of_date=date(2024, 12, 1),
            balance_account="45203",
            currency=Currency.RUB,
            amount=Decimal("1000000"),
            start_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            rate=Decimal("0.15"),
            rate_type=RateType.FLOATING,  # Floating
            # Но нет repricing_frequency! Ошибка!
        )
    except ValueError as e:
        print(f"   [ERROR] Ошибка валидации: {e}")

    # Ошибка 4: Ипотека с некорректным product_type
    print("\n4. Попытка создать ипотеку с некорректным product_type:")
    try:
        loan = RetailLoan(
            position_id="INVALID_004",
            as_of_date=date(2024, 12, 1),
            balance_account="45507",
            currency=Currency.RUB,
            amount=Decimal("3000000"),
            start_date=date(2020, 6, 1),
            maturity_date=date(2040, 6, 1),
            rate=Decimal("0.095"),
            product_type="consumer",  # Не mortgage!
            is_mortgage=True,  # Ошибка!
        )
    except ValueError as e:
        print(f"   [ERROR] Ошибка валидации: {e}")

    print("\n[OK] Валидация работает корректно!")


# ============================================================================
# Пример 7: Factory функция создания из словаря
# ============================================================================

def example_factory_creation():
    """Создание объектов через factory функцию из dict"""

    print("\n" + "=" * 80)
    print("ПРИМЕР 7: Factory функция create_position_from_dict()")
    print("=" * 80)

    # Симуляция данных из КХД (словарь)
    data_from_dwh = {
        'position_id': 'DWH_12345',
        'as_of_date': date(2024, 12, 1),
        'instrument_type': 'loan_corporate',  # Строка, не enum
        'balance_account': '45203',
        'currency': 'RUB',
        'amount': Decimal('25000000'),
        'counterparty_type': 'corporate',
        'start_date': date(2024, 6, 1),
        'maturity_date': date(2029, 6, 1),
        'rate': Decimal('0.155'),
        'rate_type': 'fixed',
        'industry_sector': 'Construction',
        'borrower_rating': 'BB',
    }

    # Автоматически создается нужный класс (CorporateLoan)
    position = create_position_from_dict(data_from_dwh)

    print(f"\nИз словаря создан объект: {type(position).__name__}")
    print(f"ID: {position.position_id}")
    print(f"Тип: {position.instrument_type}")
    print(f"Сумма: {position.amount:,.0f} {position.currency}")

    # Проверяем, что это действительно CorporateLoan
    if isinstance(position, CorporateLoan):
        print(f"Отрасль заемщика: {position.industry_sector}")
        print(f"Рейтинг: {position.borrower_rating}")

    print("\n[OK] Factory функция работает корректно!")

    return position


# ============================================================================
# Main: Запуск всех примеров
# ============================================================================

def main():
    """Запуск всех примеров"""

    print("\n" + "=" * 80)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ КЛАССОВ БАЛАНСОВЫХ ИНСТРУМЕНТОВ")
    print("=" * 80)

    # Запускаем примеры
    loan_corp = example_corporate_loan()
    loan_retail = example_retail_mortgage()
    dep_corp = example_corporate_deposit()
    dep_retail = example_retail_demand_deposit()
    df, positions = example_bulk_operations()
    example_validation_errors()
    position = example_factory_creation()

    print("\n" + "=" * 80)
    print("ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ УСПЕШНО!")
    print("=" * 80)


if __name__ == "__main__":
    main()
