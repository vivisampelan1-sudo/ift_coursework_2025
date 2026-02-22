"""Tests for the MinIO storage module."""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, ANY
from io import BytesIO

from modules.output.minio_storage import MinIOStorage


class TestMinIOStorageInit:
    """Tests for MinIOStorage initialization."""

    @patch("modules.output.minio_storage.Minio")
    def test_init_creates_client(self, mock_minio_class, sample_config):
        """Test that MinIO client is created with correct config."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage(sample_config)

        mock_minio_class.assert_called_once_with(
            "localhost:9000",
            access_key="ift_bigdata",
            secret_key="minio_password",
            secure=False,
        )

    @patch("modules.output.minio_storage.Minio")
    def test_init_creates_bucket_if_not_exists(self, mock_minio_class, sample_config):
        """Test that bucket is created if it doesn't exist."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage(sample_config)

        mock_client.make_bucket.assert_called_once_with("investment-data")

    @patch("modules.output.minio_storage.Minio")
    def test_init_skips_bucket_creation_if_exists(
        self, mock_minio_class, sample_config
    ):
        """Test that bucket creation is skipped if already exists."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage(sample_config)

        mock_client.make_bucket.assert_not_called()


class TestStoreDataframe:
    """Tests for store_dataframe method."""

    @patch("modules.output.minio_storage.Minio")
    def test_store_dataframe(self, mock_minio_class, sample_config, sample_current_df):
        """Test storing a DataFrame to MinIO."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage(sample_config)
        storage.store_dataframe(sample_current_df, "test/data.parquet")

        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args
        assert call_args[0][0] == "investment-data"
        assert call_args[0][1] == "test/data.parquet"

    @patch("modules.output.minio_storage.Minio")
    def test_store_dataframe_handles_infinity(self, mock_minio_class, sample_config):
        """Test that Infinity values are cleaned before storage."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        # Create DataFrame with Infinity values
        df = pd.DataFrame(
            {
                "ticker": ["TEST"],
                "pe_ratio": ["Infinity"],
                "pb_ratio": [float("inf")],
                "roe": [-float("inf")],
                "normal_val": [1.5],
            }
        )

        storage = MinIOStorage(sample_config)
        # Should not raise an error
        storage.store_dataframe(df, "test/infinity.parquet")
        mock_client.put_object.assert_called_once()

    @patch("modules.output.minio_storage.Minio")
    def test_store_dataframe_with_none_values(self, mock_minio_class, sample_config):
        """Test storing DataFrame with None values."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        df = pd.DataFrame(
            {
                "ticker": ["TEST"],
                "pe_ratio": [None],
                "pb_ratio": [None],
            }
        )

        storage = MinIOStorage(sample_config)
        storage.store_dataframe(df, "test/none.parquet")
        mock_client.put_object.assert_called_once()

    @patch("modules.output.minio_storage.Minio")
    def test_store_empty_dataframe(self, mock_minio_class, sample_config):
        """Test storing an empty DataFrame."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        df = pd.DataFrame()

        storage = MinIOStorage(sample_config)
        storage.store_dataframe(df, "test/empty.parquet")
        mock_client.put_object.assert_called_once()


class TestRetrieveDataframe:
    """Tests for retrieve_dataframe method."""

    @patch("modules.output.minio_storage.Minio")
    def test_retrieve_dataframe(self, mock_minio_class, sample_config):
        """Test retrieving a DataFrame from MinIO."""
        # Create a real parquet buffer to return
        original_df = pd.DataFrame(
            {"ticker": ["AAPL"], "pe_ratio": [28.5], "roe": [0.157]}
        )
        buffer = BytesIO()
        original_df.to_parquet(buffer, index=False)
        buffer.seek(0)

        mock_response = MagicMock()
        mock_response.read.return_value = buffer.getvalue()

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.get_object.return_value = mock_response
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage(sample_config)
        df = storage.retrieve_dataframe("test/data.parquet")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df["ticker"].values[0] == "AAPL"
        assert df["pe_ratio"].values[0] == 28.5
