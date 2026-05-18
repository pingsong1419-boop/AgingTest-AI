from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
import time
import logging

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Easy320Driver")

import threading

class Easy320Controller:
    """
    Easy320 继电器控制板驱动 (独立版)
    支持 32 路继电器输出，通讯协议为 Modbus TCP。
    """
    def __init__(self, ip: str, port: int = 502, slave_id: int = 1):
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.client = ModbusTcpClient(
            self.ip, 
            port=self.port, 
            framer=FramerType.SOCKET,
            timeout=3
        )
        self.lock = threading.Lock()
        self.is_connected = False
        self.start_address = 0xFC08 

    def connect(self) -> bool:
        """建立连接并执行握手验证"""
        import socket
        with self.lock:
            # 1. 物理探测 IP 是否可达 (超时 0.8s)
            try:
                with socket.create_connection((self.ip, self.port), timeout=0.8):
                    pass
            except:
                self.is_connected = False
                return False

            # 2. 建立 Modbus 连接
            try:
                # 重新初始化 client 以更新超时设置
                self.client.close()
                self.client.timeout = 1.0
                
                if self.client.connect():
                    result = self.client.read_coils(address=self.start_address, count=1, device_id=self.slave_id)
                    if result and not result.isError():
                        self.is_connected = True
                        logger.info(f"成功连接并验证 Easy320: {self.ip}:{self.port}")
                        return True
                    else:
                        self.client.close()
                        self.is_connected = False
                        return False
                return False
            except Exception as e:
                logger.error(f"连接发生异常: {e}")
                self.is_connected = False
                return False

    def disconnect(self):
        """断开连接"""
        with self.lock:
            self.client.close()
            self.is_connected = False

    def write_relay(self, index: int, state: bool) -> bool:
        """控制单个继电器开关"""
        if not self.is_connected:
            if not self.connect(): return False
        
        address = self.start_address + index
        with self.lock:
            try:
                # 模拟调试 TAB 的操作原理：增加微小延时
                time.sleep(0.05)
                
                # 优先尝试线圈写入 (FC05)
                result = self.client.write_coil(address=address, value=state, device_id=self.slave_id)
                if result and not result.isError():
                    return True
                
                # 备选尝试寄存器写入 (FC06)
                result = self.client.write_register(address=address, value=1 if state else 0, device_id=self.slave_id)
                return result is not None and not result.isError()
            except Exception as e:
                logger.error(f"继电器控制异常: {e}")
                return False

    def read_relays(self, count: int = 32) -> list:
        """读取继电器当前状态"""
        if not self.is_connected:
            if not self.connect(): return []
        with self.lock:
            try:
                result = self.client.read_coils(address=self.start_address, count=count, device_id=self.slave_id)
                if result and not result.isError():
                    return result.bits[:count]
                
                result = self.client.read_holding_registers(address=self.start_address, count=count, device_id=self.slave_id)
                if result and not result.isError():
                    return [bool(r) for r in result.registers]
                return []
            except Exception as e:
                logger.error(f"读取状态异常: {e}")
                return []

    def batch_control(self, state: bool, delay: float = 0.05):
        """批量控制所有继电器"""
        success = True
        for i in range(32):
            success = success and self.write_relay(i, state)
            time.sleep(delay)
        return success

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
