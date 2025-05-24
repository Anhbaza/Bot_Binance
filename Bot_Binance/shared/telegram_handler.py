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
import telegram
from typing import Optional
from datetime import datetime

class TelegramHandler:
    def __init__(
        self,
        token: str,
        chat_id: str,
        logger: Optional[logging.Logger] = None
    ):
        self.token = token
        self.chat_id = chat_id
        self.logger = logger or logging.getLogger(__name__)
        self.bot = telegram.Bot(token=token)
        
    async def send_message(self, message: str) -> bool:
        """Send message to Telegram"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            return True
        except Exception as e:
            self.logger.error(f"Telegram error: {str(e)}")
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
