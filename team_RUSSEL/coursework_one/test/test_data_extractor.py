"""
Unit tests for modules.input.data_extractor.

:module: test.test_data_extractor
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from modules.input.data_extractor import DataExtractor


@pytest.fixture
def config():
    return {
        "extraction": {
            "lookback_years": 5,
            "batch_size": 10,
            "frequency": "daily",
        }
    }


@pytest.fixture
def extractor(config):
    return DataExtractor(config)


@pytest.fixture
def sample_company():
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "gics_sector": "Technology",
        "gics_industry": "Consumer Electronics",
    }


class TestSafeInfoValue:
    """Tests for DataExtractor._safe_info_value static method."""

    def test_returns_valid_float(self):
        info = {"pe_ratio": 25.5}
        assert DataExtractor._safe_info_value(info, "pe_ratio") == 25.5

    def test_returns_valid_int(self):
        info = {"marketCap": 1000000}
        assert DataExtractor._safe_info_value(info, "marketCap") == 1000000

    def test_returns_valid_string(self):
        info = {"sector": "Technology"}
        assert DataExtractor._safe_info_value(info, "sector") == "Technology"

    def test_returns_none_for_missing_key(self):
        info = {"pe_ratio": 25.5}
        assert DataExtractor._safe_info_value(info, "missing_key") is None

    def test_returns_none_for_nan(self):
        info = {"pe_ratio": float("nan")}
        assert DataExtractor._safe_info_value(info, "pe_ratio") is None

    def test_returns_none_for_inf(self):
        info = {"pe_ratio": float("inf")}
        assert DataExtractor._safe_info_value(info, "pe_ratio") is None

    def test_returns_none_for_negative_inf(self):
        info = {"pe_ratio": float("-inf")}
        assert DataExtractor._safe_info_value(info, "pe_ratio") is None

    def test_returns_none_for_numpy_nan(self):
        info = {"val": np.nan}
        assert DataExtractor._safe_info_value(info, "val") is None

    def test_returns_none_for_numpy_inf(self):
        info = {"val": np.inf}
        assert DataExtractor._safe_info_value(info, "val") is None

    def test_returns_none_for_list_value(self):
        info = {"val": [1, 2, 3]}
        assert DataExtractor._safe_info_value(info, "val") is None

    def test_returns_none_for_dict_value(self):
        info = {"val": {"nested": 1}}
        assert DataExtractor._safe_info_value(info, "val") is None

    def test_returns_none_for_non_dict_info(self):
        assert DataExtractor._safe_info_value(None, "key") is None
        assert DataExtractor._safe_info_value("string", "key") is None

    def test_converts_numpy_scalar(self):
        info = {"val": np.float64(12.5)}
        result = DataExtractor._safe_info_value(info, "val")
        assert result == 12.5
        assert isinstance(result, float)


class TestSafeScalar:
    """Tests for DataExtractor._safe_scalar static method."""

    def test_returns_plain_float(self):
        assert DataExtractor._safe_scalar(3.14) == 3.14

    def test_returns_plain_int(self):
        assert DataExtractor._safe_scalar(42) == 42

    def test_returns_none_for_none(self):
        assert DataExtractor._safe_scalar(None) is None

    def test_returns_none_for_nan(self):
        assert DataExtractor._safe_scalar(float("nan")) is None

    def test_returns_none_for_inf(self):
        assert DataExtractor._safe_scalar(float("inf")) is None

    def test_returns_none_for_negative_inf(self):
        assert DataExtractor._safe_scalar(float("-inf")) is None

    def test_converts_numpy_float64(self):
        result = DataExtractor._safe_scalar(np.float64(5.5))
        assert result == 5.5
        assert isinstance(result, float)

    def test_converts_numpy_int64(self):
        result = DataExtractor._safe_scalar(np.int64(100))
        assert result == 100

    def test_returns_none_for_pandas_na(self):
        assert DataExtractor._safe_scalar(pd.NA) is None

    def test_returns_none_for_pandas_nat(self):
        assert DataExtractor._safe_scalar(pd.NaT) is None


class TestSafeDivide:
    """Tests for DataExtractor._safe_divide static method."""

    def test_normal_division(self):
        assert DataExtractor._safe_divide(10.0, 2.0) == 5.0

    def test_division_returns_float(self):
        result = DataExtractor._safe_divide(10, 4)
        assert result == 2.5
        assert isinstance(result, float)

    def test_returns_none_for_zero_denominator(self):
        assert DataExtractor._safe_divide(10.0, 0) is None

    def test_returns_none_when_numerator_is_none(self):
        assert DataExtractor._safe_divide(None, 2.0) is None

    def test_returns_none_when_denominator_is_none(self):
        assert DataExtractor._safe_divide(10.0, None) is None

    def test_returns_none_for_both_none(self):
        assert DataExtractor._safe_divide(None, None) is None

    def test_returns_none_for_inf_result(self):
        # Very small denominator leading to inf
        result = DataExtractor._safe_divide(1e308, 1e-308)
        assert result is None

    def test_handles_negative_values(self):
        result = DataExtractor._safe_divide(-20.0, 4.0)
        assert result == -5.0


class TestExtractCompanyData:
    """Tests for DataExtractor.extract_company_data."""

    def test_returns_dataframe(self, extractor, sample_company):
        """extract_company_data returns a DataFrame."""
        mock_stock = MagicMock()
        mock_stock.info = {
            "currentPrice": 150.0,
            "marketCap": 2500000000000,
            "trailingPE": 28.5,
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }

        with patch("modules.input.data_extractor.yf.Ticker", return_value=mock_stock):
            result = extractor.extract_company_data(sample_company)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_contains_required_columns(self, extractor, sample_company):
        """extract_company_data DataFrame contains core factor columns."""
        mock_stock = MagicMock()
        mock_stock.info = {"currentPrice": 150.0, "trailingPE": 28.5}

        with patch("modules.input.data_extractor.yf.Ticker", return_value=mock_stock):
            result = extractor.extract_company_data(sample_company)

        for col in ["ticker", "date", "pe_ratio", "roe", "profit_margin"]:
            assert col in result.columns

    def test_ticker_is_set_correctly(self, extractor, sample_company):
        """extract_company_data sets ticker from company dict."""
        mock_stock = MagicMock()
        mock_stock.info = {}

        with patch("modules.input.data_extractor.yf.Ticker", return_value=mock_stock):
            result = extractor.extract_company_data(sample_company)

        assert result.iloc[0]["ticker"] == "AAPL"

    def test_returns_row_on_exception(self, extractor, sample_company):
        """extract_company_data returns a row even when yfinance raises."""
        with patch(
            "modules.input.data_extractor.yf.Ticker",
            side_effect=Exception("Network error"),
        ):
            result = extractor.extract_company_data(sample_company)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "AAPL"

    def test_sector_from_company_dict(self, extractor, sample_company):
        """extract_company_data uses gics_sector from company dict as db_sector."""
        mock_stock = MagicMock()
        mock_stock.info = {}

        with patch("modules.input.data_extractor.yf.Ticker", return_value=mock_stock):
            result = extractor.extract_company_data(sample_company)

        assert result.iloc[0]["db_sector"] == "Technology"


class TestBuildFundamentals:
    """Tests for DataExtractor._build_fundamentals_from_statements."""

    def test_returns_empty_df_for_none_statements(self, extractor):
        """Returns empty DataFrame when statements are None."""
        result = extractor._build_fundamentals_from_statements(
            None, None, None, is_annual=True
        )
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_returns_empty_df_for_empty_statements(self, extractor):
        """Returns empty DataFrame when income/balance statements are empty."""
        result = extractor._build_fundamentals_from_statements(
            pd.DataFrame(), pd.DataFrame(), None, is_annual=True
        )
        assert result.empty

    def test_annual_fundamentals_has_expected_columns(self, extractor):
        """Annual fundamentals DataFrame has ROE, ROA, margin columns."""
        import pandas as pd
        from datetime import datetime

        date1 = pd.Timestamp("2023-12-31")
        date2 = pd.Timestamp("2022-12-31")

        inc = pd.DataFrame(
            {
                date1: {"Net Income": 1e9, "Total Revenue": 5e9, "Diluted EPS": 2.5,
                        "EBITDA": 2e9, "Operating Income": 1.5e9, "Gross Profit": 3e9},
                date2: {"Net Income": 8e8, "Total Revenue": 4e9, "Diluted EPS": 2.0,
                        "EBITDA": 1.5e9, "Operating Income": 1.2e9, "Gross Profit": 2.5e9},
            }
        )
        bal = pd.DataFrame(
            {
                date1: {"Stockholders Equity": 5e9, "Total Assets": 20e9,
                        "Total Debt": 2e9, "Ordinary Shares Number": 1e9},
                date2: {"Stockholders Equity": 4.5e9, "Total Assets": 18e9,
                        "Total Debt": 2.5e9, "Ordinary Shares Number": 1e9},
            }
        )

        result = extractor._build_fundamentals_from_statements(
            inc, bal, None, is_annual=True
        )

        assert not result.empty
        assert "roe" in result.columns
        assert "roa" in result.columns
        assert "profit_margin" in result.columns
        assert "eps" in result.columns


class TestExtractBulkData:
    """Tests for DataExtractor.extract_bulk_data."""

    def test_returns_combined_dataframe(self, extractor):
        """extract_bulk_data concatenates results from multiple companies."""
        companies = [
            {"ticker": "AAPL", "name": "Apple"},
            {"ticker": "MSFT", "name": "Microsoft"},
        ]

        mock_df = pd.DataFrame([{"ticker": "X", "date": "2026-01-01"}])

        with patch.object(extractor, "extract_company_data", return_value=mock_df):
            result = extractor.extract_bulk_data(companies)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_returns_empty_for_empty_companies(self, extractor):
        """extract_bulk_data returns empty DataFrame for empty input."""
        result = extractor.extract_bulk_data([])
        assert isinstance(result, pd.DataFrame)
        assert result.empty
