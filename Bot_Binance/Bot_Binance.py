"""
Binance Trading Bot
Handles trading operations and management of the entire bot system.

Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 12:35:10 UTC
"""

import os
import sys
import asyncio
import logging
import yaml
from datetime import datetime, timedelta
from typing import Dict, Optional
from binance.client import Client
from signal_bot.signal_bot import SignalBot
from trade_manager.trade_manager import TradeManager
from shared.telegram_handler import TelegramHandler
from trade_manager.gui_manager import GUIManager
from shared.websocket_server import WebSocketServer

class BotManager:
    """Manages all components of the trading bot system"""
    
    def __init__(self):
        """Initialize Bot Manager"""
        self.config: Dict = {}
        self.logger = self._setup_logging()
        self.client: Optional[Client] = None
        self.telegram: Optional[TelegramHandler] = None
        self.signal_bot: Optional[SignalBot] = None
        self.trade_manager: Optional[TradeManager] = None
        self.ws_server: Optional[WebSocketServer] = None
        self.gui_manager: Optional[GUIManager] = None
        self._is_running: bool = False
        self.start_time: datetime = datetime.utcnow()

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

            # File handler
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

            # Validate required config fields
            required_fields = [
                'api_key', 'api_secret', 'telegram_token', 
                'telegram_chat_id', 'min_volume', 'min_confidence'
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
            self.logger.info(f"- Timeframes: {', '.join(self.config.get('timeframes', ['1m','5m','15m','1h','4h']))}")
            self.logger.info(f"- Order Size: ${self.config.get('order_size', 100):,}")
            self.logger.info(f"- Max Orders: {self.config.get('max_orders', 10)}")
            self.logger.info(f"- Risk Per Trade: {self.config.get('risk_per_trade', 1)}%")

            return True

        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return False

    async def initialize(self) -> bool:
        """Initialize all bot components"""
        try:
            self.start_time = datetime.utcnow()
            
            # Load configuration
            if not self._load_config():
                return False

            # Initialize Binance client
            try:
                self.client = Client(
                    self.config['api_key'],
                    self.config['api_secret'],
                    testnet=self.config.get('test_mode', True)
                )
                # Test connection
                server_time = self.client.get_server_time()
                self.logger.info(
                    "Connected to Binance API "
                    f"(Server Time: {datetime.fromtimestamp(server_time['serverTime']/1000)})"
                )
            except Exception as e:
                self.logger.error(f"Failed to connect to Binance: {str(e)}")
                return False

            # Initialize Telegram
            try:
                self.telegram = TelegramHandler(
                    self.config['telegram_token'],
                    self.config['telegram_chat_id']
                )
                
                # Send startup message
                if not await self.telegram.send_message(
                    "Bot Manager Starting\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"User: {os.getenv('USER', 'Anhbaza01')}\n"
                    f"Mode: {'Test Mode' if self.config.get('test_mode', True) else 'Production'}"
                ):
                    self.logger.error("Failed to send Telegram message")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Failed to initialize Telegram: {str(e)}")
                return False

            # Initialize SignalBot
            try:
                self.signal_bot = SignalBot()
                self.signal_bot.telegram = self.telegram
                if not await self.signal_bot.initialize(self.client):
                    self.logger.error("Failed to initialize SignalBot")
                    return False
            except Exception as e:
                self.logger.error(f"Error initializing SignalBot: {str(e)}")
                return False

            # Initialize TradeManager
            try:
                self.trade_manager = TradeManager(self.client)
                self.trade_manager.telegram = self.telegram
                if not await self.trade_manager.initialize():
                    self.logger.error("Failed to initialize TradeManager")
                    return False
            except Exception as e:
                self.logger.error(f"Error initializing TradeManager: {str(e)}")
                return False

            # Initialize GUI if enabled
            if self.config.get('gui_enabled', True):
                try:
                    self.gui_manager = GUIManager(self.trade_manager)
                    self.gui_manager.start()
                    self.logger.info("GUI started successfully")
                except Exception as e:
                    self.logger.error(f"Failed to start GUI: {str(e)}")
                    return False

            # Initialize WebSocket server if enabled
            if self.config.get('ws_enabled', True):
                try:
                    self.ws_server = WebSocketServer(
                        self.signal_bot,
                        self.trade_manager,
                        self.config.get('ws_host', 'localhost'),
                        self.config.get('ws_port', 8765)
                    )
                    await self.ws_server.start()
                    self.logger.info("WebSocket server started successfully")
                except Exception as e:
                    self.logger.error(f"Failed to start WebSocket server: {str(e)}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Run the bot manager"""
        try:
            # Initialize components
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return

            self._is_running = True
            self.logger.info("Bot Manager started successfully")

            # Main loop
            while self._is_running:
                try:
                    # Update GUI if enabled
                    if self.gui_manager:
                        runtime = datetime.utcnow() - self.start_time
                        self.gui_manager.update_status(
                            "Running", 
                            str(runtime).split('.')[0]
                        )

                    # Wait before next update
                    await asyncio.sleep(1)

                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop all bot components"""
        try:
            self._is_running = False
            
            # Stop components in reverse order
            if self.ws_server:
                await self.ws_server.stop()
                self.logger.info("WebSocket server stopped")
                
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
            
            # Send stop message on Telegram
            if self.telegram:
                await self.telegram.send_message(
                    "Bot Manager Stopping\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"Runtime: {runtime_str}"
                )
                
        except Exception as e:
            self.logger.error(f"Error stopping manager: {str(e)}")

def run_app():
    """Application entry point"""
    try:
        # Print startup message
        print("\n" + "="*50)
        print("Trading Bot Starting Up")
        print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"User: {os.getenv('USER', 'Anhbaza01')}")
        print("="*50 + "\n")

        # Create event loop
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