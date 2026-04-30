#!/usr/bin/env python3
"""BingX API Client v2 — Fixed asyncio loop handling."""
import asyncio
import aiohttp
import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger("BingXAPI")

class BingXAPIClient:
    BASE_URL = "https://open-api.bingx.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy session creation in correct event loop."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-BX-APIKEY": self.api_key}
            )
        return self._session
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for BingX v2."""
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = True) -> Dict[str, Any]:
        """Make authenticated request to BingX API."""
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        
        if signed:
            params["signature"] = self._generate_signature(params)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            session = await self._get_session()
            
            if method == "GET":
                async with session.get(url, params=params) as response:
                    data = await response.json()
            elif method == "POST":
                async with session.post(url, data=params) as response:
                    data = await response.json()
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if data.get("code") != 0:
                logger.error(f"API error: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"code": -1, "msg": str(e)}
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """Get futures account balance."""
        result = await self._request("GET", "/openApi/v2/account/balance", signed=True)
        
        if result.get("code") == 0:
            data = result.get("data", {})
            # Handle nested dict structure
            if isinstance(data, dict) and "balance" in data:
                balance_data = data["balance"]
                if isinstance(balance_data, dict):
                    return {
                        "total_equity": float(balance_data.get("balance", 0)),
                        "available_balance": float(balance_data.get("availableMargin", 0)),
                        "used": float(balance_data.get("usedMargin", 0)),
                        "equity": float(balance_data.get("equity", 0)),
                        "unrealizedProfit": float(balance_data.get("unrealizedProfit", 0))
                    }
            # Fallback for direct values
            return {
                "total_equity": float(data.get("balance", data.get("totalEquity", 0))),
                "available_balance": float(data.get("availableMargin", data.get("available", 0))),
                "used": float(data.get("usedMargin", 0)),
                "equity": float(data.get("equity", 0)),
                "unrealizedProfit": float(data.get("unrealizedProfit", 0))
        }
        return {"total_equity": 0, "available_balance": 0, "used": 0, "equity": 0}
    
    async def get_positions(self, symbol: Optional[str] = None) -> list:
        """Get open positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        result = await self._request("GET", "/openApi/v2/position", params=params, signed=True)
        if result.get("code") == 0:
            data = result.get("data", [])
            return data if isinstance(data, list) else [data] if data else []
        return []
    
    async def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        """Get symbol specifications."""
        result = await self._request("GET", "/openApi/v2/market/symbol", 
                                   params={"symbol": symbol}, signed=False)
        if result.get("code") == 0:
            return result.get("data", {})
        return {}
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: Optional[float] = None,
                         stop_loss: Optional[float] = None,
                         take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Place futures order."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price:
            params["price"] = price
        if stop_loss:
            params["stopLoss"] = stop_loss
        if take_profit:
            params["takeProfit"] = take_profit
        
        return await self._request("POST", "/openApi/v2/order", params=params, signed=True)
    
    async def close_position(self, symbol: str, position_side: str, 
                            quantity: Optional[float] = None) -> Dict[str, Any]:
        """Close position by position side."""
        params = {
            "symbol": symbol,
            "positionSide": position_side,
        }
        if quantity:
            params["quantity"] = quantity
        
        return await self._request("POST", "/openApi/v2/position/close", params=params, signed=True)
    
    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> Dict[str, Any]:
        """Set leverage for symbol."""
        params = {
            "symbol": symbol,
            "leverage": leverage,
            "positionSide": position_side,
        }
        return await self._request("POST", "/openApi/v2/leverage", params=params, signed=True)
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker data."""
        result = await self._request("GET", "/openApi/v2/ticker", 
                                   params={"symbol": symbol}, signed=False)
        if result.get("code") == 0:
            return result.get("data", {})
        return {}
    
    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> list:
        """Get kline/candlestick data."""
        result = await self._request("GET", "/openApi/v2/market/kline",
                                   params={"symbol": symbol, "interval": interval, "limit": limit},
                                   signed=False)
        if result.get("code") == 0:
            return result.get("data", [])
        return []
    
    async def get_symbol_info(self) -> list:
        """Get all trading symbols."""
        result = await self._request("GET", "/openApi/v2/market/symbols", signed=False)
        if result.get("code") == 0:
            data = result.get("data", [])
            return data if isinstance(data, list) else []
        return []
    
    def get_health(self) -> Dict[str, Any]:
        """Get client health status."""
        return {
            "session_active": self._session is not None and not self._session.closed,
            "api_key_configured": bool(self.api_key),
        }
    
    async def close(self):
        """Close session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
