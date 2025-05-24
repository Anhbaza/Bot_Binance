"""
Signal Bot Implementation without TA-Lib dependency
Author: Anhbaza01
Version: 1.0.0
Date: 2025-05-24
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from binance.client import Client

class TechnicalAnalyzer:
    """Technical Analysis calculations without TA-Lib"""
    
    @staticmethod
    def calculate_rsi(prices: np.array, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        try:
            # Calculate price changes
            deltas = np.diff(prices)
            
            # Separate gains and losses
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Calculate average gains and losses
            avg_gains = np.mean(gains[:period])
            avg_losses = np.mean(losses[:period])
            
            if avg_losses == 0:
                return 100.0
                
            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi)
            
        except Exception:
            return 50.0  # Neutral value on error
            
    @staticmethod
    def calculate_macd(prices: np.array, 
                      fast_period: int = 12,
                      slow_period: int = 26,
                      signal_period: int = 9) -> Tuple[float, float, float]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        try:
            # Convert to pandas Series for easier calculation
            close_prices = pd.Series(prices)
            
            # Calculate EMAs
            ema_fast = close_prices.ewm(span=fast_period, adjust=False).mean()
            ema_slow = close_prices.ewm(span=slow_period, adjust=False).mean()
            
            # Calculate MACD line
            macd_line = ema_fast - ema_slow
            
            # Calculate signal line
            signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            return (
                float(macd_line.iloc[-1]),
                float(signal_line.iloc[-1]),
                float(histogram.iloc[-1])
            )
            
        except Exception:
            return 0.0, 0.0, 0.0
            
    @staticmethod
    def calculate_bb(prices: np.array, period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        try:
            # Convert to pandas Series
            close_prices = pd.Series(prices)
            
            # Calculate middle band (SMA)
            middle_band = close_prices.rolling(window=period).mean()
            
            # Calculate standard deviation
            std = close_prices.rolling(window=period).std()
            
            # Calculate upper and lower bands
            upper_band = middle_band + (std_dev * std)
            lower_band = middle_band - (std_dev * std)
            
            return (
                float(upper_band.iloc[-1]),
                float(middle_band.iloc[-1]),
                float(lower_band.iloc[-1])
            )
            
        except Exception:
            price = prices[-1]
            return price, price, price
            
    @staticmethod
    def calculate_sma(prices: np.array, period: int) -> float:
        """Calculate Simple Moving Average"""
        try:
            return float(np.mean(prices[-period:]))
        except Exception:
            return prices[-1]
            
    @staticmethod
    def calculate_ema(prices: np.array, period: int) -> float:
        """Calculate Exponential Moving Average"""
        try:
            close_prices = pd.Series(prices)
            return float(close_prices.ewm(span=period, adjust=False).mean().iloc[-1])
        except Exception:
            return prices[-1]

class SignalGenerator:
    """Generate trading signals based on technical analysis"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.analyzer = TechnicalAnalyzer()
        
    def generate_signal(self, symbol: str, klines: List[dict]) -> Optional[Dict]:
        """Generate trading signal from klines data"""
        try:
            # Convert klines to numpy arrays
            closes = np.array([float(k['close']) for k in klines])
            volumes = np.array([float(k['volume']) for k in klines])
            
            # Current values
            current_price = closes[-1]
            current_volume = volumes[-1]
            avg_volume = np.mean(volumes)
            
            # Calculate indicators
            rsi = self.analyzer.calculate_rsi(closes)
            macd, signal, hist = self.analyzer.calculate_macd(closes)
            upper_bb, middle_bb, lower_bb = self.analyzer.calculate_bb(closes)
            
            # Additional indicators
            sma_50 = self.analyzer.calculate_sma(closes, 50)
            ema_21 = self.analyzer.calculate_ema(closes, 21)
            
            # Generate signal
            signal_data = {
                'symbol': symbol,
                'timestamp': datetime.utcnow(),
                'price': current_price,
                'volume': current_volume,
                'volume_ratio': current_volume / avg_volume,
                'indicators': {
                    'rsi': rsi,
                    'macd': macd,
                    'signal': signal,
                    'hist': hist,
                    'bb_upper': upper_bb,
                    'bb_middle': middle_bb,
                    'bb_lower': lower_bb,
                    'sma_50': sma_50,
                    'ema_21': ema_21
                }
            }
            
            # Signal logic
            if (rsi < 30 and 
                current_price < lower_bb and
                current_volume > avg_volume * 1.5 and
                hist > 0):
                # Strong buy signal
                signal_data['type'] = 'BUY'
                signal_data['strength'] = min(100, (30 - rsi) * 3.33)
                signal_data['reason'] = (
                    f"RSI oversold ({rsi:.1f}), "
                    f"Price below BB ({current_price:.2f} < {lower_bb:.2f}), "
                    f"High volume (150% above avg), "
                    f"Positive MACD histogram"
                )
                
            elif (rsi > 70 and
                  current_price > upper_bb and
                  current_volume > avg_volume * 1.5 and
                  hist < 0):
                # Strong sell signal  
                signal_data['type'] = 'SELL'
                signal_data['strength'] = min(100, (rsi - 70) * 3.33)
                signal_data['reason'] = (
                    f"RSI overbought ({rsi:.1f}), "
                    f"Price above BB ({current_price:.2f} > {upper_bb:.2f}), "
                    f"High volume (150% above avg), "
                    f"Negative MACD histogram"
                )
                
            else:
                return None
                
            return signal_data
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {str(e)}")
            return None

class SignalBot:
    def __init__(self, client, logger, pair_manager):
        """Initialize Signal Bot"""
        self.logger = logging.getLogger("SignalBot")
        self.pair_manager = pair_manager
        self.signal_generator = None
        self.client = None
        self.telegram = None
        self._is_running = False
        self.start_time = datetime.utcnow()
        self._is_testnet = True
        self.symbols = []
        self.timeframes = ['1m', '5m', '15m', '1h', '4h']
        self.min_volume = 1000000  # Minimum 24h volume in USDT
        self.min_strength = 70     # Minimum signal strength (0-100)
        
    async def initialize(self, client=None) -> bool:
        """Initialize Signal Bot"""
        try:
            self.start_time = datetime.utcnow()
            self.client = client
            self.signal_generator = SignalGenerator(self.logger)
            
            # Log initialization
            self.logger.info("Signal Bot initializing...")
            self.logger.info(f"Mode: {'Test Mode' if self._is_testnet else 'Production'}")
            
            # Load trading pairs
            if self._is_testnet:
                self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # Test pairs
            else:
                await self._load_symbols()
            
            self.logger.info(f"Loaded {len(self.symbols)} trading pairs")
            
            # Send initialization message
            if self.telegram:
                await self.telegram.send_message(
                    "Signal Bot Initializing\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"User: {os.getenv('USER', 'Anhbaza01')}\n"
                    f"Mode: {'Test Mode' if self._is_testnet else 'Production'}\n"
                    f"Pairs: {len(self.symbols)}\n"
                    f"Timeframes: {', '.join(self.timeframes)}"
                )

            self.logger.info("Signal Bot initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Signal Bot initialization error: {str(e)}")
            return False

    async def run(self):
        """Run Signal Bot"""
        self._is_running = True
        self.logger.info("Signal Bot started")
        
        while self._is_running:
            try:
                for symbol in self.symbols:
                    for interval in self.timeframes:
                        # Get klines data
                        klines = await self._get_klines(symbol, interval)
                        if not klines:
                            continue
                            
                        # Generate signal
                        signal = self.signal_generator.generate_signal(symbol, klines)
                        
                        if signal and signal['strength'] >= self.min_strength:
                            # Log signal
                            self.logger.info(
                                f"Signal: {signal['type']} {symbol} "
                                f"({interval}) - Strength: {signal['strength']:.1f}%"
                            )
                            
                            # Send notification
                            if self.telegram:
                                await self.telegram.send_message(
                                    f"Trading Signal\n\n"
                                    f"Symbol: {symbol}\n"
                                    f"Type: {signal['type']}\n"
                                    f"Timeframe: {interval}\n"
                                    f"Price: ${signal['price']:,.2f}\n"
                                    f"Strength: {signal['strength']:.1f}%\n"
                                    f"Reason: {signal['reason']}\n\n"
                                    f"Indicators:\n"
                                    f"RSI: {signal['indicators']['rsi']:.1f}\n"
                                    f"MACD: {signal['indicators']['macd']:.4f}\n"
                                    f"Signal: {signal['indicators']['signal']:.4f}\n"
                                    f"BB Upper: ${signal['indicators']['bb_upper']:,.2f}\n"
                                    f"BB Lower: ${signal['indicators']['bb_lower']:,.2f}"
                                )
                        
                        # Add delay between symbols
                        await asyncio.sleep(0.1)
                        
                # Log status and wait before next scan
                self.logger.info(
                    f"Market scan completed - "
                    f"Runtime: {datetime.utcnow() - self.start_time}"
                )
                await asyncio.sleep(60)  # 1 minute delay
                
            except Exception as e:
                self.logger.error(f"Error in scan cycle: {str(e)}")
                await asyncio.sleep(60)

    async def stop(self):
        """Stop Signal Bot"""
        try:
            self._is_running = False
            runtime = datetime.utcnow() - self.start_time
            
            self.logger.info(f"Signal Bot stopping...")
            self.logger.info(f"Total runtime: {runtime}")
            
            if self.telegram:
                await self.telegram.send_message(
                    "Signal Bot Stopping\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"Total Runtime: {runtime}"
                )
                
        except Exception as e:
            self.logger.error(f"Error stopping Signal Bot: {str(e)}")
            
    async def _get_klines(self, symbol: str, interval: str) -> List[dict]:
        """Get klines/candlestick data"""
        try:
            if self._is_testnet:
                # Generate test data
                now = datetime.utcnow()
                data = []
                price = 100.0
                
                for i in range(100):
                    timestamp = now - timedelta(minutes=i)
                    price = price * (1 + np.random.normal(0, 0.001))
                    kline = {
                        'timestamp': timestamp.timestamp() * 1000,
                        'open': price * (1 + np.random.normal(0, 0.0001)),
                        'high': price * (1 + np.random.normal(0, 0.0002)),
                        'low': price * (1 + np.random.normal(0, 0.0002)),
                        'close': price,
                        'volume': np.random.normal(1000, 100)
                    }
                    data.append(kline)
                    
                return data
                
            else:
                # Get real klines from Binance
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=100
                )
                
                return [
                    {
                        'timestamp': k[0],
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5])
                    }
                    for k in klines
                ]

        except Exception as e:
            self.logger.error(f"Error getting klines for {symbol}: {str(e)}")
            return []
