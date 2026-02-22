"""Fresh test of real data extraction."""
import sys
import importlib

# Force reload of modules
if 'modules.input.data_extractor' in sys.modules:
    del sys.modules['modules.input.data_extractor']
if 'modules.utils.config_loader' in sys.modules:
    del sys.modules['modules.utils.config_loader']

from modules.utils.config_loader import load_config
from modules.input.data_extractor import DataExtractor

print("✅ Modules reloaded!")

config = load_config('config/conf.yaml')
extractor = DataExtractor(config)

test_company = {'id': 1, 'ticker': 'AAPL', 'name': 'Apple Inc.'}

print("\n📊 Extracting AAPL data...")
df = extractor.extract_company_data(test_company)

print("\nColumns in DataFrame:")
print(df.columns.tolist())

print("\nData:")
print(df.to_string())
