from flask import Flask, render_template_string, jsonify, request, redirect, url_for
from threading import Thread
import time
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.binance_client import binance_client
from src.order_manager import order_manager

app = Flask(__name__)

bot_instance = None
signals_cache = []
positions_cache = {}
balance_cache = {'balance': 0, 'daily_pnl': 0}
trade_history_cache = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance Futures Bot Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: #0d1117; 
            color: #e6edf3;
            min-height: 100vh;
        }
        .header {
            background: #161b22;
            padding: 20px 30px;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #58a6ff; font-size: 24px; }
        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }
        .status-paper { background: #238636; color: #fff; }
        .status-live { background: #da3633; color: #fff; }
        
        .stats-bar {
            display: flex;
            gap: 20px;
            padding: 20px 30px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }
        .stat-card {
            background: #21262d;
            padding: 15px 25px;
            border-radius: 8px;
            min-width: 150px;
        }
        .stat-label { font-size: 12px; color: #8b949e; margin-bottom: 5px; }
        .stat-value { font-size: 24px; font-weight: bold; }
        .stat-value.green { color: #3fb950; }
        .stat-value.red { color: #f85149; }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px 30px;
        }
        .panel {
            background: #161b22;
            border-radius: 8px;
            border: 1px solid #30363d;
            overflow: hidden;
        }
        .panel-header {
            padding: 15px 20px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header h2 { font-size: 16px; }
        .panel-body { padding: 15px; max-height: 400px; overflow-y: auto; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }
        th { background: #21262d; color: #8b949e; font-size: 12px; font-weight: 600; }
        td { font-size: 14px; }
        
        .direction-long { color: #3fb950; font-weight: bold; }
        .direction-short { color: #f85149; font-weight: bold; }
        .score { color: #58a6ff; }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s;
        }
        .btn-primary { background: #238636; color: #fff; }
        .btn-danger { background: #da3633; color: #fff; }
        .btn-warning { background: #d29922; color: #fff; }
        .btn:hover { opacity: 0.9; transform: scale(1.02); }
        
        .actions { display: flex; gap: 10px; }
        .empty-state { color: #8b949e; text-align: center; padding: 40px; }
        
        .log-panel { grid-column: 1 / -1; }
        .log-content {
            font-family: 'Consolas', monospace;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
            background: #0d1117;
            padding: 10px;
            border-radius: 4px;
        }
        
        .refresh-info { font-size: 12px; color: #8b949e; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .updating { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Binance Futures Bot</h1>
        <span class="status-badge {{'status-paper' if mode=='paper' else 'status-live'}}">
            {{ mode.upper() }}
        </span>
    </div>
    
    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-label">Bakiye (USDT)</div>
            <div class="stat-value">{{ "%.2f"|format(balance) }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Günlük PnL</div>
            <div class="stat-value {{'green' if daily_pnl>=0 else 'red'}}">
                {{ "%.2f"|format(daily_pnl) }}%
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Aktif Pozisyon</div>
            <div class="stat-value">{{ positions|length }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Aktif Sinyal</div>
            <div class="stat-value">{{ signals|length }}</div>
        </div>
    </div>
    
    <div class="main-content">
        <div class="panel">
            <div class="panel-header">
                <h2>📊 Sinyaller</h2>
                <div class="refresh-info">{{ last_scan }}</div>
            </div>
            <div class="panel-body">
                {% if signals %}
                <table>
                    <thead>
                        <tr>
                            <th>Koin</th>
                            <th>Yön</th>
                            <th>Entry</th>
                            <th>VWAP</th>
                            <th>TP1</th>
                            <th>TP2</th>
                            <th>SL</th>
                            <th>RSI</th>
                            <th>Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for sig in signals %}
                        <tr>
                            <td>{{ sig.symbol }}</td>
                            <td class="{{'direction-long' if sig.direction=='LONG' else 'direction-short'}}">
                                {{ sig.direction }}
                            </td>
                            <td>{{ "%.4f"|format(sig.entry_price) }}</td>
                            <td>{{ "%.4f"|format(sig.vwap) }}</td>
                            <td class="green">{{ "%.4f"|format(sig.entry_price * 1.03) }}</td>
                            <td class="green">{{ "%.4f"|format(sig.entry_price * 1.05) }}</td>
                            <td class="red">{{ "%.4f"|format(sig.entry_price * 0.98) }}</td>
                            <td>{{ "%.1f"|format(sig.rsi) }}</td>
                            <td class="score">{{ "%.1f"|format(sig.score) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="empty-state">Sinyal bulunamadı</div>
                {% endif %}
            </div>
        </div>
        
        <div class="panel">
            <div class="panel-header">
                <h2>💼 Açık Pozisyonlar</h2>
                <button class="btn btn-danger" onclick="closeAllPositions()">Tümünü Kapat</button>
            </div>
            <div class="panel-body">
                {% if positions %}
                <table>
                    <thead>
                        <tr>
                            <th>Koin</th>
                            <th>Yön</th>
                            <th>Entry</th>
                            <th>TP1</th>
                            <th>TP2</th>
                            <th>SL</th>
                            <th>Güncel</th>
                            <th>PnL</th>
                            <th>İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for sym, pos in positions.items() %}
                        <tr>
                            <td>{{ sym }}</td>
                            <td class="{{'direction-long' if pos.direction=='LONG' else 'direction-short'}}">
                                {{ pos.direction }}
                            </td>
                            <td>{{ "%.4f"|format(pos.entry_price) }}</td>
                            <td class="green">{{ "%.4f"|format(pos.tp1_price) if pos.tp1_price else '-' }}</td>
                            <td class="green">{{ "%.4f"|format(pos.tp2_price) if pos.tp2_price else '-' }}</td>
                            <td class="red">{{ "%.4f"|format(pos.sl_price) }}</td>
                            <td>{{ "%.4f"|format(pos.current_price) if pos.current_price else '-' }}</td>
                            <td class="{{'green' if pos.pnl>=0 else 'red'}}">
                                {{ "%.2f"|format(pos.pnl) }}%
                            </td>
                            <td>
                                <button class="btn btn-danger" onclick="closePosition('{{sym}}')">Kapat</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="empty-state">Açık pozisyon yok</div>
                {% endif %}
            </div>
        </div>
        
        <div class="panel log-panel">
            <div class="panel-header">
                <h2>📜 İşlem Geçmişi</h2>
            </div>
            <div class="panel-body">
                {% if history %}
                <table>
                    <thead>
                        <tr>
                            <th>Zaman</th>
                            <th>Koin</th>
                            <th>Yön</th>
                            <th>Giriş</th>
                            <th>Çıkış</th>
                            <th>PnL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for trade in history %}
                        <tr>
                            <td>{{ trade.time }}</td>
                            <td>{{ trade.symbol }}</td>
                            <td class="{{'direction-long' if trade.direction=='LONG' else 'direction-short'}}">
                                {{ trade.direction }}
                            </td>
                            <td>{{ "%.4f"|format(trade.entry_price) }}</td>
                            <td>{{ "%.4f"|format(trade.exit_price) }}</td>
                            <td class="{{'green' if trade.pnl>=0 else 'red'}}">
                                {{ "%.2f"|format(trade.pnl) }} USDT
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="empty-state">İşlem geçmişi yok</div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function openPosition(symbol, direction) {
            if(confirm(symbol + ' ' + direction + ' pozisyon açılsın mı?')) {
                fetch('/api/open_position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: symbol, direction: direction})
                }).then(() => setTimeout(() => location.reload(), 1000));
            }
        }
        
        function closePosition(symbol) {
            if(confirm(symbol + ' pozisyonu kapatılsın mı?')) {
                fetch('/api/close_position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: symbol})
                }).then(() => setTimeout(() => location.reload(), 1000));
            }
        }
        
        function closeAllPositions() {
            if(confirm('Tüm pozisyonlar kapatılsın mı?')) {
                fetch('/api/close_all', {method: 'POST'})
                    .then(() => setTimeout(() => location.reload(), 1000));
            }
        }
        
        setInterval(() => location.reload(), 30000);
    </script>
</body>
</html>
"""

def run_dashboard(bot):
    global bot_instance
    bot_instance = bot
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

class DashboardServer:
    def __init__(self, bot):
        self.bot = bot
        self.thread = None
    
    def start(self):
        global bot_instance
        bot_instance = self.bot
        self.thread = Thread(target=run_dashboard, args=(self.bot,), daemon=True)
        self.thread.start()

@app.route('/')
def index():
    mode = 'paper' if config.is_paper_mode else 'live'
    return render_template_string(HTML_TEMPLATE,
        mode=mode,
        balance=balance_cache.get('balance', 0),
        daily_pnl=balance_cache.get('daily_pnl', 0),
        positions=positions_cache,
        signals=signals_cache,
        history=trade_history_cache[-10:],
        last_scan="Son tarama: " + (bot_instance._last_scan_time.strftime('%H:%M:%S') if bot_instance and bot_instance._last_scan_time else 'Henüz yok')
    )

@app.route('/api/open_position', methods=['POST'])
def api_open_position():
    data = request.json
    if bot_instance and data.get('symbol'):
        for sig in signals_cache:
            if sig['symbol'] == data['symbol']:
                bot_instance._execute_trade(sig)
                return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/close_position', methods=['POST'])
def api_close_position():
    data = request.json
    if bot_instance and data.get('symbol'):
        if data['symbol'] in bot_instance._active_trades:
            pos = bot_instance._active_trades[data['symbol']]
            order_manager.close_position(data['symbol'], pos['direction'], pos['amount'])
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/close_all', methods=['POST'])
def api_close_all():
    if bot_instance:
        bot_instance._close_all_positions()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/status')
def api_status():
    return jsonify({
        'mode': 'paper' if config.is_paper_mode else 'live',
        'balance': balance_cache.get('balance', 0),
        'daily_pnl': balance_cache.get('daily_pnl', 0),
        'positions': positions_cache,
        'signals': signals_cache,
        'history': trade_history_cache[-10:]
    })

def update_dashboard_data(bot):
    global signals_cache, positions_cache, balance_cache, trade_history_cache
    
    signals_cache = bot._current_signals
    trade_history_cache = bot._trade_history
    
    balance_cache['balance'] = bot._last_balance
    balance_cache['daily_pnl'] = bot._daily_pnl
    
    positions_cache = {}
    for symbol, pos in bot._active_trades.items():
        try:
            ticker = binance_client.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            if pos['direction'] == 'LONG':
                pnl = (current_price - pos['entry_price']) / pos['entry_price'] * 100
            else:
                pnl = (pos['entry_price'] - current_price) / pos['entry_price'] * 100
            pos_copy = pos.copy()
            pos_copy['current_price'] = current_price
            pos_copy['pnl'] = pnl
            positions_cache[symbol] = pos_copy
        except:
            pos_copy = pos.copy()
            pos_copy['current_price'] = None
            pos_copy['pnl'] = 0
            positions_cache[symbol] = pos_copy