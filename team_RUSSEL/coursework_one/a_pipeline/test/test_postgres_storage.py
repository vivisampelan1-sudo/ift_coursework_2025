"""
Unit tests for modules.output.postgres_storage.

:module: test.test_postgres_storage
"""
import math
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, call

from a_pipeline.modules.output.postgres_storage import PostgresStorage


@pytest.fixture
def mock_connector():
    connector = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = MagicMock()
    connector.get_postgres_connection.return_value = conn
    return connector


@pytest.fixture
def storage(mock_connector):
    return PostgresStorage(mock_connector)


@pytest.fixture
def sample_row():
    return {
        "ticker": "AAPL",
        "date": "2026-01-31",
        "company_id": "AAPL",
        "company_name": "Apple Inc.",
        "open": 180.0,
        "high": 185.0,
        "low": 178.0,
        "close": 182.0,
        "volume": 50000000,
        "current_price": 182.0,
        "market_cap": 2800000000000,
        "pe_ratio": 28.5,
        "forward_pe": 26.0,
        "pb_ratio": 45.0,
        "ps_ratio": 7.5,
        "eps": 6.39,
        "forward_eps": 7.0,
        "ev_to_ebitda": 22.0,
        "ev_to_revenue": 7.0,
        "book_value": 4.05,
        "roe": 0.87,
        "roa": 0.28,
        "debt_to_equity": 175.0,
        "current_ratio": 0.95,
        "profit_margin": 0.25,
        "operating_margin": 0.30,
        "gross_margin": 0.43,
        "free_cash_flow": 90000000000,
        "revenue": 380000000000,
        "total_debt": 110000000000,
        "ebitda": 130000000000,
        "dividend_yield": 0.005,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "db_sector": "Technology",
        "db_industry": "Consumer Electronics",
    }


class TestToPythonScalar:
    """Tests for PostgresStorage._to_python_scalar."""

    def test_returns_none_for_none(self, storage):
        assert storage._to_python_scalar(None) is None

    def test_returns_plain_int(self, storage):
        assert storage._to_python_scalar(42) == 42

    def test_returns_plain_float(self, storage):
        assert storage._to_python_scalar(3.14) == 3.14

    def test_returns_plain_string(self, storage):
        assert storage._to_python_scalar("hello") == "hello"

    def test_converts_numpy_float64(self, storage):
        result = storage._to_python_scalar(np.float64(1.5))
        assert result == 1.5
        assert isinstance(result, float)

    def test_converts_numpy_int64(self, storage):
        result = storage._to_python_scalar(np.int64(100))
        assert result == 100

    def test_returns_none_for_nan(self, storage):
        assert storage._to_python_scalar(float("nan")) is None

    def test_returns_none_for_inf(self, storage):
        assert storage._to_python_scalar(float("inf")) is None

    def test_returns_none_for_negative_inf(self, storage):
        assert storage._to_python_scalar(float("-inf")) is None

    def test_returns_none_for_numpy_nan(self, storage):
        assert storage._to_python_scalar(np.nan) is None

    def test_returns_none_for_numpy_inf(self, storage):
        assert storage._to_python_scalar(np.inf) is None

    def test_returns_none_for_pandas_na(self, storage):
        assert storage._to_python_scalar(pd.NA) is None

    def test_returns_none_for_pandas_nat(self, storage):
        assert storage._to_python_scalar(pd.NaT) is None

    def test_handles_numpy_float32_inf(self, storage):
        """numpy float32 infinity must also be caught."""
        assert storage._to_python_scalar(np.float32(np.inf)) is None


class TestUpsertMetrics:
    """Tests for PostgresStorage.upsert_metrics."""

    def test_empty_dataframe_does_nothing(self, storage):
        """upsert_metrics returns immediately for empty DataFrame."""
        df = pd.DataFrame()
        storage.upsert_metrics(df)
        storage.conn.cursor.assert_not_called()

    def test_upserts_valid_rows(self, storage, sample_row):
        """upsert_metrics executes SQL and commits for valid rows."""
        df = pd.DataFrame([sample_row])
        mock_cursor = MagicMock()
        storage.conn.cursor.return_value = mock_cursor

        storage.upsert_metrics(df)

        mock_cursor.execute.assert_called_once()
        storage.conn.commit.assert_called_once()

    def test_sanitises_infinity_before_insert(self, storage, sample_row):
        """upsert_metrics replaces inf values with NaN before inserting."""
        sample_row["pe_ratio"] = float("inf")
        df = pd.DataFrame([sample_row])
        mock_cursor = MagicMock()
        storage.conn.cursor.return_value = mock_cursor

        storage.upsert_metrics(df)

        # Should not raise — infinity should have been sanitised
        storage.conn.commit.assert_called_once()

    def test_skips_bad_row_and_continues(self, storage, sample_row):
        """upsert_metrics skips a row that causes a DB error and continues."""
        row2 = dict(sample_row)
        row2["ticker"] = "MSFT"
        df = pd.DataFrame([sample_row, row2])

        mock_cursor = MagicMock()
        # First execute raises, second succeeds
        mock_cursor.execute.side_effect = [Exception("DB error"), None]
        storage.conn.cursor.return_value = mock_cursor

        storage.upsert_metrics(df)  # Should not raise

        storage.conn.commit.assert_called_once()

    def test_multiple_rows_all_committed(self, storage, sample_row):
        """upsert_metrics commits all valid rows in one transaction."""
        rows = [dict(sample_row) for _ in range(5)]
        for i, r in enumerate(rows):
            r["ticker"] = f"TKR{i}"
        df = pd.DataFrame(rows)

        mock_cursor = MagicMock()
        storage.conn.cursor.return_value = mock_cursor

        storage.upsert_metrics(df)

        assert mock_cursor.execute.call_count == 5
        storage.conn.commit.assert_called_once()


class TestExtractRowParams:
    """Tests for PostgresStorage._extract_row_params."""

    def test_returns_tuple(self, storage, sample_row):
        """_extract_row_params returns a tuple."""
        row = pd.Series(sample_row)
        result = storage._extract_row_params(row)
        assert isinstance(result, tuple)

    def test_tuple_length_matches_sql_columns(self, storage, sample_row):
        """_extract_row_params returns correct number of parameters for SQL."""
        row = pd.Series(sample_row)
        result = storage._extract_row_params(row)
        # 37 columns in INSERT: company_id, company_name, ticker, date,
        # open, high, low, close, volume, current_price, market_cap,
        # pe_ratio, forward_pe, pb_ratio, ps_ratio, eps, forward_eps,
        # ev_to_ebitda, ev_to_revenue, book_value, roe, roa, debt_to_equity,
        # current_ratio, profit_margin, operating_margin, gross_margin,
        # free_cash_flow, revenue, total_debt, ebitda, dividend_yield,
        # sector, industry, db_sector, db_industry, cash = 37
        assert len(result) == 37

    def test_handles_missing_optional_columns(self, storage):
        """_extract_row_params handles rows with missing optional fields."""
        row = pd.Series({"ticker": "TEST", "date": "2026-01-01"})
        result = storage._extract_row_params(row)
        assert isinstance(result, tuple)
        assert result[2] == "TEST"  # ticker at index 2

    def test_sector_included_in_params(self, storage, sample_row):
        """_extract_row_params includes sector and industry in output tuple."""
        row = pd.Series(sample_row)
        result = storage._extract_row_params(row)
        # sector is at index 32, industry at 33
        assert result[32] == "Technology"
        assert result[33] == "Consumer Electronics"
