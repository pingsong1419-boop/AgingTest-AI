import socket
import time
import struct
import threading

class NGI83624A:
    """
    NGI 83624A 电池模拟器驱动 (24通道)
    协议：
    设置单通道电压: SOUR<n>:VOLT 数值
    设置单通道限流: SOUR<n>:OUTCURR 数值 (单位mA)
    设置单通道量程: SOUR<n>:RANG 0/2/3 (0大量程, 2小量程, 3自动)
    设置单通道输出: OUTP<n>:ONOFF 1/0
    全通道设置: SOUR:VOLT 数值(@1,2,...,24)
    读取单通道电压: MEAS<n>:VOLT?
    读取单通道电流: MEAS<n>:CURR? (单位mA)
    全通道读取电压: MEAS:VOLT?(@1,2,...,24)
    """
    def __init__(self, ip: str, port: int = 5025, max_channels: int = 24):
        self.ip = ip
        self.port = port
        self.max_channels = max_channels
        self.sock = None
        self.is_connected = False
        self._lock = threading.Lock()
        
        # 预先生成所有通道的标识符 (@1,2,3...24)
        self.all_ch_str = "(@" + ",".join(str(i) for i in range(1, max_channels + 1)) + ")"

    def connect(self) -> bool:
        if self.is_connected:
            self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            self.sock.settimeout(2.0)
            self.sock.connect((self.ip, self.port))
            self.is_connected = True
            print(f"[*] NGI 83624A ({self.ip}) 链路已建立")
            return True
        except Exception as e:
            print(f"[NGI83624A] 连接失败 ({self.ip}): {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except:
                pass
        self.sock = None
        self.is_connected = False

    def _ensure_connected(self) -> bool:
        if self.is_connected and self.sock:
            return True
        return self.connect()

    def _safe_send(self, cmd_bytes: bytes, retries: int = 2, logger=None) -> bool:
        for i in range(retries + 1):
            try:
                if not self._ensure_connected(): continue
                self._clear_buffer()
                cmd_str = cmd_bytes.decode().strip()
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd_str}")
                self.sock.send(cmd_bytes)
                return True
            except Exception as e:
                print(f"[NGI83624A] 发送失败 (尝试 {i+1}): {e}")
                self.is_connected = False
                time.sleep(0.2)
        return False

    def set_voltage(self, channel: int, voltage: float, logger=None) -> bool:
        with self._lock:
            try:
                if channel == 0:
                    cmd = f"SOUR:VOLT {voltage}{self.all_ch_str}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                    if logger: logger(f"[IP: {self.ip}] [广播] 设置全通道电压: {voltage}V")
                else:
                    cmd = f"SOUR{channel}:VOLT {voltage}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电压异常: {e}")
                return False

    def set_current_limit(self, channel: int, current: float, logger=None) -> bool:
        # Note: current unit is mA for NGI protocol
        with self._lock:
            try:
                if channel == 0:
                    cmd = f"SOUR:OUTCURR {current}{self.all_ch_str}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                else:
                    cmd = f"SOUR{channel}:OUTCURR {current}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电流异常: {e}")
                return False

    def set_range(self, channel: int, range_str: str, logger=None) -> bool:
        """
        range_str: HIGH, LOW, AUTO -> mapped to 0, 2, 3
        """
        range_val = 3 # default auto
        if range_str.upper() == "HIGH": range_val = 0
        elif range_str.upper() == "LOW": range_val = 2
        
        with self._lock:
            try:
                if channel == 0:
                    cmd = f"SOUR:RANG {range_val}{self.all_ch_str}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                else:
                    cmd = f"SOUR{channel}:RANG {range_val}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置量程异常: {e}")
                return False

    def output_control(self, channel: int, state: bool, logger=None) -> bool:
        with self._lock:
            try:
                val = 1 if state else 0
                if channel == 0:
                    cmd = f"OUTP:ONOFF {val}{self.all_ch_str}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
                    if logger: logger(f"[IP: {self.ip}] [广播] {'开启' if state else '关闭'}全通道输出")
                else:
                    cmd = f"OUTP{channel}:ONOFF {val}\n"
                    if not self._safe_send(cmd.encode(), logger=logger): return False
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
        self.sock.settimeout(2.0)

    def measure_voltage(self, channel: int, logger=None) -> float:
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return -1.0
            self._clear_buffer()
            try:
                if channel == 0:
                    cmd = f"MEAS:VOLT?{self.all_ch_str}\n"
                else:
                    cmd = f"MEAS{channel}:VOLT?\n"
                    
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data}")
                
                if "," in data:
                    vals = [float(v) for v in data.split(",") if v.strip()]
                    return sum(vals)
                return float(data)
            except Exception as e:
                self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取电压异常: {e}")
                return -1.0

    def measure_current(self, channel: int, logger=None) -> float:
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return -1.0
            self._clear_buffer()
            try:
                if channel == 0:
                    cmd = f"MEAS:CURR?{self.all_ch_str}\n"
                else:
                    cmd = f"MEAS{channel}:CURR?\n"
                    
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data}")
                
                if "," in data:
                    vals = [float(v) for v in data.split(",") if v.strip()]
                    return sum(vals)
                return float(data)
            except Exception as e:
                self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取电流异常: {e}")
                return -1.0
