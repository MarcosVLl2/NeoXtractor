"""Provides game config manager."""

import os
from core.config import Config

class ConfigManager:
    """Game config manager."""

    def __init__(self):
        self.configs: list[Config] = []
        self._name_dict: dict[str, Config] = {}

    def add_config(self, cfg: Config):
        """Add a game config to this manager."""
        if cfg.name in self._name_dict:
            raise ValueError("Config is already in Config Manager.")
        self.configs.append(cfg)
        self._name_dict[cfg.name] = cfg

    def add_configs(self, cfgs: list[Config]):
        """Add multiple game configs to this manager."""
        for cfg in cfgs:
            self.add_config(cfg)

    def remove_config(self, cfg: Config | str):
        """Remove a game config by name or instance."""
        if isinstance(cfg, str):
            cfg = self._name_dict[cfg]
        self.configs.remove(cfg)
        self._name_dict.pop(cfg.name)

    def get_config(self, name: str) -> Config | None:
        """Get a config by name."""
        return self._name_dict.get(name)

    def load_from_path(self, path = "configs"):
        """Load all configs in path to this manager."""
        for cfg_file in os.listdir(path):
            cfg_path = os.path.join(path, cfg_file)
            cfg = Config.from_file(cfg_path)
            self.add_config(cfg)
