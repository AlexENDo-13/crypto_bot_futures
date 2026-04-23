#!/usr/bin/env python3
from aiohttp import web

class WebServer:
    def __init__(self, engine, port=5000):
        self.engine = engine; self.port = port
        self.app = web.Application()
        self.app.router.add_get("/api/stats", self.handle_stats)
        self.app.router.add_get("/api/positions", self.handle_positions)
        self.app.router.add_get("/api/history", self.handle_history)
        self.app.router.add_get("/api/health", self.handle_health)
        self.runner = None
    async def handle_stats(self, request):
        if self.engine: return web.json_response(self.engine.get_stats())
        return web.json_response({"error": "Engine not running"})
    async def handle_positions(self, request):
        if self.engine: return web.json_response(self.engine.get_open_positions())
        return web.json_response([])
    async def handle_history(self, request):
        if self.engine: return web.json_response(self.engine.get_closed_positions())
        return web.json_response([])
    async def handle_health(self, request):
        if self.engine: return web.json_response(self.engine.get_health())
        return web.json_response({"status": "stopped"})
    async def start(self):
        self.runner = web.AppRunner(self.app); await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port); await site.start()
    async def stop(self):
        if self.runner: await self.runner.cleanup()
