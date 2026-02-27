"""
Unit tests for modules.output.mongo_storage.

:module: test.test_mongo_storage
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import datetime

from modules.output.mongo_storage import MongoStorage


@pytest.fixture
def mock_connector():
    connector = MagicMock()
    client = MagicMock()
    db = MagicMock()
    collection = MagicMock()

    connector.get_mongo_client.return_value = client
    client.__getitem__.return_value = db
    db.__getitem__.return_value = collection

    return connector, collection


@pytest.fixture
def storage(mock_connector):
    connector, _ = mock_connector
    return MongoStorage(connector)


class TestMongoStorage:
    """Tests for MongoStorage class."""

    def test_init_creates_collection(self, mock_connector):
        """MongoStorage initialises with correct database and collection."""
        connector, collection = mock_connector
        ms = MongoStorage(connector)
        assert ms.collection is not None

    def test_store_empty_dataframe_does_nothing(self, storage, mock_connector):
        """store_dataframe does nothing for empty DataFrame."""
        _, collection = mock_connector
        df = pd.DataFrame()
        storage.store_dataframe(df)
        collection.bulk_write.assert_not_called()

    def test_store_dataframe_calls_bulk_write(self, storage, mock_connector):
        """store_dataframe calls bulk_write with operations for valid rows."""
        _, collection = mock_connector
        mock_result = MagicMock()
        mock_result.upserted_count = 1
        mock_result.modified_count = 0
        mock_result.matched_count = 0
        collection.bulk_write.return_value = mock_result

        df = pd.DataFrame([
            {"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": 28.5},
        ])
        storage.store_dataframe(df)
        collection.bulk_write.assert_called_once()

    def test_store_dataframe_skips_missing_ticker(self, storage, mock_connector):
        """store_dataframe skips rows where ticker/date are empty strings."""
        _, collection = mock_connector
        df = pd.DataFrame([
            {"ticker": "", "date": "2026-01-31", "pe_ratio": 28.5},   # empty ticker
            {"ticker": "AAPL", "date": "", "pe_ratio": 28.5},          # empty date
        ])
        storage.store_dataframe(df)
        collection.bulk_write.assert_not_called()

    def test_store_multiple_rows(self, storage, mock_connector):
        """store_dataframe creates one operation per valid row."""
        _, collection = mock_connector
        mock_result = MagicMock()
        mock_result.upserted_count = 3
        mock_result.modified_count = 0
        mock_result.matched_count = 0
        collection.bulk_write.return_value = mock_result

        df = pd.DataFrame([
            {"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": 28.5},
            {"ticker": "MSFT", "date": "2026-01-31", "pe_ratio": 32.0},
            {"ticker": "GOOG", "date": "2026-01-31", "pe_ratio": 22.0},
        ])
        storage.store_dataframe(df)

        call_args = collection.bulk_write.call_args[0][0]
        assert len(call_args) == 3

    def test_query_by_ticker_returns_dataframe(self, storage, mock_connector):
        """query_by_ticker returns DataFrame from collection results."""
        _, collection = mock_connector
        collection.find.return_value = [
            {"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": 28.5},
        ]

        result = storage.query_by_ticker("AAPL")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "AAPL"

    def test_query_by_ticker_empty_result(self, storage, mock_connector):
        """query_by_ticker returns empty DataFrame when no results found."""
        _, collection = mock_connector
        collection.find.return_value = []

        result = storage.query_by_ticker("UNKNOWN")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_query_by_year_returns_dataframe(self, storage, mock_connector):
        """query_by_year returns DataFrame with matching records."""
        _, collection = mock_connector
        collection.find.return_value = [
            {"ticker": "AAPL", "date": "2024-06-30"},
            {"ticker": "MSFT", "date": "2024-09-30"},
        ]

        result = storage.query_by_year(2024)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_query_by_ticker_and_year(self, storage, mock_connector):
        """query_by_ticker_and_year filters by both ticker and year."""
        _, collection = mock_connector
        collection.find.return_value = [
            {"ticker": "AAPL", "date": "2024-03-31"},
        ]

        result = storage.query_by_ticker_and_year("AAPL", 2024)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

        # Verify the find was called with correct filter
        find_filter = collection.find.call_args[0][0]
        assert find_filter["ticker"] == "AAPL"
        assert "2024" in str(find_filter["date"])
