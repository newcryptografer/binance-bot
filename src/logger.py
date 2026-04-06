import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def setup(self, name: str = "BinanceBot", log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
        if self._logger is not None:
            return self._logger
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()
        
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        self._logger = logger
        return logger

    def get_logger(self) -> logging.Logger:
        if self._logger is None:
            return self.setup()
        return self._logger

    def info(self, msg: str) -> None:
        self.get_logger().info(msg)

    def warning(self, msg: str) -> None:
        self.get_logger().warning(msg)

    def error(self, msg: str) -> None:
        self.get_logger().error(msg)

    def debug(self, msg: str) -> None:
        self.get_logger().debug(msg)


logger = Logger()