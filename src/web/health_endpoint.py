#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health Endpoint v1.0
HTTP /health, /metrics, /api/status
"""
import logging
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed. Health endpoint disabled. pip install aiohttp")

class HealthEndpoint:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 mode_switcher=None, database=None, position_tracker=None):
        self.host = host
        self.port = port
        self.mode_switcher = mode_switcher
        self.db = database
        self.pt = position_tracker
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    async def start(self):
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not available, health endpoint disabled")
            return
        self.app = web.Application()
        self.app.router.add_get("/health", self._handle_health)
        self.app.router.add_get("/metrics", self._handle_metrics)
        self.app.router.add_get("/api/status", self._handle_status)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self._site = web.TCPSite(self.runner, self.host, self.port)
        await self._site.start()
        logger.info(f"Health endpoint started at http://{self.host}:{self.port}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health endpoint stopped")

    async def _handle_health(self, request: web.Request) -> web.Response:
        healthy = True
        checks = {}
        if self.mode_switcher:
            checks["mode"] = self.mode_switcher.mode_name
            checks["can_trade"] = self.mode_switcher.can_trade()
        else:
            checks["mode"] = "unknown"
        status = "healthy" if healthy else "unhealthy"
        return web.json_response({
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "checks": checks
        })

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        data: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}
        if self.db:
            try:
                data["trade_stats_24h"] = self.db.get_trade_stats(days=1)
                data["trade_stats_7d"] = self.db.get_trade_stats(days=7)
            except Exception as e:
                data["db_error"] = str(e)
        if self.pt:
            try:
                data["open_positions"] = len(self.pt.get_open_positions())
            except Exception as e:
                data["position_error"] = str(e)
        return web.json_response(data)

    async def _handle_status(self, request: web.Request) -> web.Response:
        data = {
            "timestamp": datetime.now().isoformat(),
            "health": "ok",
            "mode": self.mode_switcher.mode_name if self.mode_switcher else "unknown",
            "uptime": None,
        }
        if self.db:
            try:
                data["unresolved_errors"] = len(self.db.get_unresolved_errors())
            except Exception:
                pass
        return web.json_response(data)
