# Analytics Module

Модуль для анализа рисков ALM (Asset-Liability Management).

## Модули

### liquidity.py

Анализ ликвидности с расчетом гэпа по временным бакетам.

#### Основные возможности:

1. **Гэп-анализ ликвидности** - расчет гэпа по контрактным срокам погашения
2. **Временные бакеты** - стандартные бакеты от overnight до 5+ лет
3. **Multi-currency support** - автоматическая конвертация в базовую валюту
4. **Коэффициенты ликвидности** - LCR, gaps, и другие метрики
5. **Excel export** - экспорт результатов в многостраничный Excel файл

#### Временные бакеты:

- Overnight (0 дней)
- 1-7 days
- 8-30 days
- 1-3 months (31-90 days)
- 3-6 months (91-180 days)
- 6-12 months (181-365 days)
- 1-2 years (366-730 days)
- 2-3 years (731-1095 days)
- 3-5 years (1096-1825 days)
- 5+ years (1826+ days)

#### Пример использования:

```python
from data.loaders.csv_loader import BalanceSheetLoader
from analytics.liquidity import LiquidityGapAnalyzer
from datetime import date

# Загрузка позиций
loader = BalanceSheetLoader()
positions = loader.load_from_csv("data/sample/balance_sheet_2024-12-01.csv")

# Создание анализатора
analyzer = LiquidityGapAnalyzer(
    positions=positions,
    as_of_date=date(2024, 12, 1)
)

# Расчет гэпа
gap_df = analyzer.calculate_gap()

# Расчет коэффициентов
ratios = analyzer.calculate_ratios()
print(f"LCR: {ratios['liquidity_coverage_ratio']:.2%}")

# Вывод отчета
analyzer.print_gap_report()

# Экспорт в Excel
analyzer.export_to_excel("output/liquidity_gap_analysis.xlsx")
```

#### Структура Excel файла:

Экспортируемый файл содержит 4 листа:

1. **Liquidity Gap** - гэп по временным бакетам
   - Assets: сумма активов в бакете
   - Liabilities: сумма пассивов в бакете
   - Gap: разница (Assets - Liabilities)
   - Cumulative Gap: накопленный гэп

2. **Summary by Currency** - сводка по валютам и инструментам
   - Группировка по: classification, instrument_type, currency
   - Суммы в исходной валюте и в базовой валюте
   - Количество позиций

3. **Ratios** - коэффициенты ликвидности
   - Liquid Assets (0-30d)
   - Short-term Liabilities (0-30d)
   - Liquidity Coverage Ratio (LCR)
   - Gap 30 days
   - Total Assets/Liabilities

4. **Parameters** - параметры анализа
   - As of Date
   - Base Currency
   - Number of Positions
   - Analysis Date

#### Классификация активов и пассивов:

**Активы:**
- Кредиты юридическим лицам (loan_corporate)
- Кредиты физическим лицам (loan_retail)
- Облигации (bond)

**Пассивы:**
- Депозиты юридических лиц (deposit_corporate)
- Депозиты физических лиц (deposit_retail)

#### Особенности:

- **Perpetual instruments** (без maturity_date) помещаются в бакет "5+ years"
- **Overdue positions** (maturity_date < as_of_date) помещаются в отдельный бакет "Overdue"
- **FX conversion** - все суммы конвертируются в базовую валюту (по умолчанию RUB)
- **Contractual maturity** - используются контрактные сроки погашения (не behavioral)

## Запуск примера

```bash
python analyze_liquidity.py
```

Результат будет сохранен в `output/liquidity_gap_analysis_2024-12-01.xlsx`.

## Тестирование

```bash
python -m pytest tests/unit/test_liquidity.py -v
```

## Планы развития

- [ ] Behavioral maturity для депозитов до востребования
- [ ] Stress scenarios для гэп-анализа
- [ ] NSFR (Net Stable Funding Ratio) расчет
- [ ] Liquidity buffer analysis
- [ ] Funding concentration metrics
