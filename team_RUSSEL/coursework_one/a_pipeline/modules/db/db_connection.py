"""
Database connection module for PostgreSQL and MongoDB.

Provides a unified connector class that manages connections to both
PostgreSQL and MongoDB, along with a helper to load the investable
universe from the ``company_static`` table.

:module: modules.db.db_connection
"""
import psycopg2
from pymongo import MongoClient
import logging

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    Handles connections to PostgreSQL and MongoDB.

    Implements lazy connection creation — connections are only opened
    when first requested and are reused thereafter.

    :param config: Dictionary containing ``postgres`` and ``mongodb`` sub-keys.
    :type config: dict
    """

    def __init__(self, config: dict):
        """
        Initialise database connector.

        :param config: Application configuration dictionary.
        :type config: dict
        """
        self.config = config
        self._pg_conn = None
        self._mongo_client = None

    def get_postgres_connection(self):
        """
        Get or create a PostgreSQL connection.

        :returns: Active psycopg2 connection object.
        :rtype: psycopg2.extensions.connection
        """
        if self._pg_conn is None or self._pg_conn.closed:
            logger.info("Opening new PostgreSQL connection...")
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
        Get or create a MongoDB client.

        :returns: Active pymongo MongoClient.
        :rtype: pymongo.MongoClient
        """
        if self._mongo_client is None:
            connection_string = (
                f"mongodb://{self.config['mongodb']['host']}:"
                f"{self.config['mongodb']['port']}/"
            )
            logger.info("Opening new MongoDB connection...")
            self._mongo_client = MongoClient(connection_string)
        return self._mongo_client

    def close_all(self):
        """Close all open database connections gracefully."""
        if self._pg_conn and not self._pg_conn.closed:
            self._pg_conn.close()
            logger.info("PostgreSQL connection closed.")
        if self._mongo_client:
            self._mongo_client.close()
            logger.info("MongoDB connection closed.")

    def __enter__(self):
        """Support context manager usage."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connections on context manager exit."""
        self.close_all()
        return False


def load_company_list(db_connector: DatabaseConnector) -> list:
    """
    Load list of companies from the ``company_static`` table.

    Reads all companies from ``systematic_equity.company_static``
    and returns them as a list of dictionaries.

    :param db_connector: An initialised DatabaseConnector instance.
    :type db_connector: DatabaseConnector
    :returns: List of company dictionaries with keys:
        ``ticker``, ``name``, ``gics_sector``, ``gics_industry``,
        ``country``, ``region``.
    :rtype: list[dict]
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
    logger.info(f"Loaded {len(companies)} companies from company_static")
    return companies
