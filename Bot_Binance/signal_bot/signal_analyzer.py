"""
Signal Analyzer for Trading Bot
Analyzes price data for trading signals
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from ..shared.constants import (
    SignalType,
    TradingConfig as Config
)

class SignalAnalyzer:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
    def _calculate_rsi(
        self,
        closes: List[float],
        period: int = Config.RSI_PERIOD
    ) -> Optional[float]:
        """Calculate RSI indicator"""
        try:
            # Convert to numpy array
            prices = np.array(closes)
            
            # Calculate price changes
            deltas = np.diff(prices)
            
            # Separate gains and losses
            gains = deltas.copy()
            losses = deltas.copy()
            
            gains[gains < 0] = 0
            losses[losses > 0] = 0
            losses = abs(losses)
            
            # Calculate average gains and losses
            avg_gain = np.mean(gains[:period])
            avg_loss = np.mean(losses[:period])
            
            if avg_loss == 0:
                return 100.0
                
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            self.logger.error(f"RSI calculation error: {str(e)}")
            return None

    def check_volume_signal(
        self,
        klines: List[Dict],
        ratio_min: float = Config.VOLUME_RATIO_MIN
    ) -> Optional[str]:
        """Check for volume breakout"""
        try:
            # Get volume data
            volumes = [k['volume'] for k in klines]
            
            # Calculate average volume
            avg_volume = np.mean(volumes[:-1])
            current_volume = volumes[-1]
            
            # Calculate volume ratio
            volume_ratio = current_volume / avg_volume
            
            # Check breakout
            if volume_ratio >= ratio_min:
                # Check price direction
                close = klines[-1]['close']
                open_price = klines[-1]['open']
                
                if close > open_price:
                    return SignalType.LONG.value
                elif close < open_price:
                    return SignalType.SHORT.value
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Volume analysis error: {str(e)}")
            return None

    def analyze_trend(
        self,
        klines: List[Dict],
        period: int = 20
    ) -> Optional[str]:
        """Analyze price trend"""
        try:
            # Get close prices
            closes = [k['close'] for k in klines]
            
            # Calculate SMA
            sma = pd.Series(closes).rolling(period).mean().iloc[-1]
            current_price = closes[-1]
            
            # Compare price to SMA
            if current_price > sma * 1.02:  # 2% above SMA
                return SignalType.LONG.value
            elif current_price < sma * 0.98:  # 2% below SMA
                return SignalType.SHORT.value
                
            return None
            
        except Exception as e:
            self.logger.error(f"Trend analysis error: {str(e)}")
            return None

    def calculate_targets(
        self,
        symbol: str,
        signal_type: str,
        entry_price: float,
        risk_reward: float = 2.0
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate take profit and stop loss levels"""
        try:
            if signal_type == SignalType.LONG.value:
                # Long position
                sl_pct = Config.RISK_PER_TRADE / 100
                tp_pct = sl_pct * risk_reward
                
                sl = entry_price * (1 - sl_pct)
                tp = entry_price * (1 + tp_pct)
                
            else:
                # Short position
                sl_pct = Config.RISK_PER_TRADE / 100
                tp_pct = sl_pct * risk_reward
                
                sl = entry_price * (1 + sl_pct)
                tp = entry_price * (1 - tp_pct)
                
            return tp, sl
            
        except Exception as e:
            self.logger.error(f"Target calculation error: {str(e)}")
            return None, None

    def calculate_confidence(
        self,
        signal: Dict,
        klines: List[Dict]
    ) -> float:
        """Calculate signal confidence score"""
        try:
            confidence = 0.0
            
            # 1. RSI Weight (30%)
            rsi = self._calculate_rsi([k['close'] for k in klines])
            if rsi is not None:
                if signal['type'] == SignalType.LONG.value:
                    if rsi <= Config.RSI_OVERSOLD:
                        confidence += 30
                    elif rsi <= 40:
                        confidence += 20
                else:  # SHORT
                    if rsi >= Config.RSI_OVERBOUGHT:
                        confidence += 30
                    elif rsi >= 60:
                        confidence += 20
                        
            # 2. Volume Weight (30%)
            volumes = [k['volume'] for k in klines]
            avg_volume = np.mean(volumes[:-1])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume
            
            if volume_ratio >= Config.VOLUME_RATIO_MIN * 2:
                confidence += 30
            elif volume_ratio >= Config.VOLUME_RATIO_MIN:
                confidence += 20
                
            # 3. Trend Weight (20%)
            trend = self.analyze_trend(klines)
            if trend == signal['type']:
                confidence += 20
                
            # 4. Price Action (20%)
            close = klines[-1]['close']
            open_price = klines[-1]['open']
            if (
                signal['type'] == SignalType.LONG.value and
                close > open_price
            ) or (
                signal['type'] == SignalType.SHORT.value and
                close < open_price
            ):
                confidence += 20
                
            return confidence
            
        except Exception as e:
            self.logger.error(f"Confidence calculation error: {str(e)}")
            return 0.0

    def analyze_pair(
        self,
        symbol: str,
        klines: List[Dict]
    ) -> Optional[Dict]:
        """Analyze pair for trading signals"""
        try:
            # Calculate RSI
            closes = [k['close'] for k in klines]
            rsi = self._calculate_rsi(closes)
            
            if rsi is None:
                return None
                
            signal_type = None
            reason = []
            
            # Check RSI conditions
            if rsi <= Config.RSI_OVERSOLD:
                # Check for long signal
                volume_signal = self.check_volume_signal(klines)
                if volume_signal == SignalType.LONG.value:
                    signal_type = SignalType.LONG.value
                    reason.append(
                        f"RSI oversold ({rsi:.2f}) "
                        f"with volume breakout"
                    )
                    
            elif rsi >= Config.RSI_OVERBOUGHT:
                # Check for short signal
                volume_signal = self.check_volume_signal(klines)
                if volume_signal == SignalType.SHORT.value:
                    signal_type = SignalType.SHORT.value
                    reason.append(
                        f"RSI overbought ({rsi:.2f}) "
                        f"with volume breakout"
                    )
                    
            if signal_type:
                # Calculate entry and targets
                entry_price = klines[-1]['close']
                tp, sl = self.calculate_targets(
                    symbol,
                    signal_type,
                    entry_price
                )
                
                if tp and sl:
                    # Create signal
                    signal = {
                        'symbol': symbol,
                        'type': signal_type,
                        'entry': entry_price,
                        'tp': tp,
                        'sl': sl,
                        'time': klines[-1]['time'],
                        'reason': ' | '.join(reason)
                    }
                    
                    # Calculate confidence
                    signal['confidence'] = self.calculate_confidence(
                        signal,
                        klines
                    )
                    
                    if signal['confidence'] >= Config.CONFIDENCE_THRESHOLD:
                        return signal
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Signal analysis error for {symbol}: {str(e)}")
            return None
