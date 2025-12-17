# ALM Risk Calculator - Balance Sheet Instruments

Модуль классов для представления балансовых инструментов в системе ALM калькулятора.

## 📦 Установка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск тестов
pytest

# Запуск примеров
python models/examples.py
```

## 🏗️ Архитектура классов

```
Position (базовый класс)
    └── BalanceSheetInstrument (абстрактный)
            ├── LoanBase (абстрактный)
            │       ├── CorporateLoan
            │       └── RetailLoan
            └── DepositBase (абстрактный)
                    ├── CorporateDeposit
                    └── RetailDeposit
```

## 📝 Основные классы

### 1. CorporateLoan - Кредиты юридическим лицам

```python
from datetime import date
from decimal import Decimal
from models import CorporateLoan, Currency, RateType, RepricingFrequency

loan = CorporateLoan(
    position_id="CORP_LOAN_001",
    as_of_date=date(2024, 12, 1),
    balance_account="45203",
    currency=Currency.RUB,
    amount=Decimal("50000000"),

    start_date=date(2024, 1, 15),
    maturity_date=date(2027, 1, 15),

    rate=Decimal("0.16"),  # 16% годовых
    rate_type=RateType.FLOATING,
    repricing_date=date(2025, 1, 15),
    repricing_frequency=RepricingFrequency.QUARTERLY,

    industry_sector="Manufacturing",
    borrower_rating="BB+",
)

# Расчеты
print(f"Время до погашения: {loan.get_time_to_maturity_years():.2f} лет")
print(f"Время до репрайсинга: {loan.get_time_to_repricing_years():.2f} лет")
print(f"Чистая экспозиция: {loan.get_net_exposure()}")

# Денежные потоки
cash_flows = loan.get_cash_flows()
```

### 2. RetailLoan - Кредиты физическим лицам

```python
from models import RetailLoan

# Ипотечный кредит
mortgage = RetailLoan(
    position_id="RETAIL_LOAN_001",
    as_of_date=date(2024, 12, 1),
    balance_account="45507",
    currency=Currency.RUB,
    amount=Decimal("3000000"),

    start_date=date(2020, 6, 1),
    maturity_date=date(2040, 6, 1),

    rate=Decimal("0.095"),  # 9.5%
    rate_type=RateType.FIXED,

    product_type="mortgage",
    is_mortgage=True,
    loan_to_value=Decimal("0.67"),

    borrower_age=35,
    borrower_income=Decimal("150000"),

    is_amortizing=True,  # Аннуитетный платеж
)
```

### 3. CorporateDeposit - Депозиты юридических лиц

```python
from models import CorporateDeposit

deposit = CorporateDeposit(
    position_id="CORP_DEP_001",
    as_of_date=date(2024, 12, 1),
    balance_account="42301",
    currency=Currency.RUB,
    amount=Decimal("20000000"),

    start_date=date(2024, 9, 1),
    maturity_date=date(2025, 3, 1),

    rate=Decimal("0.14"),  # 14%

    is_operational=False,  # Срочный депозит, не расчетный счет
    industry_sector="Retail Trade",
    depositor_rating="A",
)
```

### 4. RetailDeposit - Депозиты физических лиц

```python
from models import RetailDeposit

# Депозит до востребования (NMD)
nmd_deposit = RetailDeposit(
    position_id="RETAIL_DEP_001",
    as_of_date=date(2024, 12, 1),
    balance_account="42307",
    currency=Currency.RUB,
    amount=Decimal("500000"),

    start_date=date(2022, 3, 15),
    maturity_date=None,  # Бессрочный

    rate=Decimal("0.005"),  # 0.5%

    is_demand_deposit=True,
    product_type="current_account",
    is_insured=True,  # АСВ

    depositor_segment="mass",
)

# Срочный депозит
time_deposit = RetailDeposit(
    position_id="RETAIL_DEP_002",
    as_of_date=date(2024, 12, 1),
    balance_account="42307",
    currency=Currency.RUB,
    amount=Decimal("1000000"),

    start_date=date(2024, 6, 1),
    maturity_date=date(2025, 6, 1),

    rate=Decimal("0.12"),  # 12%

    is_demand_deposit=False,
    product_type="time_deposit",
    is_insured=True,
)
```

## 🔧 Работа с массивами позиций

### Конвертация в DataFrame

```python
from models import positions_to_dataframe, dataframe_to_positions
import pandas as pd

# Создаем список позиций
positions = [loan1, loan2, deposit1, deposit2]

# Конвертируем в DataFrame
df = positions_to_dataframe(positions)

# Группировка и анализ
summary = df.groupby('instrument_type')['amount'].agg(['count', 'sum', 'mean'])
print(summary)

# Фильтрация
corporate_loans = df[df['instrument_type'] == 'loan_corporate']

# Конвертируем обратно в объекты
positions_back = dataframe_to_positions(df)
```

### Factory функция из dict

```python
from models import create_position_from_dict

# Данные из КХД (например, результат SQL запроса)
data_from_dwh = {
    'position_id': 'DWH_12345',
    'as_of_date': date(2024, 12, 1),
    'instrument_type': 'loan_corporate',  # Строка, не enum
    'balance_account': '45203',
    'currency': 'RUB',
    'amount': Decimal('25000000'),
    'start_date': date(2024, 6, 1),
    'maturity_date': date(2029, 6, 1),
    'rate': Decimal('0.155'),
    # ... остальные поля
}

# Автоматически создается нужный класс
position = create_position_from_dict(data_from_dwh)
# position будет экземпляром CorporateLoan
```

## 📊 Ключевые методы

### Для всех инструментов:

- `get_effective_maturity()` - эффективная дата погашения (с учетом behavioral assumptions)
- `get_time_to_maturity_years()` - время до погашения в годах
- `get_time_to_repricing_years()` - время до репрайсинга в годах (для IRR gap analysis)
- `get_cash_flows(scenario=None)` - денежные потоки по инструменту

### Специфичные для кредитов:

- `get_net_exposure()` - чистая экспозиция (amount - provision_amount)

### Behavioral assumptions:

Для применения behavioral assumptions (prepayment, runoff и т.д.) используется внешний `AssumptionEngine`, который:
1. Читает assumptions из конфига
2. Применяет фильтры к позициям
3. Создает synthetic позиции с adjusted cash flows

## ✅ Валидация

Все классы используют Pydantic для валидации. Примеры ошибок:

```python
# Ошибка: нулевая сумма
loan = CorporateLoan(..., amount=Decimal("0"))
# ValueError: Amount cannot be zero

# Ошибка: maturity раньше start
loan = CorporateLoan(..., start_date=date(2027, 1, 1), maturity_date=date(2024, 1, 1))
# ValueError: maturity_date must be after start_date

# Ошибка: floating rate без repricing_frequency
loan = CorporateLoan(..., rate_type=RateType.FLOATING)
# ValueError: floating rate requires repricing_frequency

# Ошибка: ипотека с product_type != 'mortgage'
loan = RetailLoan(..., is_mortgage=True, product_type='consumer')
# ValueError: is_mortgage flag requires product_type=mortgage
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# Только unit тесты
pytest tests/unit

# Тесты с покрытием
pytest --cov=models --cov-report=html

# Конкретный файл
pytest tests/unit/test_positions.py

# Конкретный тест
pytest tests/unit/test_positions.py::TestValidation::test_zero_amount_raises_error
```

## 📚 Enums

### InstrumentType
- `LOAN_CORPORATE` - кредиты ЮЛ
- `LOAN_RETAIL` - кредиты ФЛ
- `DEPOSIT_CORPORATE` - депозиты ЮЛ
- `DEPOSIT_RETAIL` - депозиты ФЛ
- `BOND`, `EQUITY`, `CASH`, `OTHER` - для будущего

### Currency
- `RUB`, `USD`, `EUR`, `CNY`, `GBP`

### RateType
- `FIXED` - фиксированная ставка
- `FLOATING` - плавающая ставка
- `ZERO` - нулевая ставка

### RepricingFrequency
- `DAILY`, `MONTHLY`, `QUARTERLY`, `SEMIANNUAL`, `ANNUAL`

### AssetQuality
- `STANDARD` - стандартные
- `WATCH` - под наблюдением
- `SUBSTANDARD` - субстандартные
- `DOUBTFUL` - сомнительные
- `LOSS` - безнадежные

### CounterpartyType
- `CORPORATE` - юрлица
- `RETAIL` - физлица
- `BANK` - банки
- `GOVERNMENT` - государство
- `OTHER` - прочие

## 🔄 Денежные потоки

### Для активов (кредиты):
```python
loan.get_cash_flows()
# [{'date': date(2027, 1, 1),
#   'principal': Decimal('10000000'),  # Положительный
#   'interest': Decimal('3000000'),
#   'total': Decimal('13000000')}]
```

### Для пассивов (депозиты):
```python
deposit.get_cash_flows()
# [{'date': date(2025, 3, 1),
#   'principal': Decimal('-20000000'),  # Отрицательный (отток)
#   'interest': Decimal('-700000'),
#   'total': Decimal('-20700000')}]
```

### Для NMD (бессрочных депозитов):
```python
nmd_deposit.get_cash_flows()
# []  # Пустой список
# Денежные потоки будут сгенерированы AssumptionEngine
```

## 🎯 Следующие шаги

1. **AssumptionEngine** - применение behavioral assumptions
2. **Gap Analysis Calculator** - расчет гэпов ликвидности и IRR
3. **Duration Calculator** - расчет duration/DV01
4. **Data Connectors** - загрузка из КХД/Excel/API
5. **Config Loader** - загрузка конфигураций
6. **Versioning Framework** - версионирование расчетов
