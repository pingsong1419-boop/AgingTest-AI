import socket
import time
import struct

class Lingtu66100:
    """
    领图 66100 多通道电池模拟器驱动 (基于 SCPI 协议)
    适配：SOURce[ch]:VOLTage:AMPLitude 指令格式
    """
    def __init__(self, ip: str, port: int = 5025):
        self.ip = ip
        self.port = port
        self.sock = None
        self.is_connected = False

    def connect(self) -> bool:
        # 如果当前已经是连接状态，先尝试安全断开
        if self.is_connected:
            self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置 LINGER 选项，确保关闭时立即发送 RST 报文释放端口
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            self.sock.settimeout(3.0)
            self.sock.connect((self.ip, self.port))
            self.is_connected = True
            
            # 清除仪器缓冲区并测试通讯
            self.sock.send(b"*CLS\n") # 清除状态寄存器
            time.sleep(0.1)
            self.sock.send(b"*IDN?\n")
            idn = self.sock.recv(1024).decode().strip()
            print(f"[*] 联机成功: {idn}")
            return True
        except Exception as e:
            print(f"[Lingtu66100] 连接失败 ({self.ip}): {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.sock:
            try:
                # 彻底关闭连接
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except:
                pass
        self.sock = None
        self.is_connected = False


    def set_voltage(self, channel: int, voltage: float, logger=None) -> bool:
        """设置电压，并等待确认"""
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return False
        try:
            cmd = f"SOUR{channel}:VOLT {voltage}\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            # 等待操作完成
            if logger: logger(f"[IP: {self.ip}] [TX] *OPC?")
            self.sock.send(b"*OPC?\n")
            res = self.sock.recv(10).decode().strip()
            if logger: logger(f"[IP: {self.ip}] [RX] {res}")
            return "1" in res
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 设置电压异常: {e}")
            return False


    def set_current_limit(self, channel: int, current: float, logger=None):
        """设置电流限制: SOURce[ch]:CURRent:LIMit <value>"""
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return False
        try:
            cmd = f"SOUR{channel}:CURR {current}\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            return True
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 设置电流异常: {e}")
            return False

    def set_range(self, channel: int, range_str: str, logger=None) -> bool:
        """
        设置量程: SOURce[ch]:CURRent:RANGe <HIGH|LOW>
        range_str: "HIGH" 或 "LOW"
        """
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return False
        try:
            # 这里的指令根据 66100 协议手册调整，通常为 SOUR:CURR:RANG
            cmd = f"SOUR{channel}:CURR:RANG {range_str}\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            return True
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 设置量程异常: {e}")
            return False

    def output_control(self, channel: int, state: bool, logger=None) -> bool:
        """控制输出开关，并等待确认"""
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return False
        try:
            val = 1 if state else 0
            cmd = f"OUTP{channel}:STAT {val}\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            
            if logger: logger(f"[IP: {self.ip}] [TX] *OPC?")
            self.sock.send(b"*OPC?\n")
            res = self.sock.recv(10).decode().strip()
            if logger: logger(f"[IP: {self.ip}] [RX] {res}")
            return "1" in res
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 输出控制异常: {e}")
            return False


    def measure_voltage(self, channel: int, logger=None) -> float:
        """测量实时电压: MEASure[ch]:VOLTage?"""
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return -1.0
        try:
            cmd = f"MEAS{channel}:VOLT?\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            data = self.sock.recv(1024).decode().strip()
            if logger: logger(f"[IP: {self.ip}] [RX] {data} V")
            return float(data)
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 测量电压异常: {e}")
            return -1.0

    def measure_current(self, channel: int, logger=None) -> float:
        """测量实时电流: MEASure[ch]:CURRent?"""
        if not self.is_connected:
            if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
            return -1.0
        try:
            cmd = f"MEAS{channel}:CURR?\n"
            if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
            self.sock.send(cmd.encode())
            data = self.sock.recv(1024).decode().strip()
            if logger: logger(f"[IP: {self.ip}] [RX] {data} A")
            return float(data)
        except Exception as e:
            if logger: logger(f"[IP: {self.ip}] [!] 测量电流异常: {e}")
            return -1.0
