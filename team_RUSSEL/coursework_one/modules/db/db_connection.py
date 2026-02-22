"""
Database connection module for PostgreSQL and MongoDB.
"""
import psycopg2
from pymongo import MongoClient
from typing import Optional
import os


class DatabaseConnector:
    """Handles connections to PostgreSQL and MongoDB."""
    
    def __init__(self, config: dict):
        """
        Initialize database connector.
        
        Args:
            config: Dictionary with database configuration
        """
        self.config = config
        self._pg_conn = None
        self._mongo_client = None
    
    def get_postgres_connection(self):
        """
        Get PostgreSQL connection.
        
        Returns:
            psycopg2 connection object
        """
        if self._pg_conn is None or self._pg_conn.closed:
            self._pg_conn = psycopg2.connect(
                host=self.config['postgres']['host'],
                port=self.config['postgres']['port'],
                database=self.config['postgres']['database'],
                user=self.config['postgres']['user'],
                password=self.config['postgres']['password']
            )
        return self._pg_conn
    
    def get_mongo_client(self):
        """
        Get MongoDB client.
        
        Returns:
            pymongo MongoClient object
        """
        if self._mongo_client is None:
            connection_string = (
                f"mongodb://{self.config['mongodb']['host']}:"
                f"{self.config['mongodb']['port']}/"
            )
            self._mongo_client = MongoClient(connection_string)
        return self._mongo_client
    
    def close_all(self):
        """Close all database connections."""
        if self._pg_conn and not self._pg_conn.closed:
            self._pg_conn.close()
        if self._mongo_client:
            self._mongo_client.close()


def load_company_list(db_connector: DatabaseConnector) -> list:
    """
    Load list of companies from company_static table.
    
    Args:
        db_connector: DatabaseConnector instance
        
    Returns:
        List of company dictionaries
    """
    conn = db_connector.get_postgres_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT symbol, security, gics_sector, gics_industry, country, region
        FROM systematic_equity.company_static
        ORDER BY symbol
    """
    
    cursor.execute(query)
    companies = []
    
    for row in cursor.fetchall():
        companies.append({
            'ticker': row[0].strip(),
            'name': row[1],
            'gics_sector': row[2],
            'gics_industry': row[3],
            'country': row[4],
            'region': row[5]
        })
    
    cursor.close()
    return companies