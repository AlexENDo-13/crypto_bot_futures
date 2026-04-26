#!/usr/bin/env python3
"""
Standalone BingX API Test
Minimal script to test API connectivity and signature
"""
import time
import hmac
import hashlib
import urllib.parse
import requests

API_KEY = "CdSWeAc3nivQLxvBqbX40cGwGi5P9TLboVUl2VvoYQfYMfM8it9WbGCwmtbZG77pYl3rzTVx7hkxTgwkw"
API_SECRET = "JmF7d48wrEfkkF1WWLS2OSSJmVVvtyzb5mnVmweM2MLqKAyYUwoTJT8FG6SZ8A08qv2Rb6RUZycnGe43PQ"

BASE_URL = "https://open-api.bingx.com"

def sign(secret, params):
    """BingX v2 signature"""
    query = urllib.parse.urlencode(sorted(params.items()))
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return query + f"&signature={sig}"

def test_balance():
    params = {
        "timestamp": str(int(time.time() * 1000)),
        "recvWindow": "5000"
    }
    query = sign(API_SECRET, params)
    url = f"{BASE_URL}/openApi/swap/v2/user/balance?{query}"
    headers = {"X-BX-APIKEY": API_KEY}

    print(f"URL: {url[:120]}...")
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    return resp.json()

def test_positions():
    params = {
        "timestamp": str(int(time.time() * 1000)),
        "recvWindow": "5000"
    }
    query = sign(API_SECRET, params)
    url = f"{BASE_URL}/openApi/swap/v2/user/positions?{query}"
    headers = {"X-BX-APIKEY": API_KEY}

    resp = requests.get(url, headers=headers, timeout=10)
    print(f"\nPositions Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    return resp.json()

def test_klines():
    params = {
        "symbol": "BTC-USDT",
        "interval": "15m",
        "limit": "5"
    }
    url = f"{BASE_URL}/openApi/swap/v2/quote/klines"
    resp = requests.get(url, params=params, timeout=10)
    print(f"\nKlines Status: {resp.status_code}")
    data = resp.json()
    if data.get("code") == 0:
        print(f"Klines received: {len(data.get('data', []))} candles")
    else:
        print(f"Response: {resp.text[:300]}")
    return data

if __name__ == "__main__":
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please set API_KEY and API_SECRET variables first!")
        exit(1)

    print("Testing BingX API...")
    print("=" * 50)

    print("\n1. Testing Balance (signed)...")
    test_balance()

    print("\n2. Testing Positions (signed)...")
    test_positions()

    print("\n3. Testing Klines (public)...")
    test_klines()
