"""
Пример анализа ликвидности.

Загружает позиции из CSV и выполняет гэп-анализ ликвидности.
Результаты сохраняются в Excel файл.
"""

from data.loaders.csv_loader import BalanceSheetLoader
from analytics.liquidity import LiquidityGapAnalyzer
from datetime import date

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)


def main():
    """Основная функция для запуска анализа ликвидности."""

    print("\n" + "=" * 80)
    print("LIQUIDITY GAP ANALYSIS")
    print("=" * 80 + "\n")

    # 1. Загружаем позиции из CSV
    print("Step 1: Loading positions from CSV...")
    csv_path = "data/sample/balance_sheet_2024-12-01.csv"
    loader = BalanceSheetLoader()
    positions = loader.load_from_csv(csv_path)
    print(f"  Loaded {len(positions)} positions\n")

    # 2. Создаем анализатор ликвидности
    print("Step 2: Initializing liquidity analyzer...")
    analyzer = LiquidityGapAnalyzer(
        positions=positions,
        as_of_date=date(2024, 12, 1)
    )
    print("  Analyzer initialized\n")

    # 3. Рассчитываем гэп по бакетам
    print("Step 3: Calculating liquidity gap by buckets...")
    gap_df = analyzer.calculate_gap()
    print(f"  Gap calculated for {len(gap_df)} buckets\n")

    # 4. Рассчитываем сводку по валютам
    print("Step 4: Calculating summary by currency...")
    summary_df = analyzer.calculate_summary_by_currency()
    print(f"  Summary created with {len(summary_df)} rows\n")

    # 5. Рассчитываем коэффициенты
    print("Step 5: Calculating liquidity ratios...")
    ratios = analyzer.calculate_ratios()
    print(f"  Liquidity Coverage Ratio: {ratios['liquidity_coverage_ratio']:.2%}")
    print(f"  Gap 30 days: {ratios['gap_30d']:,.0f} RUB\n")

    # 6. Выводим отчет в консоль
    analyzer.print_gap_report()

    # 7. Экспортируем в Excel
    print("Step 6: Exporting results to Excel...")
    output_path = "output/liquidity_gap_analysis_2024-12-01.xlsx"
    analyzer.export_to_excel(output_path)
    print(f"  Results saved to: {output_path}\n")

    print("=" * 80)
    print("ANALYSIS COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
