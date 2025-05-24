"""
WebSocket Client Base Class
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:17:42 UTC
"""

import json
import asyncio
import logging
import websockets
from typing import Dict, Optional, Callable
from datetime import datetime

class WebSocketClient:
    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int = 8765,
        logger: Optional[logging.Logger] = None
    ):
        self.name = name
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger(__name__)
        
        # WebSocket connection
        self.websocket = None
        self._connected = False
        
        # Message handlers
        self.handlers = {}
        
        # Reconnection settings
        self.retry_interval = 5
        self.max_retries = 5
        self._retry_count = 0

    async def connect(self) -> bool:
        """Connect to WebSocket server"""
        try:
            # Build WebSocket URI
            uri = f"ws://{self.host}:{self.port}"
            
            self.logger.info(f"Connecting to {uri}...")
            
            # Connect with timeout
            self.websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=10
            )
            
            self._connected = True
            self._retry_count = 0
            
            self.logger.info(f"Connected to WebSocket server")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            return False

    async def reconnect(self) -> bool:
        """Attempt to reconnect"""
        try:
            if self._retry_count >= self.max_retries:
                self.logger.error("Max reconnection attempts reached")
                return False
                
            self._retry_count += 1
            self.logger.info(
                f"Reconnecting (attempt {self._retry_count}/{self.max_retries})..."
            )
            
            # Close existing connection
            await self.stop()
            
            # Wait before retry
            await asyncio.sleep(self.retry_interval)
            
            # Try to connect
            return await self.connect()
            
        except Exception as e:
            self.logger.error(f"Reconnection error: {str(e)}")
            return False

    def register_handler(
        self,
        message_type: str,
        handler: Callable
    ):
        """Register message handler"""
        self.handlers[message_type] = handler
        self.logger.debug(f"Registered handler for {message_type}")

    async def send_message(self, message: Dict) -> bool:
        """Send message to server"""
        try:
            if not self.is_connected():
                self.logger.error("Not connected to server")
                return False
                
            # Convert to JSON
            json_message = json.dumps(message)
            
            # Send message
            await self.websocket.send(json_message)
            
            self.logger.debug(f"Sent: {json_message}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            self._connected = False
            return False

    async def handle_message(self, message: str):
        """Handle incoming message"""
        try:
            # Parse JSON message
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type in self.handlers:
                # Call registered handler
                await self.handlers[message_type](data.get('data', {}))
            else:
                self.logger.warning(f"No handler for message type: {message_type}")
                
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON message")
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")

    async def listen(self):
        """Listen for messages"""
        while True:
            try:
                if not self.is_connected():
                    if not await self.reconnect():
                        # Failed to reconnect
                        break
                        
                # Wait for message
                message = await self.websocket.recv()
                
                # Handle message
                await self.handle_message(message)
                
            except websockets.ConnectionClosed:
                self.logger.warning("Connection closed")
                self._connected = False
                
                if not await self.reconnect():
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in listen loop: {str(e)}")
                await asyncio.sleep(1)

    async def stop(self):
        """Stop client connection"""
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            finally:
                self.websocket = None
                self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to server"""
        return self._connected and self.websocket is not None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
