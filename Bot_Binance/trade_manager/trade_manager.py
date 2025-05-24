"""
Trade Manager Implementation
Main trading operations and management for Binance trading bot.

Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 12:40:18 UTC
"""

import logging
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from binance.client import Client
from binance.enums import *
from shared.pair_manager import PairManager

class Trade:
    """Represents a single trade"""
    def __init__(self, symbol: str, trade_type: str, entry_price: float, amount: float):
        self.symbol = symbol
        self.type = trade_type  # BUY or SELL
        self.entry_price = entry_price
        self.amount = amount
        self.current_price = entry_price
        self.pnl = 0.0
        self.pnl_percent = 0.0
        self.entry_time = datetime.utcnow()
        self.status = "OPEN"
        self.stop_loss = None
        self.take_profit = None
        self.order_id = None
        self.position_size = 0.0
        self.leverage = 1

    def update(self, current_price: float):
        """Update trade metrics"""
        self.current_price = current_price
        if self.type == "BUY":
            self.pnl = (current_price - self.entry_price) * self.amount
            self.pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        else:  # SELL
            self.pnl = (self.entry_price - current_price) * self.amount
            self.pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100

    def set_stop_loss(self, price: float):
        """Set stop loss price"""
        self.stop_loss = price

    def set_take_profit(self, price: float):
        """Set take profit price"""
        self.take_profit = price

    def to_dict(self) -> Dict:
        """Convert trade to dictionary"""
        return {
            'symbol': self.symbol,
            'type': self.type,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'amount': self.amount,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'order_id': self.order_id,
            'position_size': self.position_size,
            'leverage': self.leverage
        }

class Position:
    """Represents a trading position"""
    def __init__(self, symbol: str, side: str, amount: float, entry_price: float):
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.entry_price = entry_price
        self.current_price = entry_price
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.timestamp = datetime.utcnow()

    def update(self, current_price: float):
        """Update position metrics"""
        self.current_price = current_price
        multiplier = 1 if self.side == "BUY" else -1
        self.unrealized_pnl = (current_price - self.entry_price) * self.amount * multiplier

class TradeManager:
    """Manages trading operations"""
    def __init__(self, client, logger, pair_manager):
        """Initialize Trade Manager"""
        self.logger = logging.getLogger('TradeManager')
        self.client = client
        self.telegram = None
        self._is_running = False
        self.start_time = None
        self._is_test_mode = True
        self.pair_manager = pair_manager
        
        # Trading data
        self.active_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.positions: Dict[str, Position] = {}
        self.price_cache: Dict[str, float] = {}
        self.order_history: List[Dict] = []
        
        # Trading parameters
        self.max_trades = 10
        self.risk_per_trade = 0.01  # 1% risk per trade
        self.max_drawdown = 0.05    # 5% max drawdown
        self.profit_target = 0.03   # 3% profit target
        self.stop_loss = 0.02       # 2% stop loss
        
        # Performance metrics
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.best_trade = 0.0
        self.worst_trade = 0.0

    async def initialize(self) -> bool:
        """Initialize Trade Manager"""
        try:
            self.start_time = datetime.utcnow()
            self.logger.info("Initializing Trade Manager...")

            if not self.client:
                self.logger.error("Binance client not provided")
                return False

            # Test connection
            try:
                server_time = self.client.get_server_time()
                self.logger.info(
                    "Trade Manager connected to Binance "
                    f"(Server Time: {datetime.fromtimestamp(server_time['serverTime']/1000)})"
                )
                
                # Get account info
                account = self.client.get_account()
                balances = {
                    asset['asset']: float(asset['free']) 
                    for asset in account['balances'] 
                    if float(asset['free']) > 0
                }
                
                self.logger.info(f"Account balances loaded: {len(balances)} assets found")
                
            except Exception as e:
                self.logger.error(f"Failed to connect to Binance: {str(e)}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error initializing Trade Manager: {str(e)}")
            return False

    async def start(self):
        """Start Trade Manager"""
        self._is_running = True
        self.logger.info("Trade Manager started")
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_positions())
        asyncio.create_task(self._monitor_orders())

    async def stop(self):
        """Stop Trade Manager"""
        self._is_running = False
        
        # Close all open positions
        for trade in self.active_trades[:]:
            await self.close_trade(trade.symbol)
            
        # Cancel all open orders
        try:
            self.client.cancel_all_orders()
            self.logger.info("All orders cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
            
        self.logger.info("Trade Manager stopped")

    async def _monitor_positions(self):
        """Monitor open positions"""
        while self._is_running:
            try:
                for trade in self.active_trades:
                    current_price = self.price_cache.get(trade.symbol)
                    if not current_price:
                        continue
                        
                    trade.update(current_price)
                    
                    # Check stop loss
                    if trade.stop_loss and (
                        (trade.type == "BUY" and current_price <= trade.stop_loss) or
                        (trade.type == "SELL" and current_price >= trade.stop_loss)
                    ):
                        await self.close_trade(trade.symbol)
                        self.logger.info(f"Stop loss triggered for {trade.symbol}")
                        
                    # Check take profit
                    if trade.take_profit and (
                        (trade.type == "BUY" and current_price >= trade.take_profit) or
                        (trade.type == "SELL" and current_price <= trade.take_profit)
                    ):
                        await self.close_trade(trade.symbol)
                        self.logger.info(f"Take profit triggered for {trade.symbol}")
                        
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring positions: {str(e)}")
                await asyncio.sleep(5)

    async def _monitor_orders(self):
        """Monitor open orders"""
        while self._is_running:
            try:
                open_orders = self.client.get_open_orders()
                for order in open_orders:
                    # Process order updates
                    order_id = order['orderId']
                    symbol = order['symbol']
                    status = order['status']
                    
                    # Handle filled orders
                    if status == ORDER_STATUS_FILLED:
                        trade = next(
                            (t for t in self.active_trades if t.order_id == order_id), 
                            None
                        )
                        if trade:
                            trade.status = "FILLED"
                            self.logger.info(f"Order filled for {symbol}")
                            
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring orders: {str(e)}")
                await asyncio.sleep(5)

    async def place_trade(
        self, 
        symbol: str, 
        trade_type: str, 
        amount: float, 
        price: float
    ) -> Optional[Trade]:
        """Place a new trade"""
        try:
            if len(self.active_trades) >= self.max_trades:
                self.logger.warning("Maximum number of trades reached")
                return None

            # Create order
            order = None
            if not self._is_test_mode:
                order_side = SIDE_BUY if trade_type == "BUY" else SIDE_SELL
                order = self.client.create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=amount
                )

            # Create trade object
            trade = Trade(symbol, trade_type, price, amount)
            if order:
                trade.order_id = order['orderId']
                
            # Calculate and set stop loss/take profit
            if trade_type == "BUY":
                sl_price = price * (1 - self.stop_loss)
                tp_price = price * (1 + self.profit_target)
            else:
                sl_price = price * (1 + self.stop_loss)
                tp_price = price * (1 - self.profit_target)
                
            trade.set_stop_loss(sl_price)
            trade.set_take_profit(tp_price)
            
            self.active_trades.append(trade)

            # Send notification
            if self.telegram:
                await self.telegram.send_message(
                    f"New Trade Opened\n\n"
                    f"Symbol: {symbol}\n"
                    f"Type: {trade_type}\n"
                    f"Entry Price: ${price:,.2f}\n"
                    f"Amount: {amount}\n"
                    f"Stop Loss: ${sl_price:,.2f}\n"
                    f"Take Profit: ${tp_price:,.2f}"
                )

            self.logger.info(
                f"New {trade_type} trade placed for {symbol} "
                f"at ${price:,.2f}"
            )
            return trade

        except Exception as e:
            self.logger.error(f"Error placing trade: {str(e)}")
            return None

    async def close_trade(self, symbol: str) -> bool:
        """Close an existing trade"""
        try:
            trade = next((t for t in self.active_trades if t.symbol == symbol), None)
            if not trade:
                self.logger.warning(f"No active trade found for {symbol}")
                return False

            # Close position if not in test mode
            if not self._is_test_mode:
                order_side = SIDE_SELL if trade.type == "BUY" else SIDE_BUY
                self.client.create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=trade.amount
                )

            # Update final P/L
            if symbol in self.price_cache:
                trade.update(self.price_cache[symbol])

            # Update statistics
            self.total_pnl += trade.pnl
            if trade.pnl > 0:
                self.win_count += 1
                self.best_trade = max(self.best_trade, trade.pnl_percent)
            else:
                self.loss_count += 1
                self.worst_trade = min(self.worst_trade, trade.pnl_percent)

            # Move to closed trades
            self.active_trades.remove(trade)
            self.closed_trades.append(trade)

            # Send notification
            if self.telegram:
                await self.telegram.send_message(
                    f"Trade Closed\n\n"
                    f"Symbol: {symbol}\n"
                    f"Type: {trade.type}\n"
                    f"Entry: ${trade.entry_price:,.2f}\n"
                    f"Exit: ${trade.current_price:,.2f}\n"
                    f"P/L: {trade.pnl_percent:+.2f}%"
                )

            self.logger.info(
                f"Closed {trade.type} trade for {symbol} "
                f"with P/L: {trade.pnl_percent:+.2f}%"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error closing trade: {str(e)}")
            return False

    async def update_prices(self, prices: Dict[str, float]):
        """Update current prices and trade metrics"""
        self.price_cache.update(prices)
        for trade in self.active_trades:
            if trade.symbol in prices:
                trade.update(prices[trade.symbol])

    def get_trade_summary(self) -> Dict:
        """Get summary of all trades"""
        total_trades = len(self.closed_trades)
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0

        return {
            'active_trades': len(self.active_trades),
            'closed_trades': total_trades,
            'total_pnl': self.total_pnl,
            'win_rate': win_rate,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'best_trade': self.best_trade,
            'worst_trade': self.worst_trade,
            'avg_win': (self.total_pnl / self.win_count) if self.win_count > 0 else 0,
            'avg_loss': (self.total_pnl / self.loss_count) if self.loss_count > 0 else 0
        }

    def get_active_trades(self) -> List[Dict]:
        """Get list of active trades"""
        return [trade.to_dict() for trade in self.active_trades]

    def get_closed_trades(self) -> List[Dict]:
        """Get list of closed trades"""
        return [trade.to_dict() for trade in self.closed_trades]

    # ... (previous code remains the same until get_portfolio_metrics method) ...

    def get_portfolio_metrics(self) -> Dict:
        """Get portfolio performance metrics"""
        metrics = {
            'total_pnl': self.total_pnl,
            'total_trades': len(self.closed_trades),
            'win_rate': (self.win_count / len(self.closed_trades) * 100) if self.closed_trades else 0,
            'best_trade': self.best_trade,
            'worst_trade': self.worst_trade,
            'active_positions': len(self.active_trades),
            'avg_trade_duration': self._calculate_avg_trade_duration(),
            'drawdown': self._calculate_drawdown(),
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'profit_factor': self._calculate_profit_factor(),
            'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        return metrics

    def _calculate_avg_trade_duration(self) -> float:
        """Calculate average trade duration"""
        if not self.closed_trades:
            return 0
            
        durations = []
        for trade in self.closed_trades:
            duration = (datetime.utcnow() - trade.entry_time).total_seconds() / 3600  # hours
            durations.append(duration)
            
        return sum(durations) / len(durations)

    def _calculate_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.closed_trades:
            return 0
            
        peak = 0
        max_dd = 0
        
        for trade in self.closed_trades:
            peak = max(peak, trade.pnl)
            if peak > 0:
                dd = (peak - trade.pnl) / peak * 100
                max_dd = max(max_dd, dd)
                
        return max_dd

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not self.closed_trades:
            return 0
            
        returns = [trade.pnl_percent for trade in self.closed_trades]
        if not returns:
            return 0
            
        avg_return = sum(returns) / len(returns)
        std_dev = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
        
        if std_dev == 0:
            return 0
            
        return (avg_return - risk_free_rate) / std_dev

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor"""
        total_profit = sum(t.pnl for t in self.closed_trades if t.pnl > 0)
        total_loss = abs(sum(t.pnl for t in self.closed_trades if t.pnl < 0))
        
        return total_profit / total_loss if total_loss != 0 else 0

    def get_risk_metrics(self) -> Dict:
        """Get risk management metrics"""
        portfolio_value = sum(t.amount * t.current_price for t in self.active_trades)
        exposure = sum(t.amount * t.entry_price for t in self.active_trades)
        
        metrics = {
            'portfolio_value': portfolio_value,
            'total_exposure': exposure,
            'exposure_ratio': (exposure / portfolio_value * 100) if portfolio_value > 0 else 0,
            'free_margin': self._calculate_free_margin(),
            'margin_level': self._calculate_margin_level(),
            'risk_per_trade': self.risk_per_trade * 100,
            'max_drawdown': self._calculate_drawdown(),
            'var_95': self._calculate_var(),
            'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        return metrics

    def _calculate_free_margin(self) -> float:
        """Calculate free margin"""
        try:
            account = self.client.get_account()
            return float(account['availableBalance'])
        except:
            return 0.0

    def _calculate_margin_level(self) -> float:
        """Calculate margin level"""
        try:
            account = self.client.get_account()
            total_margin = float(account['totalMarginBalance'])
            used_margin = float(account['totalMaintMargin'])
            return (total_margin / used_margin * 100) if used_margin > 0 else 0
        except:
            return 0.0

    def _calculate_var(self, confidence: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if not self.closed_trades:
            return 0
            
        returns = [trade.pnl_percent for trade in self.closed_trades]
        if not returns:
            return 0
            
        returns.sort()
        index = int((1 - confidence) * len(returns))
        return abs(returns[index])

    def export_trade_history(self, format: str = 'csv') -> str:
        """Export trade history to CSV or JSON"""
        try:
            data = []
            for trade in self.closed_trades:
                data.append({
                    'symbol': trade.symbol,
                    'type': trade.type,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.current_price,
                    'amount': trade.amount,
                    'pnl': trade.pnl,
                    'pnl_percent': trade.pnl_percent,
                    'entry_time': trade.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': str(datetime.utcnow() - trade.entry_time).split('.')[0],
                    'status': trade.status
                })
                
            filename = f'trade_history_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}'
            
            if format.lower() == 'csv':
                import pandas as pd
                df = pd.DataFrame(data)
                filepath = f'{filename}.csv'
                df.to_csv(filepath, index=False)
            else:
                import json
                filepath = f'{filename}.json'
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                    
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error exporting trade history: {str(e)}")
            return ""

    def get_performance_report(self) -> Dict:
        """Generate comprehensive performance report"""
        report = {
            'summary': self.get_trade_summary(),
            'portfolio': self.get_portfolio_metrics(),
            'risk': self.get_risk_metrics(),
            'active_trades': self.get_active_trades(),
            'closed_trades': self.get_closed_trades(),
            'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        return report

    async def update_market_data(self):
        """Update market data periodically"""
        while self._is_running:
            try:
                # Get prices for active trades
                symbols = [trade.symbol for trade in self.active_trades]
                if not symbols:
                    await asyncio.sleep(1)
                    continue
                    
                tickers = self.client.get_symbol_ticker(symbols=symbols)
                prices = {t['symbol']: float(t['price']) for t in tickers}
                
                # Update trade data
                await self.update_prices(prices)
                
                # Update GUI if available
                if hasattr(self, 'gui_manager') and self.gui_manager:
                    self.gui_manager.update_trades(self.get_active_trades())
                    
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error updating market data: {str(e)}")
                await asyncio.sleep(5)

    def __str__(self) -> str:
        """String representation of TradeManager"""
        return (
            f"TradeManager(active_trades={len(self.active_trades)}, "
            f"closed_trades={len(self.closed_trades)}, "
            f"total_pnl={self.total_pnl:,.2f}, "
            f"win_rate={self.win_count/len(self.closed_trades)*100 if self.closed_trades else 0:.1f}%)"
        )

    def __repr__(self) -> str:
        """Detailed representation of TradeManager"""
        return (
            f"TradeManager("
            f"active_trades={len(self.active_trades)}, "
            f"closed_trades={len(self.closed_trades)}, "
            f"total_pnl={self.total_pnl:,.2f}, "
            f"win_count={self.win_count}, "
            f"loss_count={self.loss_count}, "
            f"best_trade={self.best_trade:,.2f}%, "
            f"worst_trade={self.worst_trade:,.2f}%, "
            f"test_mode={self._is_test_mode})"
        )