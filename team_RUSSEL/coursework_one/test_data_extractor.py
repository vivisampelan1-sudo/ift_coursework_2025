"""Test the data extraction module."""
from modules.utils.config_loader import load_config
from modules.input.data_extractor import DataExtractor

# Load configuration
config = load_config('config/conf.yaml')
print("✅ Configuration loaded!")

# Initialize data extractor
extractor = DataExtractor(config)
print("✅ DataExtractor initialized!")
print(f"   Lookback years: {extractor.lookback_years}")

# Create sample companies for testing
sample_companies = [
    {'id': 1, 'ticker': 'AAPL', 'name': 'Apple Inc.'},
    {'id': 2, 'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
    {'id': 3, 'ticker': 'GOOGL', 'name': 'Alphabet Inc.'},
]

# Extract data
print("\n📊 Extracting data for sample companies...")
df = extractor.extract_bulk_data(sample_companies)

# Display results
print("\n✅ Extraction complete!")
print(f"   Total records: {len(df)}")
print("\nData preview:")
print(df)
