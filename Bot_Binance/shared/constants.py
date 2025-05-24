"""
Constants and Configuration
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 10:03:02 UTC
"""

from enum import Enum

class Config:
    # Minimum 24h USDT volume for trading pairs
    MIN_VOLUME = 1_000_000  # $1M USD
    
    # Technical indicators
    RSI_PERIOD = 14
    FAST_MA = 12
    SLOW_MA = 26
    VOLUME_PERIOD = 20
    
    # Signal requirements
    MIN_CONFIDENCE = 70  # Minimum confidence score (0-100)
    VOLUME_RATIO_MIN = 1.5  # Minimum volume vs average
    
    # Trading parameters
    MAX_TRADES = 5  # Maximum concurrent trades
    ORDER_SIZE = 100  # Order size in USDT
    
    # Risk management
    MAX_LOSS_PERCENT = 2.0  # Maximum loss per trade
    DAILY_LOSS_LIMIT = 5.0  # Maximum daily loss
    
    # Take profit and stop loss defaults
    DEFAULT_TP_PERCENT = 1.0
    DEFAULT_SL_PERCENT = 0.5
    
    # Timeframes to scan
    TIMEFRAMES = [
        "1m",
        "5m", 
        "15m",
        "1h",
        "4h"
    ]

class SignalType(Enum):
    """Signal types"""
    LONG = "LONG"
    SHORT = "SHORT"

class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    OCO = "OCO"

class OrderSide(Enum):
    """Order sides"""
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    """Order statuses"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class MessageType(Enum):
    """WebSocket message types"""
    REGISTER = "REGISTER"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    ORDER_UPDATE = "ORDER_UPDATE"
    ERROR = "ERROR"
    PING = "PING"
    PONG = "PONG"

class ClientType(Enum):
    """WebSocket client types"""
    SIGNAL_BOT = "SIGNAL_BOT"
    TRADE_MANAGER = "TRADE_MANAGER"
    GUI = "GUI"

class ErrorCode(Enum):
    """Error codes"""
    INVALID_MESSAGE = 1001
    INVALID_CLIENT = 1002
    INVALID_SIGNAL = 1003
    INVALID_ORDER = 1004
    CONNECTION_ERROR = 1005
    API_ERROR = 1006
    DATABASE_ERROR = 1007

class TradingMode(Enum):
    """Trading modes"""
    SPOT = "SPOT"
    MARGIN = "MARGIN"
    FUTURES = "FUTURES"

class TradingStatus(Enum):
    """Trading statuses"""
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"

class TimeInForce(Enum):
    """Time in force types"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill

class PriceSource(Enum):
    """Price data sources"""
    BINANCE = "BINANCE"
    TRADINGVIEW = "TRADINGVIEW"
    CUSTOM = "CUSTOM"

class Interval(Enum):
    """Candlestick intervals"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

class TradePosition(Enum):
    """Trade positions"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"

class TradeStatus(Enum):
    """Trade statuses"""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    ERROR = "ERROR"

class TradeResult(Enum):
    """Trade results"""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"

class LogLevel(Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Color:
    """GUI colors"""
    # Main colors
    PRIMARY = "#2196F3"
    SECONDARY = "#757575"
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"
    ERROR = "#F44336"
    INFO = "#2196F3"
    
    # Text colors
    TEXT_PRIMARY = "#212121"
    TEXT_SECONDARY = "#757575"
    TEXT_DISABLED = "#BDBDBD"
    
    # Background colors
    BG_PRIMARY = "#FFFFFF"
    BG_SECONDARY = "#F5F5F5"
    
    # Trading colors
    PROFIT = "#4CAF50"
    LOSS = "#F44336"
    NEUTRAL = "#9E9E9E"
    
    # Chart colors
    CHART_UP = "#26A69A"
    CHART_DOWN = "#EF5350"
    CHART_GRID = "#E0E0E0"
    
    # Indicator colors
    IND_1 = "#2196F3"
    IND_2 = "#FFA726"
    IND_3 = "#66BB6A"
    IND_4 = "#AB47BC"
    IND_5 = "#EC407A"

class GuiConfig:
    """GUI configuration"""
    # Window settings 
    WINDOW_TITLE = "Trading Bot Manager"
    WINDOW_SIZE = "1200x800"
    MIN_WINDOW_SIZE = "800x600"
    
    # Update intervals (ms)
    PRICE_UPDATE = 1000
    SIGNAL_UPDATE = 5000 
    TRADE_UPDATE = 2000
    STATS_UPDATE = 10000
    
    # Table settings
    TABLE_ROW_HEIGHT = 25
    MAX_TABLE_ROWS = 100
    
    # Font settings
    FONT_FAMILY = "Helvetica"
    FONT_SIZE_SMALL = 10
    FONT_SIZE_NORMAL = 12
    FONT_SIZE_LARGE = 14
    FONT_SIZE_HEADER = 16

class DatabaseConfig:
    """Database configuration"""
    # SQLite settings
    DB_PATH = "database/trading.db"
    BACKUP_DIR = "database/backups"
    BACKUP_INTERVAL = 86400  # 24 hours
    
    # Tables
    TRADES_TABLE = "trades"
    SIGNALS_TABLE = "signals"
    ORDERS_TABLE = "orders"
    STATS_TABLE = "stats"
    
    # Maximum records
    MAX_TRADE_RECORDS = 10000
    MAX_SIGNAL_RECORDS = 5000
    MAX_ORDER_RECORDS = 20000

class TelegramConfig:
    """Telegram configuration"""
    # Message templates
    START_MSG = """
🤖 *Trading Bot Started*

Time: {time}
User: {user}
Mode: {mode}
"""

    SIGNAL_MSG = """
🔔 *New Trading Signal*

Symbol: {symbol}
Type: {type}
Entry: {entry}
Take Profit: {tp}
Stop Loss: {sl}
Confidence: {confidence}%

Time: {time}
"""

    ORDER_MSG = """
📊 *Order Update*

Symbol: {symbol}
Side: {side}
Type: {type}
Price: {price}
Quantity: {qty}
Status: {status}

Time: {time}
"""

    TRADE_MSG = """
💰 *Trade {status}*

Symbol: {symbol}
Type: {type}
Entry: {entry}
Exit: {exit}
Profit: {profit}%
Duration: {duration}

Time: {time}
"""

    ERROR_MSG = """
❌ *Error*

Type: {type}
Details: {details}

Time: {time}
"""

    # Update intervals
    PRICE_UPDATE = 300  # 5 minutes
    BALANCE_UPDATE = 3600  # 1 hour
    STATS_UPDATE = 86400  # 24 hours