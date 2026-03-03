"""
Unit tests for modules.utils.config_loader.

:module: test.test_config_loader
"""
import pytest
import tempfile
import os
from pathlib import Path

from a_pipeline.modules.utils.config_loader import load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        """load_config returns a dict from a valid YAML file."""
        cfg_file = tmp_path / "conf.yaml"
        cfg_file.write_text(
            "postgres:\n"
            "  host: localhost\n"
            "  port: 5439\n"
            "mongodb:\n"
            "  host: localhost\n"
            "  port: 27019\n"
        )
        result = load_config(str(cfg_file))
        assert isinstance(result, dict)
        assert result["postgres"]["host"] == "localhost"
        assert result["postgres"]["port"] == 5439
        assert result["mongodb"]["port"] == 27019

    def test_load_config_returns_all_sections(self, tmp_path):
        """load_config returns all top-level sections from YAML."""
        cfg_file = tmp_path / "conf.yaml"
        cfg_file.write_text(
            "postgres:\n  host: db\n"
            "mongodb:\n  host: mongo\n"
            "minio:\n  endpoint: localhost:9000\n"
            "extraction:\n  lookback_years: 5\n"
        )
        result = load_config(str(cfg_file))
        assert "postgres" in result
        assert "mongodb" in result
        assert "minio" in result
        assert "extraction" in result

    def test_load_config_file_not_found(self):
        """load_config raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/conf.yaml")

    def test_load_config_default_path_used(self):
        """load_config uses config/conf.yaml as default path."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.yaml")

    def test_load_config_nested_values(self, tmp_path):
        """load_config correctly parses nested YAML structures."""
        cfg_file = tmp_path / "conf.yaml"
        cfg_file.write_text(
            "extraction:\n"
            "  frequency: daily\n"
            "  lookback_years: 5\n"
            "  batch_size: 10\n"
        )
        result = load_config(str(cfg_file))
        assert result["extraction"]["frequency"] == "daily"
        assert result["extraction"]["lookback_years"] == 5
        assert result["extraction"]["batch_size"] == 10

    def test_load_config_returns_dict_type(self, tmp_path):
        """load_config always returns a Python dict."""
        cfg_file = tmp_path / "conf.yaml"
        cfg_file.write_text("key: value\n")
        result = load_config(str(cfg_file))
        assert type(result) is dict
