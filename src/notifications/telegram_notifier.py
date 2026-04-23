
import asyncio
import aiohttp
import threading
from typing import Dict, Callable, List, Optional

from src.core.logger import BotLogger


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, logger: BotLogger,
                 commands_enabled: bool = True, allowed_users: List[str] = None,
                 proxy_url: str = None, proxy_auto_rotate: bool = False):
        self.token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        self.enabled = bool(bot_token and chat_id)
        self.commands_enabled = commands_enabled
        self.allowed_users = set(allowed_users or [])
        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._command_handlers: Dict[str, Callable] = {}
        self._last_update_id = 0
        self._engine_ref = None
        
        # Прокси
        self.proxy_url = proxy_url
        self.proxy_auto_rotate = proxy_auto_rotate
        self._proxy_list: List[str] = []
        self._current_proxy_index = 0
        self._proxy_failures: Dict[str, int] = {}

        if self.enabled:
            self._start_event_loop()

    def set_proxy_list(self, proxies: List[str]):
        """Устанавливает список прокси для ротации."""
        self._proxy_list = proxies
        self._current_proxy_index = 0
        self.logger.info(f"📡 Загружено {len(proxies)} прокси для Telegram")
    
    def _get_next_proxy(self) -> Optional[str]:
        """Возвращает следующий рабочий прокси из списка."""
        if not self._proxy_list:
            return self.proxy_url
        
        # Пропускаем прокси с >3 ошибками
        for _ in range(len(self._proxy_list)):
            proxy = self._proxy_list[self._current_proxy_index]
            self._current_proxy_index = (self._current_proxy_index + 1) % len(self._proxy_list)
            
            if self._proxy_failures.get(proxy, 0) < 3:
                return proxy
        
        return self.proxy_url   # fallback
    
    def _mark_proxy_failure(self, proxy: str):
        """Отмечает ошибку прокси."""
        self._proxy_failures[proxy] = self._proxy_failures.get(proxy, 0) + 1
        if self._proxy_failures[proxy] >= 3:
            self.logger.warning(f"⚠️ Прокси {proxy} заблокирован после 3 ошибок")
    
    def _fetch_proxy_list_from_source(self, source_url: str) -> List[str]:
        """Загружает свежий список прокси из внешнего источника."""
        try:
            import requests
            resp = requests.get(source_url, timeout=10)
            if resp.status_code == 200:
                proxies = [line.strip() for line in resp.text.splitlines() 
                          if line.strip() and not line.startswith('#')]
                return proxies
        except Exception as e:
            self.logger.debug(f"Не удалось загрузить прокси: {e}")
        return []

    def set_engine(self, engine):
        self._engine_ref = engine
        self._register_default_commands()

    def _register_default_commands(self):
        self.register_command("/status", self.cmd_status)
        self.register_command("/balance", self.cmd_balance)
        self.register_command("/close", self.cmd_close)
        self.register_command("/pause", self.cmd_pause)
        self.register_command("/resume", self.cmd_resume)
        self.register_command("/performance", self.cmd_performance)
        self.register_command("/emergency_close_all", self.cmd_emergency_close)
        self.register_command("/help", self.cmd_help)

    def register_command(self, command: str, handler: Callable):
        self._command_handlers[command.lower()] = handler

    def _start_event_loop(self):
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            if self.commands_enabled:
                self._loop.create_task(self._poll_updates())
            self._loop.run_forever()

        threading.Thread(target=run_loop, daemon=True).start()

    async def _get_session(self):
        if self._session is None or self._session.closed:
            connector = None
            proxy = None

            if self.proxy_auto_rotate and self._proxy_list:
                proxy = self._get_next_proxy()
            elif self.proxy_url:
                proxy = self.proxy_url

            if proxy:
                import aiohttp
                connector = aiohttp.TCPConnector()
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    headers={"Proxy-Authorization": f"Basic {proxy}"} if "user:pass" in proxy else {}
                )
                # Для SOCKS5 требуется дополнительная настройка через aiohttp_socks
                if proxy.startswith("socks5://"):
                    try:
                        from aiohttp_socks import ProxyConnector
                        connector = ProxyConnector.from_url(proxy)
                        self._session = aiohttp.ClientSession(connector=connector)
                    except ImportError:
                        self.logger.warning("aiohttp_socks не установлен, прокси SOCKS5 не работает")
                        self._session = aiohttp.ClientSession()
            else:
                self._session = aiohttp.ClientSession()
        return self._session

    async def send_message(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            async with session.post(url, json=payload, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            self.logger.error(f"Telegram error: {e}")
            return False

    def send_sync(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            asyncio.run_coroutine_threadsafe(self.send_message(text), self._loop)
            return True
        except:
            return False

    async def _poll_updates(self):
        while self.enabled:
            try:
                await self._check_updates()
            except Exception:
                pass
            await asyncio.sleep(2)

    async def _check_updates(self):
        session = await self._get_session()
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {"offset": self._last_update_id + 1, "timeout": 5}
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if not data.get("ok"):
                return
            for update in data.get("result", []):
                self._last_update_id = update["update_id"]
                msg = update.get("message")
                if not msg:
                    continue
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if self.allowed_users and chat_id not in self.allowed_users:
                    continue
                await self._handle_command(text, chat_id)

    async def _handle_command(self, text: str, chat_id: str):
        parts = text.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]
        handler = self._command_handlers.get(cmd)
        if handler:
            result = handler(args)
            await self.send_message(result)

    def cmd_status(self, args):
        eng = self._engine_ref
        if not eng:
            return "Движок не активен"
        status = f"🟢 Работает\nБаланс: {eng.balance:.2f} USDT\nПозиций: {len(eng.open_positions)}"
        for sym, pos in eng.open_positions.items():
            pnl = pos.calculate_unrealized_pnl()
            status += f"\n{sym} {pos.side.value} PnL: {pnl:+.2f}"
        return status

    def cmd_balance(self, args):
        eng = self._engine_ref
        if not eng:
            return "Нет данных"
        return f"💰 Баланс: {eng.balance:.2f} USDT\nДоступно: {eng.real_balance:.2f} USDT"

    def cmd_close(self, args):
        if not args:
            return "Укажите символ: /close BTC/USDT"
        symbol = args[0].upper()
        if self._engine_ref and self._engine_ref.close_position(symbol):
            return f"✅ Позиция {symbol} закрыта"
        return f"❌ Не удалось закрыть {symbol}"

    def cmd_pause(self, args):
        if self._engine_ref:
            self._engine_ref._running = False
            return "⏸ Бот приостановлен"
        return "Движок не активен"

    def cmd_resume(self, args):
        if self._engine_ref:
            self._engine_ref._running = True
            return "▶ Бот возобновлён"
        return "Движок не активен"

    def cmd_performance(self, args):
        eng = self._engine_ref
        if not eng:
            return "Нет данных"
        pm = eng.performance_metrics
        return (f"Win Rate: {pm.get_win_rate():.1f}%\n"
                f"PnL сегодня: {pm.get_daily_pnl_percent():.2f}%\n"
                f"Сделок сегодня: {len([t for t in pm.trades if t.get('exit_price')])}")

    def cmd_emergency_close(self, args):
        if self._engine_ref:
            pnl = self._engine_ref.emergency_close_all()
            return f"🛑 Все позиции закрыты. PnL: {pnl:+.2f} USDT"
        return "Движок не активен"

    def cmd_help(self, args):
        return ("/status, /balance, /close SYMBOL, /pause, /resume, "
                "/performance, /emergency_close_all, /help")
