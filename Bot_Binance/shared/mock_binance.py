class MockBinanceClient:
    def __init__(self):
        self.open_orders = []
        
    def cancel_all_orders(self, symbol=None):
        """
        Hủy tất cả các lệnh đang mở
        Args:
            symbol (str, optional): Cặp giao dịch cụ thể. Nếu None sẽ hủy tất cả các lệnh
        """
        if symbol:
            self.open_orders = [order for order in self.open_orders 
                              if order['symbol'] != symbol]
        else:
            self.open_orders.clear()
        return True
