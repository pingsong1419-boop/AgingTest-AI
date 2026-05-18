from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
from pymodbus.exceptions import ModbusException
import logging
import threading

# 配置日志
import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

class MainboardPowerRU60:
    """
    主机供电电源专用驱动 (RU60-30V200A)
    独立文件存储，避免与 AFE 驱动产生耦合
    """
    def __init__(self, ip: str, port: int = 2000):
        self.ip = ip
        self.port = port
        self.unit_id = 1
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
        with self.lock:
            try:
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
                    # 握手验证：读取 100 号电压寄存器
                    result = self.client.read_input_registers(100, count=1, device_id=self.unit_id)
                    if result and not result.isError():
                        self.is_connected = True
                        return True
                    else:
                        self.client.close()
                        self.is_connected = False
                        return False
                return False
            except Exception:
                self.is_connected = False
                return False

    def disconnect(self):
        with self.lock:
            self.client.close()
            self.is_connected = False

    def set_voltage(self, voltage: float, logger=None) -> bool:
        """设置电压 (十进制地址 149, 倍率 100)"""
        with self.lock:
            if not self.is_connected:
                if logger: logger(f"[IP: {self.ip}] 错误: 主机电源未连接")
                return False
            try:
                val = int(round(voltage * 100))
                if logger: logger(f"[IP: {self.ip}] [TX] Write Register 149: {val}")
                result = self.client.write_register(149, val, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[IP: {self.ip}] [RX] {'Success' if success else 'Error'}")
                return success
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电压异常: {e}")
                return False

    def set_current(self, current: float, logger=None) -> bool:
        """设置电流 (十进制地址 150, 倍率 10)"""
        with self.lock:
            if not self.is_connected:
                if logger: logger(f"[IP: {self.ip}] 错误: 主机电源未连接")
                return False
            try:
                val = int(round(current * 100))
                if logger: logger(f"[IP: {self.ip}] [TX] Write Register 150: {val}")
                result = self.client.write_register(150, val, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[IP: {self.ip}] [RX] {'Success' if success else 'Error'}")
                return success
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电流异常: {e}")
                return False

    def output_control(self, state: bool, logger=None) -> bool:
        """输出控制 (十进制线圈地址 133)"""
        with self.lock:
            if not self.is_connected:
                if logger: logger(f"[IP: {self.ip}] 错误: 主机电源未连接")
                return False
            try:
                if logger: logger(f"[IP: {self.ip}] [TX] Write Coil 133: {state}")
                result = self.client.write_coil(133, state, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[IP: {self.ip}] [RX] {'Success' if success else 'Error'}")
                return success
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 输出控制异常: {e}")
                return False

    def measure_voltage(self, logger=None) -> float:
        """测量电压 (十进制输入寄存器地址 100, 倍率 100)"""
        with self.lock:
            if not self.is_connected:
                if logger: logger(f"[IP: {self.ip}] 错误: 主机电源未连接")
                return -1.0
            try:
                if logger: logger(f"[IP: {self.ip}] [TX] Read Register 100")
                result = self.client.read_holding_registers(100, count=1, device_id=self.unit_id)
                if not result or result.isError():
                    if logger: logger(f"[IP: {self.ip}] [RX] Error")
                    return -1.0
                val = result.registers[0] / 100.0
                if logger: logger(f"[IP: {self.ip}] [RX] {val} V")
                return val
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 测量电压异常: {e}")
                return -1.0

    def measure_current(self, logger=None) -> float:
        """测量电流 (十进制输入寄存器地址 101, 倍率 10)"""
        with self.lock:
            if not self.is_connected:
                if logger: logger(f"[IP: {self.ip}] 错误: 主机电源未连接")
                return -1.0
            try:
                if logger: logger(f"[IP: {self.ip}] [TX] Read Register 101")
                result = self.client.read_holding_registers(101, count=1, device_id=self.unit_id)
                if not result or result.isError():
                    if logger: logger(f"[IP: {self.ip}] [RX] Error")
                    return -1.0
                val = result.registers[0] / 100.0
                if logger: logger(f"[IP: {self.ip}] [RX] {val} A")
                return val
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 测量电流异常: {e}")
                return -1.0
