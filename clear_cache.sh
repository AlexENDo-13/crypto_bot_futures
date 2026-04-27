#!/bin/bash
echo "=========================================="
echo "  CryptoBot v11 — Cache Cleaner"
echo "=========================================="
echo ""

echo "[1/4] Deleting __pycache__ folders..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "  Done."

echo "[2/4] Deleting .pyc files..."
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "  Done."

echo "[3/4] Deleting .pyo files..."
find . -type f -name "*.pyo" -delete 2>/dev/null
echo "  Done."

echo "[4/4] Deleting old logs..."
find logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null
echo "  Done."

echo ""
echo "=========================================="
echo "  Cache cleaned successfully!"
echo "  Run: python main.py"
echo "=========================================="
