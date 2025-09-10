"""Configuration management for claude-notes."""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Manages configuration settings for claude-notes."""

    DEFAULT_CONFIG_PATH = Path.home() / ".claude" / "claude-notes.settings.json"

    @staticmethod
    def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
        """Load configuration from file.

        Args:
            config_path: Path to config file. If None, uses default location.

        Returns:
            Dictionary of configuration settings. Empty dict if file doesn't exist.
        """
        path = config_path or ConfigManager.DEFAULT_CONFIG_PATH

        if not path.exists():
            return {}

        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            # Return empty dict on error, allowing CLI to continue with defaults
            import click

            click.echo(f"Warning: Could not load config from {path}: {e}", err=True)
            return {}

    @staticmethod
    def save_config(settings: Dict[str, Any], config_path: Optional[Path] = None) -> None:
        """Save configuration to file.

        Args:
            settings: Dictionary of settings to save
            config_path: Path to config file. If None, uses default location.
        """
        path = config_path or ConfigManager.DEFAULT_CONFIG_PATH

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Filter out None values and internal Click context values
        filtered_settings = {
            k: v for k, v in settings.items() if v is not None and not k.startswith("_") and k != "save_config"
        }

        with open(path, "w") as f:
            json.dump(filtered_settings, f, indent=2)

    @staticmethod
    def merge_configs(file_config: Dict[str, Any], cli_args: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration from file with CLI arguments.

        CLI arguments take precedence over file configuration.

        Args:
            file_config: Configuration loaded from file
            cli_args: Arguments passed via CLI

        Returns:
            Merged configuration dictionary
        """
        # Start with file config
        merged = file_config.copy()

        # Override with CLI args (excluding None values and special keys)
        for key, value in cli_args.items():
            # Skip None values, internal Click context values, and special flags
            if value is not None and not key.startswith("_") and key not in ["config_file", "save_config"]:
                merged[key] = value

        return merged

    @staticmethod
    def get_config_path_from_args(ctx) -> Optional[Path]:
        """Extract config file path from Click context if provided."""
        # Look for config_file in params
        config_file = ctx.params.get("config_file")
        if config_file:
            return Path(config_file)
        return None
