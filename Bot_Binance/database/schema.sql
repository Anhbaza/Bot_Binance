-- Trading Bot Database Schema
-- Author: Anhbaza01
-- Version: 1.0.0
-- Last Updated: 2025-05-24 08:21:44 UTC

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('LONG', 'SHORT')),
    entry_price REAL NOT NULL,
    exit_price REAL,
    take_profit REAL NOT NULL,
    stop_loss REAL NOT NULL,
    quantity REAL NOT NULL,
    profit REAL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    reason TEXT,
    open_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    close_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Signals table
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('LONG', 'SHORT')),
    entry_price REAL NOT NULL,
    take_profit REAL NOT NULL, 
    stop_loss REAL NOT NULL,
    confidence REAL NOT NULL,
    rsi REAL,
    volume_ratio REAL,
    reason TEXT,
    processed BOOLEAN DEFAULT FALSE,
    time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Trading pairs table
CREATE TABLE IF NOT EXISTS pairs (
    symbol TEXT PRIMARY KEY,
    base_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    min_price REAL NOT NULL,
    min_qty REAL NOT NULL,
    min_notional REAL NOT NULL,
    price_precision INTEGER NOT NULL,
    qty_precision INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    last_price REAL,
    volume_24h REAL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Trading statistics table
CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_profit REAL NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0,
    avg_profit REAL NOT NULL DEFAULT 0,
    max_drawdown REAL NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Triggers for updated_at
CREATE TRIGGER IF NOT EXISTS trades_updated 
    AFTER UPDATE ON trades
BEGIN
    UPDATE trades 
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS pairs_updated
    AFTER UPDATE ON pairs
BEGIN
    UPDATE pairs
    SET updated_at = CURRENT_TIMESTAMP
    WHERE symbol = NEW.symbol;
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_processed ON signals(processed);
CREATE INDEX IF NOT EXISTS idx_pairs_enabled ON pairs(enabled);
