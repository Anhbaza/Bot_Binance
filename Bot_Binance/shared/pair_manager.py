from typing import List, Set
import asyncio
from datetime import datetime

class PairManager:
    def __init__(self):
        self._selected_pairs: Set[str] = set()
        self._scan_mode = "all"  # "all" hoặc "selected"
        self._lock = asyncio.Lock()
        
    async def set_scan_mode(self, mode: str, pairs: List[str] = None):
        """Thiết lập chế độ quét"""
        async with self._lock:
            self._scan_mode = mode
            if mode == "selected" and pairs:
                self._selected_pairs = set(pairs)
            elif mode == "all":
                self._selected_pairs.clear()
                
    async def get_pairs_to_scan(self) -> List[str]:
        """Lấy danh sách cặp cần quét"""
        async with self._lock:
            if self._scan_mode == "all":
                return []  # Scanner sẽ quét tất cả
            return list(self._selected_pairs)
            
    async def is_pair_monitored(self, pair: str) -> bool:
        """Kiểm tra xem một cặp có đang được theo dõi không"""
        async with self._lock:
            return (self._scan_mode == "all" or 
                   pair in self._selected_pairs)
