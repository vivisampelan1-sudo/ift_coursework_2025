#!/usr/bin/env python3
"""
Example queries for annual company metrics.

Run these queries to analyze the data.
"""

EXAMPLE_QUERIES = {
    "value_quality_screen": """
    -- Top 10 cheapest stocks with good quality (Value + Quality screen)
    SELECT ticker, company_name, gics_sector, gics_industry,
           pe_ratio, pb_ratio, roe_factor, pm_factor, de_factor
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025 
      AND pe_ratio > 0 AND pe_ratio < 100 
      AND roe_factor > 0.15
      AND pm_factor > 0.15
    ORDER BY pe_ratio ASC
    LIMIT 10;
    """,
    
    "sector_comparison": """
    -- Average metrics by sector (2025)
    SELECT gics_sector,
           COUNT(DISTINCT ticker) as num_companies,
           ROUND(AVG(pe_ratio)::numeric, 2) as avg_pe,
           ROUND(AVG(pb_ratio)::numeric, 2) as avg_pb,
           ROUND(AVG(roe_factor)::numeric, 4) as avg_roe,
           ROUND(AVG(pm_factor)::numeric, 4) as avg_pm,
           ROUND(AVG(de_factor)::numeric, 4) as avg_de
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025 AND pe_ratio > 0
    GROUP BY gics_sector
    ORDER BY avg_roe DESC;
    """,
    
    "improving_profitability": """
    -- Companies with improving profitability (2023 → 2025)
    SELECT a.ticker, a.company_name, cs.gics_sector,
           ROUND(a.pm_factor::numeric, 4) as pm_2023,
           ROUND(b.pm_factor::numeric, 4) as pm_2025,
           ROUND((b.pm_factor - a.pm_factor)::numeric, 4) as improvement
    FROM systematic_equity.annual_company_metrics a
    JOIN systematic_equity.annual_company_metrics b 
      ON a.ticker = b.ticker AND b.year = 2025 AND a.year = 2023
    JOIN systematic_equity.company_static cs ON a.ticker = cs.symbol
    WHERE b.pm_factor > a.pm_factor AND a.pm_factor IS NOT NULL AND b.pm_factor IS NOT NULL
    ORDER BY improvement DESC
    LIMIT 20;
    """,
    
    "high_quality_companies": """
    -- High-quality companies (High ROE + Low Debt + Good PM)
    SELECT ticker, company_name, gics_sector,
           pe_ratio, roe_factor, pm_factor, de_factor,
           market_cap
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025
      AND roe_factor > 0.20
      AND de_factor < 1.0
      AND pm_factor > 0.20
      AND pe_ratio > 0 AND pe_ratio < 50
    ORDER BY roe_factor DESC
    LIMIT 15;
    """,
    
    "growth_at_reasonable_price": """
    -- Growth at reasonable price (GARP screen)
    SELECT ticker, company_name, gics_sector,
           pe_ratio, eps_annual, revenue, net_income,
           profit_margin as pm_annual, free_cash_flow
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025
      AND pe_ratio > 0 AND pe_ratio < 30
      AND roe_annual > 0.15
      AND profit_margin > 0.10
      AND revenue IS NOT NULL
    ORDER BY pe_ratio ASC
    LIMIT 20;
    """,
    
    "dividend_yield_quality": """
    -- High dividend yield with quality
    SELECT ticker, company_name, gics_sector,
           dividend_yield, pe_ratio, roe_factor, pm_factor
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025
      AND dividend_yield > 0.03
      AND dividend_yield IS NOT NULL
      AND roe_factor > 0.10
      AND pe_ratio > 0 AND pe_ratio < 50
    ORDER BY dividend_yield DESC
    LIMIT 15;
    """,
    
    "distressed_recovery": """
    -- Potentially distressed companies that might recover
    SELECT ticker, company_name, gics_sector,
           pe_ratio, pb_ratio, roe_factor, de_factor,
           market_cap
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025
      AND pb_ratio < 0.8
      AND de_factor > 2.0
      AND pe_ratio > 0 AND pe_ratio < 20
      AND pb_ratio IS NOT NULL
    ORDER BY pb_ratio ASC
    LIMIT 15;
    """,
    
    "financial_health": """
    -- Companies with strong financial health
    SELECT ticker, company_name, gics_sector,
           de_factor, current_ratio, profit_margin as pm,
           free_cash_flow, revenue
    FROM systematic_equity.annual_company_metrics
    WHERE year = 2025
      AND de_factor < 0.5
      AND current_ratio > 1.5
      AND profit_margin > 0.15
      AND free_cash_flow IS NOT NULL AND free_cash_flow > 0
    ORDER BY de_factor ASC
    LIMIT 20;
    """,
}

if __name__ == '__main__':
    print("=" * 120)
    print("USEFUL SQL QUERIES FOR ANNUAL COMPANY METRICS")
    print("=" * 120)
    
    for name, query in EXAMPLE_QUERIES.items():
        print(f"\n📊 {name.upper().replace('_', ' ')}")
        print("-" * 120)
        print(query.strip())
        print()
