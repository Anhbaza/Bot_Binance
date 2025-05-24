"""
Signal Bot for Trading
Main signal bot implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:15:05 UTC
"""

import os
import sys
import yaml
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException

from .signal_scanner import SignalScanner
from .signal_analyzer import SignalAnalyzer
from ..shared.websocket_client import WebSocketClient
from ..shared.constants import (
    SignalType,
    MessageType,
    ClientType,
    TradingConfig as Config
)

class SignalBot:
    def __init__(self):
        self.user = os.getenv('USER', 'Anhbaza01')
        self.logger = self._setup_logging()
        self._is_running = True
        
        # Components
        self.client = None  # Binance client
        self.scanner = None  # Signal scanner
        self.analyzer = None  # Signal analyzer
        self.ws_client = None  # WebSocket client
        
        # State
        self.active_signals = {}
        self.last_scan_time = None
        self.scan_interval = 300  # 5 minutes
        
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
            
            # Get API credentials from config
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
                
                # Register message handlers
                self.ws_client.register_handler(
                    MessageType.WATCH_PAIRS.value,
                    self.handle_watch_pairs
                )
                
                asyncio.create_task(self.ws_client.listen())
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"WebSocket setup error: {str(e)}")
            return False

    async def handle_watch_pairs(self, data: Dict):
        """Handle watched pairs update"""
        try:
            pairs = data.get('pairs', [])
            if self.scanner:
                self.scanner.watched_pairs = pairs
                
            self.logger.info(
                f"Updated watched pairs: "
                f"Monitoring {len(pairs)} pairs"
            )
            
            if pairs:
                self.logger.info(f"Pairs: {', '.join(pairs)}")
                
        except Exception as e:
            self.logger.error(f"Error handling watch pairs: {str(e)}")

    async def send_signal(self, signal: Dict) -> bool:
        """Send trading signal to Trade Manager"""
        try:
            if not self.ws_client or not self.ws_client.is_connected():
                self.logger.error("WebSocket not connected")
                return False
                
            # Add timestamp and format
            formatted_signal = {
                'type': MessageType.SIGNAL.value,
                'data': {
                    **signal,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
            
            # Send signal
            await self.ws_client.send_message(formatted_signal)
            
            # Store in active signals
            signal_id = f"{signal['symbol']}_{signal['timestamp']}"
            self.active_signals[signal_id] = signal
            
            self.logger.info(
                f"Signal sent: {signal['symbol']} "
                f"{signal['type']} @ {signal['entry']}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending signal: {str(e)}")
            return False

    async def scan_markets(self):
        """Scan markets for trading signals"""
        try:
            self.logger.info("Starting market scan...")
            self.last_scan_time = datetime.utcnow()
            
            # Get scan results
            results = await self.scanner.scan_pairs()
            
            signals_found = 0
            for result in results:
                # Analyze each pair
                signal = self.analyzer.analyze_pair(
                    result['symbol'],
                    result['klines']
                )
                
                if signal:
                    # Send valid signals
                    if await self.send_signal(signal):
                        signals_found += 1
                        
            self.logger.info(
                f"Scan completed - Found {signals_found} signals"
            )
            
        except Exception as e:
            self.logger.error(f"Error scanning markets: {str(e)}")

    async def initialize(self) -> bool:
        """Initialize Signal Bot"""
        try:
            # Setup Binance client
            if not await self.setup_binance():
                return False
                
            # Setup WebSocket
            if not await self.setup_websocket():
                return False
                
            # Initialize components
            self.scanner = SignalScanner(
                self.client,
                self.logger
            )
            self.analyzer = SignalAnalyzer(self.logger)
            
            # Initialize scanner
            if not await self.scanner.initialize():
                return False
                
            self.logger.info("Signal Bot initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            return False

    async def run(self):
        """Main bot loop"""
        try:
            # Initialize
            if not await self.initialize():
                self.logger.error("Failed to initialize. Check logs.")
                return
                
            self.logger.info("[+] Signal Bot started")
            self.logger.info(f"[*] Monitoring {len(self.scanner.valid_pairs)} pairs")
            
            # Main loop
            while self._is_running:
                try:
                    # Calculate next scan time
                    now = datetime.utcnow()
                    if (
                        not self.last_scan_time or
                        (now - self.last_scan_time).total_seconds() >= self.scan_interval
                    ):
                        await self.scan_markets()
                        
                    # Wait for next iteration
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(5)
                    
        except KeyboardInterrupt:
            self.logger.info("Signal Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            # Cleanup
            self._is_running = False
            
            if self.ws_client:
                await self.ws_client.stop()
                
            self.logger.info("Signal Bot stopped")

def main():
    """Main function"""
    try:
        # Create Signal Bot instance
        bot = SignalBot()
        
        # Set Windows event loop policy if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )
        
        # Create and set event loop
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
