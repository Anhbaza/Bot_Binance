"""
Binance Trading Bot Simulation
A cryptocurrency trading bot simulation that doesn't require real Binance API credentials.

Features:
- Mock trading with virtual balance
- Real-time price simulation
- Multiple trading strategies
- Risk management
- Performance tracking
- GUI monitoring interface

Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 13:07:17 UTC
"""
import os
import sys
# Thêm thư mục cha vào PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
from shared.pair_manager import PairManager
import asyncio
import logging
import yaml
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_DOWN
from signal_bot.signal_scanner import SignalScanner
# Rest of imports
from binance.client import Client
from signal_bot.signal_bot import SignalBot
from trade_manager.trade_manager import TradeManager
from shared.telegram_handler import TelegramHandler
from trade_manager.gui_manager import GUIManager
from shared.websocket_server import WebSocketServer
from shared.mock_binance import MockBinanceClient


class MockMarketData:
    """Simulates market data without real API"""
    
    def __init__(self):
        self.base_prices = {
            'BTCUSDT': 45000.0,
            'ETHUSDT': 3000.0,
            'BNBUSDT': 350.0,
            'ADAUSDT': 1.2,
            'DOGEUSDT': 0.15,
        }
        self.last_update = datetime.utcnow()
        
    def get_current_price(self, symbol: str) -> float:
        """Simulate real-time price movement"""
        base = self.base_prices.get(symbol, 100.0)
        volatility = base * 0.002  # 0.2% volatility
        change = random.uniform(-volatility, volatility)
        return round(base + change, 8)
        
    def get_all_prices(self) -> Dict[str, float]:
        """Get all simulated prices"""
        return {
            symbol: self.get_current_price(symbol)
            for symbol in self.base_prices
        }

class MockBinanceClient:
    """Mock Binance client for simulation"""
    
    def __init__(self):
        self.market_data = MockMarketData()
        self.balances = {
            'USDT': 10000.0,  # Initial balance
            'BTC': 0.0,
            'ETH': 0.0,
            'BNB': 0.0,
            'ADA': 0.0,
            'DOGE': 0.0
        }
        
    def get_server_time(self) -> Dict:
        """Mock server time"""
        return {'serverTime': int(datetime.utcnow().timestamp() * 1000)}
        
    def get_account(self) -> Dict:
        """Mock account information"""
        return {
            'makerCommission': 10,
            'takerCommission': 10,
            'buyerCommission': 0,
            'sellerCommission': 0,
            'canTrade': True,
            'canWithdraw': True,
            'canDeposit': True,
            'updateTime': int(datetime.utcnow().timestamp() * 1000),
            'balances': [
                {'asset': k, 'free': str(v), 'locked': '0.0'}
                for k, v in self.balances.items()
            ]
        }
        
    def get_symbol_info(self, symbol: str) -> Dict:
        """Mock symbol information"""
        return {
            'symbol': symbol,
            'status': 'TRADING',
            'baseAsset': symbol.replace('USDT', ''),
            'quoteAsset': 'USDT',
            'filters': [
                {
                    'filterType': 'PRICE_FILTER',
                    'minPrice': '0.00000100',
                    'maxPrice': '1000000.00000000',
                    'tickSize': '0.00000100'
                },
                {
                    'filterType': 'LOT_SIZE',
                    'minQty': '0.00000100',
                    'maxQty': '9000000.00000000',
                    'stepSize': '0.00000100'
                }
            ]
        }
        
    def get_price(self, symbol: str) -> float:
        """Get simulated price for symbol"""
        return self.market_data.get_current_price(symbol)
        
    def get_all_prices(self) -> List[Dict]:
        """Get all simulated prices"""
        prices = self.market_data.get_all_prices()
        return [
            {'symbol': symbol, 'price': str(price)}
            for symbol, price in prices.items()
        ]

class BotManager:
    """Main bot manager class"""
    
    def __init__(self):
        """Initialize Bot Manager"""
        self.config: Dict = {}
        self.logger = self._setup_logging()
        self.client = MockBinanceClient()
        self.pair_manager = PairManager()
        self.telegram = None
        self.signal_bot = None
        self.trade_manager = None
        self.gui_manager = None
        self._is_running = False
        self.start_time = datetime.utcnow()


    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        try:
            # Create logs directory
            logs_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'logs'
            )
            os.makedirs(logs_dir, exist_ok=True)

            # Create log filename with current date
            log_file = os.path.join(
                logs_dir,
                f'bot_{datetime.utcnow().strftime("%Y%m%d")}.log'
            )

            # Configure logger
            logger = logging.getLogger('BotManager')
            logger.setLevel(logging.INFO)

            # File handler with UTF-8 encoding
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(logging.INFO)

            # Console handler
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s UTC | %(levelname)s | %(message)s',
                '%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            # Clear existing handlers
            logger.handlers.clear()

            # Add handlers
            logger.addHandler(fh)
            logger.addHandler(ch)

            return logger

        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            return logging.getLogger('BotManager')

    def _load_config(self) -> bool:
        """Load configuration from YAML file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'config.yaml'
            )
            
            if not os.path.exists(config_path):
                self.logger.error(f"Config file not found: {config_path}")
                return False

            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            # Validate configuration
            required_fields = [
                'min_volume', 'min_confidence', 'timeframes',
                'order_size', 'max_orders', 'risk_per_trade'
            ]
            
            for field in required_fields:
                if field not in self.config:
                    self.logger.error(f"Missing required config field: {field}")
                    return False

            # Log configuration
            self.logger.info("Configuration loaded:")
            self.logger.info(f"- Min Volume: ${self.config['min_volume']:,}")
            self.logger.info(f"- Min Confidence: {self.config['min_confidence']}%")
            self.logger.info(f"- Timeframes: {', '.join(self.config['timeframes'])}")
            self.logger.info(f"- Order Size: ${self.config['order_size']:,}")
            self.logger.info(f"- Max Orders: {self.config['max_orders']}")
            self.logger.info(f"- Risk Per Trade: {self.config['risk_per_trade']}%")

            return True

        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return False

    async def _update_market_data(self):
        """Update simulated market data periodically"""
        while self._is_running:
            try:
                now = datetime.utcnow()
                if (now - self.last_price_update).total_seconds() >= self.price_update_interval:
                    prices = self.market_data.get_all_prices()
                    if self.trade_manager:
                        await self.trade_manager.update_prices(prices)
                    self.last_price_update = now
                await asyncio.sleep(0.1)  # Small delay to prevent CPU overload
            except Exception as e:
                self.logger.error(f"Error updating market data: {str(e)}")
                await asyncio.sleep(1)

    async def initialize(self) -> bool:
        """Initialize all bot components"""
        try:
            self.start_time = datetime.utcnow()
            
            # Load configuration
            if not self._load_config():
                return False

            # Test mock connection
            try:
                server_time = self.client.get_server_time()
                self.logger.info(
                    f"Connected to Mock Binance API "
                    f"(Server Time: {datetime.fromtimestamp(server_time['serverTime']/1000)})"
                )
            except Exception as e:
                self.logger.error(f"Failed to connect to Mock API: {str(e)}")
                return False

            # Initialize components
            try:
                # Import required modules
                from signal_bot.signal_bot import SignalBot
                from trade_manager.trade_manager import TradeManager
                from trade_manager.gui_manager import GUIManager

                 # Initialize Signal Bot với pair_manager
                self.signal_bot = SignalBot(
                    client=self.client,
                    logger=self.logger,
                    pair_manager=self.pair_manager
                )
                if not await self.signal_bot.initialize():
                    self.logger.error("Failed to initialize SignalBot")
                    return False
                self.logger.info("Signal Bot initialized successfully")

                # Initialize TradeManager với pair_manager
                self.trade_manager = TradeManager(
                    client=self.client,
                    logger=self.logger,
                    pair_manager=self.pair_manager
                )
                if not await self.trade_manager.initialize():
                    self.logger.error("Failed to initialize TradeManager")
                    return False
                self.logger.info("Trade Manager initialized successfully")


                # Initialize GUI if enabled
                if self.config.get('gui_enabled', True):
                    self.gui_manager = GUIManager(self.trade_manager)
                    self.gui_manager.start()
                    self.logger.info("GUI started successfully")

                return True

            except ImportError as e:
                self.logger.error(f"Failed to import required modules: {str(e)}")
                return False
            except Exception as e:
                self.logger.error(f"Error initializing components: {str(e)}")
                return False

        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Run the bot manager"""
        try:
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return

            self._is_running = True
            self.logger.info("Bot Manager started successfully")

            # Start market data updates
            market_update_task = asyncio.create_task(self._update_market_data())

            # Main loop
            while self._is_running:
                try:
                    # Update GUI status
                    if self.gui_manager:
                        runtime = datetime.utcnow() - self.start_time
                        self.gui_manager.update_status(
                            "Running", 
                            str(runtime).split('.')[0]
                        )

                    await asyncio.sleep(1)

                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            # Clean up
            self._is_running = False
            try:
                market_update_task.cancel()
                await market_update_task
            except:
                pass
            await self.stop()

    async def stop(self):
        """Stop all bot components"""
        try:
            self._is_running = False
            
            # Stop components in reverse order
            if self.gui_manager:
                self.gui_manager.stop()
                self.logger.info("GUI stopped")
                
            if self.trade_manager:
                await self.trade_manager.stop()
                self.logger.info("Trade Manager stopped")
                
            if self.signal_bot:
                await self.signal_bot.stop()
                self.logger.info("Signal Bot stopped")

            # Calculate runtime
            runtime = datetime.utcnow() - self.start_time
            runtime_str = str(runtime).split('.')[0]
            
            self.logger.info(f"Bot Manager stopped after running for {runtime_str}")
                
        except Exception as e:
            self.logger.error(f"Error stopping manager: {str(e)}")

def run_app():
    """Application entry point"""
    try:
        # Print startup banner
        print("\n" + "="*50)
        print("Trading Bot Starting Up")
        print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"User: {os.getenv('USER', 'Anhbaza01')}")
        print("="*50 + "\n")

        # Create and configure event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create and run bot manager
        manager = BotManager()
        
        try:
            loop.run_until_complete(manager.run())
        except KeyboardInterrupt:
            print("\nStopping bot...")
            loop.run_until_complete(manager.stop())
        finally:
            loop.close()
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(run_app())