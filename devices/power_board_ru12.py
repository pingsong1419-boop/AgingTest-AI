from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
import threading
import logging
import time

# 配置日志
logger = logging.getLogger("PowerBoardRU12")

class PowerBoardRU12:
    """
    万瑞达电气 (YunXingHe) RU12-3040 功能板电源驱动 (Modbus TCP)
    控制指令与主机板电源 (RU60) 保持一致
    """
    def __init__(self, ip: str, port: int = 10001):
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
                    # 握手验证
                    result = self.client.read_input_registers(100, count=1, device_id=self.unit_id)
                    if result and not result.isError():
                        self.is_connected = True
                        return True
                    else:
                        self.client.close()
                        self.is_connected = False
                        return False
                return False
            except Exception as e:
                logger.error(f"Connect error: {e}")
                self.is_connected = False
                return False

    def disconnect(self):
        with self.lock:
            if self.client:
                self.client.close()
            self.is_connected = False

    def set_voltage(self, voltage: float, logger=None) -> bool:
        """设置电压 (十进制地址 149, 倍率 100)"""
        with self.lock:
            if not self.is_connected: return False
            try:
                val = int(round(voltage * 100))
                result = self.client.write_register(149, val, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[PowerBoard] 设置电压: {voltage}V, 结果: {success}")
                return success
            except Exception as e:
                if logger: logger(f"[PowerBoard] 设置电压异常: {e}")
                return False

    def set_current(self, current: float, logger=None) -> bool:
        """设置电流 (十进制地址 150, 倍率 100)"""
        with self.lock:
            if not self.is_connected: return False
            try:
                val = int(round(current * 100))
                result = self.client.write_register(150, val, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[PowerBoard] 设置电流: {current}A, 结果: {success}")
                return success
            except Exception as e:
                if logger: logger(f"[PowerBoard] 设置电流异常: {e}")
                return False

    def output_control(self, state: bool, logger=None) -> bool:
        """输出控制 (十进制线圈地址 133)"""
        with self.lock:
            if not self.is_connected: return False
            try:
                result = self.client.write_coil(133, state, device_id=self.unit_id)
                success = result is not None and not result.isError()
                if logger: logger(f"[PowerBoard] 输出控制: {'ON' if state else 'OFF'}, 结果: {success}")
                return success
            except Exception as e:
                if logger: logger(f"[PowerBoard] 输出控制异常: {e}")
                return False

    def measure_voltage(self, logger=None) -> float:
        """测量电压 (十进制输入寄存器地址 100, 倍率 100)"""
        with self.lock:
            if not self.is_connected: return -1.0
            try:
                result = self.client.read_input_registers(100, count=1, device_id=self.unit_id)
                if not result or result.isError():
                    return -1.0
                val = result.registers[0] / 100.0
                return val
            except Exception as e:
                if logger: logger(f"[PowerBoard] 测量电压异常: {e}")
                return -1.0

    def measure_current(self, logger=None) -> float:
        """测量电流 (十进制输入寄存器地址 101, 倍率 100)"""
        with self.lock:
            if not self.is_connected: return -1.0
            try:
                result = self.client.read_input_registers(101, count=1, device_id=self.unit_id)
                if not result or result.isError():
                    return -1.0
                val = result.registers[0] / 100.0
                return val
            except Exception as e:
                if logger: logger(f"[PowerBoard] 测量电流异常: {e}")
                return -1.0
