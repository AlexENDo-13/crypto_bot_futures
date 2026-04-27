#!/usr/bin/env python3
"""Test BingX signature generation."""
import hashlib
import hmac
import urllib.parse
import time

def test_signature(api_secret, params):
    payload = dict(params)
    payload["timestamp"] = str(int(time.time() * 1000))
    payload["recvWindow"] = "5000"

    sorted_items = sorted(payload.items(), key=lambda x: x[0])
    query_string = urllib.parse.urlencode(sorted_items)

    signature = hmac.new(
        api_secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    payload["signature"] = signature
    return query_string, signature, payload

if __name__ == "__main__":
    # Example from BingX docs
    secret = "your_api_secret_here"
    params = {"symbol": "BTC-USDT", "side": "BUY", "positionSide": "LONG", "type": "MARKET", "quantity": "0.01"}

    qs, sig, full = test_signature(secret, params)
    print(f"Query string: {qs}")
    print(f"Signature: {sig}")
    print(f"Full payload: {full}")
