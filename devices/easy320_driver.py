from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
import time
import logging

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Easy320Driver")

class Easy320Controller:
    """
    Easy320 继电器控制板驱动 (独立版)
    支持 32 路继电器输出，通讯协议为 Modbus TCP。
    """
    def __init__(self, ip: str, port: int = 502, slave_id: int = 1):
        """
        初始化驱动
        :param ip: 设备 IP 地址
        :param port: Modbus TCP 端口 (默认为 502)
        :param slave_id: 从机 ID (默认为 1)
        """
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.client = ModbusTcpClient(
            self.ip, 
            port=self.port, 
            framer=FramerType.SOCKET,
            timeout=3
        )
        self.is_connected = False
        # Easy320 继电器起始地址 (0xFC08 = 64520)
        self.start_address = 0xFC08 

    def connect(self) -> bool:
        """建立连接"""
        try:
            if self.client.connect():
                self.is_connected = True
                logger.info(f"成功连接至 Easy320: {self.ip}:{self.port}")
                return True
            else:
                logger.error(f"连接 Easy320 失败: {self.ip}:{self.port}")
                return False
        except Exception as e:
            logger.error(f"连接发生异常: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.client.close()
        self.is_connected = False
        logger.info("已断开 Easy320 连接")

    def write_relay(self, index: int, state: bool) -> bool:
        """
        控制单个继电器开关
        :param index: 继电器索引 (0-31)
        :param state: True 为开启, False 为关闭
        :return: 操作是否成功
        """
        if not self.is_connected:
            if not self.connect():
                return False
        
        address = self.start_address + index
        try:
            # 优先尝试功能码 05 (Write Single Coil)
            # 使用 device_id 替代 slave 以兼容本项目环境
            result = self.client.write_coil(address=address, value=state, device_id=self.slave_id)
            if result and not result.isError():
                logger.debug(f"继电器 CH-{index+1} 设置为 {'开启' if state else '关闭'} (FC05)")
                return True
            
            # 若 FC05 报错，尝试功能码 06 (Write Single Register)
            result = self.client.write_register(address=address, value=1 if state else 0, device_id=self.slave_id)
            if result and not result.isError():
                logger.debug(f"继电器 CH-{index+1} 设置为 {'开启' if state else '关闭'} (FC06)")
                return True
                
            logger.error(f"继电器 CH-{index+1} 控制失败: {result}")
            return False
        except Exception as e:
            logger.error(f"继电器控制异常: {e}")
            return False

    def read_relays(self, count: int = 32) -> list:
        """
        读取继电器当前状态
        :param count: 读取数量 (默认 32)
        :return: 包含 bool 值的列表，读取失败返回空列表
        """
        if not self.is_connected:
            if not self.connect():
                return []
        try:
            # 尝试读取线圈 (FC01)
            result = self.client.read_coils(address=self.start_address, count=count, device_id=self.slave_id)
            if result and not result.isError():
                return result.bits[:count]
            
            # 尝试读取保持寄存器 (FC03)
            result = self.client.read_holding_registers(address=self.start_address, count=count, device_id=self.slave_id)
            if result and not result.isError():
                return [bool(r) for r in result.registers]
                
            return []
        except Exception as e:
            logger.error(f"读取状态异常: {e}")
            return []

    def batch_control(self, state: bool, delay: float = 0.1):
        """
        批量控制所有继电器
        :param state: 目标状态
        :param delay: 每个继电器操作之间的延迟时间 (秒)
        """
        logger.info(f"开始批量{'开启' if state else '关闭'}继电器...")
        for i in range(32):
            self.write_relay(i, state)
            time.sleep(delay)
        logger.info("批量操作完成")

# --- 使用示例 ---
if __name__ == "__main__":
    # 请根据实际情况修改 IP 和端口
    DEVICE_IP = "192.168.1.190"
    DEVICE_PORT = 502
    
    ctrl = Easy320Controller(DEVICE_IP, DEVICE_PORT)
    
    if ctrl.connect():
        # 1. 开启第 1 路继电器
        ctrl.write_relay(0, True)
        time.sleep(1)
        
        # 2. 读取所有状态
        states = ctrl.read_relays()
        print(f"当前继电器状态: {states}")
        
        # 3. 关闭第 1 路继电器
        ctrl.write_relay(0, False)
        
        # 4. 批量操作演示
        # ctrl.batch_control(True)
        # time.sleep(2)
        # ctrl.batch_control(False)
        
        ctrl.disconnect()
