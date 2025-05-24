-- Trading Bot SQL Queries
-- Author: Anhbaza01
-- Version: 1.0.0
-- Last Updated: 2025-05-24 08:21:44 UTC

-- Get open trades
SELECT * FROM trades 
WHERE status = 'OPEN'
ORDER BY open_time DESC;

-- Get trade history
SELECT 
    t.*,
    ROUND((exit_price - entry_price) / entry_price * 100, 2) as profit_pct
FROM trades t
WHERE status = 'CLOSED'
ORDER BY close_time DESC
LIMIT ?;

-- Get trade statistics
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(SUM(profit), 2) as total_profit,
    ROUND(AVG(CASE WHEN profit > 0 THEN profit END), 2) as avg_win,
    ROUND(AVG(CASE WHEN profit < 0 THEN profit END), 2) as avg_loss,
    ROUND(AVG(CASE 
        WHEN status = 'CLOSED' 
        THEN (exit_price - entry_price) / entry_price * 100 
    END), 2) as avg_profit_pct
FROM trades
WHERE status = 'CLOSED';

-- Get unprocessed signals
SELECT * FROM signals
WHERE processed = FALSE
ORDER BY time DESC;

-- Get active pairs
SELECT
    p.*,
    COUNT(t.id) as open_trades
FROM pairs p
LEFT JOIN trades t ON t.symbol = p.symbol AND t.status = 'OPEN'
WHERE p.enabled = TRUE
GROUP BY p.symbol
HAVING open_trades < 5
ORDER BY p.volume_24h DESC;

-- Update trade statistics
UPDATE statistics SET
    total_trades = (SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'),
    winning_trades = (SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND profit > 0),
    losing_trades = (SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND profit < 0),
    total_profit = (SELECT COALESCE(SUM(profit), 0) FROM trades WHERE status = 'CLOSED'),
    win_rate = (
        SELECT ROUND(
            CAST(COUNT(CASE WHEN profit > 0 THEN 1 END) AS FLOAT) /
            CAST(COUNT(*) AS FLOAT) * 100, 2
        )
        FROM trades
        WHERE status = 'CLOSED'
    ),
    avg_profit = (
        SELECT ROUND(AVG(profit), 2)
        FROM trades
        WHERE status = 'CLOSED'
    ),
    updated_at = CURRENT_TIMESTAMP;

-- Close trade
UPDATE trades SET
    status = 'CLOSED',
    exit_price = ?,
    profit = (CASE 
        WHEN type = 'LONG' THEN (? - entry_price) * quantity
        ELSE (entry_price - ?) * quantity
    END),
    close_time = CURRENT_TIMESTAMP,
    reason = ?
WHERE id = ?;

-- Add new trade
INSERT INTO trades (
    symbol, type, entry_price, take_profit, stop_loss,
    quantity, status, open_time
) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', CURRENT_TIMESTAMP);

-- Update pair info
UPDATE pairs SET
    last_price = ?,
    volume_24h = ?,
    updated_at = CURRENT_TIMESTAMP
WHERE symbol = ?;
