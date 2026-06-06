from .aging_board_driver import AgingBoardController
from .rn_can_driver import RNCANDriver
import logging

logger = logging.getLogger("ControlBoard")

class ControlBoard:
    """
    单通道控制板类
    集成继电器控制 (Modbus TCP) 和 CAN 通讯 (RNCAN TCP)
    """
    def __init__(self, ip: str, channel_id: int):
        self.ip = ip
        self.channel_id = channel_id
        
        # 继电器控制器 (默认端口 502)
        self.relays = AgingBoardController(ip=ip)
        # CAN 控制器 (默认端口 5001)
        self.can = RNCANDriver(ip=ip, port=5001)
        
        self.is_connected = False

    def connect(self) -> bool:
        """同时尝试连接继电器和 CAN"""
        r_ok = self.relays.connect()
        # 如果老化板的主控 Modbus 都不通，大概率是没插网线或设备不存在，
        # 为了防止代理软件让 TCP 假通，这里强制 r_ok 为前置条件
        if r_ok:
            c_ok = self.can.connect()
        else:
            c_ok = False
            
        self.is_connected = r_ok and c_ok
        return self.is_connected

    def disconnect(self):
        self.relays.disconnect()
        self.can.disconnect()
        self.is_connected = False

    def get_status(self) -> dict:
        return {
            "ip": self.ip,
            "relay_connected": self.relays.is_connected,
            "can_connected": self.can.is_connected
        }
