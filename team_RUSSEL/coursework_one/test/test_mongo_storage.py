"""Tests for the MongoDB storage module."""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import datetime

from modules.output.mongo_storage import MongoStorage


class TestMongoStorageInit:
    """Tests for MongoStorage initialization."""

    def test_init(self, mock_db_connector):
        """Test MongoStorage initialization."""
        storage = MongoStorage(mock_db_connector)
        assert storage.client is not None
        assert storage.db is not None
        assert storage.collection is not None

    def test_init_uses_correct_database(self, mock_db_connector):
        """Test that correct database name is used."""
        storage = MongoStorage(mock_db_connector)
        mock_mongo = mock_db_connector.get_mongo_client()
        mock_mongo.__getitem__.assert_called_with("investment_data")


class TestStoreDataframe:
    """Tests for store_dataframe method."""

    def test_store_dataframe(self, mock_db_connector, sample_current_df):
        """Test storing a DataFrame to MongoDB."""
        storage = MongoStorage(mock_db_connector)
        mock_result = MagicMock()
        mock_result.inserted_ids = ["id1"]
        storage.collection.insert_many.return_value = mock_result

        storage.store_dataframe(sample_current_df)

        storage.collection.insert_many.assert_called_once()

    def test_store_dataframe_adds_metadata(self, mock_db_connector, sample_current_df):
        """Test that inserted_at metadata is added to records."""
        storage = MongoStorage(mock_db_connector)
        mock_result = MagicMock()
        mock_result.inserted_ids = ["id1"]
        storage.collection.insert_many.return_value = mock_result

        storage.store_dataframe(sample_current_df)

        call_args = storage.collection.insert_many.call_args[0][0]
        assert "inserted_at" in call_args[0]
        assert isinstance(call_args[0]["inserted_at"], datetime)

    def test_store_empty_dataframe(self, mock_db_connector):
        """Test storing an empty DataFrame."""
        storage = MongoStorage(mock_db_connector)
        df = pd.DataFrame()

        # Should not call insert_many for empty DataFrame
        storage.store_dataframe(df)
        storage.collection.insert_many.assert_not_called()

    def test_store_dataframe_preserves_data(
        self, mock_db_connector, sample_current_df
    ):
        """Test that all data fields are preserved when storing."""
        storage = MongoStorage(mock_db_connector)
        mock_result = MagicMock()
        mock_result.inserted_ids = ["id1"]
        storage.collection.insert_many.return_value = mock_result

        storage.store_dataframe(sample_current_df)

        call_args = storage.collection.insert_many.call_args[0][0]
        record = call_args[0]
        assert record["ticker"] == "AAPL"
        assert record["pe_ratio"] == 28.5
        assert record["roe"] == 0.157


class TestQueryByTicker:
    """Tests for query_by_ticker method."""

    def test_query_by_ticker(self, mock_db_connector):
        """Test querying data by ticker symbol."""
        storage = MongoStorage(mock_db_connector)
        storage.collection.find.return_value = [
            {"ticker": "AAPL", "pe_ratio": 28.5, "roe": 0.157}
        ]

        df = storage.query_by_ticker("AAPL")

        storage.collection.find.assert_called_once_with({"ticker": "AAPL"})
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_query_by_ticker_no_results(self, mock_db_connector):
        """Test querying when no results found."""
        storage = MongoStorage(mock_db_connector)
        storage.collection.find.return_value = []

        df = storage.query_by_ticker("INVALID")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_query_by_ticker_multiple_results(self, mock_db_connector):
        """Test querying when multiple records exist."""
        storage = MongoStorage(mock_db_connector)
        storage.collection.find.return_value = [
            {"ticker": "AAPL", "date": "2026-01-01", "pe_ratio": 27.0},
            {"ticker": "AAPL", "date": "2026-02-01", "pe_ratio": 28.5},
        ]

        df = storage.query_by_ticker("AAPL")

        assert len(df) == 2


class TestQueryByYear:
    """Tests for query_by_year method."""

    def test_query_by_year(self, mock_db_connector):
        """Test querying data by year."""
        storage = MongoStorage(mock_db_connector)
        storage.collection.find.return_value = [
            {"ticker": "AAPL", "date": "2026-02-22", "pe_ratio": 28.5}
        ]

        df = storage.query_by_year(2026)

        storage.collection.find.assert_called_once_with(
            {"date": {"$regex": "^2026"}}
        )
        assert isinstance(df, pd.DataFrame)

    def test_query_by_year_no_results(self, mock_db_connector):
        """Test querying when no data for year."""
        storage = MongoStorage(mock_db_connector)
        storage.collection.find.return_value = []

        df = storage.query_by_year(2020)

        assert isinstance(df, pd.DataFrame)
        assert df.empty
