"""
Database Manager Class
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:28:21 UTC
"""

import os
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

class DatabaseManager:
    def __init__(
        self,
        db_path: str,
        schema_path: str,
        logger: Optional[logging.Logger] = None,
        backup_dir: Optional[str] = None
    ):
        """
        Initialize Database Manager
        
        Args:
            db_path: Path to SQLite database file
            schema_path: Path to SQL schema file
            logger: Optional logger instance
            backup_dir: Optional directory for backups
        """
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.logger = logger or logging.getLogger(__name__)
        self.backup_dir = Path(backup_dir) if backup_dir else self.db_path.parent / 'backups'
        self.conn = None
        self.setup_database()
        
    def setup_database(self):
        """Setup database and tables"""
        try:
            # Create directories
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            
            # Enable foreign keys and WAL mode
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
            
            # Load and execute schema
            with open(self.schema_path, 'r') as f:
                self.conn.executescript(f.read())
                
            self.conn.commit()
            
            # Initialize statistics if empty
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM statistics")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO statistics (
                        id, total_trades, winning_trades,
                        losing_trades, total_profit, win_rate,
                        avg_profit, max_drawdown
                    ) VALUES (1, 0, 0, 0, 0, 0, 0, 0)
                """)
                self.conn.commit()
                
            self.logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Database setup error: {str(e)}")
            raise

    def backup_database(self):
        """Create database backup"""
        try:
            # Generate backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"trading_{timestamp}.db"
            
            # Create backup connection
            backup_conn = sqlite3.connect(backup_path)
            
            # Backup database
            with backup_conn:
                self.conn.backup(backup_conn)
                
            self.logger.info(f"Database backed up to: {backup_path}")
            
            # Delete old backups (keep last 5)
            backups = sorted(self.backup_dir.glob("trading_*.db"))
            if len(backups) > 5:
                for backup in backups[:-5]:
                    backup.unlink()
                    
        except Exception as e:
            self.logger.error(f"Backup error: {str(e)}")

    def dict_factory(self, cursor: sqlite3.Cursor, row: tuple) -> Dict:
        """Convert row to dictionary"""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def get_trades(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get trades with filtering
        
        Args:
            status: Filter by trade status
            symbol: Filter by trading pair
            limit: Maximum number of records
            offset: Number of records to skip
        """
        try:
            self.conn.row_factory = self.dict_factory
            cursor = self.conn.cursor()
            
            query = "SELECT * FROM trades"
            params = []
            conditions = []
            
            if status:
                conditions.append("status = ?")
                params.append(status)
                
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += """ 
                ORDER BY 
                    CASE status
                        WHEN 'OPEN' THEN 1
                        WHEN 'CLOSED' THEN 2
                        ELSE 3
                    END,
                    open_time DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
        except Exception as e:
            self.logger.error(f"Error getting trades: {str(e)}")
            return []

    def add_trade(self, trade_data: Dict) -> Optional[int]:
        """
        Add new trade
        
        Args:
            trade_data: Dictionary containing trade information
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO trades (
                    symbol, type, entry_price, take_profit,
                    stop_loss, quantity, status, reason,
                    open_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data['symbol'],
                trade_data['type'],
                trade_data['entry_price'],
                trade_data['take_profit'],
                trade_data['stop_loss'],
                trade_data['quantity'],
                trade_data.get('status', 'OPEN'),
                trade_data.get('reason', ''),
                datetime.utcnow()
            ))
            
            self.conn.commit()
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Error adding trade: {str(e)}")
            return None

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        reason: str
    ) -> Optional[Dict]:
        """
        Close existing trade
        
        Args:
            trade_id: ID of trade to close
            exit_price: Exit price
            reason: Close reason
        """
        try:
            cursor = self.conn.cursor()
            
            # Get trade details first
            cursor.execute(
                "SELECT * FROM trades WHERE id = ?",
                (trade_id,)
            )
            trade = cursor.fetchone()
            
            if not trade:
                self.logger.error(f"Trade {trade_id} not found")
                return None
                
            # Calculate profit
            quantity = trade['quantity']
            entry_price = trade['entry_price']
            trade_type = trade['type']
            
            profit = (
                (exit_price - entry_price) * quantity
                if trade_type == 'LONG'
                else (entry_price - exit_price) * quantity
            )
            
            # Update trade
            cursor.execute("""
                UPDATE trades SET
                    status = 'CLOSED',
                    exit_price = ?,
                    profit = ?,
                    close_time = ?,
                    reason = ?
                WHERE id = ?
            """, (
                exit_price,
                profit,
                datetime.utcnow(),
                reason,
                trade_id
            ))
            
            self.conn.commit()
            
            # Update statistics
            self.update_statistics()
            
            # Return updated trade
            cursor.execute(
                "SELECT * FROM trades WHERE id = ?",
                (trade_id,)
            )
            return cursor.fetchone()
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {str(e)}")
            return None

    def cancel_trade(
        self,
        trade_id: int,
        reason: str
    ) -> bool:
        """
        Cancel open trade
        
        Args:
            trade_id: ID of trade to cancel
            reason: Cancel reason
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                UPDATE trades SET
                    status = 'CANCELLED',
                    close_time = ?,
                    reason = ?
                WHERE id = ? AND status = 'OPEN'
            """, (
                datetime.utcnow(),
                reason,
                trade_id
            ))
            
            self.conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"Error cancelling trade: {str(e)}")
            return False

    def add_signal(self, signal_data: Dict) -> Optional[int]:
        """
        Add new trading signal
        
        Args:
            signal_data: Dictionary containing signal information
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO signals (
                    symbol, type, entry_price, take_profit,
                    stop_loss, confidence, rsi, volume_ratio,
                    reason, time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data['symbol'],
                signal_data['type'],
                signal_data['entry_price'],
                signal_data['take_profit'],
                signal_data['stop_loss'],
                signal_data['confidence'],
                signal_data.get('rsi'),
                signal_data.get('volume_ratio'),
                signal_data.get('reason', ''),
                datetime.utcnow()
            ))
            
            self.conn.commit()
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Error adding signal: {str(e)}")
            return None

    def get_signals(
        self,
        processed: Optional[bool] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get trading signals
        
        Args:
            processed: Filter by processed status
            symbol: Filter by trading pair
            limit: Maximum number of records
        """
        try:
            self.conn.row_factory = self.dict_factory
            cursor = self.conn.cursor()
            
            query = "SELECT * FROM signals"
            params = []
            conditions = []
            
            if processed is not None:
                conditions.append("processed = ?")
                params.append(processed)
                
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY time DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
        except Exception as e:
            self.logger.error(f"Error getting signals: {str(e)}")
            return []

    def mark_signal_processed(
        self,
        signal_id: int,
        trade_id: Optional[int] = None
    ) -> bool:
        """
        Mark signal as processed
        
        Args:
            signal_id: ID of signal to mark
            trade_id: Optional ID of trade created from signal
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                UPDATE signals SET
                    processed = TRUE,
                    trade_id = ?
                WHERE id = ?
            """, (trade_id, signal_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking signal: {str(e)}")
            return False

    def update_statistics(self) -> Optional[Dict]:
        """Update and return trading statistics"""
        try:
            cursor = self.conn.cursor()
            
            # Get trade stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN profit > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN profit < 0 THEN 1 END) as losing_trades,
                    COALESCE(SUM(profit), 0) as total_profit,
                    AVG(CASE WHEN profit > 0 THEN profit END) as avg_win,
                    AVG(CASE WHEN profit < 0 THEN profit END) as avg_loss,
                    MIN(
                        CASE 
                            WHEN type = 'LONG' 
                            THEN (exit_price - entry_price) / entry_price * 100
                            ELSE (entry_price - exit_price) / entry_price * 100
                        END
                    ) as max_drawdown
                FROM trades
                WHERE status = 'CLOSED'
            """)
            
            stats = cursor.fetchone()
            
            if not stats:
                return None
                
            # Calculate win rate
            total = stats['total_trades']
            wins = stats['winning_trades']
            win_rate = (wins / total * 100) if total > 0 else 0
            
            # Update statistics
            cursor.execute("""
                UPDATE statistics SET
                    total_trades = ?,
                    winning_trades = ?,
                    losing_trades = ?,
                    total_profit = ?,
                    win_rate = ?,
                    avg_profit = ?,
                    max_drawdown = ?,
                    updated_at = ?
                WHERE id = 1
            """, (
                stats['total_trades'],
                stats['winning_trades'],
                stats['losing_trades'],
                stats['total_profit'],
                win_rate,
                (stats['avg_win'] or 0),
                (stats['max_drawdown'] or 0),
                datetime.utcnow()
            ))
            
            self.conn.commit()
            
            # Return updated stats
            cursor.execute("SELECT * FROM statistics WHERE id = 1")
            return cursor.fetchone()
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {str(e)}")
            return None

    def get_trading_pairs(
        self,
        enabled: Optional[bool] = None
    ) -> List[Dict]:
        """
        Get trading pairs
        
        Args:
            enabled: Filter by enabled status
        """
        try:
            self.conn.row_factory = self.dict_factory
            cursor = self.conn.cursor()
            
            query = """
                SELECT p.*, COUNT(t.id) as open_trades
                FROM pairs p
                LEFT JOIN trades t ON 
                    t.symbol = p.symbol AND 
                    t.status = 'OPEN'
            """
            
            if enabled is not None:
                query += " WHERE p.enabled = ?"
                params = (enabled,)
            else:
                params = ()
                
            query += " GROUP BY p.symbol ORDER BY p.volume_24h DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
        except Exception as e:
            self.logger.error(f"Error getting pairs: {str(e)}")
            return []

    def update_pair(self, pair_data: Dict) -> bool:
        """
        Update trading pair information
        
        Args:
            pair_data: Dictionary containing pair information
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO pairs (
                    symbol, base_asset, quote_asset,
                    min_price, min_qty, min_notional,
                    price_precision, qty_precision,
                    enabled, last_price, volume_24h,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pair_data['symbol'],
                pair_data['base_asset'],
                pair_data['quote_asset'],
                pair_data['min_price'],
                pair_data['min_qty'],
                pair_data['min_notional'],
                pair_data['price_precision'],
                pair_data['qty_precision'],
                pair_data.get('enabled', True),
                pair_data.get('last_price'),
                pair_data.get('volume_24h'),
                datetime.utcnow()
            ))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error updating pair: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating pair: {str(e)}")
            return False

    def vacuum_database(self) -> bool:
        """Vacuum database to optimize storage"""
        try:
            self.conn.execute("VACUUM")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database vacuum error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error during vacuum: {str(e)}")
            return False

    def close(self):
        """Close database connection"""
        try:
            if self.conn:
                self.conn.close()
                self.conn = None
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error during close: {str(e)}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
def main():
    """Test database manager"""
    try:
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s UTC | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logger = logging.getLogger("DatabaseTest")
        
        # Initialize database
        db_path = "trading_test.db"
        schema_path = "schema.sql"
        
        with DatabaseManager(db_path, schema_path, logger) as db:
            # Test adding trade
            trade = {
                'symbol': 'BTCUSDT',
                'type': 'LONG',
                'entry_price': 50000.0,
                'take_profit': 51000.0,
                'stop_loss': 49000.0,
                'quantity': 0.1,
                'reason': 'Test trade'
            }
            
            trade_id = db.add_trade(trade)
            logger.info(f"Added trade with ID: {trade_id}")
            
            # Test getting trades
            trades = db.get_trades(status='OPEN')
            logger.info(f"Found {len(trades)} open trades")
            
            # Test closing trade
            if trade_id:
                closed = db.close_trade(
                    trade_id,
                    exit_price=50500.0,
                    reason='Test close'
                )
                logger.info(f"Closed trade: {closed}")
                
            # Test statistics
            stats = db.update_statistics()
            logger.info(f"Updated statistics: {stats}")
            
    except FileNotFoundError:
        logger.error("Schema file not found")
    except sqlite3.Error as e:
        logger.error(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    main()