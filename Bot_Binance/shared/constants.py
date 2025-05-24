"""
Trading Bot Constants
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24
"""

from enum import Enum
from typing import Dict, List

# Signal types
class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

# Message types for WebSocket
class MessageType(Enum):
    SIGNAL = "SIGNAL"         # New trading signal
    CLOSE = "CLOSE"          # Close position signal
    WATCH_PAIRS = "WATCH"    # Update watched pairs
    STATUS = "STATUS"        # Status update
    ERROR = "ERROR"          # Error message
    REGISTER = "REGISTER"    # Client registration
    HEARTBEAT = "HEARTBEAT"  # Keep-alive message

# Client types
class ClientType(Enum):
    SIGNAL_BOT = "SIGNAL_BOT"
    TRADE_BOT = "TRADE_BOT"

# Trading constants
class TradingConfig:
    # RSI settings
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    
    # Volume settings
    VOLUME_RATIO_MIN: float = 1.5
    MIN_VOLUME_USDT: int = 1_000_000
    
    # Trading settings
    MAX_TRADES: int = 5
    ORDER_SIZE: float = 100.0
    RISK_PER_TRADE: float = 1.0
    DEFAULT_LEVERAGE: int = 1
    
    # Confidence threshold
    CONFIDENCE_THRESHOLD: float = 70.0

# Database tables
TABLES_SQL: Dict[str, str] = {
    "trades": """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            take_profit REAL NOT NULL,
            stop_loss REAL NOT NULL,
            quantity REAL NOT NULL,
            profit REAL,
            status TEXT NOT NULL,
            open_time TIMESTAMP NOT NULL,
            close_time TIMESTAMP,
            reason TEXT
        )
    """,
    
    "signals": """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            take_profit REAL NOT NULL,
            stop_loss REAL NOT NULL,
            confidence REAL NOT NULL,
            time TIMESTAMP NOT NULL,
            processed BOOLEAN DEFAULT FALSE
        )
    """
}

# Timeframes supported
TIMEFRAMES: List[str] = ["5m", "15m", "1h", "4h", "1d"]

# Order status
class OrderStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

# Close reasons
class CloseReason(Enum):
    TP = "TP"              # Take profit hit
    SL = "SL"              # Stop loss hit
    SIGNAL = "SIGNAL"      # Reverse signal
    MANUAL = "MANUAL"      # Manual close
    ERROR = "ERROR"        # Error closing
