"""
Signal Scanner Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:00:58 UTC
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from binance.client import Client
from datetime import datetime, timedelta

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.constants import TradingConfig as Config
from signal_bot.signal_analyzer import SignalAnalyzer

class SignalScanner:
    def __init__(
        self,
        client: Client,
        logger: Optional[logging.Logger] = None
    ):
        self.client = client
        self.logger = logger or logging.getLogger(__name__)
        self.analyzer = SignalAnalyzer()
        self.scanning = False
        
        # Load trading pairs
        self.pairs = self._load_pairs()
        
    # Thêm vào phương thức _load_pairs():

    def _load_pairs(self) -> List[str]:
     """Load tradeable pairs"""
     try:
        pairs = []
        scan_results = []
        exchange_info = self.client.get_exchange_info()
        
        self.logger.info("Starting pairs scan...")
        
        for symbol in exchange_info['symbols']:
            try:
                # Only USDT futures pairs
                if not symbol['symbol'].endswith('USDT'):
                    continue
                    
                if not symbol['symbol'].startswith(('BTC','ETH','BNB')):
                    continue
                
                # Must be active and futures trading
                if (symbol['status'] != 'TRADING' or
                    not symbol['isSpotTradingAllowed']):
                    scan_results.append({
                        'symbol': symbol['symbol'],
                        'valid': False,
                        'reason': 'Not active or not futures'
                    })
                    continue
                    
                # Check minimum volume
                ticker = self.client.get_ticker(symbol=symbol['symbol'])
                volume = float(ticker['quoteVolume'])
                
                if volume < Config.MIN_VOLUME:
                    scan_results.append({
                        'symbol': symbol['symbol'],
                        'valid': False,
                        'volume': volume,
                        'reason': 'Insufficient volume'
                    })
                    continue
                    
                # Valid pair
                pairs.append(symbol['symbol'])
                scan_results.append({
                    'symbol': symbol['symbol'],
                    'valid': True,
                    'volume': volume
                })
                
            except Exception as e:
                self.logger.error(f"Error scanning {symbol['symbol']}: {str(e)}")
                continue
                
        # Send results to Telegram
        if hasattr(self, 'telegram'):
            asyncio.create_task(
                self.telegram.send_scan_result(scan_results)
            )
            
        self.logger.info(f"Scan complete. Found {len(pairs)} valid pairs")
        return pairs
            
     except Exception as e:
        self.logger.error(f"Error loading pairs: {str(e)}")
        return []

    async def scan_pair(
        self,
        symbol: str,
        interval: str = '1h'
    ) -> Optional[Dict]:
        """Scan single pair for signals"""
        try:
            # Get klines data
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=100
            )
            
            if not klines:
                return None
                
            # Analyze for signals
            signal = self.analyzer.analyze_klines(
                symbol,
                klines
            )
            
            if signal:
                self.logger.info(
                    f"Found signal for {symbol}: {signal['type']}"
                )
                
            return signal
            
        except Exception as e:
            self.logger.error(
                f"Error scanning {symbol}: {str(e)}"
            )
            return None

    async def start_scanning(self):
        """Start scanning process"""
        try:
            self.scanning = True
            self.logger.info("Starting scanner...")
            
            while self.scanning:
                for symbol in self.pairs:
                    if not self.scanning:
                        break
                        
                    # Scan each timeframe
                    for interval in Config.TIMEFRAMES:
                        signal = await self.scan_pair(
                            symbol,
                            interval
                        )
                        
                        if signal:
                            yield signal
                            
                    # Rate limiting
                    await asyncio.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Scanner error: {str(e)}")
        finally:
            self.scanning = False

    def stop_scanning(self):
        """Stop scanning process"""
        self.scanning = False
        self.logger.info("Scanner stopped")

    def get_valid_pairs(self) -> List[str]:
        """Get list of valid trading pairs"""
        return self.pairs.copy()

    async def get_pair_info(self, symbol: str) -> Optional[Dict]:
        """Get detailed pair information"""
        try:
            # Get current ticker
            ticker = self.client.get_ticker(symbol=symbol)
            
            # Get 24h stats
            stats = self.client.get_ticker(symbol=symbol)
            
            # Get order book
            depth = self.client.get_order_book(
                symbol=symbol,
                limit=5
            )
            
            return {
                'symbol': symbol,
                'price': float(ticker['lastPrice']),
                'volume': float(stats['volume']),
                'change': float(stats['priceChangePercent']),
                'high': float(stats['highPrice']),
                'low': float(stats['lowPrice']),
                'bid': float(depth['bids'][0][0]),
                'ask': float(depth['asks'][0][0]),
                'spread': (
                    float(depth['asks'][0][0]) -
                    float(depth['bids'][0][0])
                ),
                'updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(
                f"Error getting info for {symbol}: {str(e)}"
            )
            return None

    async def calculate_volatility(
        self,
        symbol: str,
        period: int = 14
    ) -> Optional[float]:
        """Calculate pair volatility"""
        try:
            # Get daily klines
            klines = self.client.get_klines(
                symbol=symbol,
                interval='1d',
                limit=period
            )
            
            if not klines:
                return None
                
            # Calculate daily returns
            closes = [float(k[4]) for k in klines]
            returns = [
                (closes[i] - closes[i-1]) / closes[i-1]
                for i in range(1, len(closes))
            ]
            
            # Calculate standard deviation
            import numpy as np
            volatility = np.std(returns) * 100
            
            return round(volatility, 2)
            
        except Exception as e:
            self.logger.error(
                f"Error calculating volatility for {symbol}: {str(e)}"
            )
            return None

    def filter_pairs(
        self,
        min_volume: float = None,
        min_price: float = None,
        max_spread: float = None
    ) -> List[str]:
        """Filter pairs by criteria"""
        try:
            filtered = []
            
            for symbol in self.pairs:
                try:
                    ticker = self.client.get_ticker(symbol=symbol)
                    
                    # Check volume
                    if min_volume:
                        volume = float(ticker['quoteVolume'])
                        if volume < min_volume:
                            continue
                            
                    # Check price
                    if min_price:
                        price = float(ticker['lastPrice'])
                        if price < min_price:
                            continue
                            
                    # Check spread
                    if max_spread:
                        book = self.client.get_order_book(
                            symbol=symbol,
                            limit=1
                        )
                        spread = (
                            float(book['asks'][0][0]) -
                            float(book['bids'][0][0])
                        )
                        if spread > max_spread:
                            continue
                            
                    filtered.append(symbol)
                    
                except:
                    continue
                    
            return filtered
            
        except Exception as e:
            self.logger.error(f"Error filtering pairs: {str(e)}")
            return []

    def update_pairs(self):
        """Update trading pairs list"""
        try:
            new_pairs = self._load_pairs()
            
            added = set(new_pairs) - set(self.pairs)
            removed = set(self.pairs) - set(new_pairs)
            
            self.pairs = new_pairs
            
            if added:
                self.logger.info(f"Added pairs: {added}")
            if removed:
                self.logger.info(f"Removed pairs: {removed}")
                
        except Exception as e:
            self.logger.error(f"Error updating pairs: {str(e)}")