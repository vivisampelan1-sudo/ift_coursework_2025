"""Create sample company data in PostgreSQL."""
import psycopg2

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    port=5439,
    database="fift",
    user="postgres",
    password="postgres"
)

cursor = conn.cursor()

# Create schema if it doesn't exist
cursor.execute("CREATE SCHEMA IF NOT EXISTS systematic_equity;")
print("✅ Schema created/verified")

# Create table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS systematic_equity.company_static (
        id SERIAL PRIMARY KEY,
        ticker VARCHAR(10) NOT NULL,
        company_name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
print("✅ Table created/verified")

# Insert sample companies
companies = [
    ('AAPL', 'Apple Inc.'),
    ('MSFT', 'Microsoft Corporation'),
    ('GOOGL', 'Alphabet Inc.'),
    ('AMZN', 'Amazon.com Inc.'),
    ('TSLA', 'Tesla Inc.'),
]

# Clear existing data first
cursor.execute("DELETE FROM systematic_equity.company_static;")

# Insert companies
for ticker, name in companies:
    cursor.execute(
        """
        INSERT INTO systematic_equity.company_static (ticker, company_name)
        VALUES (%s, %s)
        """,
        (ticker, name)
    )

conn.commit()
print(f"✅ Inserted {len(companies)} companies")

# Verify
cursor.execute("SELECT * FROM systematic_equity.company_static ORDER BY ticker;")
rows = cursor.fetchall()

print("\n📊 Companies in database:")
for row in rows:
    print(f"   {row[0]}: {row[1]} - {row[2]}")

cursor.close()
conn.close()
print("\n✅ Done!")
