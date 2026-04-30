"""BingX API Client v2/v3 — Fixed signature, closePosition, timeouts."""
import hmac, hashlib, time, json, logging, asyncio
from typing import Dict, Any, Optional, List
import aiohttp

logger = logging.getLogger(__name__)

class BingXAPIClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://open-api.bingx.com"):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self._connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=False
        )
        self._timeout = aiohttp.ClientTimeout(total=10, connect=5)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout
            )
        return self.session

    def _generate_signature(self, payload: str) -> str:
        return hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _build_params(self, params: Dict[str, Any]) -> str:
        if not params:
            return ""
        return "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "signature")

    async def request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, retries: int = 3) -> Dict[str, Any]:
        params = params or {}
        data = data or {}
        params["timestamp"] = int(time.time() * 1000)
        payload = self._build_params(params)
        if method.upper() == "POST" and data:
            payload += json.dumps(data, separators=(",", ":"))
        signature = self._generate_signature(payload)
        params["signature"] = signature
        url = f"{self.base_url}{endpoint}"

        query_string = self._build_params(params) + f"&signature={signature}"
        if query_string:
            url += "?" + query_string

        headers = {"X-BX-APIKEY": self.api_key, "Content-Type": "application/json"}
        session = await self._get_session()

        logger.debug(f"API {method} {endpoint} | url={url[:120]}...")

        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as resp:
                        text = await resp.text()
                        logger.debug(f"API GET {endpoint} status={resp.status} len={len(text)}")
                        result = json.loads(text)
                else:
                    async with session.post(url, headers=headers, json=data) as resp:
                        text = await resp.text()
                        logger.debug(f"API POST {endpoint} status={resp.status} len={len(text)}")
                        result = json.loads(text)

                if result.get("code") not in (0, None, 200):
                    logger.warning(f"API error {result.get('code')}: {result.get('msg')}")
                return result

            except aiohttp.ClientError as e:
                logger.warning(f"API ClientError (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}, raw: {text[:200]}")
                raise
        return {}

    async def get_account_balance(self) -> Dict[str, Any]:
        logger.info("API: get_account_balance() called")
        result = await self.request("GET", "/openApi/swap/v2/user/balance")
        logger.info(f"API: balance response code={result.get('code')}")
        data = result.get("data", {})
        if isinstance(data, dict) and "balance" in data:
            return data
        elif isinstance(data, list) and len(data) > 0:
            return data[0]
        return {"balance": "0", "availableBalance": "0"}

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        params = {"symbol": symbol} if symbol else {}
        result = await self.request("GET", "/openApi/swap/v2/user/positions", params=params)
        data = result.get("data", {})
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            positions = data.get("positions", [])
            return positions if isinstance(positions, list) else []
        return []

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        params = {"symbol": symbol} if symbol else {}
        result = await self.request("GET", "/openApi/swap/v2/trade/openOrders", params=params)
        data = result.get("data", [])
        return data if isinstance(data, list) else []

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        data = {"symbol": symbol, "orderId": order_id}
        return await self.request("DELETE", "/openApi/swap/v2/trade/order", data=data)

    async def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None, stop_price: Optional[float] = None, leverage: int = 1) -> Dict[str, Any]:
        data = {"symbol": symbol, "side": side.upper(), "positionSide": "LONG" if side.upper() == "BUY" else "SHORT", "type": order_type.upper(), "quantity": str(quantity)}
        if price:
            data["price"] = str(price)
        if stop_price:
            data["stopPrice"] = str(stop_price)
        return await self.request("POST", "/openApi/swap/v2/trade/order", data=data)

    async def close_position(self, symbol: str, position_side: str) -> Dict[str, Any]:
        """FIX: Use closePosition=true for reliable position closing."""
        side = "SELL" if position_side == "LONG" else "BUY"
        data = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": "MARKET",
            "closePosition": "true"
        }
        return await self.request("POST", "/openApi/swap/v2/trade/order", data=data)

    async def set_leverage(self, symbol: str, leverage: int, side: str = "BOTH") -> Dict[str, Any]:
        data = {"symbol": symbol, "leverage": leverage, "side": side}
        return await self.request("POST", "/openApi/swap/v2/trade/leverage", data=data)

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[list]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        result = await self.request("GET", "/openApi/swap/v3/quote/klines", params=params)
        return result.get("data", [])

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        params = {"symbol": symbol}
        result = await self.request("GET", "/openApi/swap/v2/quote/ticker", params=params)
        return result.get("data", {})

    async def get_symbol_info(self) -> Dict[str, Any]:
        return await self.request("GET", "/openApi/swap/v2/quote/contracts")

    async def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        params = {"symbol": symbol}
        result = await self.request("GET", "/openApi/swap/v2/quote/contractInfo", params=params)
        data = result.get("data", {})
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return data if isinstance(data, dict) else {}

    async def get_health(self) -> Dict[str, Any]:
        try:
            result = await self.request("GET", "/openApi/swap/v2/server/time")
            return {"status": "ok", "server_time": result.get("data")}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        if self._connector and not self._connector.closed:
            await self._connector.close()
