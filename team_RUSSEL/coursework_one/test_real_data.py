"""Test extraction with real financial data."""
from modules.utils.config_loader import load_config
from modules.input.data_extractor import DataExtractor

# Load config
config = load_config('config/conf.yaml')
print("✅ Configuration loaded!")

# Initialize extractor
extractor = DataExtractor(config)
print("✅ DataExtractor initialized with yfinance!")

# Test with one company first
print("\n" + "="*70)
print("📊 Testing with Apple (AAPL)")
print("="*70)

test_company = {'id': 1, 'ticker': 'AAPL', 'name': 'Apple Inc.'}

# Extract current data
print("\n1️⃣  Current Value Factor Metrics:")
print("-"*70)
current_df = extractor.extract_company_data(test_company)
print(current_df.to_string())

# Check for real values
print("\n📈 Data Quality Check:")
if current_df['pe_ratio'].iloc[0] is not None:
    print(f"   ✅ P/E Ratio: {current_df['pe_ratio'].iloc[0]:.2f}")
else:
    print("   ⚠️  P/E Ratio: Not available")

if current_df['pb_ratio'].iloc[0] is not None:
    print(f"   ✅ P/B Ratio: {current_df['pb_ratio'].iloc[0]:.2f}")
else:
    print("   ⚠️  P/B Ratio: Not available")

if current_df['market_cap'].iloc[0] is not None:
    market_cap_b = current_df['market_cap'].iloc[0] / 1e9
    print(f"   ✅ Market Cap: ${market_cap_b:.2f}B")
else:
    print("   ⚠️  Market Cap: Not available")

# Extract historical data
print("\n2️⃣  Historical Price Data (Last 5 Years):")
print("-"*70)
hist_df = extractor.extract_historical_data(test_company)
if not hist_df.empty:
    print(f"   ✅ Retrieved {len(hist_df)} months of data")
    print("\n   First 5 records:")
    print(hist_df.head().to_string(index=False))
    print("\n   Last 5 records:")
    print(hist_df.tail().to_string(index=False))
else:
    print("   ❌ No historical data retrieved")

print("\n" + "="*70)
print("✅ Real data extraction test complete!")
print("="*70)
