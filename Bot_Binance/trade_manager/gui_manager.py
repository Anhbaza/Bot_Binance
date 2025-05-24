"""
GUI Manager for Trading Bot
Handles GUI interface with Tkinter
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 08:38:13 UTC
"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

class GUIManager:
    def __init__(self, trade_manager: Any):
        self.trade_manager = trade_manager
        self.logger = trade_manager.logger
        
        # GUI elements
        self.root = None
        self.signals_tree = None
        self.trades_tree = None
        self.stats_labels = {}
        
        # Update queue
        self.update_queue = queue.Queue()
        
        # Setup GUI
        self._setup_gui()
        
    def _setup_gui(self):
        """Setup GUI elements"""
        try:
            # Create main window
            self.root = tk.Tk()
            self.root.title("Trading Bot Manager - Anhbaza01")
            self.root.geometry("1200x800")
            
            # Configure style
            style = ttk.Style()
            style.configure(
                "Treeview",
                rowheight=25,
                font=('Arial', 10)
            )
            
            # Create frames
            self._create_header_frame()
            self._create_signals_frame()
            self._create_trades_frame()
            
            # Start update processing
            self.root.after(100, self._process_updates)
            
        except Exception as e:
            self.logger.error(f"GUI setup error: {str(e)}")

    def _create_header_frame(self):
        """Create header with statistics"""
        try:
            header = ttk.Frame(self.root)
            header.pack(fill='x', padx=10, pady=5)
            
            # Title
            title = ttk.Label(
                header,
                text="Trading Statistics",
                font=('Arial', 14, 'bold')
            )
            title.pack(anchor='w')
            
            # Stats grid
            stats = ttk.Frame(header)
            stats.pack(fill='x', pady=5)
            
            # Create stat labels
            labels = [
                ('total_profit', 'Total Profit:', '$0.00'),
                ('win_rate', 'Win Rate:', '0%'),
                ('total_trades', 'Total Trades:', '0'),
                ('open_trades', 'Open Trades:', '0/5'),
                ('balance', 'USDT Balance:', '$0.00')
            ]
            
            for i, (key, text, value) in enumerate(labels):
                # Label
                ttk.Label(
                    stats,
                    text=text,
                    font=('Arial', 10)
                ).grid(row=0, column=i*2, padx=5)
                
                # Value
                self.stats_labels[key] = ttk.Label(
                    stats,
                    text=value,
                    font=('Arial', 10, 'bold')
                )
                self.stats_labels[key].grid(
                    row=0,
                    column=i*2+1,
                    padx=5
                )
                
        except Exception as e:
            self.logger.error(f"Header creation error: {str(e)}")

    def _create_signals_frame(self):
        """Create signals section"""
        try:
            frame = ttk.LabelFrame(
                self.root,
                text="Trading Signals",
                padding=5
            )
            frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Create treeview
            self.signals_tree = ttk.Treeview(
                frame,
                columns=(
                    'time',
                    'symbol',
                    'type',
                    'entry',
                    'tp',
                    'sl',
                    'conf',
                    'status'
                ),
                show='headings',
                height=8
            )
            
            # Configure columns
            columns = [
                ('time', 'Time', 150),
                ('symbol', 'Pair', 100),
                ('type', 'Type', 80),
                ('entry', 'Entry Price', 120),
                ('tp', 'Take Profit', 120),
                ('sl', 'Stop Loss', 120),
                ('conf', 'Confidence', 100),
                ('status', 'Status', 100)
            ]
            
            for col, text, width in columns:
                self.signals_tree.heading(col, text=text)
                self.signals_tree.column(col, width=width)
                
            # Add scrollbar
            scrollbar = ttk.Scrollbar(
                frame,
                orient='vertical',
                command=self.signals_tree.yview
            )
            self.signals_tree.configure(
                yscrollcommand=scrollbar.set
            )
            
            scrollbar.pack(side='right', fill='y')
            self.signals_tree.pack(fill='both', expand=True)
            
            # Buttons
            buttons = ttk.Frame(frame)
            buttons.pack(fill='x', pady=5)
            
            ttk.Button(
                buttons,
                text="Open Trade",
                command=self._open_trade
            ).pack(side='left', padx=5)
            
            ttk.Button(
                buttons,
                text="Clear Signals",
                command=self._clear_signals
            ).pack(side='left', padx=5)
            
        except Exception as e:
            self.logger.error(f"Signals frame creation error: {str(e)}")

    def _create_trades_frame(self):
        """Create trades section"""
        try:
            frame = ttk.LabelFrame(
                self.root,
                text="Open Trades",
                padding=5
            )
            frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Create treeview
            self.trades_tree = ttk.Treeview(
                frame,
                columns=(
                    'time',
                    'symbol',
                    'type',
                    'entry',
                    'current',
                    'tp',
                    'sl',
                    'profit'
                ),
                show='headings',
                height=8
            )
            
            # Configure columns
            columns = [
                ('time', 'Open Time', 150),
                ('symbol', 'Pair', 100),
                ('type', 'Type', 80),
                ('entry', 'Entry Price', 120),
                ('current', 'Current Price', 120),
                ('tp', 'Take Profit', 120),
                ('sl', 'Stop Loss', 120),
                ('profit', 'Profit %', 100)
            ]
            
            for col, text, width in columns:
                self.trades_tree.heading(col, text=text)
                self.trades_tree.column(col, width=width)
                
            # Add scrollbar
            scrollbar = ttk.Scrollbar(
                frame,
                orient='vertical',
                command=self.trades_tree.yview
            )
            self.trades_tree.configure(
                yscrollcommand=scrollbar.set
            )
            
            scrollbar.pack(side='right', fill='y')
            self.trades_tree.pack(fill='both', expand=True)
            
            # Buttons
            buttons = ttk.Frame(frame)
            buttons.pack(fill='x', pady=5)
            
            ttk.Button(
                buttons,
                text="Close Trade",
                command=self._close_trade
            ).pack(side='left', padx=5)
            
            ttk.Button(
                buttons,
                text="Close All",
                command=self._close_all_trades
            ).pack(side='left', padx=5)
            
        except Exception as e:
            self.logger.error(f"Trades frame creation error: {str(e)}")

    def _open_trade(self):
        """Handle open trade button"""
        try:
            # Get selected signal
            selected = self.signals_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Warning",
                    "Please select a signal to trade"
                )
                return
                
            # Get signal data
            item = self.signals_tree.item(selected[0])
            signal = item['values']
            
            # Confirm action
            if messagebox.askyesno(
                "Confirm Trade",
                f"Open {signal[2]} trade for {signal[1]}?"
            ):
                # Create trade
                asyncio.run_coroutine_threadsafe(
                    self.trade_manager.open_trade({
                        'symbol': signal[1],
                        'type': signal[2],
                        'entry_price': signal[3],
                        'take_profit': signal[4],
                        'stop_loss': signal[5]
                    }),
                    asyncio.get_event_loop()
                )
                
        except Exception as e:
            self.logger.error(f"Error opening trade: {str(e)}")
            messagebox.showerror(
                "Error",
                "Failed to open trade"
            )

    def _close_trade(self):
        """Handle close trade button"""
        try:
            # Get selected trade
            selected = self.trades_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Warning",
                    "Please select a trade to close"
                )
                return
                
            # Get trade data
            item = self.trades_tree.item(selected[0])
            trade = item['values']
            
            # Confirm action
            if messagebox.askyesno(
                "Confirm Close",
                f"Close trade for {trade[1]}?"
            ):
                # Close trade
                asyncio.run_coroutine_threadsafe(
                    self.trade_manager.close_trade(
                        trade[1],
                        "Manual close"
                    ),
                    asyncio.get_event_loop()
                )
                
        except Exception as e:
            self.logger.error(f"Error closing trade: {str(e)}")
            messagebox.showerror(
                "Error",
                "Failed to close trade"
            )

    def _close_all_trades(self):
        """Handle close all trades button"""
        try:
            # Confirm action
            if messagebox.askyesno(
                "Confirm Close All",
                "Close all open trades?"
            ):
                # Close all trades
                for trade in self.trade_manager.open_trades.keys():
                    asyncio.run_coroutine_threadsafe(
                        self.trade_manager.close_trade(
                            trade,
                            "Manual close all"
                        ),
                        asyncio.get_event_loop()
                    )
                    
        except Exception as e:
            self.logger.error(f"Error closing all trades: {str(e)}")
            messagebox.showerror(
                "Error",
                "Failed to close trades"
            )

    def _clear_signals(self):
        """Clear signals list"""
        try:
            if messagebox.askyesno(
                "Confirm Clear",
                "Clear all signals?"
            ):
                for item in self.signals_tree.get_children():
                    self.signals_tree.delete(item)
                    
                self.trade_manager.active_signals.clear()
                
        except Exception as e:
            self.logger.error(f"Error clearing signals: {str(e)}")

    def update_signals(self, signals: List[Dict]):
        """Update signals display"""
        try:
            # Clear existing items
            for item in self.signals_tree.get_children():
                self.signals_tree.delete(item)
                
            # Add signals
            for signal in signals:
                self.signals_tree.insert(
                    '',
                    'end',
                    values=(
                        datetime.fromtimestamp(
                            signal['time']/1000
                        ).strftime('%Y-%m-%d %H:%M:%S'),
                        signal['symbol'],
                        signal['type'],
                        f"{signal['entry']:.8f}",
                        f"{signal['tp']:.8f}",
                        f"{signal['sl']:.8f}",
                        f"{signal['confidence']}%",
                        'New'
                    )
                )
                
        except Exception as e:
            self.logger.error(f"Error updating signals: {str(e)}")

    def update_trades(self, trades: List[Dict]):
        """Update trades display"""
        try:
            # Clear existing items
            for item in self.trades_tree.get_children():
                self.trades_tree.delete(item)
                
            # Add trades
            for trade in trades:
                signal = trade['signal']
                order = trade['order']
                
                # Calculate profit %
                entry = float(signal['entry_price'])
                current = float(order.get('price', entry))
                profit = (
                    (current - entry) / entry * 100
                    if signal['type'] == 'LONG'
                    else (entry - current) / entry * 100
                )
                
                self.trades_tree.insert(
                    '',
                    'end',
                    values=(
                        datetime.fromtimestamp(
                            trade.get('time', datetime.utcnow().timestamp())
                        ).strftime('%Y-%m-%d %H:%M:%S'),
                        signal['symbol'],
                        signal['type'],
                        f"{signal['entry_price']:.8f}",
                        f"{current:.8f}",
                        f"{signal['take_profit']:.8f}",
                        f"{signal['stop_loss']:.8f}",
                        f"{profit:.2f}%"
                    )
                )
                
        except Exception as e:
            self.logger.error(f"Error updating trades: {str(e)}")

    def update_statistics(self, stats: Dict):
        """Update statistics display"""
        try:
            if not stats:
                return
                
            # Update labels
            self.stats_labels['total_profit'].config(
                text=f"${stats['total_profit']:.2f}"
            )
            
            self.stats_labels['win_rate'].config(
                text=f"{stats['win_rate']:.1f}%"
            )
            
            self.stats_labels['total_trades'].config(
                text=str(stats['total_trades'])
            )
            
            self.stats_labels['open_trades'].config(
                text=f"{len(self.trade_manager.open_trades)}/5"
            )
            
            self.stats_labels['balance'].config(
                text=f"${stats.get('balance', 0):.2f}"
            )
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {str(e)}")

    def _process_updates(self):
        """Process GUI updates from queue"""
        try:
            while True:
                try:
                    # Get update from queue
                    update = self.update_queue.get_nowait()
                    
                    update_type = update.get('type')
                    data = update.get('data')
                    
                    if update_type == 'signals':
                        self.update_signals(data)
                    elif update_type == 'trades':
                        self.update_trades(data)
                    elif update_type == 'stats':
                        self.update_statistics(data)
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error processing updates: {str(e)}")
        finally:
            # Schedule next update
            self.root.after(100, self._process_updates)

    def add_update(self, update_type: str, data: Any):
        """Add update to queue"""
        try:
            self.update_queue.put({
                'type': update_type,
                'data': data
            })
        except Exception as e:
            self.logger.error(f"Error adding update: {str(e)}")

    def start(self):
        """Start GUI"""
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Error starting GUI: {str(e)}")

    def stop(self):
        """Stop GUI"""
        try:
            if self.root:
                self.root.quit()
        except Exception as e:
            self.logger.error(f"Error stopping GUI: {str(e)}")
