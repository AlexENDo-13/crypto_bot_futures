"""
Web Server Module – Flask приложение для мониторинга и управления.
"""

from flask import Flask, jsonify, render_template_string, request
import threading
import json
from pathlib import Path

from src.core.logger import BotLogger
from src.utils.sqlite_history import SQLiteTradeHistory

app = Flask(__name__)
engine_ref = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>BingX Bot Monitor</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: Arial; background: #0D1117; color: #C9D1D9; padding: 20px; }
.card { background: #161B22; border-radius: 10px; padding: 15px; margin: 10px 0; }
.balance { font-size: 24px; font-weight: bold; color: #3FB950; }
.red { color: #F85149; }
</style>
</head>
<body>
<h1>🤖 BingX Bot</h1>
<div class="card">
  <h2>Баланс</h2>
  <div class="balance" id="balance">--</div>
</div>
<div class="card">
  <h2>Открытые позиции</h2>
  <div id="positions"></div>
</div>
<div class="card">
  <h2>Статус</h2>
  <div id="status">--</div>
</div>
<script>
function refresh() {
  fetch('/api/status').then(r=>r.json()).then(data=>{
    document.getElementById('balance').innerText = data.balance.toFixed(2) + ' USDT';
    let posHtml = '';
    for(let s in data.positions) {
      let p = data.positions[s];
      posHtml += `<div>${s} ${p.side} ${p.qty} @ ${p.entry_price} PnL: ${p.pnl.toFixed(2)}</div>`;
    }
    document.getElementById('positions').innerHTML = posHtml || 'Нет позиций';
    document.getElementById('status').innerText = data.running ? '🟢 Работает' : '🔴 Остановлен';
  });
}
setInterval(refresh, 3000);
refresh();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status():
    if not engine_ref:
        return jsonify({"error": "Engine not initialized"})
    eng = engine_ref
    positions = {}
    for sym, pos in eng.open_positions.items():
        positions[sym] = {
            "side": pos.side.value,
            "qty": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "pnl": pos.calculate_unrealized_pnl()
        }
    return jsonify({
        "balance": eng.balance,
        "real_balance": eng.real_balance,
        "running": eng.running,
        "positions": positions,
        "daily_pnl": eng.performance_metrics.get_daily_pnl_percent(),
        "win_rate": eng.performance_metrics.get_win_rate()
    })

@app.route('/api/trades')
def api_trades():
    db = SQLiteTradeHistory()
    trades = db.get_trades(100)
    db.close()
    return jsonify(trades)

@app.route('/api/command', methods=['POST'])
def api_command():
    if not engine_ref:
        return jsonify({"error": "Engine not initialized"}), 503
    data = request.json
    cmd = data.get('command')
    if cmd == 'pause':
        engine_ref._running = False
        return jsonify({"status": "paused"})
    elif cmd == 'resume':
        engine_ref._running = True
        return jsonify({"status": "resumed"})
    elif cmd == 'scan':
        engine_ref.scan_now()
        return jsonify({"status": "scanning"})
    elif cmd == 'close_all':
        pnl = engine_ref.risk_controller.emergency_close_all(engine_ref.open_positions, engine_ref.order_manager)
        return jsonify({"status": "closed", "pnl": pnl})
    return jsonify({"error": "Unknown command"}), 400

def start_web_server(engine, port=5000):
    global engine_ref
    engine_ref = engine
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False), daemon=True).start()