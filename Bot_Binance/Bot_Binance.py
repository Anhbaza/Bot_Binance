"""
Main Bot Runner
Starts and manages Signal Bot and Trade Manager
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:48:30 UTC
"""

import os
import sys
import yaml
import asyncio
import logging
from datetime import datetime
from signal_bot.signal_bot import SignalBot
from trade_manager.trade_manager import TradeManager
from shared.websocket_server import WebSocketServer

class BotManager:
    def __init__(self):
        self.logger = self._setup_logging()
        self.config = self._load_config()
        self._is_running = True
        
        # Components
        self.ws_server = None
        self.signal_bot = None
        self.trade_manager = None

    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        try:
            # Create logs directory
            logs_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'logs'
            )
            os.makedirs(logs_dir, exist_ok=True)
            
            # Log filename
            log_filename = os.path.join(
                logs_dir,
                f'bot_manager_{datetime.utcnow().strftime("%Y%m%d")}.log'
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
            
            logger = logging.getLogger("BotManager")
            
            # Log startup
            logger.info("="*50)
            logger.info("Bot Manager - Starting Up")
            logger.info(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            logger.info(f"User: {os.getenv('USER', 'Anhbaza01')}")
            logger.info("="*50)
            
            return logger
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("BotManager")

    def _load_config(self) -> dict:
        """Load configuration"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'config/config.yaml'
            )
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return {}

    async def start_websocket_server(self):
        """Start WebSocket server"""
        try:
            ws_config = self.config['websocket']
            
            self.ws_server = WebSocketServer(
                host=ws_config['host'],
                port=ws_config['port'],
                logger=self.logger
            )
            
            # Start server
            await self.ws_server.start()
            
            self.logger.info("WebSocket server started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting WebSocket server: {str(e)}")
            return False

    async def start_signal_bot(self):
        """Start Signal Bot"""
        try:
            self.signal_bot = SignalBot()
            
            # Run in background
            asyncio.create_task(self.signal_bot.run())
            
            self.logger.info("Signal Bot started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting Signal Bot: {str(e)}")
            return False

    async def start_trade_manager(self):
        """Start Trade Manager"""
        try:
            self.trade_manager = TradeManager()
            
            # Run in background
            asyncio.create_task(self.trade_manager.run())
            
            self.logger.info("Trade Manager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting Trade Manager: {str(e)}")
            return False

    async def run(self):
        """Run all components"""
        try:
            # Start WebSocket server first
            if not await self.start_websocket_server():
                raise Exception("Failed to start WebSocket server")
                
            # Wait for server to initialize
            await asyncio.sleep(2)
            
            # Start bots
            if not all([
                await self.start_signal_bot(),
                await self.start_trade_manager()
            ]):
                raise Exception("Failed to start bots")
                
            self.logger.info("[+] All components started successfully")
            
            # Keep running
            while self._is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping by user request...")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
        finally:
            # Cleanup
            self._is_running = False
            
            if self.signal_bot:
                await self.signal_bot.stop()
                
            if self.trade_manager:
                await self.trade_manager.stop()
                
            if self.ws_server:
                await self.ws_server.stop()
                
            self.logger.info("All components stopped")

def main():
    """Main entry point"""
    try:
        # Create manager
        manager = BotManager()
        
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
        print("\nStopping by user request...")
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
