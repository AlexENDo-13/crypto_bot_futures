#!/usr/bin/env python3
"""Main Window — Fixed for proper api_client/settings injection."""
import sys
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QTableWidget, 
    QTableWidgetItem, QTabWidget, QStatusBar
)
from PyQt5.QtCore import QTimer, pyqtSignal, QObject

class LogSignal(QObject):
    log_received = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self, api_client, settings, engine=None, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
        self.settings = settings
        self.engine = engine
        self.log_signal = LogSignal()
        
        self.setWindowTitle("CryptoBot Futures v10.0")
        self.setMinimumSize(1200, 800)
        
        self._setup_ui()
        self._setup_timers()
        
        self.log_signal.log_received.connect(self._append_log)
    
    def _setup_ui(self):
        """Setup user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Top controls
        controls = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Start")
        self.btn_start.clicked.connect(self._on_start)
        controls.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.clicked.connect(self._on_stop)
        controls.addWidget(self.btn_stop)
        
        self.btn_emergency = QPushButton("🚨 Emergency Close")
        self.btn_emergency.clicked.connect(self._on_emergency)
        controls.addWidget(self.btn_emergency)
        
        self.lbl_status = QLabel("Status: STOPPED")
        controls.addWidget(self.lbl_status)
        
        self.lbl_balance = QLabel("Balance: $0.00")
        controls.addWidget(self.lbl_balance)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Positions tab
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Qty", "Entry", "Current", "PnL", "SL", "TP"
        ])
        self.tabs.addTab(self.positions_table, "Positions")
        
        # Logs tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.tabs.addTab(self.log_text, "Logs")
        
        # Signals tab
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(6)
        self.signals_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Direction", "Confidence", "Entry Type", "Price"
        ])
        self.tabs.addTab(self.signals_table, "Signals")
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _setup_timers(self):
        """Setup update timers."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(1000)  # 1 second
    
    def _update_ui(self):
        """Update UI with engine data."""
        if not self.engine:
            return
        
        try:
            # Update status
            if self.engine.is_running():
                self.lbl_status.setText("Status: RUNNING")
                self.lbl_status.setStyleSheet("color: green;")
            else:
                self.lbl_status.setText("Status: STOPPED")
                self.lbl_status.setStyleSheet("color: red;")
            
            # Update balance
            stats = self.engine.get_stats()
            balance = stats.get("balance", 0)
            self.lbl_balance.setText(f"Balance: ${balance:.2f}")
            
            # Update positions
            positions = self.engine.get_open_positions()
            self.positions_table.setRowCount(len(positions))
            for i, pos in enumerate(positions):
                self.positions_table.setItem(i, 0, QTableWidgetItem(str(pos.get("symbol", ""))))
                self.positions_table.setItem(i, 1, QTableWidgetItem(str(pos.get("side", ""))))
                self.positions_table.setItem(i, 2, QTableWidgetItem(f"{pos.get('quantity', 0):.4f}"))
                self.positions_table.setItem(i, 3, QTableWidgetItem(f"{pos.get('entry_price', 0):.4f}"))
                self.positions_table.setItem(i, 4, QTableWidgetItem(f"{pos.get('current_price', 0):.4f}"))
                self.positions_table.setItem(i, 5, QTableWidgetItem(f"{pos.get('unrealized_pnl', 0):.2f}"))
                self.positions_table.setItem(i, 6, QTableWidgetItem(f"{pos.get('stop_loss', 0):.4f}"))
                self.positions_table.setItem(i, 7, QTableWidgetItem(f"{pos.get('take_profit', 0):.4f}"))
            
            # Update status bar
            health = self.engine.get_health()
            self.status_bar.showMessage(
                f"Loop: {health.get('loop_count', 0)} | "
                f"API Errors: {health.get('api_errors', 0)} | "
                f"Latency: {health.get('api_latency_ms', 0):.0f}ms"
            )
            
        except Exception as e:
            self._append_log(f"UI update error: {e}")
    
    def _on_start(self):
        """Start engine."""
        if self.engine and not self.engine.is_running():
            # Engine runs in separate thread, just ensure it's started
            self._append_log("Engine start requested...")
    
    def _on_stop(self):
        """Stop engine gracefully."""
        if self.engine:
            import asyncio
            asyncio.run_coroutine_threadsafe(self.engine.stop(), asyncio.get_event_loop())
            self._append_log("Engine stop requested...")
    
    def _on_emergency(self):
        """Emergency close all positions."""
        if self.engine:
            self._append_log("🚨 EMERGENCY CLOSE ALL POSITIONS!")
            # Use engine's emergency close
            if hasattr(self.engine, 'emergency_close'):
                import asyncio
                asyncio.run_coroutine_threadsafe(self.engine.emergency_close(), asyncio.get_event_loop())
    
    def _append_log(self, message: str):
        """Append message to log."""
        self.log_text.append(message)
    
    def log(self, message: str):
        """Thread-safe log."""
        self.log_signal.log_received.emit(str(message))
    
    def closeEvent(self, event):
        """Handle window close."""
        if self.engine:
            import asyncio
            try:
                asyncio.run_coroutine_threadsafe(self.engine.stop(), asyncio.get_event_loop())
            except:
                pass
        event.accept()
