#!/usr/bin/env python3
"""
Test the annual fundamentals extraction on a single ticker.
Verifies that P/E, P/B, ROE etc. vary over time (not constant).

Run from coursework_one directory:
    poetry run python test_annualy_fundamentals.py
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
company = {'ticker': ticker, 'name': 'Apple Inc.', 'gics_sector':
            'Tech', 'gics_industry': 'Hardware'}

print("=" * 80)
print(f"TESTING ANNUAL FUNDAMENTALS FOR {ticker}")
print("=" * 80)

# Extract historical data with new annual method
print("\nExtracting historical data with annual fundamentals...")
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
    print("HISTORICAL DATA WITH ANNUAL FUNDAMENTALS")
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
                    print(f"    Mean: {non_null.mean():.4f}, Std: {non_null.std():.4f}")
            else:
                print(f"  {col}: ⚠️  No non-null values to check variation.")
        else:
            print(f"  {col}: Column not found in dataset.")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

