import models.examples as modex
import analytics.liquidity as liqanalytics
from data.loaders.csv_loader import BalanceSheetLoader
from datetime import date


if __name__ == '__main__':
    loader = BalanceSheetLoader()
    positions = loader.load_from_csv("C:/work/alm_modeler/data/sample/balance_sheet_2024-12-01_fixed.csv")
    analyzer = liqanalytics.LiquidityGapAnalyzer(positions, as_of_date=date(2024, 12, 1))
    analyzer.calculate_gap()
    # modex.example_corporate_loan()
    # modex.example_bulk_operations()
    # modex.example_retail_mortgage()
    # modex.example_retail_demand_deposit()
    # modex.example_corporate_deposit()
    # modex.example_validation_errors()
