from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
import threading
import logging
import time

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AFEPowerDriver")

class AFEPowerController:
    """
    万瑞达/允星河 RU 系列电源独立驱动 (AFE 供电版)
    适用于 RU36-100V36A 等型号。
    通讯协议: Modbus TCP (SOCKET 帧结构)
    """
    def __init__(self, ip: str, port: int = 2000, slave_id: int = 1):
        """
        初始化驱动
        :param ip: 电源 IP 地址
        :param port: 端口号 (RU 系列默认为 2000)
        :param slave_id: 从机 ID (默认为 1)
        """
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.client = ModbusTcpClient(
            self.ip, 
            port=self.port, 
            framer=FramerType.SOCKET,
            timeout=2,
            retries=1
        )
        self.lock = threading.Lock()
        self.is_connected = False

    def connect(self) -> bool:
        """建立 Modbus TCP 连接 (带物理参数校验)"""
        with self.lock:
            try:
                # 检查 IP 或端口是否变化，如果变化则重建 client
                if self.client.comm_params.host != self.ip or self.client.comm_params.port != self.port:
                    try: self.client.close()
                    except: pass
                    self.client = ModbusTcpClient(
                        self.ip, 
                        port=self.port, 
                        framer=FramerType.SOCKET,
                        timeout=2,
                        retries=1
                    )
                
                if self.client.connect():
                    self.is_connected = True
                    logger.info(f"成功连接至 AFE 电源: {self.ip}:{self.port}")
                    return True
                else:
                    logger.error(f"连接 AFE 电源失败: {self.ip}:{self.port}")
                    return False
            except Exception as e:
                logger.error(f"连接异常: {e}")
                return False

    def disconnect(self):
        """断开连接"""
        with self.lock:
            self.client.close()
            self.is_connected = False
            logger.info(f"已断开 AFE 电源连接: {self.ip}")

    def set_voltage(self, voltage: float) -> bool:
        """
        设置输出电压 (寄存器地址 149)
        倍率: 10 (例如设置 8.0V，实际发送 80)
        """
        with self.lock:
            if not self.is_connected: return False
            try:
                val = int(round(voltage * 10))
                # 使用 device_id 替代 slave 以兼容本项目环境
                result = self.client.write_register(address=149, value=val, device_id=self.slave_id)
                return not result.isError()
            except Exception as e:
                logger.error(f"电压设置异常: {e}")
                return False

    def set_current(self, current: float) -> bool:
        """
        设置限流值 (寄存器地址 150)
        倍率: 10
        """
        with self.lock:
            if not self.is_connected: return False
            try:
                val = int(round(current * 10))
                result = self.client.write_register(address=150, value=val, device_id=self.slave_id)
                return not result.isError()
            except Exception as e:
                logger.error(f"电流设置异常: {e}")
                return False

    def output_control(self, state: bool) -> bool:
        """
        输出开关控制 (线圈地址 133)
        :param state: True 开启, False 关闭
        """
        with self.lock:
            if not self.is_connected: return False
            try:
                result = self.client.write_coil(address=133, value=state, device_id=self.slave_id)
                return not result.isError()
            except Exception as e:
                logger.error(f"输出控制异常: {e}")
                return False

    def measure_voltage(self) -> float:
        """
        读取实时电压 (输入寄存器地址 100)
        倍率: 0.1
        """
        with self.lock:
            if not self.is_connected: return -1.0
            try:
                result = self.client.read_input_registers(address=100, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.registers[0] / 10.0
                return -1.0
            except Exception as e:
                logger.error(f"电压读取异常: {e}")
                return -1.0

    def measure_current(self) -> float:
        """
        读取实时电流 (输入寄存器地址 101)
        倍率: 0.1
        """
        with self.lock:
            if not self.is_connected: return -1.0
            try:
                result = self.client.read_input_registers(address=101, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.registers[0] / 10.0
                return -1.0
            except Exception as e:
                logger.error(f"电流读取异常: {e}")
                return -1.0

# --- 使用示例 ---
if __name__ == "__main__":
    # 2# AFE 电源示例
    AFE2_IP = "192.168.1.203"
    AFE2_PORT = 2000
    
    # 3# AFE 电源示例
    AFE3_IP = "192.168.1.204"
    AFE3_PORT = 2000
    
    pwr = AFEPowerController(AFE2_IP, AFE2_PORT)
    
    if pwr.connect():
        # 1. 设置电压 12.5V, 限流 5A
        pwr.set_voltage(12.5)
        pwr.set_current(5.0)
        
        # 2. 开启输出
        pwr.output_control(True)
        time.sleep(1)
        
        # 3. 读取回读值
        v = pwr.measure_voltage()
        i = pwr.measure_current()
        print(f"当前电压: {v}V, 当前电流: {i}A")
        
        # 4. 关闭输出
        pwr.output_control(False)
        
        pwr.disconnect()
