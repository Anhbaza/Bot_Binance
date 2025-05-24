class MockBinanceClient:
    def __init__(self):
        self.open_orders = {}
        self._is_testnet = True

    def get_server_time(self):
        return {'serverTime': int(datetime.utcnow().timestamp() * 1000)}

    def cancel_all_orders(self, symbol=None):
        """Cancel all open orders for a symbol or all symbols"""
        try:
            if symbol:
                if symbol in self.open_orders:
                    self.open_orders[symbol] = []
            else:
                self.open_orders.clear()
            return True
        except Exception:
            return False