"""
Signal Scanner Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 10:05:29 UTC
"""

import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from binance.client import Client
from shared.pair_manager import PairManager

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from signal_bot.signal_analyzer import SignalAnalyzer
from shared.constants import Config, Interval, TradingMode

class SignalScanner:
    def __init__(self, client: Client, logger: logging.Logger,pair_manager: PairManager):
        self.client = client
        self.logger = logger
        self.telegram = None
        self._is_testnet = getattr(client, 'testnet', False)
        self.pair_manager = pair_manager

    async def _load_pairs(self) -> List[str]:
        """Load valid trading pairs"""
        try:
            monitored_pairs = await self.pair_manager.get_pairs_to_scan()
            if monitored_pairs:
                # Chỉ quét các cặp được chọn
                self.logger.info(f"Scanning selected pairs: {monitored_pairs}")
                return monitored_pairs
            # Get exchange info
            exchange_info = self.client.get_exchange_info()
            
            # Get all USDT pairs if testnet
            if self._is_testnet:
                pairs = [
                    symbol['symbol'] for symbol in exchange_info['symbols']
                    if symbol['symbol'].endswith('USDT') and
                    symbol['status'] == 'TRADING'
                ]
                self.logger.info(f"Found {len(pairs)} testnet trading pairs")
                return pairs[:10]  # Limit to 10 pairs for testing
            
            # Production mode - check volume
            valid_pairs = []
            for symbol in exchange_info['symbols']:
                if not symbol['symbol'].endswith('USDT'):
                    continue
                    
                # Check 24h volume
                ticker = self.client.get_ticker(symbol=symbol['symbol'])
                volume = float(ticker['quoteVolume'])
                
                if volume >= Config.MIN_VOLUME:
                    valid_pairs.append(symbol['symbol'])
                    self.logger.info(
                        f"Found valid pair: {symbol['symbol']} - "
                        f"Volume: ${volume:,.2f}"
                    )
            
            return valid_pairs

        except Exception as e:
            self.logger.error(f"Error loading pairs: {str(e)}")
            return []
        
   
            
    async def _get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> Optional[List]:
        """Get klines data from Binance"""
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except Exception as e:
            self.logger.error(
                f"Error getting klines for {symbol}: {str(e)}"
            )
            return None
            
    async def _scan_pair(self, symbol: str, interval: str) -> Optional[Dict]:
        """Scan single pair for signals"""
        try:
            self.logger.info(f"\nScanning {symbol} on {interval}...")
            
            # Step 1: Check Volume
            ticker = self.client.get_ticker(symbol=symbol)
            volume = float(ticker['quoteVolume'])
            
            self.logger.info(f"1. Volume Check for {symbol}:")
            self.logger.info(f"   - 24h Volume: ${volume:,.2f}")
            self.logger.info(f"   - Min Required: ${Config.MIN_VOLUME:,.2f}")
            
            if volume < Config.MIN_VOLUME:
                self.logger.info(f"   ❌ {symbol} failed volume check")
                return None
            self.logger.info(f"   ✅ {symbol} passed volume check")

            # Step 2: Get Klines
            self.logger.info(f"2. Getting {interval} klines for {symbol}...")
            klines = await self._get_klines(symbol, interval)
            if not klines:
                self.logger.info(f"   ❌ {symbol} failed to get klines")
                return None
            self.logger.info(f"   ✅ Got {len(klines)} klines")

            # Step 3: Volume Trend Check
            self.logger.info(f"3. Checking volume trend for {symbol}:")
            volumes = np.array([float(k[5]) for k in klines])
            volume_ma = self._sma(volumes, Config.VOLUME_PERIOD)[-1]
            volume_ratio = volumes[-1] / volume_ma if volume_ma > 0 else 0
            
            self.logger.info(f"   - Current Volume: ${volumes[-1]:,.2f}")
            self.logger.info(f"   - Volume MA: ${volume_ma:,.2f}")
            self.logger.info(f"   - Volume Ratio: {volume_ratio:.2f}")
            self.logger.info(f"   - Required Ratio: {Config.VOLUME_RATIO_MIN}")
            
            if volume_ratio < Config.VOLUME_RATIO_MIN:
                self.logger.info(f"   ❌ {symbol} failed volume trend check")
                return None
            self.logger.info(f"   ✅ {symbol} passed volume trend check")

            # Step 4: Price Trend Check
            self.logger.info(f"4. Checking price trend for {symbol}:")
            closes = np.array([float(k[4]) for k in klines])
            fast_ma = self._sma(closes, Config.FAST_MA)
            slow_ma = self._sma(closes, Config.SLOW_MA)
            
            curr_fast = fast_ma[-1]
            curr_slow = slow_ma[-1]
            
            self.logger.info(f"   - Current Price: ${closes[-1]:,.8f}")
            self.logger.info(f"   - Fast MA: ${curr_fast:,.8f}")
            self.logger.info(f"   - Slow MA: ${curr_slow:,.8f}")
            
            trend = None
            if curr_fast > curr_slow:
                if all(fast_ma[-5:] > slow_ma[-5:]):
                    trend = "LONG"
            elif curr_fast < curr_slow:
                if all(fast_ma[-5:] < slow_ma[-5:]):
                    trend = "SHORT"
                    
            if not trend:
                self.logger.info(f"   ❌ {symbol} no clear trend")
                return None
            self.logger.info(f"   ✅ {symbol} shows {trend} trend")

            # Step 5: RSI Check
            self.logger.info(f"5. Checking RSI for {symbol}:")
            rsi = self._rsi(closes)[-1]
            self.logger.info(f"   - Current RSI: {rsi:.2f}")
            
            if trend == "LONG" and rsi > 70:
                self.logger.info(f"   ❌ {symbol} RSI overbought")
                return None
            elif trend == "SHORT" and rsi < 30:
                self.logger.info(f"   ❌ {symbol} RSI oversold")
                return None
            self.logger.info(f"   ✅ {symbol} RSI in range")

            # Step 6: Calculate Levels
            self.logger.info(f"6. Calculating levels for {symbol}:")
            entry = closes[-1]
            upper, middle, lower = self._bollinger_bands(closes)
            
            if trend == "LONG":
                stop_loss = lower[-1]
                take_profit = entry + ((entry - stop_loss) * 2)
            else:
                stop_loss = upper[-1]
                take_profit = entry - ((stop_loss - entry) * 2)
                
            risk = abs(entry - stop_loss)
            reward = abs(take_profit - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            self.logger.info(f"   - Entry: ${entry:,.8f}")
            self.logger.info(f"   - Stop Loss: ${stop_loss:,.8f}")
            self.logger.info(f"   - Take Profit: ${take_profit:,.8f}")
            self.logger.info(f"   - Risk/Reward: {rr_ratio:.2f}")
            
            if rr_ratio < 2:
                self.logger.info(f"   ❌ {symbol} insufficient risk/reward")
                return None
            self.logger.info(f"   ✅ {symbol} levels valid")

            # Step 7: Calculate Confidence
            self.logger.info(f"7. Calculating confidence for {symbol}:")
            confidence = self._calculate_confidence(
                closes,
                volumes,
                trend
            )
            
            self.logger.info(f"   - Confidence Score: {confidence}%")
            self.logger.info(f"   - Minimum Required: {Config.MIN_CONFIDENCE}%")
            
            if confidence < Config.MIN_CONFIDENCE:
                self.logger.info(f"   ❌ {symbol} confidence too low")
                return None
            self.logger.info(f"   ✅ {symbol} confidence sufficient")

            # Create Signal
            signal = {
                'symbol': symbol,
                'type': trend,
                'entry_price': entry,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'confidence': confidence,
                'volume': volume,
                'volume_ratio': volume_ratio,
                'rsi': rsi,
                'risk_reward': rr_ratio,
                'time': int(datetime.utcnow().timestamp() * 1000)
            }

            # Log Success
            self.logger.info(f"\n✨ Signal generated for {symbol}:")
            self.logger.info(f"   Type: {trend}")
            self.logger.info(f"   Entry: ${entry:,.8f}")
            self.logger.info(f"   Take Profit: ${take_profit:,.8f}")
            self.logger.info(f"   Stop Loss: ${stop_loss:,.8f}")
            self.logger.info(f"   Confidence: {confidence}%")
            self.logger.info(f"   Risk/Reward: {rr_ratio:.2f}")
            
            # Send detailed Telegram notification
            if self.telegram:
                await self.telegram.send_message(
                    f"🎯 Signal Alert - {symbol}\n\n"
                    f"Type: {trend}\n"
                    f"Entry: ${entry:,.8f}\n"
                    f"Take Profit: ${take_profit:,.8f}\n"
                    f"Stop Loss: ${stop_loss:,.8f}\n\n"
                    f"Confidence: {confidence}%\n"
                    f"Risk/Reward: {rr_ratio:.2f}\n"
                    f"RSI: {rsi:.2f}\n"
                    f"Volume 24h: ${volume:,.2f}\n"
                    f"Volume Ratio: {volume_ratio:.2f}x\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )

            return signal

        except Exception as e:
            self.logger.error(f"Error scanning {symbol}: {str(e)}")
            return None
            
    async def start_scanning(self):
        """Start scanning for signals"""
        try:
            self._is_scanning = True
            
            while self._is_scanning:
                # Load/reload pairs
                if not self.pairs:
                    self.pairs = await self._load_pairs()
                    
                if not self.pairs:
                    self.logger.error("No valid pairs to scan")
                    await asyncio.sleep(60)
                    continue
                    
                # Scan each pair
                for symbol in self.pairs:
                    if not self._is_scanning:
                        break
                        
                    # Check each timeframe
                    for interval in Config.TIMEFRAMES:
                        try:
                            # Check if enough time passed since last scan
                            last_scan = self.last_scan.get(
                                f"{symbol}_{interval}",
                                0
                            )
                            
                            now = int(datetime.utcnow().timestamp())
                            
                            # Convert interval to seconds
                            if interval.endswith('m'):
                                interval_seconds = int(interval[:-1]) * 60
                            elif interval.endswith('h'):
                                interval_seconds = int(interval[:-1]) * 3600
                            else:
                                interval_seconds = 86400
                                
                            # Skip if scanned recently
                            if now - last_scan < interval_seconds:
                                continue
                                
                            # Scan pair
                            signal = await self._scan_pair(
                                symbol,
                                interval
                            )
                            
                            # Update last scan time
                            self.last_scan[f"{symbol}_{interval}"] = now
                            
                            # Yield signal if found
                            if signal:
                                yield signal
                                
                            # Small delay between scans
                            await asyncio.sleep(0.1)
                            
                        except Exception as e:
                            self.logger.error(
                                f"Error scanning {symbol} on {interval}: {str(e)}"
                            )
                            continue
                            
                # Delay between scan cycles
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Scanning error: {str(e)}")
        finally:
            self._is_scanning = False
            
    def stop_scanning(self):
        """Stop scanning for signals"""
        self._is_scanning = False