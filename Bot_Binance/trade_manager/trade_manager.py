"""
Trade Manager Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:19:07 UTC
"""

import os
import sys
import yaml
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from binance.client import Client

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from trade_manager.order_manager import OrderManager
from trade_manager.gui_manager import GUIManager
from shared.websocket_client import WebSocketClient
from shared.constants import MessageType, ClientType, SignalType

class TradeManager:
    def __init__(self):
        """Initialize Trade Manager"""
        self.client = None
        self.logger = logging.getLogger('TradeManager')
        self.telegram = None
        self._is_running = False
        self.orders = []
        self.trades = []
        self.start_time = None
        
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable string"""
        try:
            if not seconds:
                return "0 seconds"
                
            duration = timedelta(seconds=int(seconds))
            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            seconds = duration.seconds % 60
            
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0 or not parts:
                parts.append(f"{seconds}s")
                
            return " ".join(parts)
            
        except Exception:
            return "unknown duration"

    async def initialize(self, client: Client) -> bool:
        """Initialize Trade Manager with Binance client"""
        try:
            self.start_time = datetime.utcnow()
            self.client = client

            if not self.client:
                self.logger.error("No Binance client provided")
                return False

            # Test API connection
            try:
                account = self.client.get_account()
                self.logger.info("Trade Manager initialized successfully")
                return True
            except Exception as e:
                self.logger.error(f"Failed to connect to Binance: {str(e)}")
                return False

        except Exception as e:
            self.logger.error(f"Trade Manager initialization error: {str(e)}")
            return False

    async def stop(self):
        """Stop Trade Manager"""
        try:
            self._is_running = False
            
            if self.start_time:
                runtime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
                runtime_str = self._format_duration(runtime_seconds)
            else:
                runtime_str = "unknown duration"
                
            self.logger.info(f"Trade Manager stopped after running for {runtime_str}")
            
            if self.telegram:
                await self.telegram.send_message(
                    "🛑 Trade Manager Stopping\n\n"
                    f"Runtime: {runtime_str}\n"
                    f"Total Orders: {len(self.orders)}\n"
                    f"Total Trades: {len(self.trades)}"
                )
        except Exception as e:
            self.logger.error(f"Error stopping Trade Manager: {str(e)}") 

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        try:
            # Create logs directory
            logs_dir = os.path.join(PROJECT_ROOT, 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            
            # Log filename
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
            
            # Log startup
            logger.info("="*50)
            logger.info("Trade Manager - Starting Up")
            logger.info(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
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
            config_path = os.path.join(PROJECT_ROOT, 'config/config.yaml')
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return {}

    def _calculate_statistics(self) -> Dict:
        """Calculate trading statistics"""
        try:
            total_trades = len(self.trade_history)
            if total_trades == 0:
                return {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'total_profit': 0.0,
                    'avg_profit': 0.0
                }
                
            winning_trades = len([
                t for t in self.trade_history
                if t['profit'] > 0
            ])
            
            total_profit = sum(
                t['profit'] for t in self.trade_history
            )
            
            return {
                'total_trades': total_trades,
                'win_rate': (winning_trades / total_trades) * 100,
                'total_profit': total_profit,
                'avg_profit': total_profit / total_trades
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating stats: {str(e)}")
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
                logger=self.logger,
                message_handler=self._handle_message
            )
            
            # Connect and register
            if await self.ws_client.connect():
                await self.ws_client.send_message({
                    'type': MessageType.REGISTER.value,
                    'client_type': ClientType.TRADE_MANAGER.value
                })
                
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"WebSocket setup error: {str(e)}")
            return False

    async def _handle_message(self, message: Dict):
        """Handle incoming WebSocket messages"""
        try:
            msg_type = message.get('type')
            
            if msg_type == MessageType.SIGNAL.value:
                await self._handle_signal(message['data'])
                
            elif msg_type == MessageType.ORDER_UPDATE.value:
                await self._handle_order_update(message['data'])
                
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")

    async def _handle_signal(self, signal: Dict):
        """Handle incoming trading signal"""
        try:
            symbol = signal['symbol']
            
            # Check if already trading this pair
            if symbol in self.open_trades:
                self.logger.info(
                    f"Already trading {symbol}, ignoring signal"
                )
                return
                
            # Check max trades limit
            if len(self.open_trades) >= self.config['trading']['max_trades']:
                self.logger.info("Max trades limit reached")
                return
                
            # Store signal
            self.active_signals[symbol] = signal
            
            # Update GUI
            if self.gui_manager:
                self.gui_manager.add_update(
                    'signals',
                    list(self.active_signals.values())
                )
                
            self.logger.info(f"New signal for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error handling signal: {str(e)}")

    async def _handle_order_update(self, update: Dict):
        """Handle order status update"""
        try:
            symbol = update['symbol']
            order_id = update['orderId']
            status = update['status']
            
            # Get trade info
            trade = self.open_trades.get(symbol)
            if not trade:
                return
                
            if status == 'FILLED':
                # Calculate profit
                entry = float(trade['entry_price'])
                exit = float(update['price'])
                
                if trade['type'] == SignalType.LONG.value:
                    profit = (exit - entry) / entry * 100
                else:
                    profit = (entry - exit) / entry * 100
                    
                # Add to history
                self.trade_history.append({
                    'symbol': symbol,
                    'type': trade['type'],
                    'entry': entry,
                    'exit': exit,
                    'profit': profit,
                    'time': int(datetime.utcnow().timestamp() * 1000)
                })
                
                # Remove from open trades
                del self.open_trades[symbol]
                
                # Log trade
                self.logger.info(
                    f"Closed {symbol} trade with {profit:.2f}% profit"
                )
                
            # Update GUI
            if self.gui_manager:
                self.gui_manager.add_update(
                    'trades',
                    list(self.open_trades.values())
                )
                
                stats = self._calculate_statistics()
                self.gui_manager.add_update('stats', stats)
                
        except Exception as e:
            self.logger.error(f"Error handling order update: {str(e)}")

    async def open_trade(self, signal: Dict) -> bool:
        """Open new trade from signal"""
        try:
            symbol = signal['symbol']
            
            # Create orders
            order = await self.order_manager.create_order(
                symbol=symbol,
                side=signal['type'],
                quantity=self.config['trading']['order_size'],
                price=signal['entry_price'],
                stop_loss=signal['stop_loss'],
                take_profit=signal['take_profit']
            )
            
            if not order:
                return False
                
            # Store trade
            self.open_trades[symbol] = {
                'symbol': symbol,
                'type': signal['type'],
                'entry_price': signal['entry_price'],
                'take_profit': signal['take_profit'],
                'stop_loss': signal['stop_loss'],
                'order': order,
                'signal': signal,
                'time': int(datetime.utcnow().timestamp() * 1000)
            }
            
            # Remove signal
            if symbol in self.active_signals:
                del self.active_signals[symbol]
                
            # Update GUI
            if self.gui_manager:
                self.gui_manager.add_update(
                    'signals',
                    list(self.active_signals.values())
                )
                self.gui_manager.add_update(
                    'trades',
                    list(self.open_trades.values())
                )
                
            self.logger.info(f"Opened trade for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error opening trade: {str(e)}")
            return False

    async def close_trade(
        self,
        symbol: str,
        reason: str = "Manual"
    ) -> bool:
        """Close existing trade"""
        try:
            # Get trade info
            trade = self.open_trades.get(symbol)
            if not trade:
                return False
                
            # Close position
            result = await self.order_manager.close_position(
                symbol,
                trade['order']['orderId']
            )
            
            if not result:
                return False
                
            self.logger.info(
                f"Closed {symbol} trade - {reason}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {str(e)}")
            return False

    async def run(self):
        """Run trade manager"""
        try:
            # Initialize
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return
                
            self.logger.info("[+] Trade Manager started")
            
            # Start GUI
            if self.gui_manager:
                self.gui_manager.start()
                
            # Keep running
            while self._is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Trade Manager stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            await self.stop()


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