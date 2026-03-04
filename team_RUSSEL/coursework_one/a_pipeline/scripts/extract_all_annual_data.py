#!/usr/bin/env python3
"""
Extract annual fundamentals for all companies in the database.
Processes ~600 companies and saves results to CSV.

Run from coursework_one directory:
    poetry run python extract_all_annual_data.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import yfinance as yf
from datetime import datetime
import logging
from pathlib import Path

from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.db.db_connection import DatabaseConnector, load_company_list

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

pd.set_option('display.max_columns', 20)
pd.set_option('display.float_format', '{:.4f}'.format)

def extract_annual_fundamentals_for_company(ticker: str, company_name: str) -> pd.DataFrame:
    """
    Extract annual fundamentals for a single company.

    :param ticker: Stock ticker symbol.
    :param company_name: Company name for display.
    :returns: DataFrame with annual fundamentals or empty DataFrame if failed.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get income statement, balance sheet, and cash flow
        income_stmt = stock.income_stmt
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        if income_stmt.empty or balance_sheet.empty:
            logger.warning(f"[{ticker}] No annual data found")
            return pd.DataFrame()
        
        # Build annual fundamentals table from statements
        periods = sorted(income_stmt.columns)
        records = []
        
        for period in periods:
            try:
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
                    'ticker': ticker,
                    'company_name': company_name,
                    'date': period,
                    'year': period.year,
                    'eps': eps,
                    'revenue': revenue,
                    'net_income': net_income,
                    'ebitda': ebitda,
                    'book_value': book_value_ps,
                    'shares': shares,
                    'total_assets': total_assets,
                    'total_debt': total_debt,
                    'equity': equity,
                    'roe': roe,
                    'roa': roa,
                    'profit_margin': profit_margin,
                    'debt_to_equity': d2e,
                    'free_cash_flow': fcf,
                })
            except Exception as e:
                logger.debug(f"[{ticker}] Error processing period {period}: {e}")
                continue
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        logger.info(f"[{ticker}] ✅ Extracted {len(df)} periods")
        return df
    
    except Exception as e:
        logger.error(f"[{ticker}] Failed: {e}")
        return pd.DataFrame()


def main():
    """Main extraction pipeline for all companies."""
    print("=" * 100)
    print("EXTRACTING ANNUAL FUNDAMENTALS FOR ALL COMPANIES")
    print("=" * 100)
    
    # Load configuration and database connector
    config = load_config('config/conf.yaml')
    db_connector = DatabaseConnector(config)
    
    # Load all companies from database
    print("\n📥 Loading company list from database...")
    companies = load_company_list(db_connector)
    print(f"✅ Loaded {len(companies)} companies\n")
    
    # Extract fundamentals for all companies
    all_results = []
    failed_count = 0
    empty_count = 0
    
    print(f"{'Ticker':<10} {'Company':<40} {'Periods':<10} {'Status'}")
    print("-" * 100)
    
    for idx, company in enumerate(companies, 1):
        ticker = company['ticker']
        name = company['name'][:35]  # Truncate for display
        
        annual_df = extract_annual_fundamentals_for_company(ticker, company['name'])
        
        if annual_df.empty:
            status = "❌ No data"
            empty_count += 1
        else:
            status = f"✅ {len(annual_df)} rows"
            all_results.append(annual_df)
        
        # Progress display every 50 companies
        if idx % 50 == 0 or idx == 1:
            print(f"[{idx}/{len(companies)}]", end=" ")
        
        if (idx % 10) == 0:
            print(f"{ticker:<10} {name:<40} {status}")
    
    print("\n" + "=" * 100)
    print("EXTRACTION COMPLETE")
    print("=" * 100)
    
    if all_results:
        # Combine all results
        combined_df = pd.concat(all_results, ignore_index=True)
        print(f"\n📊 Combined Results:")
        print(f"   Total companies with data: {len(combined_df['ticker'].unique())}")
        print(f"   Total periods extracted: {len(combined_df)}")
        print(f"   Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
        
        # Save to CSV
        output_file = f"annual_fundamentals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        combined_df.to_csv(output_file, index=False)
        print(f"\n💾 Saved to: {output_file}")
        
        # Show sample data
        print("\n" + "=" * 100)
        print("SAMPLE DATA (first 20 rows)")
        print("=" * 100)
        sample_cols = ['ticker', 'year', 'eps', 'revenue', 'net_income', 'roe', 'roa', 'profit_margin']
        print(combined_df[sample_cols].head(20).to_string(index=False))
        
        # Show summary statistics by ticker (top 10)
        print("\n" + "=" * 100)
        print("TOP 10 COMPANIES BY NUMBER OF PERIODS")
        print("=" * 100)
        ticker_counts = combined_df['ticker'].value_counts().head(10)
        for ticker, count in ticker_counts.items():
            print(f"  {ticker}: {count} periods")
    else:
        print("❌ No data extracted for any company!")
        failed_count = len(companies)
    
    print(f"\n📈 Summary:")
    print(f"   Companies extracted: {len(combined_df['ticker'].unique()) if all_results else 0}")
    print(f"   Failed companies: {empty_count}")
    print(f"   Total companies attempted: {len(companies)}")
    print("\n" + "=" * 100)


if __name__ == '__main__':
    main()
