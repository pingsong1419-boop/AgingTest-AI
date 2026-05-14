import serial
import time
import logging

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CA550Driver")

class CA550Controller:
    """
    横河 (Yokogawa) CA550 校准仪独立驱动版 (V5 - 队列安全与动态参数版)
    默认串口参数: 9600, 7位数据位, 无校验, 1位停止位 (9600, 7N1)
    """
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = serial.SEVENBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        
        self.ser = None
        self.is_connected = False

    def connect(self) -> bool:
        """建立串口连接并执行握手验证"""
        if not self.port or self.port.strip() == "":
            logger.warning("CA550 串口未配置，跳过连接。")
            return False
            
        try:
            # 物理层连接
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=1.0  # 稍微缩短超时
            )
            # 激活 DTR/RTS 信号
            self.ser.dtr = True
            self.ser.rts = True
            
            self.is_connected = self.ser.is_open
            if self.is_connected:
                # 强制等待硬件就绪并执行握手验证
                time.sleep(0.3)
                idn = self.get_idn()
                if idn and "ERROR" not in idn:
                    logger.info(f"成功连接并验证 CA550: {self.port} (IDN: {idn})")
                    return True
                else:
                    self.ser.close()
                    self.is_connected = False
                    logger.error(f"CA550 握手失败 (无响应或响应错误): {self.port}")
                    return False
            return False
        except Exception as e:
            self.is_connected = False
            logger.error(f"CA550 连接异常: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.is_connected = False
        logger.info(f"已断开物理连接: {self.port}")

    def _send_command(self, cmd: str) -> str:
        if not self.is_connected:
            return "ERROR: Not Connected"
        
        try:
            self.ser.reset_input_buffer()
            # 根据参考项目建议，使用 \r\n (CRLF) 结束符
            full_cmd = f"{cmd}\r\n".encode("ascii")
            self.ser.write(full_cmd)
            self.ser.flush()
            
            # 给予响应缓冲区填充时间
            time.sleep(0.08)
            response = self.ser.readline().decode("ascii", errors="ignore").strip()
            
            # 二次读取尝试
            if not response:
                time.sleep(0.1)
                response = self.ser.read_all().decode("ascii", errors="ignore").strip()
            
            if not response:
                return ""
            
            # 处理 Echo (回显剥离)
            if cmd.endswith("?"):
                prefix = cmd.replace("?", "")
                if response.startswith(prefix):
                    if prefix == "OD":
                        return response
                    return response[len(prefix):].strip()
            
            return response
        except Exception as e:
            logger.error(f"CA550 通讯错误: {e}")
            return f"ERROR: {e}"

    # --- 指令集 ---
    def get_idn(self): return self._send_command("*IDN?")
    def get_sn(self): return self._send_command("BSN?")
    def get_factory_date(self): return self._send_command("BGD?0")
    def get_cal_date(self): return self._send_command("BGD?1")
    def get_battery(self): return self._send_command("PU?")
    def set_backlight(self, state: int): return self._send_command(f"BL{state}")
    def set_24v_power(self, state: int): return self._send_command(f"VO{state}")
    def set_250_resistor(self, state: int): return self._send_command(f"IO{state}")
    def set_break_detection(self, state: int): return self._send_command(f"BU{state}")
    def init_f1_f2(self): return self._send_command("YC")
    def full_reset(self): return self._send_command("RC")
    def set_measure_func(self, func_code: int): return self._send_command(f"MF{func_code}")
    def set_measure_range(self, range_code: int): return self._send_command(f"MR{range_code}")
    def set_measure_state(self, state: int): return self._send_command(f"MO{state}")
    def set_wiring(self, mode: int): return self._send_command(f"WC{mode}")
    def read_measure_data(self): return self._send_command("OD?")
    def set_source_func(self, func_code: int): return self._send_command(f"SF{func_code}")
    def set_source_range(self, range_code: int): return self._send_command(f"SR{range_code}")
    def set_source_data(self, value: float): return self._send_command(f"SD{value:.4f}")
    def set_source_output(self, state: int): return self._send_command(f"SO{state}")
    def set_source_0_percent(self, value: float): return self._send_command(f"SL{value:.4f}")
    def set_source_100_percent(self, value: float): return self._send_command(f"SH{value:.4f}")

if __name__ == "__main__":
    dev = CA550Controller("COM5")
    if dev.connect():
        print(f"IDN: {dev.get_idn()}")
        dev.disconnect()
