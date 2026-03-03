"""Shared test fixtures for all test modules."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_config():
    """Provide a sample configuration dictionary for testing."""
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
        "minio": {
            "endpoint": "localhost:9000",
            "access_key": "ift_bigdata",
            "secret_key": "minio_password",
            "secure": False,
        },
        "extraction": {
            "frequency": "daily",
            "lookback_years": 5,
            "batch_size": 10,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }


@pytest.fixture
def sample_company():
    """Provide a sample company dictionary."""
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "gics_sector": "Information Technology",
        "gics_industry": "Technology Hardware",
        "country": "US",
        "region": "North America",
    }


@pytest.fixture
def sample_companies():
    """Provide a list of sample company dictionaries."""
    return [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "gics_sector": "Information Technology",
            "gics_industry": "Technology Hardware",
            "country": "US",
            "region": "North America",
        },
        {
            "ticker": "MSFT",
            "name": "Microsoft Corporation",
            "gics_sector": "Information Technology",
            "gics_industry": "Systems Software",
            "country": "US",
            "region": "North America",
        },
        {
            "ticker": "JNJ",
            "name": "Johnson & Johnson",
            "gics_sector": "Health Care",
            "gics_industry": "Pharmaceuticals",
            "country": "US",
            "region": "North America",
        },
    ]


@pytest.fixture
def sample_current_df():
    """Provide a sample DataFrame with current Value + Quality metrics."""
    return pd.DataFrame(
        [
            {
                "company_id": "AAPL",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "date": "2026-02-22",
                "current_price": 230.50,
                "market_cap": 3500000000000,
                "pe_ratio": 28.5,
                "forward_pe": 25.3,
                "pb_ratio": 45.2,
                "ps_ratio": 8.5,
                "book_value": 4.38,
                "eps": 6.42,
                "forward_eps": 7.10,
                "enterprise_value": 3600000000000,
                "ev_to_ebitda": 22.1,
                "ev_to_revenue": 8.8,
                "roe": 0.157,
                "roa": 0.285,
                "debt_to_equity": 176.3,
                "current_ratio": 1.07,
                "quick_ratio": 1.04,
                "profit_margin": 0.263,
                "operating_margin": 0.312,
                "gross_margin": 0.462,
                "free_cash_flow": 111000000000,
                "operating_cash_flow": 118000000000,
                "revenue_growth": 0.05,
                "earnings_growth": 0.10,
                "revenue": 395000000000,
                "total_debt": 111000000000,
                "total_cash": 62000000000,
                "ebitda": 133000000000,
                "dividend_yield": 0.005,
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "db_sector": "Information Technology",
                "db_industry": "Technology Hardware",
            }
        ]
    )


@pytest.fixture
def sample_historical_df():
    """Provide a sample DataFrame with historical price data."""
    return pd.DataFrame(
        [
            {
                "company_id": "AAPL",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "date": "2025-01-01",
                "Open": 185.0,
                "High": 190.0,
                "Low": 183.0,
                "Close": 188.5,
                "Volume": 50000000,
            },
            {
                "company_id": "AAPL",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "date": "2025-02-01",
                "Open": 188.5,
                "High": 195.0,
                "Low": 186.0,
                "Close": 193.2,
                "Volume": 48000000,
            },
        ]
    )


@pytest.fixture
def mock_db_connector(sample_config):
    """Provide a mock DatabaseConnector."""
    mock = MagicMock()
    mock.config = sample_config

    # Mock PostgreSQL connection
    mock_pg_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("AAPL        ", "Apple Inc.", "Information Technology", "Technology Hardware", "US", "North America"),
        ("MSFT        ", "Microsoft Corporation", "Information Technology", "Systems Software", "US", "North America"),
    ]
    mock_pg_conn.cursor.return_value = mock_cursor
    mock.get_postgres_connection.return_value = mock_pg_conn

    # Mock MongoDB client
    mock_mongo = MagicMock()
    mock.get_mongo_client.return_value = mock_mongo

    return mock
