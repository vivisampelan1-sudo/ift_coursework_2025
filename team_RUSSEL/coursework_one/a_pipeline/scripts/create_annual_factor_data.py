#!/usr/bin/env python3
"""
Aggregate factor_data into annual snapshots and join with annual_fundamentals.

This script:
1. Takes the latest month-end factor_data for each year
2. Joins with annual_fundamentals to get comprehensive annual metrics
3. Creates an annual_factor_data table for easier querying

Run from coursework_one directory:
    poetry run python create_annual_factor_data.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
from a_pipeline.modules.utils.config_loader import load_config
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_annual_factor_data():
    """Create annual factor data from monthly snapshots."""
    
    print("=" * 100)
    print("CREATING ANNUAL FACTOR DATA FROM MONTHLY SNAPSHOTS")
    print("=" * 100)
    
    config = load_config('config/conf.yaml')
    conn = psycopg2.connect(
        host=config['postgres']['host'],
        port=config['postgres']['port'],
        database=config['postgres']['database'],
        user=config['postgres']['user'],
        password=config['postgres']['password']
    )
    cursor = conn.cursor()
    
    # Step 1: Create annual_factor_data table
    print("\n📋 Creating annual_factor_data table...")
    
    create_table_sql = """
    DROP TABLE IF EXISTS systematic_equity.annual_factor_data;
    
    CREATE TABLE systematic_equity.annual_factor_data AS
    WITH yearly_factor AS (
        SELECT 
            ticker,
            company_name,
            EXTRACT(YEAR FROM date) as year,
            date,
            ROW_NUMBER() OVER (PARTITION BY ticker, EXTRACT(YEAR FROM date) ORDER BY date DESC) as rn,
            current_price,
            market_cap,
            pe_ratio,
            forward_pe,
            pb_ratio,
            ps_ratio,
            ev_to_ebitda,
            ev_to_revenue,
            book_value,
            eps,
            roe,
            roa,
            debt_to_equity,
            current_ratio,
            profit_margin,
            operating_margin,
            gross_margin,
            free_cash_flow,
            revenue,
            total_debt,
            ebitda,
            dividend_yield,
            sector,
            industry,
            db_sector,
            db_industry
        FROM systematic_equity.factor_data
    )
    SELECT 
        ticker,
        company_name,
        year,
        date,
        current_price,
        market_cap,
        pe_ratio,
        forward_pe,
        pb_ratio,
        ps_ratio,
        ev_to_ebitda,
        ev_to_revenue,
        book_value,
        eps,
        roe,
        roa,
        debt_to_equity,
        current_ratio,
        profit_margin,
        operating_margin,
        gross_margin,
        free_cash_flow,
        revenue,
        total_debt,
        ebitda,
        dividend_yield,
        sector,
        industry,
        db_sector,
        db_industry
    FROM yearly_factor
    WHERE rn = 1
    ORDER BY ticker, year;
    
    -- Create indexes for performance
    CREATE INDEX idx_annual_factor_ticker ON systematic_equity.annual_factor_data(ticker);
    CREATE INDEX idx_annual_factor_year ON systematic_equity.annual_factor_data(year);
    CREATE INDEX idx_annual_factor_ticker_year ON systematic_equity.annual_factor_data(ticker, year);
    """
    
    cursor.execute(create_table_sql)
    conn.commit()
    print("✅ annual_factor_data table created")
    
    # Step 2: Check data
    cursor.execute("""
        SELECT COUNT(*) as total_rows,
               COUNT(DISTINCT ticker) as num_tickers,
               MIN(year) as min_year,
               MAX(year) as max_year
        FROM systematic_equity.annual_factor_data;
    """)
    
    stats = cursor.fetchone()
    print(f"\n📊 Annual Factor Data Summary:")
    print(f"   Total rows: {stats[0]}")
    print(f"   Unique tickers: {stats[1]}")
    print(f"   Year range: {stats[2]} - {stats[3]}")
    
    # Step 3: Create a comprehensive view joining annual_factor_data with annual_fundamentals
    print("\n📋 Creating comprehensive annual data view...")
    
    view_sql = """
    CREATE OR REPLACE VIEW systematic_equity.annual_company_metrics AS
    SELECT 
        COALESCE(fd.ticker, af.ticker) as ticker,
        COALESCE(fd.company_name, af.company_name) as company_name,
        cs.security,
        cs.gics_sector,
        cs.gics_industry,
        cs.country,
        cs.region,
        COALESCE(fd.year, af.year) as year,
        
        -- Price & Valuation (from factor_data)
        fd.current_price,
        fd.market_cap,
        fd.pe_ratio,
        fd.forward_pe,
        fd.pb_ratio,
        fd.ps_ratio,
        fd.ev_to_ebitda,
        fd.ev_to_revenue,
        fd.dividend_yield,
        
        -- Fundamentals (from factor_data)
        fd.eps as eps_factor,
        fd.roe as roe_factor,
        fd.roa as roa_factor,
        fd.debt_to_equity as de_factor,
        fd.profit_margin as pm_factor,
        fd.operating_margin,
        fd.gross_margin,
        
        -- Detailed Fundamentals (from annual_fundamentals)
        af.eps as eps_annual,
        af.revenue,
        af.net_income,
        af.ebitda as ebitda_annual,
        af.book_value,
        af.shares,
        af.total_assets,
        af.total_debt as total_debt_annual,
        af.equity,
        af.roe as roe_annual,
        af.roa as roa_annual,
        af.profit_margin as pm_annual,
        af.debt_to_equity as de_annual,
        af.free_cash_flow,
        
        fd.date as snapshot_date
    FROM systematic_equity.annual_factor_data fd
    FULL OUTER JOIN systematic_equity.annual_fundamentals af 
        ON fd.ticker = af.ticker AND fd.year = af.year
    LEFT JOIN systematic_equity.company_static cs 
        ON COALESCE(fd.ticker, af.ticker) = cs.symbol
    ORDER BY COALESCE(fd.ticker, af.ticker), COALESCE(fd.year, af.year);
    """
    
    cursor.execute(view_sql)
    conn.commit()
    print("✅ annual_company_metrics view created")
    
    # Step 4: Show sample data
    print(f"\n📋 Sample data from annual_company_metrics (2025):")
    print("=" * 100)
    
    cursor.execute("""
        SELECT 
            ticker, company_name, gics_sector, pe_ratio, pb_ratio, roe_factor, pm_factor, de_factor, year
        FROM systematic_equity.annual_company_metrics
        WHERE year = 2025
        LIMIT 10;
    """)
    
    print(f"{'Ticker':<8} {'Company':<25} {'Sector':<20} {'P/E':<8} {'P/B':<8} {'ROE':<8} {'PM':<8} {'D/E':<8} {'Year':<6}")
    print("-" * 110)
    
    for row in cursor.fetchall():
        ticker, company, sector, pe, pb, roe, pm, de, year = row
        pe_str = f"{float(pe):.2f}" if pe else "N/A"
        pb_str = f"{float(pb):.2f}" if pb else "N/A"
        roe_str = f"{float(roe):.4f}" if roe else "N/A"
        pm_str = f"{float(pm):.4f}" if pm else "N/A"
        de_str = f"{float(de):.4f}" if de else "N/A"
        
        print(f"{ticker:<8} {(company or 'N/A')[:25]:<25} {(sector or 'N/A')[:20]:<20} {pe_str:<8} {pb_str:<8} {roe_str:<8} {pm_str:<8} {de_str:<8} {year:<6}")
    
    # Step 5: Show what queries are now possible
    print("\n" + "=" * 100)
    print("✅ ANNUAL FACTOR DATA SUCCESSFULLY CREATED")
    print("=" * 100)
    
    print("\n📚 Now you can run queries like:")
    print("""
-- Top 10 cheapest stocks with good quality (Value + Quality screen)
SELECT ticker, company_name, gics_sector, pe_ratio, pb_ratio, roe_factor, pm_factor, de_factor
FROM systematic_equity.annual_company_metrics
WHERE year = 2025 
  AND pe_ratio > 0 AND pe_ratio < 100 
  AND roe_factor > 0.15
  AND pm_factor > 0.15
ORDER BY pe_ratio ASC
LIMIT 10;

-- Compare companies by sector (2025)
SELECT gics_sector,
       COUNT(DISTINCT ticker) as num_companies,
       ROUND(AVG(pe_ratio)::numeric, 2) as avg_pe,
       ROUND(AVG(pb_ratio)::numeric, 2) as avg_pb,
       ROUND(AVG(roe_factor)::numeric, 4) as avg_roe,
       ROUND(AVG(pm_factor)::numeric, 4) as avg_pm
FROM systematic_equity.annual_company_metrics
WHERE year = 2025 AND pe_ratio > 0
GROUP BY gics_sector
ORDER BY avg_roe DESC;

-- Find improving companies (2023 vs 2025)
SELECT a.ticker, a.company_name, 
       a.pm_factor as pm_2023, 
       b.pm_factor as pm_2025,
       (b.pm_factor - a.pm_factor) as pm_improvement
FROM systematic_equity.annual_company_metrics a
JOIN systematic_equity.annual_company_metrics b 
  ON a.ticker = b.ticker AND b.year = 2025 AND a.year = 2023
WHERE b.pm_factor > a.pm_factor
ORDER BY pm_improvement DESC
LIMIT 20;
    """)
    
    conn.close()


if __name__ == '__main__':
    create_annual_factor_data()
