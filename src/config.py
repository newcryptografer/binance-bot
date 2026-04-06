import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    _instance: Optional['Config'] = None
    _config: Optional[Dict[str, Any]] = None

    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', 'config.yaml')
        
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            loaded = yaml.safe_load(f)
            self._config = loaded if loaded is not None else {}
        
        self._load_env_overrides()
        
        print(f"[DEBUG] Config loaded - api_key: '{self._config.get('binance', {}).get('api_key', '')}'")
        
        return self._config  # type: ignore[return-value]

    def _load_env_overrides(self) -> None:
        if self._config is None:
            return
            
        if os.getenv('BINANCE_API_KEY'):
            self._config.setdefault('binance', {})['api_key'] = os.getenv('BINANCE_API_KEY')
        if os.getenv('BINANCE_API_SECRET'):
            self._config.setdefault('binance', {})['api_secret'] = os.getenv('BINANCE_API_SECRET')
        if os.getenv('TRADING_MODE'):
            self._config.setdefault('trading', {})['mode'] = os.getenv('TRADING_MODE')

    @property
    def binance(self) -> Dict[str, Any]:
        return self._config.get('binance', {}) if self._config is not None else {}

    @property
    def trading(self) -> Dict[str, Any]:
        return self._config.get('trading', {}) if self._config is not None else {}

    @property
    def scanning(self) -> Dict[str, Any]:
        return self._config.get('scanning', {}) if self._config is not None else {}

    @property
    def risk(self) -> Dict[str, Any]:
        return self._config.get('risk', {}) if self._config is not None else {}

    @property
    def is_paper_mode(self) -> bool:
        return self.trading.get('mode', 'paper') == 'paper'
    
    @property
    def use_live_market_data(self) -> bool:
        return not self.is_paper_mode or bool(self.binance.get('api_key') and self.binance.get('api_secret'))

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default) if self._config else default


config = Config()