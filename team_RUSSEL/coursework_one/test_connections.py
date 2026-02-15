import psycopg2
from pymongo import MongoClient

# Test PostgreSQL
try:
    conn = psycopg2.connect(
        host="localhost",
        port=5439,
        database="fift",
        user="postgres",
        password="postgres"  # Check docker-compose.yml for actual password
    )
    print("✅ PostgreSQL connection successful!")
    conn.close()
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")

# Test MongoDB
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client.admin
    print("✅ MongoDB connection successful!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
