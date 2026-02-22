"""Clean old placeholder data from MongoDB."""
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27019/")
db = client['investment_data']
collection = db['company_metrics']

# Delete records where company_name is NaN (old placeholder data)
result = collection.delete_many({'company_name': None})

print(f"✅ Deleted {result.deleted_count} old placeholder records")

# Count remaining records
count = collection.count_documents({})
print(f"✅ Remaining records: {count}")
