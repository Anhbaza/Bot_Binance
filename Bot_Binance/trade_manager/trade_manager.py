"""
Trade Manager Bot
Main bot implementation for managing trades
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:35:10
"""

import os
import sys
import yaml
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException

from .order_manager import OrderManager
from .gui_manager import GUIManager
from ..shared.websocket_client import WebSocketClient
from ..database.db_manager import DatabaseManager
from ..shared.constants import (
    SignalType,
    MessageType,
    ClientType,
    OrderStatus,
    TradingConfig as Config
)

class TradeManager:
    def __init__(self):
        self.user = os.getenv('USER', 'Anhbaza01')
        self.logger = self._setup_logging()
        self._is_running = True
        
        # Components
        self.client = None
        self.order_manager = None
        self.gui_manager = None
        self.ws_client = None
        self.db = None
        
        # Load config
        self.config = self._load_config()
        
        # Trading state
        self.active_signals = {}
        self.open_trades = {}
        self.watched_pairs = set()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        try:
            # Create logs directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logs_dir = os.path.join(current_dir, '../logs')
            os.makedirs(logs_dir, exist_ok=True)
            
            # Log filename with timestamp
            log_filename = os.path.join(
                logs_dir,
                f'trade_manager_{datetime.utcnow().strftime("%Y%m%d")}.log'
            )
            
            # Configure logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s UTC | %(levelname)s | %(message)s',
                handlers=[
                    logging.FileHandler(log_filename),
                    logging.StreamHandler(sys.stdout)
                ],
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            logger = logging.getLogger("TradeManager")
            
            # Log startup info
            logger.info("="*50)
            logger.info("Trade Manager Bot - Logging Initialized")
            logger.info(f"Log File: {log_filename}")
            logger.info(f"Current Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"User: {self.user}")
            logger.info("="*50)
            
            return logger
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("TradeManager")

    def _load_config(self) -> Dict:
        """Load configuration from file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '../config/config.yaml'
            )
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return {}

    async def setup_binance(self) -> bool:
        """Setup Binance API client"""
        try:
            self.logger.info("Setting up Binance client...")
            
            # Get API credentials
            api_key = self.config['binance'].get('api_key', '')
            api_secret = self.config['binance'].get('api_secret', '')
            testnet = self.config['binance'].get('testnet', True)
            
            # Initialize client
            self.client = Client(
                api_key,
                api_secret,
                testnet=testnet
            )
            
            # Test connection
            server_time = self.client.get_server_time()
            if not server_time:
                raise ConnectionError("Could not get server time")
                
            self.logger.info("Binance client setup successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Binance setup error: {str(e)}")
            return False

    async def setup_database(self) -> bool:
        """Setup database connection"""
        try:
            self.logger.info("Setting up database...")
            
            # Get paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(
                current_dir,
                '../database/trading.db'
            )
            schema_path = os.path.join(
                current_dir,
                '../database/schema.sql'
            )
            
            # Initialize database
            self.db = DatabaseManager(
                db_path,
                schema_path,
                self.logger
            )
            
            self.logger.info("Database setup successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Database setup error: {str(e)}")
            return False

    async def setup_websocket(self) -> bool:
        """Setup WebSocket client"""
        try:
            # Get WebSocket config
            ws_config = self.config['websocket']
            
            # Initialize client
            self.ws_client = WebSocketClient(
                name="TradeManager",
                host=ws_config['host'],
                port=ws_config['port'],
                logger=self.logger
            )
            
            # Connect and register
            if await self.ws_client.connect():
                await self.ws_client.send_message({
                    'type': MessageType.REGISTER.value,
                    'client_type': ClientType.TRADE_BOT.value
                })
                
                # Register message handlers
                self.ws_client.register_handler(
                    MessageType.SIGNAL.value,
                    self.handle_signal
                )
                
                asyncio.create_task(self.ws_client.listen())
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"WebSocket setup error: {str(e)}")
            return False

    async def handle_signal(self, signal: Dict):
        """Handle incoming trading signal"""
        try:
            symbol = signal['symbol']
            signal_type = signal['type']
            
            self.logger.info(
                f"Received {signal_type} signal for {symbol}"
            )
            
            # Check if we can trade
            if len(self.open_trades) >= Config.MAX_TRADES:
                self.logger.warning("Maximum trades reached")
                return
                
            if symbol in self.open_trades:
                self.logger.warning(f"Already trading {symbol}")
                return
                
            # Store signal
            signal_id = f"{symbol}_{signal['time']}"
            self.active_signals[signal_id] = signal
            
            # Update GUI
            if self.gui_manager:
                self.gui_manager.update_signals(
                    list(self.active_signals.values())
                )
                
            # Add to database
            await self.db.add_signal(signal)
            
        except Exception as e:
            self.logger.error(f"Error handling signal: {str(e)}")

    async def open_trade(self, signal: Dict) -> bool:
        """Open new trade from signal"""
        try:
            symbol = signal['symbol']
            
            # Create order
            order = await self.order_manager.create_order(
                symbol=symbol,
                side=signal['type'],
                quantity=Config.ORDER_SIZE,
                price=signal['entry_price'],
                stop_loss=signal['stop_loss'],
                take_profit=signal['take_profit']
            )
            
            if not order:
                return False
                
            # Add to database
            trade_id = await self.db.add_trade({
                'symbol': symbol,
                'type': signal['type'],
                'entry_price': signal['entry_price'],
                'take_profit': signal['take_profit'],
                'stop_loss': signal['stop_loss'],
                'quantity': Config.ORDER_SIZE,
                'reason': signal.get('reason', '')
            })
            
            if not trade_id:
                # Cancel order if database fails
                await self.order_manager.cancel_order(
                    symbol,
                    order['orderId']
                )
                return False
                
            # Store trade
            self.open_trades[symbol] = {
                'id': trade_id,
                'order': order,
                'signal': signal
            }
            
            # Update GUI
            if self.gui_manager:
                self.gui_manager.update_trades(
                    list(self.open_trades.values())
                )
                
            self.logger.info(
                f"Opened {signal['type']} trade for {symbol}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error opening trade: {str(e)}")
            return False

    async def close_trade(
        self,
        symbol: str,
        reason: str
    ) -> bool:
        """Close existing trade"""
        try:
            if symbol not in self.open_trades:
                self.logger.warning(f"No open trade for {symbol}")
                return False
                
            trade = self.open_trades[symbol]
            
            # Close position
            result = await self.order_manager.close_position(
                symbol,
                trade['order']['orderId']
            )
            
            if not result:
                return False
                
            # Update database
            updated = await self.db.close_trade(
                trade['id'],
                result['price'],
                reason
            )
            
            if not updated:
                return False
                
            # Remove trade
            del self.open_trades[symbol]
            
            # Update GUI
            if self.gui_manager:
                self.gui_manager.update_trades(
                    list(self.open_trades.values())
                )
                
            self.logger.info(f"Closed trade for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {str(e)}")
            return False

    async def check_trades(self):
        """Check and update open trades"""
        try:
            for symbol, trade in self.open_trades.items():
                # Get current price
                ticker = await self.order_manager.get_ticker(symbol)
                if not ticker:
                    continue
                    
                price = float(ticker['price'])
                
                # Check stop loss and take profit
                entry = trade['signal']['entry_price']
                sl = trade['signal']['stop_loss']
                tp = trade['signal']['take_profit']
                
                if trade['signal']['type'] == SignalType.LONG.value:
                    if price <= sl:
                        await self.close_trade(symbol, "Stop loss")
                    elif price >= tp:
                        await self.close_trade(symbol, "Take profit")
                else:
                    if price >= sl:
                        await self.close_trade(symbol, "Stop loss")
                    elif price <= tp:
                        await self.close_trade(symbol, "Take profit")
                        
        except Exception as e:
            self.logger.error(f"Error checking trades: {str(e)}")

    async def initialize(self) -> bool:
        """Initialize Trade Manager"""
        try:
            # Setup components
            if not all([
                await self.setup_binance(),
                await self.setup_database(),
                await self.setup_websocket()
            ]):
                return False
                
            # Initialize order manager
            self.order_manager = OrderManager(
                self.client,
                self.logger
            )
            
            # Initialize GUI
            self.gui_manager = GUIManager(self)
            
            # Load existing trades
            trades = await self.db.get_trades(status='OPEN')
            for trade in trades:
                self.open_trades[trade['symbol']] = {
                    'id': trade['id'],
                    'order': {
                        'orderId': trade.get('order_id'),
                        'status': trade['status']
                    },
                    'signal': {
                        'symbol': trade['symbol'],
                        'type': trade['type'],
                        'entry_price': trade['entry_price'],
                        'take_profit': trade['take_profit'],
                        'stop_loss': trade['stop_loss']
                    }
                }
                
            self.logger.info("Trade Manager initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Main bot loop"""
        try:
            # Initialize
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return
                
            self.logger.info("[+] Trade Manager started")
            
            # Start GUI
            if self.gui_manager:
                self.gui_manager.start()
                
            # Main loop
            while self._is_running:
                try:
                    # Check trades every second
                    await self.check_trades()
                    
                    # Update database statistics
                    await self.db.update_statistics()
                    
                    # Wait for next iteration
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(5)
                    
        except KeyboardInterrupt:
            self.logger.info("Trade Manager stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            # Cleanup
            self._is_running = False
            
            if self.ws_client:
                await self.ws_client.stop()
                
            if self.gui_manager:
                self.gui_manager.stop()
                
            if self.db:
                self.db.close()
                
            self.logger.info("Trade Manager stopped")

def main():
    """Main function"""
    try:
        # Create Trade Manager
        manager = TradeManager()
        
        # Set Windows event loop policy if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )
            
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run manager
        loop.run_until_complete(manager.run())
        
    except KeyboardInterrupt:
        print("\nTrade Manager stopped by user")
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
    finally:
        try:
            loop = asyncio.get_event_loop()
            
            # Cancel pending tasks
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if tasks:
                loop.run_until_complete(
                    asyncio.gather(*tasks, return_exceptions=True)
                )
                
            # Close loop
            loop.close()
            
        except Exception as e:
            print(f"\nError during shutdown: {str(e)}")

if __name__ == "__main__":
    main()
