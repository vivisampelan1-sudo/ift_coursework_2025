"""
Unit tests for modules.output.minio_storage.

:module: test.test_minio_storage
"""
import pytest
import pandas as pd
import numpy as np
from io import BytesIO
from unittest.mock import MagicMock, patch

from modules.output.minio_storage import MinIOStorage


@pytest.fixture
def config():
    return {
        "minio": {
            "endpoint": "localhost:9000",
            "access_key": "ift_bigdata",
            "secret_key": "minio_password",
            "secure": False,
        }
    }


@pytest.fixture
def storage(config):
    with patch("modules.output.minio_storage.Minio") as mock_minio_cls:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_cls.return_value = mock_client
        s = MinIOStorage(config)
        s.client = mock_client
        return s


class TestCleanDataframe:
    """Tests for MinIOStorage._clean_dataframe static method."""

    def test_replaces_inf_with_none(self):
        df = pd.DataFrame({"val": [1.0, float("inf"), -float("inf"), 3.0]})
        result = MinIOStorage._clean_dataframe(df)
        assert result["val"].isna().sum() == 2
        assert result["val"].iloc[0] == 1.0
        assert result["val"].iloc[3] == 3.0

    def test_preserves_text_columns(self):
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "sector": ["Technology", "Technology"],
            "val": [1.0, 2.0],
        })
        result = MinIOStorage._clean_dataframe(df)
        assert list(result["ticker"]) == ["AAPL", "MSFT"]
        assert list(result["sector"]) == ["Technology", "Technology"]

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"val": [1.0, float("inf")]})
        original_val = df["val"].iloc[1]
        MinIOStorage._clean_dataframe(df)
        # Original should be unchanged (copy is made inside method)
        assert df["val"].iloc[1] == original_val

    def test_handles_empty_dataframe(self):
        df = pd.DataFrame()
        result = MinIOStorage._clean_dataframe(df)
        assert result.empty

    def test_handles_all_valid_data(self):
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "pe_ratio": [28.5],
            "roe": [0.87],
        })
        result = MinIOStorage._clean_dataframe(df)
        assert result["pe_ratio"].iloc[0] == 28.5
        assert result["roe"].iloc[0] == 0.87

    def test_replaces_numpy_inf(self):
        df = pd.DataFrame({"val": [np.inf, -np.inf, 1.0]})
        result = MinIOStorage._clean_dataframe(df)
        assert result["val"].isna().sum() == 2

    def test_known_text_columns_not_converted(self):
        """None of the known text columns should be coerced to numeric."""
        text_cols = ["company_id", "ticker", "company_name", "date",
                     "sector", "industry", "db_sector", "db_industry"]
        df = pd.DataFrame({col: ["test_value"] for col in text_cols})
        result = MinIOStorage._clean_dataframe(df)
        for col in text_cols:
            # Accept either object or pandas StringDtype (pandas 3.x)
            assert result[col].dtype == object or hasattr(result[col].dtype, "na_value")


class TestMinIOStorageInit:
    """Tests for MinIOStorage initialisation."""

    def test_creates_bucket_if_not_exists(self, config):
        """MinIOStorage creates bucket when it does not exist."""
        with patch("modules.output.minio_storage.Minio") as mock_minio_cls:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = False
            mock_minio_cls.return_value = mock_client

            MinIOStorage(config)

            mock_client.make_bucket.assert_called_once_with("investment-data")

    def test_does_not_create_bucket_if_exists(self, config):
        """MinIOStorage does not create bucket when it already exists."""
        with patch("modules.output.minio_storage.Minio") as mock_minio_cls:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_cls.return_value = mock_client

            MinIOStorage(config)

            mock_client.make_bucket.assert_not_called()


class TestStoreDataframe:
    """Tests for MinIOStorage.store_dataframe."""

    def test_calls_put_object(self, storage):
        """store_dataframe calls put_object on the MinIO client."""
        df = pd.DataFrame([
            {"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": 28.5}
        ])
        storage.store_dataframe(df, "current_data/2026/01/31/test.parquet")
        storage.client.put_object.assert_called_once()

    def test_stores_with_correct_object_name(self, storage):
        """store_dataframe uses provided object name."""
        df = pd.DataFrame([{"ticker": "AAPL", "date": "2026-01-31"}])
        obj_name = "current_data/2026/01/test.parquet"
        storage.store_dataframe(df, obj_name)

        call_args = storage.client.put_object.call_args
        assert call_args[0][1] == obj_name

    def test_sanitises_inf_before_storage(self, storage):
        """store_dataframe sanitises infinity before writing Parquet."""
        df = pd.DataFrame([{"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": float("inf")}])
        # Should not raise
        storage.store_dataframe(df, "test/test.parquet")
        storage.client.put_object.assert_called_once()


class TestRetrieveDataframe:
    """Tests for MinIOStorage.retrieve_dataframe."""

    def test_retrieve_returns_dataframe(self, storage):
        """retrieve_dataframe returns a DataFrame from Parquet bytes."""
        original_df = pd.DataFrame([
            {"ticker": "AAPL", "date": "2026-01-31", "pe_ratio": 28.5}
        ])
        buf = BytesIO()
        original_df.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)

        mock_response = MagicMock()
        mock_response.read.return_value = buf.getvalue()
        storage.client.get_object.return_value = mock_response

        result = storage.retrieve_dataframe("test/test.parquet")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "AAPL"
