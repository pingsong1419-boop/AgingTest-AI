import socket
import time
import struct
import threading

class Lingtu66100:
    """
    领图 66100 多通道电池模拟器驱动 (基于 SCPI 协议)
    适配：SOURce[ch]:VOLTage:AMPLitude 指令格式
    """
    def __init__(self, ip: str, port: int = 5025, max_channels: int = 18):
        self.ip = ip
        self.port = port
        self.max_channels = max_channels
        self.sock = None
        self.is_connected = False
        self._lock = threading.Lock()

    def connect(self) -> bool:
        # 如果当前已经是连接状态，先尝试安全断开
        if self.is_connected:
            self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            self.sock.settimeout(2.0)
            self.sock.connect((self.ip, self.port))
            self.is_connected = True
            print(f"[*] 模拟器 ({self.ip}) TCP 链路已建立")
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


    def _ensure_connected(self) -> bool:
        """确保连接有效，如果断开则尝试重连"""
        # BUG-06修复: 不再发送\n心跳，\n是SCPI终结符会污染指令流
        if self.is_connected and self.sock:
            return True
        return self.connect()

    def _safe_send(self, cmd_bytes: bytes, retries: int = 2, logger=None) -> bool:
        """带重试的发送逻辑"""
        for i in range(retries + 1):
            try:
                if not self._ensure_connected(): continue
                self._clear_buffer()
                cmd_str = cmd_bytes.decode().strip()
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd_str}")
                self.sock.send(cmd_bytes)
                return True
            except Exception as e:
                print(f"[Lingtu66100] 发送失败 (尝试 {i+1}): {e}")
                self.is_connected = False
                time.sleep(0.2)
        return False

    def set_voltage(self, channel: int, voltage: float, logger=None) -> bool:
        """设置电压"""
        with self._lock:
            try:
                channels = range(1, self.max_channels + 1) if channel == 0 else [channel]
                for ch in channels:
                    cmd = f"SOUR{ch}:VOLT {voltage}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                    time.sleep(0.02) 
                
                if logger and channel == 0: logger(f"[IP: {self.ip}] [广播] 设置所有通道电压: {voltage}V")
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电压异常: {e}")
                return False


    def set_current_limit(self, channel: int, current: float, logger=None):
        """设置电流限制: SOURce[ch]:CURRent:LIMit <value>"""
        # BUG-02修复: 加锁，防止多线程并发时粘包
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                channels = range(1, self.max_channels + 1) if channel == 0 else [channel]
                for ch in channels:
                    cmd = f"SOUR{ch}:CURR {current}\n"
                    self._safe_send(cmd.encode(), logger=logger)
                    time.sleep(0.02)
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电流异常: {e}")
                self.is_connected = False
                return False

    def set_range(self, channel: int, range_str: str, logger=None) -> bool:
        """设置量程: SOURce[ch]:CURRent:RANGe <HIGH|LOW>"""
        # BUG-02修复: 加锁
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                channels = range(1, self.max_channels + 1) if channel == 0 else [channel]
                for ch in channels:
                    cmd = f"SOUR{ch}:CURR:RANG {range_str}\n"
                    self._safe_send(cmd.encode(), logger=logger)
                    time.sleep(0.02)
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置量程异常: {e}")
                self.is_connected = False
                return False

    def output_control(self, channel: int, state: bool, logger=None) -> bool:
        """控制输出开关"""
        with self._lock:
            try:
                val = 1 if state else 0
                channels = range(1, self.max_channels + 1) if channel == 0 else [channel]
                for ch in channels:
                    cmd = f"OUTP{ch}:STAT {val}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                    time.sleep(0.02) 
                
                if logger and channel == 0: logger(f"[IP: {self.ip}] [广播] {'开启' if state else '关闭'}所有通道输出")
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 输出控制异常: {e}")
                return False


    def _clear_buffer(self):
        if not self.sock: return
        self.sock.setblocking(False)
        try:
            while True: self.sock.recv(4096)
        except: pass
        self.sock.setblocking(True)

    def measure_voltage(self, channel: int, logger=None) -> float:
        """测量/读取通道设定电压: SOURce[ch]:VOLTage?"""
        # BUG-07修复: 加锁，防止多线程并发时响应报文乱序
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return -1.0
            self._clear_buffer()
            try:
                cmd = f"SOUR{channel}:VOLT?\n"
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data} V")
                return float(data)
            except Exception as e:
                self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取设定电压异常: {e}")
                return -1.0

    def measure_current(self, channel: int, logger=None) -> float:
        """测量实时电流: MEASure[ch]:CURRent?"""
        # BUG-07修复: 加锁
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return -1.0
            self._clear_buffer()
            try:
                cmd = f"MEAS{channel}:CURR?\n"
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data} A")
                return float(data)
            except Exception as e:
                self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取设定电流异常: {e}")
                return -1.0
