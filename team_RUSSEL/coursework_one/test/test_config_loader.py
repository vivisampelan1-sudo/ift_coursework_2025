"""Tests for the configuration loader utility."""
import pytest
import os
import tempfile
import yaml

from modules.utils.config_loader import load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self):
        """Test loading a valid YAML configuration file."""
        # Create a temporary config file
        config_data = {
            "postgres": {"host": "localhost", "port": 5439},
            "mongodb": {"host": "localhost", "port": 27019},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["postgres"]["host"] == "localhost"
            assert config["postgres"]["port"] == 5439
            assert config["mongodb"]["host"] == "localhost"
            assert config["mongodb"]["port"] == 27019
        finally:
            os.unlink(temp_path)

    def test_load_config_file_not_found(self):
        """Test that FileNotFoundError is raised for missing config."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent/path/config.yaml")

    def test_load_config_default_path(self):
        """Test loading config from the default path."""
        config = load_config("config/conf.yaml")
        assert "postgres" in config
        assert "mongodb" in config
        assert "minio" in config
        assert "extraction" in config
        assert "logging" in config

    def test_config_contains_required_postgres_fields(self):
        """Test that config has all required PostgreSQL fields."""
        config = load_config("config/conf.yaml")
        required_fields = ["host", "port", "database", "user", "password"]
        for field in required_fields:
            assert field in config["postgres"], f"Missing postgres field: {field}"

    def test_config_contains_required_mongodb_fields(self):
        """Test that config has all required MongoDB fields."""
        config = load_config("config/conf.yaml")
        required_fields = ["host", "port", "database"]
        for field in required_fields:
            assert field in config["mongodb"], f"Missing mongodb field: {field}"

    def test_config_contains_required_minio_fields(self):
        """Test that config has all required MinIO fields."""
        config = load_config("config/conf.yaml")
        required_fields = ["endpoint", "access_key", "secret_key", "secure"]
        for field in required_fields:
            assert field in config["minio"], f"Missing minio field: {field}"

    def test_config_contains_extraction_settings(self):
        """Test that config has extraction settings."""
        config = load_config("config/conf.yaml")
        assert "frequency" in config["extraction"]
        assert "lookback_years" in config["extraction"]
        assert config["extraction"]["lookback_years"] > 0

    def test_config_returns_dict(self):
        """Test that load_config returns a dictionary."""
        config = load_config("config/conf.yaml")
        assert isinstance(config, dict)
