# ─── main.py ───────────────────────────────────────────────────────────────────

import pandas as pd

from granite.client import GraniteAPI
from granite.expense_categorizer import ExpenseCategorizer
from granite.invoice_parser import InvoiceParser
from granite.financial_scorer_granite import FinancialScorerGranite

#from utils.prophet_forecast import CashFlowForecaster
from utils.tax_estimator import TaxEstimator
from utils.vector_index import RAGLoanAdvisor
from utils.financial_scorer_rules import FinancialScorerRules
from cashflow_forecasting.forecasting_engine import CashFlowForecaster
from cashflow_forecasting.forecasting_engine import ForecastExplainer
from cashflow_forecasting.scenario_manager import apply_scenario
from utils.business_profile import load_profile
from dash_modules.analytics.run_smb_analysis import run_smb_analysis

print("✅ financial_bot.py loaded")



class FinancialBot:
    """
    Orchestrates all modules, including dynamic tax‐bracket lookup by country.
    """

    def __init__(self):
        print("✅ financial_bot.py loaded")

        # Initialize Granite client
        self.granite_client = GraniteAPI()

        # Module instances
        self.expense_categorizer    = ExpenseCategorizer(self.granite_client)
        self.invoice_parser         = InvoiceParser(self.granite_client)
        self.cash_flow_forecaster   = CashFlowForecaster()
        self.tax_estimator          = TaxEstimator(self.granite_client)
        self.loan_advisor           = RAGLoanAdvisor()
        self.scorer_rules           = FinancialScorerRules()
        self.scorer_granite         = FinancialScorerGranite(self.granite_client)
        self.forecast_explainer = ForecastExplainer(self.granite_client)
        


        # Data container
        self.transactions = pd.DataFrame()

    def load_ledger_json(self, json_path: str) -> bool:
        """
        Load transactions from a JSON file in the format:
        {
            "root": {
                "balance": float,
                "history": [
                    {
                        "amount": float,
                        "type": "credit" | "debit",
                        "desc": str,
                        "date": "MM/DD/YY" or similar
                    },
                    ...
                ]
            }
        }
        """
        import json
        from pathlib import Path
    
        try:
            path = Path(json_path)
            if not path.exists():
                print(f"❌ File not found: {json_path}")
                return False
    
            with open(path, 'r') as f:
                raw = json.load(f)
    
            df = pd.DataFrame(raw["history"])
            
            df['Date'] = pd.to_datetime(df['date'], errors='coerce')
            df['Amount'] = pd.to_numeric(df['amount'], errors='coerce')
            df["credit"] = df.apply(lambda row: row["amount"] if row["type"] == "credit" else 0, axis=1)
            df["debit"] = df.apply(lambda row: row["amount"] if row["type"] == "debit" else 0, axis=1)
            # Debit amounts are negative
            df['Amount'] = df.apply(
                lambda row: -row['Amount'] if row.get('type', '').lower() == 'debit' else row['Amount'],
                axis=1
            )
    
            df['Description'] = df['desc'].astype(str).str.strip()
            df = df[abs(df['Amount']) > 0.01].copy()
    
            df = df.rename(columns={"credit": "Credit", "debit": "Debit"})
            self.transactions = df
            print(f"✅ Loaded {len(df)} transactions from JSON.")
            return True
    
        except Exception as e:
            print(f"❌ Error loading JSON ledger: {e}")
            return False


    def categorize_all(self):
        if self.transactions.empty:
            print("No transactions loaded.")
            return
        self.transactions['Category'] = self.transactions.apply(
            lambda row: self.expense_categorizer.categorize(row['Description'], row['Amount']),
            axis=1
        )
        print("✅ All transactions categorized.")

    def forecast_cash_flow(self) -> dict:
        return self.cash_flow_forecaster.forecast(self.transactions)

    def loan_advice(self, question: str) -> str:
        return self.loan_advisor.answer_loan_question(question)

    def score_financials(self) -> dict:
            business_profile = load_profile()
            results = run_smb_analysis(business_profile)

            return {
                "score": results["score"]["overall_score"],
                "rating": results["score"]["health_rating"],
                "summary": results["summary"],
                #"insights": results["insights"],
                #"benchmarking": results["benchmarking"],
                #"ai_analysis": results["ai_analysis"]
            }
    
    def explain_cashflow_forecast(self, days=30) -> str:
        forecast_df = self.cash_flow_forecaster.forecast(self.transactions, days)
        return self.forecast_explainer.explain_forecast(forecast_df, days)
    
    def simulate_and_explain(self, scenario: dict) -> str:
        print("Scene:",scenario)
        from cashflow_forecasting.scenario_manager import apply_scenario
        forecast_df = self.cash_flow_forecaster.forecast(self.transactions, 30)
        adjusted_df = apply_scenario(forecast_df, scenario)
        return self.forecast_explainer.explain_forecast(adjusted_df,30)


    def run_full_analysis(self, json_path: str):
        # 1) Load JSON Ledger
        if not self.load_ledger_json(json_path):
            return
    
        # 2) Categorize expenses
        self.categorize_all()
    
        # 3) Forecast cash flow
        forecast = self.forecast_cash_flow()
        print("\n📈 Cash Flow Forecast (next 5 days):")
        for date, pred in zip(forecast['ds'][-5:], forecast['yhat'][-5:]):
            print(f"  • {date}: ${pred:,.2f}")
    
        # 4) Ask user for country/region to estimate taxes
        country = input("\nEnter the country/region for SMB tax estimation (e.g., 'United States', 'Singapore'): ").strip()
        annual_profit = self.transactions[self.transactions['Amount'] > 0]['Amount'].sum() \
                        - abs(self.transactions[self.transactions['Amount'] < 0]['Amount'].sum())
        tax_info = self.tax_estimator.estimate(annual_profit, country)
    
        # 5) Display tax estimation results
        print(f"\n💼 SMB Tax Estimation for {country}:")
        if tax_info.get("error"):
            print(f"  ❌ {tax_info['error']}")
        else:
            print(f"  • Annual Net Profit: ${tax_info['annual_net_profit']:,.2f}")
            print(f"  • Estimated Tax Owed: ${tax_info['estimated_tax']:,.2f}")
            print("  • Brackets:")
            for b in tax_info['brackets']:
                print(f"    – {b['min_income']:,} to {b.get('max_income', '∞'):,} @ {b['rate']*100:.1f}%")
            if tax_info['deductions']:
                print("  • Deductions:")
                for d in tax_info['deductions']:
                    if d.get("max_amount") is not None:
                        print(f"    – {d['name']}: up to ${d['max_amount']:,}")
                    elif d.get("percent") is not None:
                        print(f"    – {d['name']}: {d['percent']*100:.1f}% of taxable income")
            if tax_info['subsidies']:
                print("  • Subsidies/Credits:")
                for s in tax_info['subsidies']:
                    print(f"    – {s['name']}: {s['description']}")
            if tax_info.get("applied_deductions"):
                print("  • Applied Deductions (demo):")
                for ad in tax_info['applied_deductions']:
                    print(f"    – {ad}")
            print("\n  📝 Granite Breakdown:\n")
            print(tax_info['granite_breakdown'])
    
        # 6) Sample RAG loan advice  
        sample_q = "What SBA loan programs have the lowest interest rates for small retailers?"
        loan_answer = self.loan_advice(sample_q)
        print(f"\n💡 Sample Loan Advice:\n{loan_answer}")
    
        # 7) Financial health score + commentary
        score_data = self.score_financials()
        print(f"\n🏅 Financial Health Score: {score_data['score']}/100")
        print(f"🗒 Commentary:\n{score_data['commentary']}")
    
    
    def forecast_summary(self, days: int = 30) -> str:
        print("✅ forecast_summary method called")
        print(self.transactions)

        forecast_df = self.cash_flow_forecaster.forecast_summary(self.transactions, days)

        neg_days = forecast_df.get("neg", 0)

        if neg_days > 0:
            return (
                f"📉 Cash Flow Alert!\n"
                f"Your forecast shows {neg_days} day(s) with negative projected balance in the next {days} days.\n"
                f"💡 Consider cutting expenses or delaying non-essential payments.\n\n"
                f"📊 Forecast Summary:\n"
                f"- Min: ${forecast_df['min']}\n"
                f"- Max: ${forecast_df['max']}\n"
                f"- Avg: ${forecast_df['mean']}"
            )

        return (
            f"✅ Your cash flow looks healthy for the next {days} days!\n\n"
            f"📊 Forecast Summary:\n"
            f"- Min: ${forecast_df['min']}\n"
            f"- Max: ${forecast_df['max']}\n"
            f"- Avg: ${forecast_df['mean']}"
        )



if __name__ == "__main__":
    bot = FinancialBot()
    bot.run_full_analysis("ledger/ledger.json")