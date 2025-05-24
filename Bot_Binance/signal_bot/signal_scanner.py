"""
Signal Scanner for Trading Bot
Scans trading pairs for potential signals
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24
"""

import logging
import asyncio
from typing import Dict, List, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
from ..shared.constants import TradingConfig

class SignalScanner:
    def __init__(
        self,
        client: Client,
        logger: Optional[logging.Logger] = None
    ):
        self.client = client
        self.logger = logger or logging.getLogger(__name__)
        
        # Monitored pairs
        self.valid_pairs = []
        self.watched_pairs = []
        
        # Last scan time
        self.last_scan = {}
        
    async def get_valid_pairs(self) -> List[str]:
        """Get list of valid trading pairs"""
        try:
            # Get exchange info
            info = self.client.get_exchange_info()
            
            # Get 24h stats for volume filtering
            tickers = self.client.get_ticker()
            volume_dict = {
                t['symbol']: float(t['quoteVolume'])
                for t in tickers
            }
            
            # Filter valid pairs
            valid_pairs = []
            for symbol in info['symbols']:
                if (
                    # Trading status
                    symbol['status'] == 'TRADING' and
                    # USDT pairs only
                    symbol['quoteAsset'] == 'USDT' and
                    # Check volume
                    symbol['symbol'] in volume_dict and
                    volume_dict[symbol['symbol']] >= TradingConfig.MIN_VOLUME_USDT
                ):
                    valid_pairs.append(symbol['symbol'])
                    
            # Sort by volume
            valid_pairs.sort(
                key=lambda x: volume_dict[x],
                reverse=True
            )
            
            # Log stats
            self.logger.info(f"Found {len(valid_pairs)} valid pairs")
            self.logger.info("Top 5 pairs by volume:")
            for pair in valid_pairs[:5]:
                volume = volume_dict[pair]
                self.logger.info(f"  {pair}: ${volume:,.2f}")
                
            return valid_pairs
            
        except Exception as e:
            self.logger.error(f"Error getting valid pairs: {str(e)}")
            return []
            
    async def get_klines(
        self,
        symbol: str,
        interval: str = '15m',
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """Get kline data for a symbol"""
        try:
            # Get klines from Binance
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # Format klines
            formatted = []
            for k in klines:
                formatted.append({
                    'time': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': k[6],
                    'quote_volume': float(k[7])
                })
                
            return formatted
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error for {symbol}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting klines for {symbol}: {str(e)}")
            return None
            
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker data"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return {
                'symbol': ticker['symbol'],
                'price': float(ticker['price'])
            }
            
        except Exception as e:
            self.logger.error(f"Error getting ticker for {symbol}: {str(e)}")
            return None
            
    async def scan_pair(self, symbol: str) -> Optional[Dict]:
        """Scan single pair for signals"""
        try:
            # Get kline data
            klines = await self.get_klines(symbol)
            if not klines:
                return None
                
            # Get current price
            ticker = await self.get_ticker(symbol)
            if not ticker:
                return None
                
            return {
                'symbol': symbol,
                'klines': klines,
                'current_price': ticker['price'],
                'time': klines[-1]['time']
            }
            
        except Exception as e:
            self.logger.error(f"Error scanning {symbol}: {str(e)}")
            return None
            
    async def scan_pairs(
        self,
        pairs: Optional[List[str]] = None
    ) -> List[Dict]:
        """Scan multiple pairs"""
        try:
            # Use provided pairs or all valid pairs
            pairs_to_scan = pairs or self.valid_pairs
            
            self.logger.info(f"Scanning {len(pairs_to_scan)} pairs...")
            
            # Create scan tasks
            tasks = []
            for symbol in pairs_to_scan:
                tasks.append(asyncio.create_task(
                    self.scan_pair(symbol)
                ))
                
            # Wait for all scans
            results = await asyncio.gather(*tasks)
            
            # Filter valid results
            valid_results = [r for r in results if r is not None]
            
            self.logger.info(
                f"Scan completed - {len(valid_results)} valid results"
            )
            
            return valid_results
            
        except Exception as e:
            self.logger.error(f"Error scanning pairs: {str(e)}")
            return []
            
    async def initialize(self) -> bool:
        """Initialize scanner"""
        try:
            # Get valid pairs
            self.valid_pairs = await self.get_valid_pairs()
            if not self.valid_pairs:
                self.logger.error("No valid pairs found")
                return False
                
            self.logger.info("Signal Scanner initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Scanner initialization error: {str(e)}")
            return False
