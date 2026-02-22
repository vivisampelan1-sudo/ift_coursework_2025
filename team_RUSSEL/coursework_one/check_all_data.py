"""Check all data in the pipeline."""
import psycopg2
from pymongo import MongoClient
import pandas as pd

print("="*70)
print("📊 COMPLETE DATA AUDIT")
print("="*70)

# 1. PostgreSQL - Company List
print("\n1️⃣  POSTGRESQL - Companies (Source Data)")
print("-"*70)
conn = psycopg2.connect(
    host="localhost",
    port=5439,
    database="fift",
    user="postgres",
    password="postgres"
)
query = "SELECT id, ticker, company_name FROM systematic_equity.company_static ORDER BY ticker"
companies_df = pd.read_sql(query, conn)
print(companies_df.to_string(index=False))
conn.close()

# 2. MongoDB - Extracted Data
print("\n2️⃣  MONGODB - Extracted Financial Data")
print("-"*70)
client = MongoClient("mongodb://localhost:27019/")
db = client['investment_data']
mongo_data = list(db['company_metrics'].find({}, {'_id': 0}))

if mongo_data:
    mongo_df = pd.DataFrame(mongo_data)
    print(mongo_df.to_string(index=False))
    
    # Check if data has real values or just None
    print("\n📈 Data Quality Check:")
    null_counts = mongo_df.isnull().sum()
    print(f"   Revenue nulls: {null_counts.get('revenue', 0)}/{len(mongo_df)}")
    print(f"   Profit nulls: {null_counts.get('profit', 0)}/{len(mongo_df)}")
    print(f"   Market cap nulls: {null_counts.get('market_cap', 0)}/{len(mongo_df)}")
    
    if null_counts.get('revenue', 0) == len(mongo_df):
        print("\n⚠️  WARNING: All financial data is NULL (placeholder data)")
        print("   You may need to connect to a real data source for actual values")
else:
    print("   No data found!")

# 3. Summary
print("\n" + "="*70)
print("📋 SUMMARY")
print("="*70)
print(f"✅ PostgreSQL: {len(companies_df)} companies")
print(f"✅ MongoDB: {len(mongo_data)} records")
print(f"⚠️  Data Status: {'PLACEHOLDER (None values)' if null_counts.get('revenue', 0) == len(mongo_df) else 'REAL DATA'}")
print("="*70)
