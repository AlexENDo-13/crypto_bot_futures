#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BingX API Tester v1.0
Standalone script to test API keys, endpoints, signatures, and trading.
"""
import asyncio
import hashlib
import hmac
import time
import urllib.parse
import json
from typing import Optional, Dict, Any

import aiohttp


class BingXTester:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://open-api.bingx.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self.results = []

    async def _get_session(self):
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-BX-APIKEY": self.api_key,
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _sign_v2(self, timestamp: str) -> str:
        """BingX v2: HMAC(secret, timestamp + apiKey)"""
        msg = timestamp + self.api_key
        return hmac.new(self.api_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def _sign_v3(self, params: dict) -> str:
        """BingX v3: HMAC(secret, query_string)"""
        qs = urllib.parse.urlencode(sorted(params.items()))
        return hmac.new(self.api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()

    async def _request(self, method: str, endpoint: str, params: dict = None, 
                       signed: bool = False, v2_sig: bool = False) -> dict:
        params = params or {}
        if signed:
            ts = str(int(time.time() * 1000))
            params["timestamp"] = ts
            params["apiKey"] = self.api_key
            if v2_sig:
                params["signature"] = self._sign_v2(ts)
            else:
                params["signature"] = self._sign_v3(params)

        url = f"{self.base_url}{endpoint}"
        try:
            session = await self._get_session()
            if method == "GET":
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    return await r.json(content_type=None)
            elif method == "POST":
                async with session.post(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    return await r.json(content_type=None)
            elif method == "DELETE":
                async with session.delete(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    return await r.json(content_type=None)
        except Exception as e:
            return {"code": -1, "msg": str(e)}

    def _log(self, test: str, success: bool, detail: str, data: Any = None):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} | {test}")
        if detail:
            print(f"       {detail}")
        if data and not success:
            print(f"       Response: {json.dumps(data, indent=2)[:300]}")
        self.results.append({"test": test, "success": success, "detail": detail, "data": data})

    async def run_all_tests(self):
        print("=" * 60)
        print("  BINGX API TESTER v1.0")
        print("=" * 60)
        print(f"  API Key: {self.api_key[:4]}...{self.api_key[-4:]}")
        print(f"  Base URL: {self.base_url}")
        print("=" * 60)

        # ── 1. CREDENTIALS CHECK ──
        print("\n📋 1. CREDENTIALS CHECK")
        if not self.api_key or not self.api_secret:
            self._log("Credentials present", False, "API key or secret is empty!")
            return
        self._log("Credentials present", True, f"Key length: {len(self.api_key)}, Secret length: {len(self.api_secret)}")

        # ── 2. PUBLIC API TESTS ──
        print("\n🌐 2. PUBLIC API (no signature)")

        # Test klines
        r = await self._request("GET", "/openApi/swap/v3/quote/klines", 
                                {"symbol": "BTC-USDT", "interval": "15m", "limit": 5})
        ok = r.get("code") == 0 and "data" in r and len(r["data"]) > 0
        self._log("Klines (v3)", ok, f"Got {len(r.get('data', []))} candles" if ok else r.get("msg", "Unknown"), r)

        # Test ticker
        r = await self._request("GET", "/openApi/swap/v3/quote/ticker", {"symbol": "BTC-USDT"})
        ok = r.get("code") == 0 and "data" in r
        price = r.get("data", {}).get("lastPrice", "N/A") if ok else "N/A"
        self._log("Ticker (v3)", ok, f"BTC price: {price}" if ok else r.get("msg", "Unknown"), r)

        # Test all tickers
        r = await self._request("GET", "/openApi/swap/v3/quote/ticker", {})
        ok = r.get("code") == 0 and "data" in r
        count = len(r.get("data", [])) if ok else 0
        self._log("All Tickers (v3)", ok, f"Got {count} tickers" if ok else r.get("msg", "Unknown"), r)

        # Test contracts
        r = await self._request("GET", "/openApi/swap/v3/quote/contracts", {})
        ok = r.get("code") == 0 and "data" in r
        count = len(r.get("data", [])) if ok else 0
        self._log("Contracts (v3)", ok, f"Got {count} contracts" if ok else r.get("msg", "Unknown"), r)

        # ── 3. SIGNED API TESTS ──
        print("\n🔐 3. SIGNED API (with signature)")

        # Test balance with v2 signature
        r = await self._request("GET", "/openApi/swap/v2/user/balance", {}, signed=True, v2_sig=True)
        ok = r.get("code") == 0 and "data" in r
        balance = r.get("data", {}).get("balance", r.get("data", {}).get("totalEquity", "N/A")) if ok else "N/A"
        self._log("Balance (v2 sig)", ok, f"Balance: {balance}" if ok else r.get("msg", "Unknown"), r)

        # Test balance with v3 signature (fallback)
        if not ok:
            r = await self._request("GET", "/openApi/swap/v2/user/balance", {}, signed=True, v2_sig=False)
            ok = r.get("code") == 0 and "data" in r
            self._log("Balance (v3 sig fallback)", ok, f"Balance: {r.get('data', {}).get('balance', 'N/A')}" if ok else r.get("msg", ""), r)

        # Test positions
        r = await self._request("GET", "/openApi/swap/v2/user/positions", {}, signed=True, v2_sig=True)
        ok = r.get("code") == 0 and "data" in r
        positions = r.get("data", []) if ok else []
        if isinstance(positions, dict) and "positions" in positions:
            positions = positions["positions"]
        self._log("Positions (v2)", ok, f"Open positions: {len(positions)}" if ok else r.get("msg", "Unknown"), r)

        # Test leverage setting
        r = await self._request("POST", "/openApi/swap/v2/trade/leverage", 
                                {"symbol": "BTC-USDT", "leverage": 5, "positionSide": "BOTH"}, 
                                signed=True, v2_sig=True)
        ok = r.get("code") == 0
        self._log("Set Leverage (v2)", ok, "Leverage set to 5x" if ok else r.get("msg", "Unknown"), r)

        # ── 4. TRADING TEST (optional) ──
        print("\n💰 4. TRADING TEST (optional)")
        print("  ⚠️  This will place a REAL order if demo_mode=False")

        # Get current price first
        ticker = await self._request("GET", "/openApi/swap/v3/quote/ticker", {"symbol": "BTC-USDT"})
        price = float(ticker.get("data", {}).get("lastPrice", 0)) if ticker.get("code") == 0 else 0

        if price > 0:
            print(f"  Current BTC price: {price}")
            print("  Skipping auto-trade test. Use manual test below if needed.")
        else:
            self._log("Price fetch", False, "Cannot get price for trading test", ticker)

        # ── 5. SUMMARY ──
        print("\n" + "=" * 60)
        print("  TEST SUMMARY")
        print("=" * 60)
        passed = sum(1 for r in self.results if r["success"])
        failed = sum(1 for r in self.results if not r["success"])
        print(f"  Total: {len(self.results)} | Passed: {passed} | Failed: {failed}")

        if failed > 0:
            print("\n  Failed tests:")
            for r in self.results:
                if not r["success"]:
                    print(f"    - {r['test']}: {r['detail']}")

        print("=" * 60)

        if passed >= 3 and any(r["test"] == "Balance (v2 sig)" and r["success"] for r in self.results):
            print("\n  🎉 API keys are WORKING! You can use them in the bot.")
        elif passed >= 2:
            print("\n  ⚠️  Partially working. Check failed tests above.")
            print("     If Balance fails but Ticker works — check signature format.")
        else:
            print("\n  ❌ API keys NOT working. Check:")
            print("     1. Key has Futures/Perpetual permissions")
            print("     2. Secret was copied fully (shown once at creation)")
            print("     3. IP whitelist includes your current IP")
            print("     4. Key is not expired or revoked")

        await self._close()
        return self.results


async def main():
    import os

    print("BingX API Key Tester")
    print("=" * 60)

    # Try to read from config first
    api_key = os.getenv("BINGX_API_KEY", "")
    api_secret = os.getenv("BINGX_API_SECRET", "")

    if not api_key or not api_secret:
        try:
            with open("config/bot_config.json", "r") as f:
                cfg = json.load(f)
                api_key = cfg.get("api_key", "")
                api_secret = cfg.get("api_secret", "")
        except Exception:
            pass

    if not api_key:
        api_key = input("Enter BingX API Key: ").strip()
    if not api_secret:
        api_secret = input("Enter BingX API Secret: ").strip()

    if not api_key or not api_secret:
        print("❌ API key and secret are required!")
        return

    tester = BingXTester(api_key=api_key, api_secret=api_secret)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
