"""
Configuration loader utility.

Loads application configuration from a YAML file and returns it
as a Python dictionary.

:module: modules.utils.config_loader
"""
import yaml
from pathlib import Path


def load_config(config_path: str = "config/conf.yaml") -> dict:
    """
    Load configuration from a YAML file.

    :param config_path: Path to the YAML configuration file.
        Defaults to ``config/conf.yaml``.
    :type config_path: str
    :returns: Parsed configuration dictionary.
    :rtype: dict
    :raises FileNotFoundError: If the configuration file does not exist.
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config
