"""Tests for the data extraction module."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime

from modules.input.data_extractor import DataExtractor


class TestDataExtractorInit:
    """Tests for DataExtractor initialization."""

    def test_init(self, sample_config):
        """Test DataExtractor initialization."""
        extractor = DataExtractor(sample_config)
        assert extractor.config == sample_config
        assert extractor.lookback_years == 5

    def test_init_lookback_years(self, sample_config):
        """Test that lookback_years is set from config."""
        sample_config["extraction"]["lookback_years"] = 3
        extractor = DataExtractor(sample_config)
        assert extractor.lookback_years == 3


class TestExtractCompanyData:
    """Tests for extract_company_data method."""

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_success(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test successful data extraction for a single company."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 230.50,
            "marketCap": 3500000000000,
            "trailingPE": 28.5,
            "forwardPE": 25.3,
            "priceToBook": 45.2,
            "bookValue": 4.38,
            "trailingEps": 6.42,
            "returnOnEquity": 0.157,
            "returnOnAssets": 0.285,
            "debtToEquity": 176.3,
            "profitMargins": 0.263,
            "currentRatio": 1.07,
            "freeCashflow": 111000000000,
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df["ticker"].values[0] == "AAPL"
        assert df["company_name"].values[0] == "Apple Inc."
        assert df["current_price"].values[0] == 230.50
        assert df["pe_ratio"].values[0] == 28.5
        assert df["roe"].values[0] == 0.157
        assert df["debt_to_equity"].values[0] == 176.3

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_missing_fields(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test extraction when some fields are missing from API."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 100.0,
            # Missing most fields - should return None
        }
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        assert len(df) == 1
        assert df["ticker"].values[0] == "AAPL"
        assert df["current_price"].values[0] == 100.0
        assert df["pe_ratio"].values[0] is None
        assert df["roe"].values[0] is None

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_api_failure(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test extraction when API call fails."""
        mock_ticker_class.side_effect = Exception("API Error")

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        # Should return a row with error info, not crash
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df["ticker"].values[0] == "AAPL"
        assert "error" in df.columns

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_has_date(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test that extracted data includes a date field."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 100.0}
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        assert "date" in df.columns
        # Date should be today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert df["date"].values[0] == today

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_value_metrics(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test that all Value factor metrics are extracted."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 28.5,
            "forwardPE": 25.3,
            "priceToBook": 45.2,
            "priceToSalesTrailing12Months": 8.5,
            "enterpriseToEbitda": 22.1,
            "enterpriseToRevenue": 8.8,
        }
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        value_columns = [
            "pe_ratio", "forward_pe", "pb_ratio", "ps_ratio",
            "ev_to_ebitda", "ev_to_revenue",
        ]
        for col in value_columns:
            assert col in df.columns, f"Missing Value metric: {col}"

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_company_data_quality_metrics(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test that all Quality factor metrics are extracted."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "returnOnEquity": 0.157,
            "returnOnAssets": 0.285,
            "debtToEquity": 176.3,
            "currentRatio": 1.07,
            "profitMargins": 0.263,
            "operatingMargins": 0.312,
            "freeCashflow": 111000000000,
        }
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_company_data(sample_company)

        quality_columns = [
            "roe", "roa", "debt_to_equity", "current_ratio",
            "profit_margin", "operating_margin", "free_cash_flow",
        ]
        for col in quality_columns:
            assert col in df.columns, f"Missing Quality metric: {col}"


class TestExtractHistoricalData:
    """Tests for extract_historical_data method."""

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_historical_data_success(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test successful historical data extraction."""
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame(
            {
                "Open": [185.0, 188.5],
                "High": [190.0, 195.0],
                "Low": [183.0, 186.0],
                "Close": [188.5, 193.2],
                "Volume": [50000000, 48000000],
            },
            index=pd.to_datetime(["2025-01-01", "2025-02-01"]),
        )
        mock_hist.index.name = "Date"
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_historical_data(sample_company)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "ticker" in df.columns
        assert "date" in df.columns
        assert "Close" in df.columns
        assert df["ticker"].values[0] == "AAPL"

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_historical_data_empty(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test extraction when no historical data available."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_historical_data(sample_company)

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_historical_data_api_failure(
        self, mock_ticker_class, sample_config, sample_company
    ):
        """Test extraction when API fails."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("API Error")
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_historical_data(sample_company)

        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestExtractBulkData:
    """Tests for bulk extraction methods."""

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_bulk_data(
        self, mock_ticker_class, sample_config, sample_companies
    ):
        """Test bulk data extraction for multiple companies."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 100.0, "trailingPE": 20.0}
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_bulk_data(sample_companies)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_bulk_data_empty_list(self, mock_ticker_class, sample_config):
        """Test bulk extraction with empty company list."""
        extractor = DataExtractor(sample_config)
        df = extractor.extract_bulk_data([])

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("modules.input.data_extractor.yf.Ticker")
    def test_extract_bulk_historical_data(
        self, mock_ticker_class, sample_config, sample_companies
    ):
        """Test bulk historical data extraction."""
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [98.0],
                "Close": [103.0],
                "Volume": [1000000],
            },
            index=pd.to_datetime(["2025-01-01"]),
        )
        mock_hist.index.name = "Date"
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        extractor = DataExtractor(sample_config)
        df = extractor.extract_bulk_historical_data(sample_companies)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
