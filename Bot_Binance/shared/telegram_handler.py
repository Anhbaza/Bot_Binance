"""
Telegram Handler for Bot Notifications
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:24:27 UTC
"""

import os
import sys
import logging
import asyncio
import aiohttp
import telegram
from typing import Optional
from datetime import datetime

class TelegramHandler:
    def __init__(self, token: str, chat_id: str = None):
        self.token = token.strip()
        self.chat_id = chat_id.strip() if chat_id else None
        self.logger = logging.getLogger('TelegramHandler')
        
        # Validate token
        if not self.token or len(self.token) < 45:
            self.logger.error("Invalid Telegram token format")
            raise ValueError("Invalid Telegram token")
            
        # Log initialization
        self.logger.info(
            f"Initializing Telegram handler with token: {self.token[:8]}...{self.token[-4:]}"
        )
        if self.chat_id:
            self.logger.info(f"Chat ID: {self.chat_id}")

    async def send_message(self, message: str) -> bool:
        """Send message via Telegram"""
        try:
            if not self.token or not self.chat_id:
                self.logger.error("Missing Telegram token or chat ID")
                return False

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }) as response:
                    if response.status == 200:
                        self.logger.info(f"Telegram message sent: {message[:50]}...")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Telegram error: {error_text}")
                        return False

        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")
            return False
            
    async def send_signal(self, signal: dict) -> bool:
        """Send trading signal notification"""
        try:
            message = (
                f"🔔 <b>New Trading Signal</b>\n\n"
                f"Symbol: {signal['symbol']}\n"
                f"Type: {signal['type']}\n"
                f"Entry: {signal['entry_price']}\n"
                f"Take Profit: {signal['take_profit']}\n"
                f"Stop Loss: {signal['stop_loss']}\n"
                f"Confidence: {signal['confidence']}%\n\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            return await self.send_message(message)
        except Exception as e:
            self.logger.error(f"Error sending signal: {str(e)}")
            return False
            
    async def send_order(self, order: dict) -> bool:
        """Send order notification"""
        try:
            message = (
                f"📊 <b>Order Update</b>\n\n"
                f"Symbol: {order['symbol']}\n"
                f"Side: {order['side']}\n"
                f"Type: {order['type']}\n"
                f"Price: {order['price']}\n"
                f"Quantity: {order['quantity']}\n"
                f"Status: {order['status']}\n\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            return await self.send_message(message)
        except Exception as e:
            self.logger.error(f"Error sending order: {str(e)}")
            return False
            
    async def send_scan_result(self, pairs: list) -> bool:
        """Send scanning results"""
        try:
            valid_pairs = [p for p in pairs if p['valid']]
            invalid_pairs = [p for p in pairs if not p['valid']]
            
            message = (
                f"🔍 <b>Scanning Results</b>\n\n"
                f"Total Pairs: {len(pairs)}\n"
                f"Valid: {len(valid_pairs)}\n"
                f"Invalid: {len(invalid_pairs)}\n\n"
                f"<b>Valid Pairs:</b>\n"
            )
            
            for pair in valid_pairs:
                message += (
                    f"• {pair['symbol']} - "
                    f"Volume: ${pair['volume']:,.0f}\n"
                )
                
            message += f"\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            
            return await self.send_message(message)
        except Exception as e:
            self.logger.error(f"Error sending scan results: {str(e)}")
            return False
