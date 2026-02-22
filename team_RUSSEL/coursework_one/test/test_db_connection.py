"""Tests for the database connection module."""
import pytest
from unittest.mock import patch, MagicMock

from modules.db.db_connection import DatabaseConnector, load_company_list


class TestDatabaseConnector:
    """Tests for the DatabaseConnector class."""

    def test_init(self, sample_config):
        """Test DatabaseConnector initialization."""
        connector = DatabaseConnector(sample_config)
        assert connector.config == sample_config
        assert connector._pg_conn is None
        assert connector._mongo_client is None

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_connection(self, mock_connect, sample_config):
        """Test PostgreSQL connection creation."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        connector = DatabaseConnector(sample_config)
        conn = connector.get_postgres_connection()

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5439,
            database="fift",
            user="postgres",
            password="postgres",
        )
        assert conn == mock_conn

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_connection_reuses_existing(self, mock_connect, sample_config):
        """Test that existing connection is reused."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        connector = DatabaseConnector(sample_config)
        conn1 = connector.get_postgres_connection()
        conn2 = connector.get_postgres_connection()

        # Should only connect once
        mock_connect.assert_called_once()
        assert conn1 == conn2

    @patch("modules.db.db_connection.psycopg2.connect")
    def test_get_postgres_reconnects_if_closed(self, mock_connect, sample_config):
        """Test reconnection when connection is closed."""
        mock_conn = MagicMock()
        mock_conn.closed = True
        mock_connect.return_value = mock_conn

        connector = DatabaseConnector(sample_config)
        connector._pg_conn = mock_conn
        connector.get_postgres_connection()

        # Should reconnect since connection was closed
        mock_connect.assert_called_once()

    @patch("modules.db.db_connection.MongoClient")
    def test_get_mongo_client(self, mock_mongo_class, sample_config):
        """Test MongoDB client creation."""
        mock_client = MagicMock()
        mock_mongo_class.return_value = mock_client

        connector = DatabaseConnector(sample_config)
        client = connector.get_mongo_client()

        mock_mongo_class.assert_called_once_with("mongodb://localhost:27019/")
        assert client == mock_client

    @patch("modules.db.db_connection.MongoClient")
    def test_get_mongo_client_reuses_existing(self, mock_mongo_class, sample_config):
        """Test that existing MongoDB client is reused."""
        mock_client = MagicMock()
        mock_mongo_class.return_value = mock_client

        connector = DatabaseConnector(sample_config)
        client1 = connector.get_mongo_client()
        client2 = connector.get_mongo_client()

        mock_mongo_class.assert_called_once()
        assert client1 == client2

    @patch("modules.db.db_connection.psycopg2.connect")
    @patch("modules.db.db_connection.MongoClient")
    def test_close_all(self, mock_mongo_class, mock_connect, sample_config):
        """Test closing all connections."""
        mock_pg_conn = MagicMock()
        mock_pg_conn.closed = False
        mock_connect.return_value = mock_pg_conn

        mock_mongo_client = MagicMock()
        mock_mongo_class.return_value = mock_mongo_client

        connector = DatabaseConnector(sample_config)
        connector.get_postgres_connection()
        connector.get_mongo_client()
        connector.close_all()

        mock_pg_conn.close.assert_called_once()
        mock_mongo_client.close.assert_called_once()

    def test_close_all_no_connections(self, sample_config):
        """Test close_all when no connections exist."""
        connector = DatabaseConnector(sample_config)
        # Should not raise any errors
        connector.close_all()


class TestLoadCompanyList:
    """Tests for the load_company_list function."""

    def test_load_company_list(self, mock_db_connector):
        """Test loading company list from database."""
        companies = load_company_list(mock_db_connector)

        assert len(companies) == 2
        assert companies[0]["ticker"] == "AAPL"
        assert companies[0]["name"] == "Apple Inc."
        assert companies[0]["gics_sector"] == "Information Technology"
        assert companies[1]["ticker"] == "MSFT"

    def test_load_company_list_strips_ticker(self, mock_db_connector):
        """Test that ticker symbols are stripped of whitespace."""
        companies = load_company_list(mock_db_connector)
        # CHAR(12) pads with spaces, strip should remove them
        assert companies[0]["ticker"] == "AAPL"
        assert " " not in companies[0]["ticker"]

    def test_load_company_list_returns_list(self, mock_db_connector):
        """Test that function returns a list."""
        companies = load_company_list(mock_db_connector)
        assert isinstance(companies, list)

    def test_load_company_list_has_required_fields(self, mock_db_connector):
        """Test that each company has all required fields."""
        companies = load_company_list(mock_db_connector)
        required_fields = [
            "ticker",
            "name",
            "gics_sector",
            "gics_industry",
            "country",
            "region",
        ]
        for company in companies:
            for field in required_fields:
                assert field in company, f"Missing field: {field}"

    def test_load_company_list_empty_result(self):
        """Test with empty database result."""
        mock_connector = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connector.get_postgres_connection.return_value = mock_conn

        companies = load_company_list(mock_connector)
        assert companies == []

    def test_load_company_list_cursor_closed(self, mock_db_connector):
        """Test that cursor is properly closed after query."""
        load_company_list(mock_db_connector)
        mock_conn = mock_db_connector.get_postgres_connection()
        mock_cursor = mock_conn.cursor()
        mock_cursor.close.assert_called()
