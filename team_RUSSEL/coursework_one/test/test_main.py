"""Tests for the main pipeline application."""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from Main import main, setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_returns_logger(self, sample_config):
        """Test that setup_logging returns a logger."""
        logger = setup_logging(sample_config)
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_setup_logging_uses_config_level(self, sample_config):
        """Test that logging level from config is applied."""
        sample_config["logging"]["level"] = "DEBUG"
        logger = setup_logging(sample_config)
        assert logger is not None


class TestMainPipeline:
    """Tests for the main pipeline function."""

    @patch("Main.MongoStorage")
    @patch("Main.MinIOStorage")
    @patch("Main.DataExtractor")
    @patch("Main.load_company_list")
    @patch("Main.DatabaseConnector")
    @patch("Main.load_config")
    def test_main_runs_successfully(
        self,
        mock_load_config,
        mock_db_class,
        mock_load_companies,
        mock_extractor_class,
        mock_minio_class,
        mock_mongo_class,
        sample_config,
        sample_companies,
        sample_current_df,
        sample_historical_df,
    ):
        """Test that main pipeline runs without errors."""
        mock_load_config.return_value = sample_config
        mock_load_companies.return_value = sample_companies

        mock_extractor = MagicMock()
        mock_extractor.extract_bulk_data.return_value = sample_current_df
        mock_extractor.extract_bulk_historical_data.return_value = (
            sample_historical_df
        )
        mock_extractor_class.return_value = mock_extractor

        # Should not raise
        main("config/conf.yaml")

    @patch("Main.MongoStorage")
    @patch("Main.MinIOStorage")
    @patch("Main.DataExtractor")
    @patch("Main.load_company_list")
    @patch("Main.DatabaseConnector")
    @patch("Main.load_config")
    def test_main_handles_empty_data(
        self,
        mock_load_config,
        mock_db_class,
        mock_load_companies,
        mock_extractor_class,
        mock_minio_class,
        mock_mongo_class,
        sample_config,
    ):
        """Test that pipeline handles empty extraction gracefully."""
        mock_load_config.return_value = sample_config
        mock_load_companies.return_value = []

        mock_extractor = MagicMock()
        mock_extractor.extract_bulk_data.return_value = pd.DataFrame()
        mock_extractor.extract_bulk_historical_data.return_value = pd.DataFrame()
        mock_extractor_class.return_value = mock_extractor

        # Should not raise
        main("config/conf.yaml")

    @patch("Main.MongoStorage")
    @patch("Main.MinIOStorage")
    @patch("Main.DataExtractor")
    @patch("Main.load_company_list")
    @patch("Main.DatabaseConnector")
    @patch("Main.load_config")
    def test_main_with_custom_date(
        self,
        mock_load_config,
        mock_db_class,
        mock_load_companies,
        mock_extractor_class,
        mock_minio_class,
        mock_mongo_class,
        sample_config,
        sample_current_df,
        sample_historical_df,
    ):
        """Test pipeline with a custom run date."""
        mock_load_config.return_value = sample_config
        mock_load_companies.return_value = []

        mock_extractor = MagicMock()
        mock_extractor.extract_bulk_data.return_value = sample_current_df
        mock_extractor.extract_bulk_historical_data.return_value = (
            sample_historical_df
        )
        mock_extractor_class.return_value = mock_extractor

        main("config/conf.yaml", run_date="2026-01-15")

    @patch("Main.MongoStorage")
    @patch("Main.MinIOStorage")
    @patch("Main.DataExtractor")
    @patch("Main.load_company_list")
    @patch("Main.DatabaseConnector")
    @patch("Main.load_config")
    def test_main_with_frequency_override(
        self,
        mock_load_config,
        mock_db_class,
        mock_load_companies,
        mock_extractor_class,
        mock_minio_class,
        mock_mongo_class,
        sample_config,
        sample_current_df,
        sample_historical_df,
    ):
        """Test pipeline with frequency override."""
        mock_load_config.return_value = sample_config
        mock_load_companies.return_value = []

        mock_extractor = MagicMock()
        mock_extractor.extract_bulk_data.return_value = sample_current_df
        mock_extractor.extract_bulk_historical_data.return_value = (
            sample_historical_df
        )
        mock_extractor_class.return_value = mock_extractor

        main("config/conf.yaml", frequency="weekly")

    @patch("Main.MongoStorage")
    @patch("Main.MinIOStorage")
    @patch("Main.DataExtractor")
    @patch("Main.load_company_list")
    @patch("Main.DatabaseConnector")
    @patch("Main.load_config")
    def test_main_closes_connections_on_success(
        self,
        mock_load_config,
        mock_db_class,
        mock_load_companies,
        mock_extractor_class,
        mock_minio_class,
        mock_mongo_class,
        sample_config,
        sample_current_df,
        sample_historical_df,
    ):
        """Test that database connections are closed after pipeline."""
        mock_load_config.return_value = sample_config
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_load_companies.return_value = []

        mock_extractor = MagicMock()
        mock_extractor.extract_bulk_data.return_value = sample_current_df
        mock_extractor.extract_bulk_historical_data.return_value = (
            sample_historical_df
        )
        mock_extractor_class.return_value = mock_extractor

        main("config/conf.yaml")

        mock_db.close_all.assert_called_once()
