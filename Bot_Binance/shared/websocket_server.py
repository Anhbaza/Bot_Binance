"""
WebSocket Server Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:17:42 UTC
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Set, Dict, Optional
import websockets
from websockets.server import WebSocketServerProtocol

from .constants import MessageType, ClientType

class WebSocketServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        logger: Optional[logging.Logger] = None
    ):
        self.host = host
        self.port = port
        self.logger = logger or self._setup_logging()
        
        # Client connections
        self.clients: Set[WebSocketServerProtocol] = set()
        
        # Registered bots
        self.signal_bot = None  # Signal Bot connection
        self.trade_bot = None   # Trade Manager connection
        
        # Server status
        self._running = False

    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        try:
            # Create logs directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logs_dir = os.path.join(current_dir, '../logs')
            os.makedirs(logs_dir, exist_ok=True)
            
            # Log filename with timestamp
            log_filename = os.path.join(
                logs_dir,
                f'websocket_server_{datetime.utcnow().strftime("%Y%m%d")}.log'
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
            
            logger = logging.getLogger("WebSocketServer")
            
            # Log startup info
            logger.info("="*50)
            logger.info("WebSocket Server - Logging Initialized")
            logger.info(f"Log File: {log_filename}")
            logger.info(f"Current Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*50)
            
            return logger
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("WebSocketServer")

    async def register_client(
        self,
        websocket: WebSocketServerProtocol,
        client_type: str
    ):
        """Register new client connection"""
        try:
            # Add to clients set
            self.clients.add(websocket)
            
            # Store bot connection
            if client_type == ClientType.SIGNAL_BOT.value:
                self.signal_bot = websocket
                self.logger.info("[+] Signal Bot connected")
                
            elif client_type == ClientType.TRADE_BOT.value:
                self.trade_bot = websocket
                self.logger.info("[+] Trade Manager Bot connected")
                
            # Broadcast status
            status = {
                'type': MessageType.STATUS.value,
                'data': {
                    'signal_bot': self.signal_bot is not None,
                    'trade_bot': self.trade_bot is not None,
                    'time': datetime.utcnow().isoformat()
                }
            }
            
            await self.broadcast(json.dumps(status))
            
        except Exception as e:
            self.logger.error(f"[-] Error registering client: {str(e)}")

    async def unregister_client(
        self,
        websocket: WebSocketServerProtocol
    ):
        """Unregister client connection"""
        try:
            # Remove from clients set
            self.clients.remove(websocket)
            
            # Update bot status
            if websocket == self.signal_bot:
                self.signal_bot = None
                self.logger.info("[-] Signal Bot disconnected")
                
            elif websocket == self.trade_bot:
                self.trade_bot = None
                self.logger.info("[-] Trade Manager Bot disconnected")
                
            # Broadcast status
            status = {
                'type': MessageType.STATUS.value,
                'data': {
                    'signal_bot': self.signal_bot is not None,
                    'trade_bot': self.trade_bot is not None,
                    'time': datetime.utcnow().isoformat()
                }
            }
            
            await self.broadcast(json.dumps(status))
            
        except Exception as e:
            self.logger.error(f"[-] Error unregistering client: {str(e)}")

    async def broadcast(self, message: str):
        """Broadcast message to all clients"""
        if not self.clients:
            return
            
        # Create tasks for each client
        tasks = [
            asyncio.create_task(client.send(message))
            for client in self.clients
        ]
        
        # Wait for all tasks
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.ALL_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()

    async def handle_message(
        self,
        websocket: WebSocketServerProtocol,
        message: str
    ):
        """Handle incoming message"""
        try:
            # Parse JSON message
            data = json.loads(message)
            message_type = data.get('type')
            
            # Log message
            self.logger.info(
                f"[*] Received {message_type} from "
                f"{'Signal Bot' if websocket == self.signal_bot else 'Trade Bot'}"
            )
            
            if message_type == MessageType.REGISTER.value:
                # Register new client
                await self.register_client(
                    websocket,
                    data.get('client_type')
                )
                return
                
            # Forward message to other bot
            if websocket == self.signal_bot and self.trade_bot:
                await self.trade_bot.send(message)
                
            elif websocket == self.trade_bot and self.signal_bot:
                await self.signal_bot.send(message)
                
        except json.JSONDecodeError:
            self.logger.error("[-] Invalid JSON message")
        except Exception as e:
            self.logger.error(f"[-] Error handling message: {str(e)}")

    async def handler(self, websocket: WebSocketServerProtocol):
        """Handle new WebSocket connection"""
        try:
            # Log client info
            client_info = f"{websocket.remote_address}"
            self.logger.info(f"[+] New connection from {client_info}")
            
            # Handle messages
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"[-] Connection closed: {client_info}")
        finally:
            await self.unregister_client(websocket)

    async def start(self):
        """Start WebSocket server"""
        try:
            self._running = True
            
            # Create server
            server = await websockets.serve(
                self.handler,
                self.host,
                self.port
            )
            
            self.logger.info(
                f"[+] WebSocket server started on "
                f"ws://{self.host}:{self.port}"
            )
            
            # Run indefinitely
            await server.wait_closed()
            
        except Exception as e:
            self.logger.error(f"[-] Server error: {str(e)}")
        finally:
            self._running = False

    async def stop(self):
        """Stop WebSocket server"""
        self._running = False
        
        # Close all connections
        tasks = [
            asyncio.create_task(client.close())
            for client in self.clients
        ]
        
        # Wait for all to close
        if tasks:
            await asyncio.wait(tasks)
            
        self.logger.info("[+] WebSocket server stopped")

def main():
    """Main function"""
    try:
        # Create and start server
        server = WebSocketServer()
        
        # Set Windows event loop policy if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )
            
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run server
        loop.run_until_complete(server.start())
        
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
    finally:
        # Cleanup
        try:
            loop = asyncio.get_event_loop()
            
            # Stop server
            loop.run_until_complete(server.stop())
            
            # Close loop
            loop.close()
            
        except Exception as e:
            print(f"\nError during shutdown: {str(e)}")

if __name__ == "__main__":
    main()
