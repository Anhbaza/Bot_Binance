"""
Order Manager for Trading Bot
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 10:11:16 UTC
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.constants import Config, OrderType, OrderSide, OrderStatus, TimeInForce

class OrderManager:
    def __init__(
        self,
        client: Client,
        logger: Optional[logging.Logger] = None
    ):
        self.client = client
        self.logger = logger or logging.getLogger(__name__)
        self.telegram = None  # Will be set by TradeManager
        self.open_orders = {}
        self.order_updates = {}

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker data"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return {
                'symbol': ticker['symbol'],
                'price': float(ticker['price'])
            }
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error for {symbol}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting ticker for {symbol}: {str(e)}")
            return None

    async def get_exchange_info(self, symbol: str) -> Optional[Dict]:
        """Get exchange information for symbol"""
        try:
            info = self.client.get_exchange_info()
            
            # Find symbol info
            symbol_info = None
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
                    
            if not symbol_info:
                raise ValueError(f"Symbol {symbol} not found")
                
            # Extract filters
            filters = {
                f['filterType']: f
                for f in symbol_info['filters']
            }
            
            return {
                'symbol': symbol,
                'base_asset': symbol_info['baseAsset'],
                'quote_asset': symbol_info['quoteAsset'],
                'min_price': float(filters['PRICE_FILTER']['minPrice']),
                'max_price': float(filters['PRICE_FILTER']['maxPrice']),
                'tick_size': float(filters['PRICE_FILTER']['tickSize']),
                'min_qty': float(filters['LOT_SIZE']['minQty']),
                'max_qty': float(filters['LOT_SIZE']['maxQty']),
                'step_size': float(filters['LOT_SIZE']['stepSize']),
                'min_notional': float(filters['MIN_NOTIONAL']['minNotional'])
            }
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting exchange info: {str(e)}")
            return None

    def _calculate_quantity(
        self,
        symbol: str,
        price: float,
        amount: float,
        step_size: float
    ) -> float:
        """Calculate order quantity based on USDT amount"""
        try:
            # Calculate raw quantity
            quantity = amount / price
            
            # Round to step size
            precision = len(str(step_size).split('.')[-1])
            quantity = round(quantity - (quantity % step_size), precision)
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating quantity: {str(e)}")
            return 0.0

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float,
        take_profit: float
    ) -> Optional[Dict]:
        """Create new order with OCO"""
        try:
            # Get symbol info
            info = await self.get_exchange_info(symbol)
            if not info:
                return None
                
            # Calculate quantity
            qty = self._calculate_quantity(
                symbol,
                price,
                Config.ORDER_SIZE,  # Using Config instead of TradingConfig
                info['step_size']
            )
            
            if qty <= 0:
                raise ValueError("Invalid quantity")
                
            # Create main order
            order = self.client.create_order(
                symbol=symbol,
                side=OrderSide.BUY.value if side == 'LONG' else OrderSide.SELL.value,
                type=OrderType.LIMIT.value,
                timeInForce=TimeInForce.GTC.value,
                quantity=qty,
                price=price
            )
            
            if not order:
                raise ValueError("Failed to create main order")
                
            # Create OCO order
            oco = self.client.create_oco_order(
                symbol=symbol,
                side=OrderSide.SELL.value if side == 'LONG' else OrderSide.BUY.value,
                quantity=qty,
                price=take_profit,
                stopPrice=stop_loss,
                stopLimitPrice=stop_loss,
                stopLimitTimeInForce=TimeInForce.GTC.value
            )
            
            if not oco:
                # Cancel main order if OCO fails
                self.client.cancel_order(
                    symbol=symbol,
                    orderId=order['orderId']
                )
                raise ValueError("Failed to create OCO order")
                
            # Store orders
            self.open_orders[symbol] = {
                'main': order,
                'oco': oco
            }
            
            # Send telegram notification
            if self.telegram:
                await self.telegram.send_order({
                    'symbol': symbol,
                    'side': side,
                    'type': OrderType.LIMIT.value,
                    'quantity': qty,
                    'price': price,
                    'status': OrderStatus.NEW.value
                })
            
            return {
                'symbol': symbol,
                'orderId': order['orderId'],
                'side': side,
                'quantity': qty,
                'price': price,
                'stopLoss': stop_loss,
                'takeProfit': take_profit,
                'status': OrderStatus.NEW.value
            }
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating order: {str(e)}")
            return None

    async def cancel_order(
        self,
        symbol: str,
        order_id: int
    ) -> bool:
        """Cancel existing order"""
        try:
            # Cancel main order
            self.client.cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            
            # Cancel OCO if exists
            if symbol in self.open_orders:
                oco = self.open_orders[symbol]['oco']
                try:
                    self.client.cancel_order(
                        symbol=symbol,
                        orderId=oco['orderId']
                    )
                except:
                    pass
                    
                del self.open_orders[symbol]
                
            # Send telegram notification
            if self.telegram:
                await self.telegram.send_order({
                    'symbol': symbol,
                    'orderId': order_id,
                    'status': OrderStatus.CANCELED.value
                })
                
            return True
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return False

    async def close_position(
        self,
        symbol: str,
        order_id: int
    ) -> Optional[Dict]:
        """Close position at market price"""
        try:
            # Get position info
            position = self.open_orders.get(symbol)
            if not position:
                raise ValueError(f"No position found for {symbol}")
                
            # Cancel existing orders
            await self.cancel_order(symbol, order_id)
            
            # Get current price
            ticker = await self.get_ticker(symbol)
            if not ticker:
                raise ValueError("Could not get current price")
                
            # Create market close order
            close_order = self.client.create_order(
                symbol=symbol,
                side=OrderSide.SELL.value if position['main']['side'] == OrderSide.BUY.value else OrderSide.BUY.value,
                type=OrderType.MARKET.value,
                quantity=position['main']['origQty']
            )
            
            if not close_order:
                raise ValueError("Failed to create close order")
                
            # Send telegram notification
            if self.telegram:
                await self.telegram.send_order({
                    'symbol': symbol,
                    'type': OrderType.MARKET.value,
                    'quantity': float(close_order['origQty']),
                    'price': float(close_order['price']),
                    'status': close_order['status']
                })
                
            return {
                'symbol': symbol,
                'orderId': close_order['orderId'],
                'price': float(close_order['price']),
                'quantity': float(close_order['origQty']),
                'status': close_order['status']
            }
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return None

    async def get_order_status(
        self,
        symbol: str,
        order_id: int
    ) -> Optional[Dict]:
        """Get current order status"""
        try:
            order = self.client.get_order(
                symbol=symbol,
                orderId=order_id
            )
            
            return {
                'symbol': order['symbol'],
                'orderId': order['orderId'],
                'price': float(order['price']),
                'quantity': float(order['origQty']),
                'executed': float(order['executedQty']),
                'status': order['status']
            }
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            return None

    async def get_account_balance(
        self,
        asset: str = 'USDT'
    ) -> Optional[float]:
        """Get account balance for asset"""
        try:
            account = self.client.get_account()
            
            for balance in account['balances']:
                if balance['asset'] == asset:
                    return float(balance['free'])
                    
            return 0.0
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting balance: {str(e)}")
            return None

    async def get_open_orders(
        self,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """Get all open orders"""
        try:
            orders = self.client.get_open_orders(
                symbol=symbol
            )
            
            return [{
                'symbol': o['symbol'],
                'orderId': o['orderId'],
                'price': float(o['price']),
                'quantity': float(o['origQty']),
                'side': o['side'],
                'type': o['type'],
                'status': o['status']
            } for o in orders]
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []

    async def cancel_all_orders(
        self,
        symbol: Optional[str] = None
    ) -> bool:
        """Cancel all open orders"""
        try:
            # Get open orders
            orders = await self.get_open_orders(symbol)
            
            # Cancel each order
            for order in orders:
                try:
                    await self.cancel_order(
                        order['symbol'],
                        order['orderId']
                    )
                except:
                    continue
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return False