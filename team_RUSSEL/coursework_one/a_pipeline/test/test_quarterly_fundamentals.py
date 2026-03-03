#!/usr/bin/env python3
"""
Test the quarterly fundamentals extraction on a single ticker.
Verifies that P/E, P/B, ROE etc. vary over time (not constant).

Run from coursework_one directory:
    poetry run python test_quarterly_fundamentals.py
"""
from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.input.data_extractor import DataExtractor
import pandas as pd

pd.set_option('display.max_columns', 15)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', '{:.4f}'.format)

config = load_config('a_pipeline/config/conf.yaml')
extractor = DataExtractor(config)

ticker = 'AAPL'
company = {'ticker': ticker, 'name': 'Apple Inc.', 'gics_sector': 'Tech', 'gics_industry': 'Hardware'}

print("=" * 80)
print(f"TESTING QUARTERLY FUNDAMENTALS FOR {ticker}")
print("=" * 80)

# Extract historical data with new quarterly method
print("\nExtracting historical data with quarterly fundamentals...")
df = extractor.extract_historical_data(company)

if df.empty:
    print("❌ No data returned!")
else:
    print(f"✅ Got {len(df)} monthly rows\n")

    # Show key columns
    key_cols = ['date', 'close', 'pe_ratio', 'pb_ratio', 'eps',
                'roe', 'roa', 'debt_to_equity', 'profit_margin', 'market_cap']
    available_cols = [c for c in key_cols if c in df.columns]

    print("=" * 80)
    print("HISTORICAL DATA WITH POINT-IN-TIME FUNDAMENTALS")
    print("=" * 80)
    print(df[available_cols].to_string(index=False))

    # Check if fundamentals actually vary over time
    print("\n" + "=" * 80)
    print("VARIATION CHECK (fundamentals should NOT be constant)")
    print("=" * 80)
    for col in ['pe_ratio', 'pb_ratio', 'eps', 'roe', 'market_cap']:
        if col in df.columns:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                unique_count = non_null.nunique()
                is_constant = unique_count <= 1
                status = "❌ CONSTANT (old behaviour)" if is_constant else f"✅ VARIES ({unique_count} unique values)"
                print(f"  {col}: {status}")
                if not is_constant:
                    print(f"    Range: {non_null.min():.4f} to {non_null.max():.4f}")
            else:
                print(f"  {col}: ⚠️ ALL NULL")

    # Show earliest rows with data (quarterly data only covers ~4-5 years)
    print("\n" + "=" * 80)
    print("FIRST 3 ROWS WITH FUNDAMENTALS (earliest available)")
    print("=" * 80)
    has_pe = df[df['pe_ratio'].notna()]
    if not has_pe.empty:
        print(has_pe[available_cols].head(3).to_string(index=False))
    else:
        print("⚠️ No rows have P/E ratio data")

    print("\n" + "=" * 80)
    print("LAST 3 ROWS (most recent)")
    print("=" * 80)
    print(df[available_cols].tail(3).to_string(index=False))

print("\n✅ Test complete!")