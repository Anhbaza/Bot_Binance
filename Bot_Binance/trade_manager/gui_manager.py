"""
GUI Manager for Trading Bot
Author: Anhbaza01
Version: 1.0.0
Last Updated: 2025-05-24 09:47:20 UTC
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import scrolledtext
import threading
import queue
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.constants import SignalType

class GUIManager:
    def __init__(self, trade_manager):
        self.trade_manager = trade_manager
        self.root = None
        self.running = False
        self.last_update = datetime.utcnow()
        self.log_queue = queue.Queue()
        self._setup_logger()
        
        # GUI elements
        self.signal_tree = None
        self.trade_tree = None
        self.stats_frame = None
        self.status_bar = None
        
        # Style
        self.style = None
        
        # Data
        self.signals = []
        self.trades = []
        self.stats = {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_profit': 0.0,
            'avg_profit': 0.0
        }
    def _setup_logger(self):
        """Setup custom logger for GUI"""
        class QueueHandler(logging.Handler):
            def __init__(self, queue):
                super().__init__()
                self.queue = queue

            def emit(self, record):
                self.queue.put(record)

        # Create logger
        self.logger = logging.getLogger('GUI')
        self.logger.setLevel(logging.INFO)

        # Add queue handler
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setFormatter(
            logging.Formatter('%(asctime)s UTC | %(levelname)s | %(message)s', 
                            '%Y-%m-%d %H:%M:%S')
        )
        self.logger.addHandler(queue_handler)    
    def _create_main_window(self):
        """Create main window"""
        self.root = tk.Tk()
        self.root.title("Trading Bot Control Panel")
        self.root.geometry("800x600")

        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Bot Status", padding="5")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(status_frame, text="Running Time:").grid(row=0, column=0, padx=5)
        self.runtime_label = ttk.Label(status_frame, text="00:00:00")
        self.runtime_label.grid(row=0, column=1, padx=5)

        # Control buttons
        btn_frame = ttk.Frame(main_frame, padding="5")
        btn_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Button(btn_frame, text="Start Scanning", 
                   command=self._start_scanning).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop Scanning",
                   command=self._stop_scanning).pack(side=tk.LEFT, padx=5)

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log Messages", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
    def create_gui(self):
        """Create GUI window and elements"""
        # Create main window
        self.root = tk.Tk()
        self.root.title("Trading Bot Manager - By Anhbaza01")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Setup style
        self._setup_style()
        
        # Create menu
        self._create_menu()
        
        # Create main container
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Create frames
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.BOTH, expand=True)
        
        bottom_frame = ttk.Frame(container)
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create components
        self._create_signal_frame(top_frame)
        self._create_trade_frame(bottom_frame)
        self._create_stats_frame()
        self._create_status_bar()

        # Start auto-update
        self.running = True
        self._update_gui()

        return self.root

    def on_closing(self):
        """Handle window closing"""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.stop()
            self.root.destroy()

    def start(self):
        """Start GUI if not already created"""
        if not self.root:
            self.create_gui()
        self.running = True

    def stop(self):
        """Stop GUI updates"""
        self.running = False
            
    def _setup_style(self):
        """Setup ttk styles"""
        self.style = ttk.Style()
        
        # Configure main theme
        self.style.theme_use('default')
        
        # Configure treeview
        self.style.configure(
            "Treeview",
            background="#ffffff",
            foreground="#000000",
            rowheight=25,
            fieldbackground="#ffffff"
        )
        
        # Configure treeview headings
        self.style.configure(
            "Treeview.Heading",
            background="#f0f0f0",
            foreground="#000000",
            relief="flat"
        )
        
        # Configure frame
        self.style.configure(
            "TFrame",
            background="#ffffff"
        )
        
        # Configure label
        self.style.configure(
            "TLabel",
            background="#ffffff",
            foreground="#000000",
            font=('Helvetica', 10)
        )
        
        # Configure button
        self.style.configure(
            "TButton",
            background="#4a90e2",
            foreground="#ffffff",
            padding=6
        )
            
    def _run_gui(self):
        """Run GUI main loop"""
        try:
            # Create main window
            self.root = tk.Tk()
            self.root.title("Trading Bot Manager - By Anhbaza01")
            self.root.geometry("1200x800")
            self.root.protocol("WM_DELETE_WINDOW", self.stop)
            
            # Setup style
            self._setup_style()
            
            # Create menu
            self._create_menu()
            
            # Create main container
            container = ttk.Frame(self.root)
            container.pack(fill=tk.BOTH, expand=True)
            
            # Create frames
            top_frame = ttk.Frame(container)
            top_frame.pack(fill=tk.BOTH, expand=True)
            
            bottom_frame = ttk.Frame(container)
            bottom_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create components
            self._create_signal_frame(top_frame)
            self._create_trade_frame(bottom_frame)
            self._create_stats_frame()
            self._create_status_bar()
            
            # Start update loop
            self._update_gui()
            
            # Run
            self.root.mainloop()
            
        except Exception as e:
            print(f"Error running GUI: {str(e)}")
            
    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Export Data",
            command=self._export_data
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit",
            command=self.stop
        )
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Trade menu
        trade_menu = tk.Menu(menubar, tearoff=0)
        trade_menu.add_command(
            label="Close All Trades",
            command=self._close_all_trades
        )
        trade_menu.add_command(
            label="Cancel All Orders",
            command=self._cancel_all_orders
        )
        menubar.add_cascade(label="Trade", menu=trade_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label="Refresh",
            command=self._force_refresh
        )
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="About",
            command=self._show_about
        )
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
        
    def _create_signal_frame(self, parent):
        """Create signals display frame"""
        frame = ttk.LabelFrame(
            parent,
            text="Active Signals"
        )
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(
            toolbar,
            text="Take Signal",
            command=self._take_signal
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="Ignore Signal",
            command=self._ignore_signal
        ).pack(side=tk.LEFT, padx=2)
        
        # Create treeview
        self.signal_tree = ttk.Treeview(
            frame,
            columns=(
                "Time",
                "Symbol",
                "Type",
                "Entry",
                "TP",
                "SL",
                "Confidence"
            ),
            show="headings"
        )
        
        # Set headings
        self.signal_tree.heading("Time", text="Time (UTC)")
        self.signal_tree.heading("Symbol", text="Symbol")
        self.signal_tree.heading("Type", text="Type")
        self.signal_tree.heading("Entry", text="Entry")
        self.signal_tree.heading("TP", text="Take Profit")
        self.signal_tree.heading("SL", text="Stop Loss")
        self.signal_tree.heading("Confidence", text="Confidence")
        
        # Set column widths
        self.signal_tree.column("Time", width=150)
        self.signal_tree.column("Symbol", width=100)
        self.signal_tree.column("Type", width=100)
        self.signal_tree.column("Entry", width=100)
        self.signal_tree.column("TP", width=100)
        self.signal_tree.column("SL", width=100)
        self.signal_tree.column("Confidence", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            frame,
            orient=tk.VERTICAL,
            command=self.signal_tree.yview
        )
        self.signal_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.signal_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _create_trade_frame(self, parent):
        """Create trades display frame"""
        frame = ttk.LabelFrame(
            parent,
            text="Open Trades"
        )
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(
            toolbar,
            text="Close Trade",
            command=self._close_trade
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="Modify TP/SL",
            command=self._modify_trade
        ).pack(side=tk.LEFT, padx=2)
        
        # Create treeview
        self.trade_tree = ttk.Treeview(
            frame,
            columns=(
                "Time",
                "Symbol",
                "Type",
                "Entry",
                "Current",
                "TP",
                "SL",
                "PnL"
            ),
            show="headings"
        )
        
        # Set headings
        self.trade_tree.heading("Time", text="Time (UTC)")
        self.trade_tree.heading("Symbol", text="Symbol")
        self.trade_tree.heading("Type", text="Type")
        self.trade_tree.heading("Entry", text="Entry")
        self.trade_tree.heading("Current", text="Current")
        self.trade_tree.heading("TP", text="Take Profit")
        self.trade_tree.heading("SL", text="Stop Loss")
        self.trade_tree.heading("PnL", text="Profit/Loss")
        
        # Set column widths
        self.trade_tree.column("Time", width=150)
        self.trade_tree.column("Symbol", width=100)
        self.trade_tree.column("Type", width=100)
        self.trade_tree.column("Entry", width=100)
        self.trade_tree.column("Current", width=100)
        self.trade_tree.column("TP", width=100)
        self.trade_tree.column("SL", width=100)
        self.trade_tree.column("PnL", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            frame,
            orient=tk.VERTICAL,
            command=self.trade_tree.yview
        )
        self.trade_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.trade_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _create_stats_frame(self):
        """Create statistics display frame"""
        self.stats_frame = ttk.LabelFrame(
            self.root,
            text="Trading Statistics"
        )
        self.stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create grid
        for i in range(2):
            self.stats_frame.grid_columnconfigure(i*2+1, weight=1)
            
        # Labels - Row 0
        ttk.Label(
            self.stats_frame,
            text="Total Trades:"
        ).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        
        ttk.Label(
            self.stats_frame,
            text="0"
        ).grid(row=0, column=1, padx=5, pady=5, sticky='e')
        
        ttk.Label(
            self.stats_frame,
            text="Win Rate:"
        ).grid(row=0, column=2, padx=5, pady=5, sticky='w')
        
        ttk.Label(
            self.stats_frame,
            text="0.00%"
        ).grid(row=0, column=3, padx=5, pady=5, sticky='e')
        
        # Labels - Row 1
        ttk.Label(
            self.stats_frame,
            text="Total Profit:"
        ).grid(row=1, column=0, padx=5, pady=5, sticky='w')
        
        ttk.Label(
            self.stats_frame,
            text="0.00%"
        ).grid(row=1, column=1, padx=5, pady=5, sticky='e')
        
        ttk.Label(
            self.stats_frame,
            text="Average Profit:"
        ).grid(row=1, column=2, padx=5, pady=5, sticky='w')
        
        ttk.Label(
            self.stats_frame,
            text="0.00%"
        ).grid(row=1, column=3, padx=5, pady=5, sticky='e')
        
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = ttk.Label(
            self.root,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _update_gui(self):
        """Update GUI elements"""
        if not self.running:
            return
            
        try:
            # Update data
            self._update_signals()
            self._update_trades()
            self._update_stats()
            
            # Update status
            self._update_status()
            
            # Schedule next update
            self.root.after(1000, self._update_gui)
            
        except Exception as e:
            self.status_bar.config(
                text=f"Error: {str(e)}"
            )
            
    def _update_signals(self):
        """Update signals display"""
        # Clear current items
        self.signal_tree.delete(*self.signal_tree.get_children())
        
        # Add signals
        for signal in self.signals:
            # Format time
            time_str = datetime.fromtimestamp(
                signal['time'] / 1000
            ).strftime('%Y-%m-%d %H:%M:%S')
            
            # Add item
            self.signal_tree.insert(
                "",
                tk.END,
                values=(
                    time_str,
                    signal['symbol'],
                    signal['type'],
                    f"{signal['entry_price']:.8f}",
                    f"{signal['take_profit']:.8f}",
                    f"{signal['stop_loss']:.8f}",
                    f"{signal['confidence']}%"
                )
            )
            
            # Set colors
            item = self.signal_tree.get_children()[-1]
            if signal['type'] == SignalType.LONG.value:
                self.signal_tree.tag_configure(
                    item,
                    background="#e8f5e9"
                )
            else:
                self.signal_tree.tag_configure(
                    item,
                    background="#ffebee"
                )
            
    def _update_trades(self):
        """Update trades display"""
        # Clear current items
        self.trade_tree.delete(*self.trade_tree.get_children())
        
        # Add trades
        for trade in self.trades:
            # Format time
            time_str = datetime.fromtimestamp(
                trade['time'] / 1000
            ).strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate PnL
            entry = float(trade['entry_price'])
            current = float(trade.get('current_price', entry))
            
            if trade['type'] == SignalType.LONG.value:
                pnl = (current - entry) / entry * 100
            else:
                pnl = (entry - current) / entry * 100
                
            # Add item
            self.trade_tree.insert(
                "",
                tk.END,
                values=(
                    time_str,
                    trade['symbol'],
                    trade['type'],
                    f"{entry:.8f}",
                    f"{current:.8f}",
                    f"{trade['take_profit']:.8f}",
                    f"{trade['stop_loss']:.8f}",
                    f"{pnl:.2f}%"
                )
            )
            
            # Set colors
            item = self.trade_tree.get_children()[-1]
            if pnl >= 0:
                self.trade_tree.tag_configure(
                    item,
                    background="#e8f5e9"
                )
            else:
                self.trade_tree.tag_configure(
                    item,
                    background="#ffebee"
                )
            
    def _update_stats(self):
        """Update statistics display"""
        if not self.stats:
            return
            
        # Update labels
        for widget in self.stats_frame.winfo_children():
            if isinstance(widget, ttk.Label):
                grid_info = widget.grid_info()
                
                if grid_info['row'] == 0:
                    if grid_info['column'] == 1:
                        widget.config(
                            text=str(self.stats['total_trades'])
                        )
                    elif grid_info['column'] == 3:
                        widget.config(
                            text=f"{self.stats['win_rate']:.2f}%"
                        )
                        
                elif grid_info['row'] == 1:
                    if grid_info['column'] == 1:
                        widget.config(
                            text=f"{self.stats['total_profit']:.2f}%"
                        )
                    elif grid_info['column'] == 3:
                        widget.config(
                            text=f"{self.stats['avg_profit']:.2f}%"
                        )
                        
    def _update_status(self):
        """Update status bar"""
        now = datetime.utcnow()
        self.status_bar.config(
            text=(
                f"Last Update: "
                f"{self.last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC | "
                f"Signals: {len(self.signals)} | "
                f"Trades: {len(self.trades)}"
            )
        )
        self.last_update = now
        
    def _take_signal(self):
        """Handle take signal button click"""
        selection = self.signal_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Warning",
                "Please select a signal first"
            )
            return
            
        # Get signal data
        item = self.signal_tree.item(selection[0])
        signal_data = {
            'symbol': item['values'][1],
            'type': item['values'][2],
            'entry_price': float(item['values'][3]),
            'take_profit': float(item['values'][4]),
            'stop_loss': float(item['values'][5])
        }
        
        # Confirm action
        if messagebox.askyesno(
            "Confirm Trade",
            f"Take {signal_data['type']} trade on {signal_data['symbol']}?"
        ):
            # Execute trade
            asyncio.create_task(
                self.trade_manager.open_trade(signal_data)
            )
            
    def _ignore_signal(self):
        """Handle ignore signal button click"""
        selection = self.signal_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Warning",
                "Please select a signal first"
            )
            return
            
        # Get signal data
        item = self.signal_tree.item(selection[0])
        symbol = item['values'][1]
        
        # Remove from signals
        self.signals = [
            s for s in self.signals
            if s['symbol'] != symbol
        ]
        
    def _close_trade(self):
        """Handle close trade button click"""
        selection = self.trade_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Warning",
                "Please select a trade first"
            )
            return
            
        # Get trade data
        item = self.trade_tree.item(selection[0])
        symbol = item['values'][1]
        
        # Confirm action
        if messagebox.askyesno(
            "Confirm Close",
            f"Close trade for {symbol}?"
        ):
            # Close trade
            asyncio.create_task(
                self.trade_manager.close_trade(
                    symbol,
                    "Manual close"
                )
            )
            
    def _modify_trade(self):
        """Handle modify trade button click"""
        selection = self.trade_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Warning",
                "Please select a trade first"
            )
            return
            
        # Get trade data
        item = self.trade_tree.item(selection[0])
        symbol = item['values'][1]
        current_tp = float(item['values'][5])
        current_sl = float(item['values'][6])
        
        # Show modification dialog
        dialog = TradeModifyDialog(
            self.root,
            symbol,
            current_tp,
            current_sl
        )
        
        if dialog.result:
            # Update trade
            asyncio.create_task(
                self.trade_manager.modify_trade(
                    symbol,
                    dialog.result['tp'],
                    dialog.result['sl']
                )
            )
            
    def _close_all_trades(self):
        """Handle close all trades menu action"""
        if not self.trades:
            messagebox.showinfo(
                "Info",
                "No open trades"
            )
            return
            
        # Confirm action
        if messagebox.askyesno(
            "Confirm Close All",
            "Close all open trades?"
        ):
            # Close all trades
            for trade in self.trades:
                asyncio.create_task(
                    self.trade_manager.close_trade(
                        trade['symbol'],
                        "Manual close all"
                    )
                )
                
    def _cancel_all_orders(self):
        """Handle cancel all orders menu action"""
        # Confirm action
        if messagebox.askyesno(
            "Confirm Cancel All",
            "Cancel all open orders?"
        ):
            # Cancel orders
            asyncio.create_task(
                self.trade_manager.order_manager.cancel_all_orders()
            )
            
    def _force_refresh(self):
        """Handle refresh menu action"""
        self._update_signals()
        self._update_trades()
        self._update_stats()
        
    def _export_data(self):
        """Handle export data menu action"""
        try:
            # Create export directory
            export_dir = os.path.join(PROJECT_ROOT, 'exports')
            os.makedirs(export_dir, exist_ok=True)
            
            # Export signals
            signals_file = os.path.join(
                export_dir,
                f"signals_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            with open(signals_file, 'w') as f:
                f.write("Time,Symbol,Type,Entry,TP,SL,Confidence\n")
                for signal in self.signals:
                    time_str = datetime.fromtimestamp(
                        signal['time'] / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    f.write(
                        f"{time_str},"
                        f"{signal['symbol']},"
                        f"{signal['type']},"
                        f"{signal['entry_price']},"
                        f"{signal['take_profit']},"
                        f"{signal['stop_loss']},"
                        f"{signal['confidence']}\n"
                    )
                    
            # Export trades
            trades_file = os.path.join(
                export_dir,
                f"trades_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            with open(trades_file, 'w') as f:
                f.write("Time,Symbol,Type,Entry,Current,TP,SL,PnL\n")
                for trade in self.trades:
                    time_str = datetime.fromtimestamp(
                        trade['time'] / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    entry = float(trade['entry_price'])
                    current = float(trade.get('current_price', entry))
                    
                    if trade['type'] == SignalType.LONG.value:
                        pnl = (current - entry) / entry * 100
                    else:
                        pnl = (entry - current) / entry * 100
                        
                    f.write(
                        f"{time_str},"
                        f"{trade['symbol']},"
                        f"{trade['type']},"
                        f"{entry},"
                        f"{current},"
                        f"{trade['take_profit']},"
                        f"{trade['stop_loss']},"
                        f"{pnl:.2f}\n"
                    )
                    
            messagebox.showinfo(
                "Export Complete",
                f"Data exported to:\n{export_dir}"
            )
            
        except Exception as e:
            messagebox.showerror(
                "Export Error",
                f"Error exporting data: {str(e)}"
            )
            
    def _show_about(self):
        """Handle about menu action"""
        messagebox.showinfo(
            "About Trading Bot",
            "Trading Bot Manager\n\n"
            "Version: 1.0.0\n"
            "Author: Anhbaza01\n"
            "Last Updated: 2025-05-24\n\n"
            "A complete cryptocurrency trading bot\n"
            "with signal detection and trade management."
        )
        
    def add_update(self, data_type: str, data):
        """Add data update"""
        if data_type == 'signals':
            self.signals = data
        elif data_type == 'trades':
            self.trades = data
        elif data_type == 'stats':
            self.stats = data

class TradeModifyDialog:
    """Dialog for modifying trade TP/SL"""
    def __init__(
        self,
        parent,
        symbol: str,
        current_tp: float,
        current_sl: float
    ):
        self.top = tk.Toplevel(parent)
        self.symbol = symbol
        self.result = None
        
        # Create dialog
        self.top.title(f"Modify {symbol}")
        self.top.transient(parent)
        self.top.grab_set()
        
        # Take Profit
        tp_frame = ttk.Frame(self.top)
        tp_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(
            tp_frame,
            text="Take Profit:"
        ).pack(side=tk.LEFT)
        
        self.tp_var = tk.StringVar(value=str(current_tp))
        ttk.Entry(
            tp_frame,
            textvariable=self.tp_var
        ).pack(side=tk.LEFT, padx=5)
        
        # Stop Loss
        sl_frame = ttk.Frame(self.top)
        sl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(
            sl_frame,
            text="Stop Loss:"
        ).pack(side=tk.LEFT)
        
        self.sl_var = tk.StringVar(value=str(current_sl))
        ttk.Entry(
            sl_frame,
            textvariable=self.sl_var
        ).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            btn_frame,
            text="OK",
            command=self._on_ok
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self._on_cancel
        ).pack(side=tk.LEFT)
        
        # Position dialog
        self.top.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        self.top.wait_window()
        
    def _on_ok(self):
        """Handle OK button click"""
        try:
            tp = float(self.tp_var.get())
            sl = float(self.sl_var.get())
            
            self.result = {
                'tp': tp,
                'sl': sl
            }
            self.top.destroy()
            
        except ValueError:
            messagebox.showerror(
                "Error",
                "Invalid TP/SL values"
            )
            
    def _on_cancel(self):
        """Handle Cancel button click"""
        self.top.destroy()