"""
Signal Analyzer Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 10:08:36 UTC
"""

import os
import sys
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.constants import Config, SignalType

class SignalAnalyzer:
    def __init__(
        self,
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)

    def _convert_klines(
        self,
        klines: List[List]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Convert klines to numpy arrays"""
        try:
            # Extract OHLCV data
            opens = np.array([float(k[1]) for k in klines])
            highs = np.array([float(k[2]) for k in klines])
            lows = np.array([float(k[3]) for k in klines])
            closes = np.array([float(k[4]) for k in klines])
            volumes = np.array([float(k[5]) for k in klines])
            
            return opens, highs, lows, closes, volumes
            
        except Exception as e:
            self.logger.error(f"Error converting klines: {str(e)}")
            return None, None, None, None, None

    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        return np.convolve(data, np.ones(period)/period, mode='valid')

    def _rsi(self, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index"""
        deltas = np.diff(closes)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum()/period
        down = -seed[seed < 0].sum()/period
        rs = up/down
        rsi = np.zeros_like(closes)
        rsi[:period] = 100. - 100./(1. + rs)

        for i in range(period, len(closes)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up*(period-1) + upval)/period
            down = (down*(period-1) + downval)/period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)

        return rsi

    def _bollinger_bands(
        self,
        closes: np.ndarray,
        period: int = 20,
        num_std: int = 2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands"""
        middle = self._sma(closes, period)
        std = np.std(closes[-period:])
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        return upper, middle, lower

    def _check_volume(
        self,
        volumes: np.ndarray
    ) -> bool:
        """Check volume conditions"""
        try:
            # Calculate volume MA
            volume_ma = self._sma(volumes, Config.VOLUME_PERIOD)[-1]
            
            # Get current values
            curr_vol = volumes[-1]
            
            # Volume ratio
            volume_ratio = curr_vol / volume_ma if volume_ma > 0 else 0
            
            # Check conditions
            if volume_ratio < Config.VOLUME_RATIO_MIN:
                return False
                
            # Check trend
            vol_trend = all(volumes[-5:] >= volumes[-6:-1])
            if not vol_trend:
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking volume: {str(e)}")
            return False

    def _check_trend(
        self,
        closes: np.ndarray
    ) -> Optional[str]:
        """Determine price trend"""
        try:
            # Calculate MAs
            fast_ma = self._sma(closes, Config.FAST_MA)
            slow_ma = self._sma(closes, Config.SLOW_MA)
            
            # Get last values
            curr_fast = fast_ma[-1]
            curr_slow = slow_ma[-1]
            
            # Check crossover
            if curr_fast > curr_slow:
                # Check trend strength
                if all(fast_ma[-5:] > slow_ma[-5:]):
                    return SignalType.LONG.value
                    
            elif curr_fast < curr_slow:
                # Check trend strength  
                if all(fast_ma[-5:] < slow_ma[-5:]):
                    return SignalType.SHORT.value
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking trend: {str(e)}")
            return None

    def _calculate_levels(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        signal_type: str
    ) -> Tuple[float, float, float]:
        """Calculate entry, take profit and stop loss levels"""
        try:
            # Calculate Bollinger Bands
            upper, middle, lower = self._bollinger_bands(closes)
            
            # Get current values
            entry = closes[-1]
            curr_upper = upper[-1]
            curr_lower = lower[-1]
            
            if signal_type == SignalType.LONG.value:
                stop_loss = curr_lower
                take_profit = entry + ((entry - stop_loss) * 2)
            else:
                stop_loss = curr_upper
                take_profit = entry - ((stop_loss - entry) * 2)
                
            return entry, take_profit, stop_loss
            
        except Exception as e:
            self.logger.error(f"Error calculating levels: {str(e)}")
            return 0, 0, 0

    def _calculate_confidence(
        self,
        closes: np.ndarray,
        volumes: np.ndarray,
        signal_type: str
    ) -> float:
        """Calculate signal confidence score"""
        try:
            # Calculate indicators
            rsi = self._rsi(closes)
            
            # Moving averages
            fast_ma = self._sma(closes, 12)
            slow_ma = self._sma(closes, 26)
            
            # MACD line
            macd = fast_ma - slow_ma
            
            # Signal line
            signal = self._sma(macd, 9)
            
            # Volume ratio
            vol_ma = self._sma(volumes, Config.VOLUME_PERIOD)[-1]
            vol_ratio = volumes[-1] / vol_ma if vol_ma > 0 else 0
            
            # Get current values
            curr_rsi = rsi[-1]
            curr_macd = macd[-1]
            curr_signal = signal[-1]
            
            confidence = 0
            
            # Trend score (0-30)
            trend_score = 30 if (
                (signal_type == SignalType.LONG.value and curr_macd > curr_signal) or
                (signal_type == SignalType.SHORT.value and curr_macd < curr_signal)
            ) else 0
            
            # Volume score (0-30)
            volume_score = min(30, vol_ratio * 10)
            
            # RSI score (0-20)
            rsi_score = 20 if 30 < curr_rsi < 70 else 0
            
            # MACD score (0-20)
            macd_score = 20 if abs(curr_macd - curr_signal) > 0 else 0
            
            confidence = sum([
                trend_score,
                volume_score,
                rsi_score,
                macd_score
            ])
            
            return round(confidence, 2)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {str(e)}")
            return 0

    async def analyze_klines(
        self,
        symbol: str,
        klines: List[List]
    ) -> Optional[Dict]:
        """Analyze klines data for trading signals"""
        try:
            # Convert klines
            opens, highs, lows, closes, volumes = self._convert_klines(klines)
            
            if closes is None:
                return None
                
            # Check volume
            if not self._check_volume(volumes):
                return None
                
            # Check trend
            signal_type = self._check_trend(closes)
            if not signal_type:
                return None
                
            # Calculate levels
            entry, tp, sl = self._calculate_levels(
                closes,
                highs,
                lows,
                signal_type
            )
            
            if not all([entry, tp, sl]):
                return None
                
            # Calculate confidence
            confidence = self._calculate_confidence(
                closes,
                volumes,
                signal_type
            )
            
            if confidence < Config.MIN_CONFIDENCE:
                return None
                
            # Create signal
            signal = {
                'symbol': symbol,
                'type': signal_type,
                'entry_price': round(entry, 8),
                'take_profit': round(tp, 8),
                'stop_loss': round(sl, 8),
                'confidence': confidence,
                'rsi': round(self._rsi(closes)[-1], 2),
                'volume_ratio': round(
                    volumes[-1] / self._sma(volumes, Config.VOLUME_PERIOD)[-1]
                    if volumes[-1] > 0 else 0,
                    2
                ),
                'time': int(datetime.utcnow().timestamp() * 1000)
            }
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}")
            return None

    def validate_signal(self, signal: Dict) -> bool:
        """Validate trading signal"""
        try:
            required_fields = [
                'symbol',
                'type',
                'entry_price',
                'take_profit',
                'stop_loss',
                'confidence'
            ]
            
            # Check required fields
            if not all(k in signal for k in required_fields):
                return False
                
            # Validate values
            if signal['type'] not in [
                SignalType.LONG.value,
                SignalType.SHORT.value
            ]:
                return False
                
            if signal['confidence'] < Config.MIN_CONFIDENCE:
                return False
                
            if signal['entry_price'] <= 0:
                return False
                
            # Validate risk/reward
            entry = signal['entry_price']
            tp = signal['take_profit']
            sl = signal['stop_loss']
            
            if signal['type'] == SignalType.LONG.value:
                risk = entry - sl
                reward = tp - entry
            else:
                risk = sl - entry
                reward = entry - tp
                
            if risk <= 0 or reward <= 0:
                return False
                
            # Risk:Reward should be at least 1:2
            if reward / risk < 2:
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating signal: {str(e)}")
            return False