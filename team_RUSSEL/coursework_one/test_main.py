"""Quick test to see if Main.py components work."""
from modules.utils.config_loader import load_config
from modules.db.db_connection import DatabaseConnector, load_company_list

config = load_config('config/conf.yaml')
print("✅ Config loaded")

db_connector = DatabaseConnector(config)
print("✅ DB connected")

companies = load_company_list(db_connector)
print(f"✅ Found {len(companies)} companies:")
for company in companies:
    print(f"   - {company['ticker']}: {company['name']}")

db_connector.close_all()
