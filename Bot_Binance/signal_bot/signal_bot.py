"""
Signal Bot Implementation
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 10:52:55 UTC
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from signal_bot.signal_scanner import SignalScanner
from shared.constants import Config, SignalType, LogLevel

class SignalBot:
    def __init__(self):
        # Setup logging
        self.logger = self._setup_logging()
        
        # Components
        self.client = None
        self.signal_scanner = None
        self.telegram = None
        
        # State
        self._is_running = False
        self.start_time = None
        self.last_scan_time = {}
        self.scan_stats = {
            'total_scans': 0,
            'total_signals': 0,
            'pairs_analyzed': 0,
            'cycles_completed': 0
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        try:
            # Create logs directory
            logs_dir = os.path.join(PROJECT_ROOT, 'logs')
            os.makedirs(logs_dir, exist_ok=True)

            # Log filename with date
            log_file = os.path.join(
                logs_dir,
                f'signal_bot_{datetime.utcnow().strftime("%Y%m%d")}.log'
            )

            # Configure logger
            logger = logging.getLogger('SignalBot')
            logger.setLevel(logging.INFO)

            # File handler
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.INFO)

            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s UTC | %(levelname)s | %(message)s',
                '%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            # Add handlers
            logger.addHandler(fh)
            logger.addHandler(ch)

            return logger

        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            return logging.getLogger('SignalBot')

    async def initialize(self, client: Client) -> bool:
        """Initialize Signal Bot"""
        try:
            self.start_time = datetime.utcnow()
            self.client = client
            self._is_testnet = getattr(client, 'testnet', False)

            if not self.client:
                self.logger.error("No Binance client provided")
                return False
                
            # Test API connection
            try:
                # For testnet, just check server time
                if self._is_testnet:
                    server_time = self.client.get_server_time()
                    if not server_time:
                        raise ConnectionError("Could not get server time")
                else:
                    # For production, check account access
                    account = self.client.get_account()
                    
                self.logger.info("✅ Binance API connection successful")
                self.logger.info(f"Mode: {'Testnet' if self._is_testnet else 'Production'}")
            except Exception as e:
                self.logger.error(f"❌ Binance API connection failed: {str(e)}")
                return False

            # Send initialization message
            if self.telegram:
                await self.telegram.send_message(
                    "🤖 Signal Bot Initializing\n\n"
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"User: {os.getenv('USER', 'Anhbaza01')}\n"
                    f"Mode: {'Testnet' if self._is_testnet else 'Production'}"
                )

            self.logger.info("Signal Bot initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Signal Bot initialization error: {str(e)}")
            return False

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable string"""
        duration = timedelta(seconds=int(seconds))
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
            
        return " ".join(parts)

    async def _log_stats(self):
        """Log scanning statistics"""
        try:
            # Calculate runtime
            runtime = (datetime.utcnow() - self.start_time).total_seconds()
            
            stats = (
                f"\n{'='*50}\n"
                f"Signal Bot Statistics\n\n"
                f"Runtime: {self._format_duration(runtime)}\n"
                f"Total Scans: {self.scan_stats['total_scans']}\n"
                f"Total Signals: {self.scan_stats['total_signals']}\n"
                f"Pairs Analyzed: {self.scan_stats['pairs_analyzed']}\n"
                f"Cycles Completed: {self.scan_stats['cycles_completed']}\n"
                f"{'='*50}\n"
            )
            
            self.logger.info(stats)
            
            if self.telegram:
                await self.telegram.send_message(
                    f"📊 Signal Bot Statistics\n\n"
                    f"Runtime: {self._format_duration(runtime)}\n"
                    f"Total Scans: {self.scan_stats['total_scans']:,}\n"
                    f"Total Signals: {self.scan_stats['total_signals']:,}\n"
                    f"Pairs Analyzed: {self.scan_stats['pairs_analyzed']:,}\n"
                    f"Cycles Completed: {self.scan_stats['cycles_completed']:,}"
                )
                
        except Exception as e:
            self.logger.error(f"Error logging stats: {str(e)}")

    async def run(self):
        """Run Signal Bot"""
        try:
            self._is_running = True
            
            self.logger.info("\n" + "="*50)
            self.logger.info("Starting Market Scanner")
            self.logger.info("="*50 + "\n")

            # Load trading pairs
            self.logger.info("Loading tradeable pairs...")
            pairs = await self.signal_scanner._load_pairs()
            
            if not pairs:
                self.logger.error("No valid pairs found to scan")
                return

            self.scan_stats['pairs_analyzed'] = len(pairs)
            
            self.logger.info(f"Found {len(pairs)} valid pairs to scan")
            if self.telegram:
                await self.telegram.send_message(
                    f"🔍 Scanner initialized\n\n"
                    f"Valid pairs found: {len(pairs)}\n"
                    f"Starting detailed scan..."
                )

            # Start scanning cycles
            while self._is_running:
                try:
                    cycle_start = datetime.utcnow()
                    
                    self.logger.info("\n" + "-"*50)
                    self.logger.info(f"Starting scan cycle #{self.scan_stats['cycles_completed'] + 1}")
                    self.logger.info(f"Time: {cycle_start.strftime('%H:%M:%S')} UTC")
                    self.logger.info("-"*50 + "\n")

                    # Scan each pair
                    cycle_signals = 0
                    
                    for pair in pairs:
                        if not self._is_running:
                            break
                            
                        self.scan_stats['total_scans'] += 1
                        
                        # Log pair analysis start
                        self.logger.info(f"\nAnalyzing {pair}...")
                        
                        # Check each timeframe
                        for interval in Config.TIMEFRAMES:
                            try:
                                self.logger.info(f"\nTimeframe: {interval}")
                                
                                # Check if enough time passed since last scan
                                last_scan = self.last_scan_time.get(
                                    f"{pair}_{interval}",
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
                                    self.logger.info(
                                        f"Skipping {pair} {interval} - "
                                        f"Last scan: {self._format_duration(now - last_scan)} ago"
                                    )
                                    continue
                                
                                # Get signal
                                signal = await self.signal_scanner._scan_pair(
                                    pair,
                                    interval
                                )
                                
                                # Update last scan time
                                self.last_scan_time[f"{pair}_{interval}"] = now
                                
                                if signal:
                                    self.scan_stats['total_signals'] += 1
                                    cycle_signals += 1
                                    
                                    self.logger.info(
                                        f"\n🎯 Signal #{self.scan_stats['total_signals']} found!"
                                        f"\nPair: {pair}"
                                        f"\nType: {signal['type']}"
                                        f"\nEntry: ${signal['entry_price']:,.8f}"
                                        f"\nConfidence: {signal['confidence']}%"
                                    )
                                
                                # Small delay between timeframes
                                await asyncio.sleep(0.1)
                                
                            except Exception as e:
                                self.logger.error(
                                    f"Error scanning {pair} on {interval}: {str(e)}"
                                )
                                continue
                    
                    # Log cycle completion
                    cycle_end = datetime.utcnow()
                    cycle_duration = (cycle_end - cycle_start).total_seconds()
                    self.scan_stats['cycles_completed'] += 1
                    
                    self.logger.info("\n" + "="*50)
                    self.logger.info("Scan Cycle Completed")
                    self.logger.info(f"Time: {cycle_end.strftime('%H:%M:%S')} UTC")
                    self.logger.info(f"Duration: {self._format_duration(cycle_duration)}")
                    self.logger.info(f"Pairs Scanned: {len(pairs)}")
                    self.logger.info(f"Signals Found: {cycle_signals}")
                    self.logger.info("="*50 + "\n")
                    
                    # Send cycle summary
                    if self.telegram:
                        await self.telegram.send_message(
                            f"📊 Scan Cycle #{self.scan_stats['cycles_completed']}\n\n"
                            f"Time: {cycle_end.strftime('%H:%M:%S')} UTC\n"
                            f"Duration: {self._format_duration(cycle_duration)}\n"
                            f"Pairs Scanned: {len(pairs)}\n"
                            f"Signals Found: {cycle_signals}\n\n"
                            f"Total Scans: {self.scan_stats['total_scans']:,}\n"
                            f"Total Signals: {self.scan_stats['total_signals']:,}"
                        )
                    
                    # Log overall stats every 6 hours
                    if self.scan_stats['cycles_completed'] % 360 == 0:  # ~1 minute per cycle
                        await self._log_stats()
                    
                    # Delay between cycles
                    await asyncio.sleep(60)  # 1 minute delay
                    
                except Exception as e:
                    self.logger.error(f"Cycle error: {str(e)}")
                    await asyncio.sleep(60)  # Wait before retrying
                    continue

        except Exception as e:
            self.logger.error(f"Signal Bot error: {str(e)}")
        finally:
            self._is_running = False
            await self._log_stats()
            self.logger.info("Signal Bot stopped")

    async def stop(self):
        """Stop Signal Bot"""
        self._is_running = False
        self.logger.info("Stopping Signal Bot...")
        
        if self.telegram:
            await self.telegram.send_message(
                "🛑 Signal Bot Stopping\n\n"
                "Final Statistics:\n"
                f"Runtime: {self._format_duration((datetime.utcnow() - self.start_time).total_seconds())}\n"
                f"Total Scans: {self.scan_stats['total_scans']:,}\n"
                f"Total Signals: {self.scan_stats['total_signals']:,}\n"
                f"Pairs Analyzed: {self.scan_stats['pairs_analyzed']:,}\n"
                f"Cycles Completed: {self.scan_stats['cycles_completed']:,}"
            )