"""
Main Bot Manager
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:55:30 UTC
"""

import os
import sys
import yaml
import logging
import asyncio
import threading
from datetime import datetime
from binance.client import Client

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import components
from signal_bot.signal_bot import SignalBot
from trade_manager.trade_manager import TradeManager
from trade_manager.gui_manager import GUIManager 
from shared.websocket_server import WebSocketServer
from shared.telegram_handler import TelegramHandler
from shared.constants import Config

class BotManager:
    def __init__(self):
        self.user = os.getenv('USER', 'Anhbaza01')
        self.logger = self._setup_logging()
        self._is_running = True

        # Load config
        self.config = self._load_config()

        # Components
        self.ws_server = None
        self.signal_bot = None 
        self.trade_manager = None
        self.gui_manager = None
        self.telegram = None

    def _setup_logging(self):
     """Setup logging"""
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

        # Validate required fields
        required_fields = [
            'telegram_token',
            'telegram_chat_id',
            'api_key',
            'api_secret'
        ]

        for field in required_fields:
            if field not in self.config:
                self.logger.error(f"Missing required config field: {field}")
                return False

        # Log config (excluding sensitive data)
        self.logger.info("Configuration loaded:")
        self.logger.info(f"- Telegram Bot: Configured")
        self.logger.info(f"- Telegram Chat ID: {self.config['telegram_chat_id']}")
        self.logger.info(f"- Min Volume: ${self.config.get('min_volume', 1000000):,}")
        self.logger.info(f"- Min Confidence: {self.config.get('min_confidence', 70)}%")
        self.logger.info(f"- Timeframes: {', '.join(self.config.get('timeframes', ['1m','5m','15m','1h']))}")
        self.logger.info(f"- Order Size: ${self.config.get('order_size', 100):,}")
        self.logger.info(f"- Max Orders: {self.config.get('max_orders', 10)}")
        self.logger.info(f"- Risk Per Trade: {self.config.get('risk_per_trade', 1)}%")

        return True

     except Exception as e:
        self.logger.error(f"Error loading config: {str(e)}")
        return False

    async def setup_telegram(self) -> bool:
        """Setup Telegram notifications"""
        try:
            # Get Telegram config
            token = self.config['telegram']['token']
            chat_id = self.config['telegram']['chat_id']

            # Initialize handler
            self.telegram = TelegramHandler(
                token,
                chat_id,
                self.logger
            )

            # Test connection
            await self.telegram.send_message(
                "🤖 Trading Bot Started\n\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"User: {self.user}\n"
                f"Mode: {'Test' if self.config['binance']['testnet'] else 'Live'}"
            )

            self.logger.info("Telegram notifications setup successful")
            return True

        except Exception as e:
            self.logger.error(f"Telegram setup error: {str(e)}")
            return False

    async def setup_binance(self) -> Client:
        """Setup Binance API client"""
        try:
            self.logger.info("Setting up Binance client...")

            # Get API credentials
            api_key = self.config['binance']['api_key']
            api_secret = self.config['binance']['api_secret']
            testnet = self.config['binance']['testnet']

            # Initialize client
            client = Client(
                api_key,
                api_secret,
                testnet=testnet
            )

            # Test connection
            server_time = client.get_server_time()
            if not server_time:
                raise ConnectionError("Could not get server time")

            self.logger.info("Binance client setup successful")
            return client

        except Exception as e:
            self.logger.error(f"Binance setup error: {str(e)}")
            return None

    async def initialize(self):
     """Initialize Bot Manager"""
     try:
        self.logger.info("="*50)
        self.logger.info("Bot Manager - Starting Up")
        self.logger.info(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        self.logger.info(f"User: {os.getenv('USER', 'Anhbaza01')}")
        self.logger.info("="*50)

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
            "🤖 Trading Bot Starting\n\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"User: {os.getenv('USER', 'Anhbaza01')}"
        ):
            self.logger.error("Failed to send Telegram message")
            return False

        self.logger.info("Telegram notifications setup successful")

        # Setup Binance client
        self.logger.info("Setting up Binance client...")
        self.client = Client(
            self.config['api_key'],
            self.config['api_secret']
        )
        self.logger.info("Binance client setup successful")

        # Initialize Signal Bot
        self.signal_bot = SignalBot()
        self.signal_bot.telegram = self.telegram
        if not await self.signal_bot.initialize(self.client):
            return False

        # Initialize Trade Manager
        self.trade_manager = TradeManager()
        self.trade_manager.telegram = self.telegram
        if not await self.trade_manager.initialize(self.client):
            return False

        # Setup WebSocket server
        self.ws_server = WebSocketServer(
            self.signal_bot,
            self.trade_manager
        )
        await self.ws_server.start()

        return True

     except Exception as e:
        self.logger.error(f"Initialization error: {str(e)}")
        return False

    async def run(self):
     """Run Bot Manager"""
     try:
        # Initialize
        if not await self.initialize():
            self.logger.error("Failed to initialize")
            return

        # Start GUI in main thread
        if self.gui_manager:
            self.gui_manager.start()
            await asyncio.sleep(1)

        # Start Signal Bot
        self.logger.info("\nStarting Signal Bot...")
        signal_bot_task = asyncio.create_task(self.signal_bot.run())

        # Start Trade Manager
        self.logger.info("Starting Trade Manager...")
        trade_manager_task = asyncio.create_task(self.trade_manager.run())

        # Wait for completion
        await asyncio.gather(
            signal_bot_task,
            trade_manager_task
        )

     except KeyboardInterrupt:
        self.logger.info("Bot Manager stopped by user")
     except Exception as e:
        self.logger.error(f"Fatal error: {str(e)}")
     finally:
        await self.stop()
    async def stop(self):
        """Stop Bot Manager"""
        try:
            self._is_running = False

            # Stop components
            if self.signal_bot:
                await self.signal_bot.stop()

            if self.trade_manager:
                await self.trade_manager.stop()

            if self.gui_manager:
                self.gui_manager.stop()

            if self.ws_server:
                await self.ws_server.stop()

            # Send notification
            if self.telegram:
                await self.telegram.send_message(
                    "🛑 Trading Bot Stopped\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )

            self.logger.info("Bot Manager stopped")

        except Exception as e:
            self.logger.error(f"Error stopping manager: {str(e)}")

def main():
    """Main function"""
    try:
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        current_user = os.getenv('USER', 'Anhbaza01')
        
        print(f"\n{'='*50}")
        print(f"Trading Bot Starting Up")
        print(f"Time: {current_time} UTC")
        print(f"User: {current_user}")
        print(f"{'='*50}\n")
        
        # Create Bot Manager
        manager = BotManager()

        # Set Windows event loop policy if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        # Create and set event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create GUI first
        print("Initializing GUI...")
        manager.gui_manager = GUIManager(manager.trade_manager)
        root = manager.gui_manager.create_gui()

        # Create async task for bot operations
        async def run_bot():
            try:
                print("Initializing bot systems...")
                await manager.initialize()
                print("Starting bot operations...")
                await manager.run()
            except Exception as e:
                print(f"Bot operation error: {str(e)}")

        # Run bot in background
        def run_async():
            try:
                loop.run_until_complete(run_bot())
            except Exception as e:
                print(f"Async runtime error: {str(e)}")

        # Start bot in separate thread
        print("Starting bot in background...")
        bot_thread = threading.Thread(target=run_async, daemon=True)
        bot_thread.start()

        # Start GUI mainloop in main thread
        print("Starting GUI...")
        try:
            root.mainloop()
        except Exception as e:
            print(f"GUI runtime error: {str(e)}")
        finally:
            print("\nShutting down bot systems...")
            # Cleanup when GUI closes
            loop.call_soon_threadsafe(loop.stop)
            bot_thread.join(timeout=5.0)
            loop.close()

    except Exception as e:
        print(f"\nStartup error: {str(e)}")
    finally:
        print("\nTrading Bot shutdown complete")

if __name__ == "__main__":
    main()