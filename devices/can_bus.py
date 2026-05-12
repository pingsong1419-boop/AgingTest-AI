import time
import random
from typing import Optional, Dict

class CANBus:
    """
    CAN 总线通讯驱动 (Mock/适配器)
    后期可对接 python-can, ZLG SDK 或 Kvaser
    """
    def __init__(self, channel: str = "CAN1", bitrate: int = 500000):
        self.channel = channel
        self.bitrate = bitrate
        self.is_connected = False
        
    def connect(self) -> bool:
        print(f"[CAN] 正在初始化 {self.channel} @ {self.bitrate}bps...")
        time.sleep(0.5)
        self.is_connected = True
        return True
        
    def disconnect(self):
        self.is_connected = False
        print(f"[CAN] {self.channel} 已断开")

    def send_frame(self, arb_id: int, data: list, is_extended: bool = False, logger=None) -> bool:
        """发送 CAN 帧"""
        if not self.is_connected:
            if logger: logger(f"[COM: {self.channel}] 错误: CAN未连接")
            return False
        
        hex_data = " ".join([f"{b:02X}" for b in data])
        msg = f"[COM: {self.channel}] [TX] ID: 0x{arb_id:X} Data: [{hex_data}]"
        print(msg)
        if logger: logger(msg)
        return True

    def read_frame(self, arb_id: int, timeout: float = 1.0, logger=None) -> Optional[list]:
        """读取指定 ID 的 CAN 帧 (模拟)"""
        if not self.is_connected:
            if logger: logger(f"[COM: {self.channel}] 错误: CAN未连接")
            return None
            
        time.sleep(0.1)
        # 模拟回读数据
        mock_data = [random.randint(0, 255) for _ in range(8)]
        hex_data = " ".join([f"{b:02X}" for b in mock_data])
        msg = f"[COM: {self.channel}] [RX] ID: 0x{arb_id:X} Data: [{hex_data}]"
        print(msg)
        if logger: logger(msg)
        return mock_data

    def send_and_wait(self, send_id: int, send_data: list, wait_id: int, timeout: float = 2.0, logger=None) -> Optional[list]:
        """发送并等待响应 (交互指令)"""
        if self.send_frame(send_id, send_data, logger=logger):
            return self.read_frame(wait_id, timeout, logger=logger)
        return None
