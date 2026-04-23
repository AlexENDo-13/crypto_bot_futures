class PerformanceMetrics:
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self.daily_start_balance = 0
        self.weekly_start_balance = 0

    def get_daily_pnl_percent(self):
        return 0.0

    def get_weekly_pnl_percent(self):
        return 0.0

    def record_trade(self, symbol, price, side, strategy=""):
        pass

    def record_close(self, pnl, balance, strategy=None):
        pass
