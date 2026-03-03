#!/usr/bin/env python3
"""
Test the annual fundamentals extraction on a single ticker.
Shows historical annual data (not monthly).

Run from coursework_one directory:
    poetry run python test_annual_data.py
"""
from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.input.data_extractor import DataExtractor
import pandas as pd
import yfinance as yf

pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 250)
pd.set_option('display.float_format', '{:.4f}'.format)
pd.set_option('display.max_rows', None)

config = load_config('a_pipeline/config/conf.yaml')
extractor = DataExtractor(config)

ticker = 'AAPL'
company = {'ticker': ticker, 'name': 'Apple Inc.', 'gics_sector':
            'Tech', 'gics_industry': 'Hardware'}

print("=" * 100)
print(f"ANNUAL FUNDAMENTALS DATA FOR {ticker}")
print("=" * 100)

try:
    stock = yf.Ticker(ticker)
    
    # Get income statement, balance sheet, and cash flow
    income_stmt = stock.income_stmt
    balance_sheet = stock.balance_sheet
    cashflow = stock.cashflow
    
    if income_stmt.empty or balance_sheet.empty:
        print("❌ No annual data found!")
    else:
        # Build annual fundamentals table from statements
        periods = sorted(income_stmt.columns)
        records = []
        
        for period in periods:
            # Income statement data
            eps = income_stmt.loc['Diluted EPS', period] if 'Diluted EPS' in income_stmt.index else None
            revenue = income_stmt.loc['Total Revenue', period] if 'Total Revenue' in income_stmt.index else None
            net_income = income_stmt.loc['Net Income', period] if 'Net Income' in income_stmt.index else None
            ebitda = income_stmt.loc['EBITDA', period] if 'EBITDA' in income_stmt.index else None
            
            # Balance sheet data
            equity = balance_sheet.loc['Stockholders Equity', period] if 'Stockholders Equity' in balance_sheet.index else None
            if pd.isna(equity):
                equity = balance_sheet.loc['Common Stock Equity', period] if 'Common Stock Equity' in balance_sheet.index else None
            
            total_assets = balance_sheet.loc['Total Assets', period] if 'Total Assets' in balance_sheet.index else None
            total_debt = balance_sheet.loc['Total Debt', period] if 'Total Debt' in balance_sheet.index else None
            shares = balance_sheet.loc['Ordinary Shares Number', period] if 'Ordinary Shares Number' in balance_sheet.index else None
            
            # Cash flow data
            fcf = cashflow.loc['Free Cash Flow', period] if cashflow is not None and 'Free Cash Flow' in cashflow.index else None
            
            # Calculated metrics
            book_value_ps = equity / shares if not pd.isna(equity) and not pd.isna(shares) and shares != 0 else None
            roe = net_income / equity if not pd.isna(net_income) and not pd.isna(equity) and equity != 0 else None
            roa = net_income / total_assets if not pd.isna(net_income) and not pd.isna(total_assets) and total_assets != 0 else None
            d2e = total_debt / equity if not pd.isna(total_debt) and not pd.isna(equity) and equity != 0 else None
            profit_margin = net_income / revenue if not pd.isna(net_income) and not pd.isna(revenue) and revenue != 0 else None
            
            records.append({
                'date': period,
                'year': period.year,
                'eps': eps,
                'revenue': revenue,
                'net_income': net_income,
                'ebitda': ebitda,
                'book_value': book_value_ps,
                'shares': shares,
                'total_debt': total_debt,
                'roe': roe,
                'roa': roa,
                'profit_margin': profit_margin,
                'debt_to_equity': d2e,
                'free_cash_flow': fcf,
            })
        
        annual_df = pd.DataFrame(records)
        
        print(f"\n✅ Got {len(annual_df)} years of annual data\n")
        
        # Select key columns in logical order
        key_cols = ['year', 'date', 'eps', 'revenue', 'net_income', 'ebitda',
                    'book_value', 'shares', 'roe', 'roa', 'profit_margin',
                    'debt_to_equity', 'total_debt', 'free_cash_flow']
        
        available_cols = [c for c in key_cols if c in annual_df.columns]
        
        print("=" * 100)
        print("ANNUAL FUNDAMENTALS TABLE")
        print("=" * 100)
        table_df = annual_df[available_cols].copy()
        print(table_df.to_string(index=False))
        
        # Summary statistics
        print("\n" + "=" * 100)
        print("SUMMARY STATISTICS (for numeric fields)")
        print("=" * 100)
        numeric_cols = ['eps', 'revenue', 'net_income', 'roe', 'roa', 'profit_margin']
        for col in numeric_cols:
            if col in annual_df.columns:
                non_null = annual_df[col].dropna()
                if len(non_null) > 0:
                    print(f"\n{col}:")
                    print(f"  Count: {len(non_null)}")
                    print(f"  Min: {non_null.min():.4f}, Max: {non_null.max():.4f}")
                    print(f"  Mean: {non_null.mean():.4f}, Median: {non_null.median():.4f}")
                    print(f"  Std Dev: {non_null.std():.4f}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 100)
print("TEST COMPLETE")
print("=" * 100)
