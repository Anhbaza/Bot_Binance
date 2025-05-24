"""
Signal Bot Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:14:56
"""

import os
import sys
import yaml
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional
from binance.client import Client

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from signal_bot.signal_scanner import SignalScanner
from signal_bot.signal_analyzer import SignalAnalyzer
from shared.websocket_client import WebSocketClient
from shared.constants import MessageType, ClientType

class SignalBot:
    def __init__(self):
        self.user = os.getenv('USER', 'Anhbaza01')
        self.logger = self._setup_logging()
        self._is_running = True
        
        # Components
        self.client = None
        self.scanner = None
        self.analyzer = None
        self.ws_client = None
        
        # Load config
        self.config = self._load_config()

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
                f'signal_bot_{datetime.utcnow().strftime("%Y%m%d")}.log'
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
            
            logger = logging.getLogger("SignalBot")
            
            # Log startup info
            logger.info("="*50)
            logger.info("Signal Bot - Logging Initialized")
            logger.info(f"Log File: {log_filename}")
            logger.info(f"Current Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"User: {self.user}")
            logger.info("="*50)
            
            return logger
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("SignalBot")

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

    async def setup_websocket(self) -> bool:
        """Setup WebSocket client"""
        try:
            # Get WebSocket config
            ws_config = self.config['websocket']
            
            # Initialize client
            self.ws_client = WebSocketClient(
                name="SignalBot",
                host=ws_config['host'],
                port=ws_config['port'],
                logger=self.logger
            )
            
            # Connect and register
            if await self.ws_client.connect():
                await self.ws_client.send_message({
                    'type': MessageType.REGISTER.value,
                    'client_type': ClientType.SIGNAL_BOT.value
                })
                
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"WebSocket setup error: {str(e)}")
            return False

    async def send_signal(self, signal: Dict) -> bool:
        """Send trading signal"""
        try:
            if not self.ws_client:
                return False
                
            # Validate signal
            if not self.analyzer.validate_signal(signal):
                return False
                
            # Send via WebSocket
            success = await self.ws_client.send_message({
                'type': MessageType.SIGNAL.value,
                'data': signal
            })
            
            if success:
                self.logger.info(
                    f"Signal sent for {signal['symbol']}"
                )
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending signal: {str(e)}")
            return False

    async def initialize(self) -> bool:
        """Initialize Signal Bot"""
        try:
            # Setup components
            if not all([
                await self.setup_binance(),
                await self.setup_websocket()
            ]):
                return False
                
            # Initialize scanner & analyzer
            self.scanner = SignalScanner(
                self.client,
                self.logger
            )
            self.analyzer = SignalAnalyzer(
                self.logger
            )
            
            self.logger.info("Signal Bot initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Run signal bot"""
        try:
            # Initialize
            if not await self.initialize():
                self.logger.error("Failed to initialize")
                return
                
            self.logger.info("[+] Signal Bot started")
            
            # Start scanning
            async for signal in self.scanner.start_scanning():
                if not self._is_running:
                    break
                    
                # Send valid signals
                if signal:
                    await self.send_signal(signal)
                    
        except KeyboardInterrupt:
            self.logger.info("Signal Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop signal bot"""
        try:
            self._is_running = False
            
            if self.scanner:
                self.scanner.stop_scanning()
                
            if self.ws_client:
                await self.ws_client.stop()
                
            self.logger.info("Signal Bot stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping bot: {str(e)}")

def main():
    """Main function"""
    try:
        # Create Signal Bot
        bot = SignalBot()
        
        # Set Windows event loop policy if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )
            
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run bot
        loop.run_until_complete(bot.run())
        
    except KeyboardInterrupt:
        print("\nSignal Bot stopped by user")
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