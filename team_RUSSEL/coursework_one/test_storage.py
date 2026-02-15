"""Test the storage modules."""
from modules.utils.config_loader import load_config
from modules.db.db_connection import DatabaseConnector
from modules.input.data_extractor import DataExtractor
from modules.output.minio_storage import MinIOStorage
from modules.output.mongo_storage import MongoStorage
from datetime import datetime

# Load configuration
config = load_config('config/conf.yaml')
print("✅ Configuration loaded!")

# Initialize components
db_connector = DatabaseConnector(config)
print("✅ DatabaseConnector initialized!")

extractor = DataExtractor(config)
print("✅ DataExtractor initialized!")

minio_storage = MinIOStorage(config)
print("✅ MinIOStorage initialized!")

mongo_storage = MongoStorage(db_connector)
print("✅ MongoStorage initialized!")

# Create sample data
sample_companies = [
    {'id': 1, 'ticker': 'AAPL', 'name': 'Apple Inc.'},
    {'id': 2, 'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
]

print("\n📊 Extracting sample data...")
df = extractor.extract_bulk_data(sample_companies)
print(f"   Extracted {len(df)} records")

# Test MinIO storage
print("\n💾 Testing MinIO storage...")
object_name = f"test_data/{datetime.now().strftime('%Y/%m/%d')}/data.parquet"
minio_storage.store_dataframe(df, object_name)

# Retrieve from MinIO
print("\n📥 Retrieving from MinIO...")
retrieved_df = minio_storage.retrieve_dataframe(object_name)
print(f"✅ Retrieved {len(retrieved_df)} records from MinIO")
print(retrieved_df)

# Test MongoDB storage
print("\n💾 Testing MongoDB storage...")
mongo_storage.store_dataframe(df)

# Query from MongoDB
print("\n🔍 Querying MongoDB by ticker...")
aapl_data = mongo_storage.query_by_ticker('AAPL')
print(f"✅ Found {len(aapl_data)} records for AAPL")

# Clean up
db_connector.close_all()
print("\n✅ All tests completed successfully!")
