"""Test the database connection module."""
from modules.utils.config_loader import load_config
from modules.db.db_connection import DatabaseConnector

# Load configuration
config = load_config('config/conf.yaml')
print("✅ Configuration loaded successfully!")

# Initialize database connector
db_connector = DatabaseConnector(config)
print("✅ DatabaseConnector initialized!")

# Test PostgreSQL connection
try:
    pg_conn = db_connector.get_postgres_connection()
    print("✅ PostgreSQL connection successful!")
    print(f"   Connected to database: {config['postgres']['database']}")
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")

# Test MongoDB connection
try:
    mongo_client = db_connector.get_mongo_client()
    print("✅ MongoDB connection successful!")
    print(f"   Available databases: {mongo_client.list_database_names()}")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")

# Close connections
db_connector.close_all()
print("✅ All connections closed!")
