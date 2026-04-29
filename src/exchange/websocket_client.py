"""BingX WebSocket client."""
import asyncio, json, logging
from typing import Callable, Optional
import websockets

logger = logging.getLogger(__name__)

class BingXWebSocketClient:
    def __init__(self, on_message: Optional[Callable] = None):
        self.url = "wss://open-api-ws.bingx.com/market"
        self.on_message = on_message
        self.ws = None
        self._running = False
        self._subscriptions = []

    async def connect(self):
        try:
            self.ws = await websockets.connect(self.url)
            self._running = True
            logger.info("WebSocket connected")
            for sub in self._subscriptions:
                await self.subscribe(sub)
            await self._listen()
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self._running = False

    async def _listen(self):
        while self._running and self.ws:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=30)
                data = json.loads(msg)
                if self.on_message:
                    await self.on_message(data)
            except asyncio.TimeoutError:
                try:
                    await self.ws.ping()
                except:
                    break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket closed")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        self._running = False

    async def subscribe(self, channel: str):
        if channel not in self._subscriptions:
            self._subscriptions.append(channel)
        if self.ws and self._running:
            await self.ws.send(json.dumps({"id": channel, "reqType": "sub", "dataType": channel}))
            logger.info(f"Subscribed to {channel}")

    async def close(self):
        self._running = False
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket disconnected")
