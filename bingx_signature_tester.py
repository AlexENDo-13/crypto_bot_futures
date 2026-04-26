#!/usr/bin/env python3
"""
BingX API Signature Tester v2.1 (FIXED)
Tests multiple signature algorithms to find the correct one for your keys.
"""
import sys
import time
import hmac
import hashlib
import urllib.parse
import requests


def test_signature_v1(api_key, api_secret, endpoint, params):
    """Method + path + query_string (old BingX v1)"""
    query = urllib.parse.urlencode(sorted(params.items()))
    payload = f"GET{endpoint}?{query}"
    sig = hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return sig, query + f"&signature={sig}"


def test_signature_v2(api_key, api_secret, params):
    """BingX v2: HMAC_SHA256(secret, query_string) only"""
    query = urllib.parse.urlencode(sorted(params.items()))
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return sig, query + f"&signature={sig}"


def test_signature_v2_no_encode(api_key, api_secret, params):
    """BingX v2 without URL encoding (raw &key=value)"""
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return sig, query + f"&signature={sig}"


def test_signature_v2_with_key(api_key, api_secret, params):
    """BingX v2 with apiKey IN query string (some docs mention this)"""
    params_with_key = dict(params)
    params_with_key["apiKey"] = api_key
    query = urllib.parse.urlencode(sorted(params_with_key.items()))
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return sig, query + f"&signature={sig}"


def test_signature_v2_post_style(api_key, api_secret, params):
    """BingX POST style: body as JSON string"""
    import json
    body = json.dumps(params, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(api_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return sig, body


def test_signature_binance_style(api_key, api_secret, params):
    """Binance style: query_string only, no method/path"""
    query = urllib.parse.urlencode(sorted(params.items()))
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return sig, query + f"&signature={sig}"


def make_request(base_url, endpoint, query_string, api_key):
    """Make GET request with signature in query"""
    url = f"{base_url}{endpoint}?{query_string}"
    headers = {"X-BX-APIKEY": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 70)
    print("BingX API Signature Tester v2.1")
    print("=" * 70)
    print()

    api_key = input("Enter BingX API Key: ").strip()
    api_secret = input("Enter BingX API Secret: ").strip()

    if not api_key or not api_secret:
        print("ERROR: API Key and Secret are required!")
        sys.exit(1)

    base_url = "https://open-api.bingx.com"
    endpoint = "/openApi/swap/v2/user/balance"

    # Test parameters
    timestamp = str(int(time.time() * 1000))
    params = {
        "timestamp": timestamp,
        "recvWindow": "5000"
    }

    methods = [
        ("BingX v2 (query_string only)", test_signature_v2),
        ("BingX v2 (no URL encode)", test_signature_v2_no_encode),
        ("BingX v2 (with apiKey in query)", test_signature_v2_with_key),
        ("BingX v1 (method+path+query)", test_signature_v1),
        ("BingX POST (JSON body)", test_signature_v2_post_style),
        ("Binance style", test_signature_binance_style),
    ]

    print()
    print("Testing signature methods...")
    print("-" * 70)

    working_methods = []

    for name, method in methods:
        print(f"\n>>> Testing: {name}")
        try:
            sig, query_or_body = method(api_key, api_secret, params)
            print(f"    Signature: {sig[:32]}...")
            print(f"    Query: {query_or_body[:80]}...")

            if "POST" in name or "JSON" in name:
                print(f"    [SKIP] POST style not applicable for GET")
                continue

            result = make_request(base_url, endpoint, query_or_body, api_key)
            code = result.get("code", result.get("status", -1))

            if code == 0 or code == 200 or code == "0":
                print(f"    [SUCCESS] Code={code}")
                print(f"    Response: {str(result)[:200]}")
                working_methods.append((name, method))
            elif code == 100001:
                print(f"    [SIGNATURE MISMATCH] Code={code}")
            elif code == 100400:
                print(f"    [ENDPOINT NOT FOUND] Code={code}")
            else:
                print(f"    [ERROR] Code={code}: {result.get('msg', 'Unknown')}")

        except Exception as e:
            print(f"    [EXCEPTION] {e}")

    print()
    print("=" * 70)
    print("RESULTS:")
    print("=" * 70)

    if working_methods:
        print(f"\nFOUND {len(working_methods)} working method(s):")
        for name, _ in working_methods:
            print(f"   - {name}")
    else:
        print("\nNO working methods found!")
        print("\nPossible issues:")
        print("   1. Wrong API key/secret")
        print("   2. API key does not have Futures permissions")
        print("   3. IP restriction on API key")
        print("   4. Clock sync issue (timestamp too old/new)")
        print("   5. Wrong endpoint URL")
        print()
        print("Try:")
        print("   - Generate new API keys with Futures permissions")
        print("   - Check if your IP is whitelisted")
        print("   - Verify system time is correct")

    print()
    print("=" * 70)
    print("Manual test with curl (v2 method):")
    print("=" * 70)

    sig, query = test_signature_v2(api_key, api_secret, params)
    key_short = api_key[:10] + "..."
    print("curl -H \"X-BX-APIKEY: " + key_short + "\" \\")
    print("  \"" + base_url + endpoint + "?" + query + "\"")
    print()


if __name__ == "__main__":
    main()
