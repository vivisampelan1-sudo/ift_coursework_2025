#!/usr/bin/env python3
"""
Load annual fundamentals CSV data into PostgreSQL database.

This script reads the annual_fundamentals CSV file and inserts the data
into the systematic_equity.annual_fundamentals table, joining with the
existing company_static table.

Run from coursework_one directory:
    poetry run python load_annual_fundamentals_to_db.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import psycopg2
from datetime import datetime
import logging

from a_pipeline.modules.utils.config_loader import load_config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_csv_to_db(csv_file, config):
    """
    Load annual fundamentals CSV into PostgreSQL database.
    
    :param csv_file: Path to the CSV file
    :param config: Configuration dictionary with database settings
    """
    print("=" * 100)
    print("LOADING ANNUAL FUNDAMENTALS TO DATABASE")
    print("=" * 100)
    
    # Read CSV
    print(f"\n📥 Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"✅ Loaded {len(df)} rows from CSV")
    
    # Connect to database
    print(f"\n🔌 Connecting to PostgreSQL database...")
    conn = psycopg2.connect(
        host=config['postgres']['host'],
        port=config['postgres']['port'],
        database=config['postgres']['database'],
        user=config['postgres']['user'],
        password=config['postgres']['password']
    )
    cursor = conn.cursor()
    print("✅ Connected to database")
    
    # First, create the table and schema if they don't exist
    print(f"\n📋 Creating schema and table...")
    with open('000.Database/SQL/load_annual_fundamentals.sql', 'r') as f:
        sql_script = f.read()
    
    # Execute SQL script
    cursor.execute(sql_script)
    conn.commit()
    print("✅ Schema and tables created")
    
    # Prepare data for insertion
    print(f"\n🔄 Preparing data for insertion...")
    insert_count = 0
    skip_count = 0
    error_count = 0
    
    # Convert date column to proper format
    df['date'] = pd.to_datetime(df['date'])
    
    # Replace NaN with None for proper NULL insertion
    df = df.where(pd.notna(df), None)
    
    # Insert data
    print(f"\n📤 Inserting {len(df)} rows into database...")
    
    insert_query = """
        INSERT INTO systematic_equity.annual_fundamentals 
        (ticker, company_name, date, year, eps, revenue, net_income, ebitda,
         book_value, shares, total_assets, total_debt, equity,
         roe, roa, profit_margin, debt_to_equity, free_cash_flow)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, date) DO UPDATE 
        SET company_name = EXCLUDED.company_name,
            year = EXCLUDED.year,
            eps = EXCLUDED.eps,
            revenue = EXCLUDED.revenue,
            net_income = EXCLUDED.net_income,
            ebitda = EXCLUDED.ebitda,
            book_value = EXCLUDED.book_value,
            shares = EXCLUDED.shares,
            total_assets = EXCLUDED.total_assets,
            total_debt = EXCLUDED.total_debt,
            equity = EXCLUDED.equity,
            roe = EXCLUDED.roe,
            roa = EXCLUDED.roa,
            profit_margin = EXCLUDED.profit_margin,
            debt_to_equity = EXCLUDED.debt_to_equity,
            free_cash_flow = EXCLUDED.free_cash_flow,
            updated_at = CURRENT_TIMESTAMP;
    """
    
    for idx, row in df.iterrows():
        try:
            cursor.execute(insert_query, (
                row['ticker'], row['company_name'], row['date'], row['year'],
                row['eps'], row['revenue'], row['net_income'], row['ebitda'],
                row['book_value'], row['shares'], row['total_assets'], 
                row['total_debt'], row['equity'],
                row['roe'], row['roa'], row['profit_margin'], 
                row['debt_to_equity'], row['free_cash_flow']
            ))
            insert_count += 1
            
            # Show progress every 100 rows
            if (idx + 1) % 100 == 0:
                print(f"  Progress: {idx + 1}/{len(df)} rows inserted")
                conn.commit()
        
        except psycopg2.IntegrityError as e:
            conn.rollback()
            skip_count += 1
            logger.debug(f"Row {idx} skipped (duplicate or integrity error): {e}")
        except Exception as e:
            error_count += 1
            logger.error(f"Row {idx} error: {e}")
    
    conn.commit()
    
    # Get summary statistics
    print(f"\n📊 Retrieving database summary...")
    cursor.execute("""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT ticker) as unique_tickers,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT year) as years_covered
        FROM systematic_equity.annual_fundamentals;
    """)
    
    stats = cursor.fetchone()
    
    print("\n" + "=" * 100)
    print("LOAD SUMMARY")
    print("=" * 100)
    print(f"✅ Rows inserted: {insert_count}")
    print(f"⏭️  Rows skipped (duplicates): {skip_count}")
    if error_count > 0:
        print(f"❌ Rows with errors: {error_count}")
    print(f"\n📈 Database Statistics:")
    print(f"   Total rows in table: {stats[0]}")
    print(f"   Unique tickers: {stats[1]}")
    print(f"   Date range: {stats[2]} to {stats[3]}")
    print(f"   Years covered: {stats[4]}")
    
    # Show sample join query
    print(f"\n📋 Sample data from annual_fundamentals_with_details view:")
    print("=" * 100)
    
    cursor.execute("""
        SELECT 
            ticker, company_name, gics_sector, gics_industry, 
            year, eps, roe, profit_margin, debt_to_equity
        FROM systematic_equity.annual_fundamentals_with_details
        WHERE year = 2025
        LIMIT 10;
    """)
    
    columns = [desc[0] for desc in cursor.description]
    print(f"\n{'Ticker':<8} {'Company':<25} {'Sector':<20} {'Industry':<20} {'Year':<6} {'EPS':<10} {'ROE':<8} {'PM':<8} {'D/E':<8}")
    print("-" * 130)
    
    for row in cursor.fetchall():
        ticker, company, sector, industry, year, eps, roe, pm, de = row
        eps_str = f"{eps:.2f}" if eps else "N/A"
        roe_str = f"{roe:.4f}" if roe else "N/A"
        pm_str = f"{pm:.4f}" if pm else "N/A"
        de_str = f"{de:.4f}" if de else "N/A"
        
        print(f"{ticker:<8} {(company or 'N/A')[:25]:<25} {(sector or 'N/A')[:20]:<20} {(industry or 'N/A')[:20]:<20} {year:<6} {eps_str:<10} {roe_str:<8} {pm_str:<8} {de_str:<8}")
    
    # Close connection
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("✅ DATA SUCCESSFULLY LOADED TO DATABASE")
    print("=" * 100)
    
    # Print some useful SQL queries
    print("\n📚 Useful SQL Queries:")
    print("=" * 100)
    print("""
1. Get top 10 companies by ROE in 2025:
   SELECT ticker, company_name, roe, gics_sector 
   FROM systematic_equity.annual_fundamentals_with_details
   WHERE year = 2025 AND roe IS NOT NULL
   ORDER BY roe DESC LIMIT 10;

2. Find companies with improving profitability (2023-2025):
   SELECT ticker, company_name, 
          MAX(CASE WHEN year = 2023 THEN profit_margin END) as pm_2023,
          MAX(CASE WHEN year = 2024 THEN profit_margin END) as pm_2024,
          MAX(CASE WHEN year = 2025 THEN profit_margin END) as pm_2025
   FROM systematic_equity.annual_fundamentals
   WHERE year IN (2023, 2024, 2025)
   GROUP BY ticker, company_name
   HAVING MAX(CASE WHEN year = 2025 THEN profit_margin END) > 
          MAX(CASE WHEN year = 2023 THEN profit_margin END);

3. Compare average metrics by sector (2025):
   SELECT gics_sector,
          COUNT(DISTINCT ticker) as num_companies,
          AVG(roe) as avg_roe,
          AVG(profit_margin) as avg_profit_margin,
          AVG(debt_to_equity) as avg_debt_to_equity
   FROM systematic_equity.annual_fundamentals_with_details
   WHERE year = 2025
   GROUP BY gics_sector
   ORDER BY avg_roe DESC;

4. Find undervalued companies (low P/E and P/B):
   SELECT ticker, company_name, gics_sector, 
          eps, roe, profit_margin
   FROM systematic_equity.annual_fundamentals_with_details
   WHERE year = 2025 AND roe > 0.15
   ORDER BY roe DESC;
    """)
    print("=" * 100)


if __name__ == '__main__':
    config = load_config('config/conf.yaml')
    csv_file = 'annual_fundamentals_20260223_213714.csv'
    load_csv_to_db(csv_file, config)
