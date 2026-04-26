import requests
import hmac
import hashlib
import time

API_KEY = "CdSWeAc3nivQLxvBqbX40cGwGi5P9TLboVUl2VvoYQfYMfM8it9WbGCwmtbZG77pYl3rzTVx7hkxTgwkw"
API_SECRET = "JmF7d48wrEfkkF1WWLS2OSSJmVVvtyzb5mnVmweM2MLqKAyYUwoTJT8FG6SZ8A08qv2Rb6RUZycnGe43PQ"
BASE_URL = "https://open-api.bingx.com"

def _sign(method, path, params):
    """Подпись: query_string (для GET и POST одинаково)"""
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return query_string + f"&signature={signature}"

def request_api(method, path, params=None):
    """Универсальная функция запроса"""
    if params is None:
        params = {}
    params['timestamp'] = str(int(time.time() * 1000))
    query = _sign(method, path, params)
    url = f"{BASE_URL}{path}?{query}"
    headers = {'X-BX-APIKEY': API_KEY}
    resp = requests.request(method, url, headers=headers)
    return resp.json()

# ---------- Баланс до сделки ----------
print("=== БАЛАНС ДО СДЕЛКИ ===")
print(request_api('GET', '/openApi/swap/v2/user/balance'))

# ---------- Открываем LONG 1 XRP ----------
print("\n=== ОТКРЫВАЕМ LONG 1 XRP-USDT ===")
open_params = {
    'symbol': 'XRP-USDT',
    'side': 'BUY',
    'positionSide': 'LONG',
    'type': 'MARKET',
    'quantity': '1',   # 1 XRP
}
open_res = request_api('POST', '/openApi/swap/v2/trade/order', open_params)
print(open_res)

if open_res.get('code') == 0:
    time.sleep(3)   # даём бирже обработать позицию
    print("\n=== ЗАКРЫВАЕМ ПОЗИЦИЮ ===")
    close_params = {
        'symbol': 'XRP-USDT',
        'side': 'SELL',
        'positionSide': 'LONG',
        'type': 'MARKET',
        'quantity': '1',          # объём, который хотим закрыть
        'closePosition': 'true',  # флаг закрытия позиции
    }
    close_res = request_api('POST', '/openApi/swap/v2/trade/order', close_params)
    print(close_res)
else:
    print("⚠️  Не удалось открыть позицию. Возможно, минимальный лот > 1 XRP. Попробуйте изменить quantity на '10'.")

# ---------- Баланс после сделки ----------
print("\n=== БАЛАНС ПОСЛЕ ЗАКРЫТИЯ ===")
print(request_api('GET', '/openApi/swap/v2/user/balance'))
