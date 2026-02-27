"""
Unit tests for modules.db.db_connection.

:module: test.test_db_connection
"""
import pytest
from unittest.mock import MagicMock, patch, call

from modules.db.db_connection import DatabaseConnector, load_company_list


@pytest.fixture
def config():
    return {
        "postgres": {
            "host": "localhost",
            "port": 5439,
            "database": "fift",
            "user": "postgres",
            "password": "postgres",
        },
        "mongodb": {
            "host": "localhost",
            "port": 27019,
            "database": "investment_data",
        },
    }


class TestDatabaseConnector:
    """Tests for DatabaseConnector class."""

    def test_init_stores_config(self, config):
        """DatabaseConnector stores config and starts with no connections."""
        db = DatabaseConnector(config)
        assert db.config == config
        assert db._pg_conn is None
        assert db._mongo_client is None

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_connection_creates_new(self, mock_connect, config):
        """get_postgres_connection opens a new connection when none exists."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        db = DatabaseConnector(config)
        conn = db.get_postgres_connection()

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5439,
            database="fift",
            user="postgres",
            password="postgres",
        )
        assert conn is mock_conn

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_connection_reuses_open(self, mock_connect, config):
        """get_postgres_connection reuses an existing open connection."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        db = DatabaseConnector(config)
        conn1 = db.get_postgres_connection()
        conn2 = db.get_postgres_connection()

        assert mock_connect.call_count == 1
        assert conn1 is conn2

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_connection_reopens_if_closed(self, mock_connect, config):
        """get_postgres_connection opens a new connection if old one is closed."""
        mock_conn_new = MagicMock()
        mock_conn_new.closed = False
        mock_connect.return_value = mock_conn_new

        mock_conn_closed = MagicMock()
        mock_conn_closed.closed = True

        db = DatabaseConnector(config)
        db._pg_conn = mock_conn_closed  # inject closed connection

        conn = db.get_postgres_connection()

        mock_connect.assert_called_once()
        assert conn is mock_conn_new

    @patch("modules.db.db_connection.MongoClient")
    def test_get_mongo_client_creates_new(self, mock_mongo, config):
        """get_mongo_client creates a new client when none exists."""
        mock_client = MagicMock()
        mock_mongo.return_value = mock_client

        db = DatabaseConnector(config)
        client = db.get_mongo_client()

        mock_mongo.assert_called_once_with("mongodb://localhost:27019/")
        assert client is mock_client

    @patch("modules.db.db_connection.MongoClient")
    def test_get_mongo_client_reuses_existing(self, mock_mongo, config):
        """get_mongo_client reuses an existing client."""
        mock_client = MagicMock()
        mock_mongo.return_value = mock_client

        db = DatabaseConnector(config)
        client1 = db.get_mongo_client()
        client2 = db.get_mongo_client()

        assert mock_mongo.call_count == 1
        assert client1 is client2

    @patch("modules.db.db_connection.psycopg2.connect")
    @patch("modules.db.db_connection.MongoClient")
    def test_close_all_closes_both(self, mock_mongo, mock_pg, config):
        """close_all closes both PostgreSQL and MongoDB connections."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pg.return_value = mock_conn

        mock_client = MagicMock()
        mock_mongo.return_value = mock_client

        db = DatabaseConnector(config)
        db.get_postgres_connection()
        db.get_mongo_client()
        db.close_all()

        mock_conn.close.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_context_manager_closes_on_exit(self, mock_connect, config):
        """DatabaseConnector closes connections on context manager exit."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        with DatabaseConnector(config) as db:
            db.get_postgres_connection()

        mock_conn.close.assert_called_once()


class TestLoadCompanyList:
    """Tests for load_company_list function."""

    def test_returns_list_of_dicts(self, config):
        """load_company_list returns a list of dicts with expected keys."""
        mock_connector = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_connector.get_postgres_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("AAPL ", "Apple Inc.", "Technology", "Consumer Electronics", "US", "North America"),
            ("MSFT ", "Microsoft Corp.", "Technology", "Software", "US", "North America"),
        ]

        result = load_company_list(mock_connector)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["ticker"] == "AAPL"  # strip() applied
        assert result[0]["name"] == "Apple Inc."
        assert result[0]["gics_sector"] == "Technology"
        assert result[0]["country"] == "US"

    def test_strips_ticker_whitespace(self, config):
        """load_company_list strips whitespace from ticker symbols."""
        mock_connector = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_connector.get_postgres_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("  TSLA  ", "Tesla Inc.", "Consumer Cyclical", "Auto", "US", "NA"),
        ]

        result = load_company_list(mock_connector)
        assert result[0]["ticker"] == "TSLA"

    def test_empty_table_returns_empty_list(self, config):
        """load_company_list returns empty list when table is empty."""
        mock_connector = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_connector.get_postgres_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = load_company_list(mock_connector)
        assert result == []
