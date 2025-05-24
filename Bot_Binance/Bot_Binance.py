"""
Bot Binance Implementation
Author: Anhbaza01
Version: 1.0.0
"""

import os
import sys
import asyncio
import logging
import yaml
from datetime import datetime, timedelta
from binance.client import Client
from signal_bot.signal_bot import SignalBot
from trade_manager.trade_manager import TradeManager
from shared.telegram_handler import TelegramHandler
from trade_manager.gui_manager import GUIManager
from shared.websocket_server import WebSocketServer

class BotManager:
    def __init__(self):
        """Initialize Bot Manager"""
        self.config = {}
        self.logger = self._setup_logging()
        self.client = None
        self.telegram = None
        self.signal_bot = None
        self.trade_manager = None
        self.ws_server = None
        self.gui_manager = None
        self._is_running = False
        self.start_time = datetime.utcnow()

    def _setup_logging(self):
        """Setup logging with UTF-8 encoding"""
        try:
            # Create logs directory
            logs_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'logs'
            )
            os.makedirs(logs_dir, exist_ok=True)

            # Log filename
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

            # Console handler with UTF-8 encoding
            if os.name == 'nt':
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
                
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)

            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s UTC | %(levelname)s | %(message)s',
                '%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            # Remove existing handlers
            logger.handlers = []

            # Add handlers
            logger.addHandler(fh)
            logger.addHandler(ch)

            return logger

        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            return logging.getLogger('BotManager')

    def _load_config(self):
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

            # Log config (excluding sensitive data)
            self.logger.info("Configuration loaded:")
            self.logger.info(f"- Telegram Bot: Configured")
            self.logger.info(f"- Telegram Chat ID: {self.config['telegram_chat_id']}")
            self.logger.info(f"- Min Volume: ${self.config.get('min_volume', 1000000):,}")
            self.logger.info(f"- Min Confidence: {self.config.get('min_confidence', 70)}%")
            self.logger.info(f"- Timeframes: {', '.join(self.config.get('timeframes', ['1m','5m','15m','1h','4h']))}")
            self.logger.info(f"- Order Size: ${self.config.get('order_size', 100):,}")
            self.logger.info(f"- Max Orders: {self.config.get('max_orders', 10)}")
            self.logger.info(f"- Risk Per Trade: {self.config.get('risk_per_trade', 1)}%")

            return True

        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return False

    def _validate_api_key(self, api_key: str) -> bool:
        """Validate Binance API key format"""
        if not api_key or len(api_key) != 64:
            return False
        if not api_key.isalnum():
            return False
        return True

    async def initialize(self):
        """Initialize Bot Manager"""
        try:
            self.start_time = datetime.utcnow()
            
            # Load config
            if not self._load_config():
                return False

            # Setup Telegram
            self.telegram = TelegramHandler(
                self.config['telegram_token'],
                self.config['telegram_chat_id']
            )

            # Test Telegram
            if not await self.telegram.send_message(
                "Bot Manager Starting\n\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"User: {os.getenv('USER', 'Anhbaza01')}\n"
                f"Mode: {'Test Mode' if self.config.get('test_mode', True) else 'Production'}"
            ):
                self.logger.error("Failed to send Telegram message")
                return False

            self.logger.info("Telegram notifications setup successful")

            # Setup Binance client if not in test mode
            if not self.config.get('test_mode', True):
                self.logger.info("Setting up Binance client...")
                try:
                    if not self._validate_api_key(self.config['api_key']):
                        self.logger.error("Invalid API key format")
                        return False
                        
                    self.client = Client(
                        self.config['api_key'],
                        self.config['api_secret'],
                        testnet=self.config.get('testnet', False)
                    )
                    
                    # Test API connection
                    server_time = self.client.get_server_time()
                    if not server_time:
                        raise Exception("Could not get server time")
                        
                    self.logger.info("Binance client setup successful")
                    
                except Exception as e:
                    self.logger.error(f"Failed to setup Binance client: {str(e)}")
                    return False

            # Initialize Signal Bot
            self.signal_bot = SignalBot()
            self.signal_bot.telegram = self.telegram
            if not await self.signal_bot.initialize(self.client):
                return False

            # Initialize Trade Manager if not in test mode
            if not self.config.get('test_mode', True):
                self.trade_manager = TradeManager()
                self.trade_manager.telegram = self.telegram
                if not await self.trade_manager.initialize(self.client):
                    return False

            # Initialize GUI Manager if enabled
            if self.config.get('gui_enabled', True):
                self.gui_manager = GUIManager()

            # Setup WebSocket server
            if self.config.get('ws_enabled', True):
                self.ws_server = WebSocketServer(
                    self.signal_bot,
                    self.trade_manager,
                    self.config.get('ws_host', 'localhost'),
                    self.config.get('ws_port', 8765)
                )

            return True

        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Run Bot Manager"""
        try:
            # Initialize components
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return

            # Start GUI in separate thread if enabled
            if self.gui_manager:
                self.gui_manager.start()

            # Start WebSocket server if enabled
            if self.ws_server:
                await self.ws_server.start()

            # Start Signal Bot
            self.logger.info("\nStarting Signal Bot...")
            signal_bot_task = asyncio.create_task(self.signal_bot.run())

            # Start Trade Manager if not in test mode
            trade_manager_task = None
            if self.trade_manager:
                self.logger.info("Starting Trade Manager...")
                trade_manager_task = asyncio.create_task(self.trade_manager.run())

            # Wait for completion
            tasks = [signal_bot_task]
            if trade_manager_task:
                tasks.append(trade_manager_task)
                
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            self.logger.info("Bot Manager stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            await self.stop()

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

    async def stop(self):
        """Stop Bot Manager"""
        try:
            self._is_running = False
            
            # Stop components
            if self.signal_bot:
                await self.signal_bot.stop()
                
            if self.trade_manager:
                await self.trade_manager.stop()
                
            if self.ws_server:
                await self.ws_server.stop()
                
            if self.gui_manager:
                self.gui_manager.stop()

            # Calculate runtime
            runtime = datetime.utcnow() - self.start_time
            runtime_str = self._format_duration(runtime.total_seconds())
            
            self.logger.info(f"Bot Manager stopped after running for {runtime_str}")
            
            if self.telegram:
                await self.telegram.send_message(
                    "Bot Manager Stopping\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"Runtime: {runtime_str}"
                )
                
        except Exception as e:
            self.logger.error(f"Error stopping manager: {str(e)}")

def start_bot():
    """Start the bot"""
    try:
        print("\n" + "="*50)
        print("Trading Bot Starting Up")
        print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"User: {os.getenv('USER', 'Anhbaza01')}")
        print("="*50 + "\n")

        # Initialize GUI
        print("Initializing GUI...")
        manager = BotManager()
        
        if manager.config.get('gui_enabled', True):
            print("Starting GUI...")
            manager.gui_manager = GUIManager()
            manager.gui_manager.start()

        # Start bot in background
        print("Starting bot in background...")
        print("Initializing bot systems...")
        
        async def run_bot():
            await manager.run()
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(run_bot())
        except KeyboardInterrupt:
            print("\nStopping bot...")
            loop.run_until_complete(manager.stop())
        finally:
            loop.close()
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    start_bot()