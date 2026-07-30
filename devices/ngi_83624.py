import socket
import time
import struct
import threading

class NGI83624:
    """
    NGI 83624 单/全通道 电池模拟器驱动 (基于 SCPI 协议)
    """
    def __init__(self, ip: str, port: int = 7000, max_channels: int = 24):
        self.ip = ip
        self.port = port
        self.max_channels = max_channels
        self.sock = None
        self.is_connected = False
        self._lock = threading.Lock()
        self._fail_count = 0

    def connect(self) -> bool:
        if self.is_connected:
            self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            self.sock.settimeout(2.0)
            self.sock.connect((self.ip, self.port))
            self.sock.sendall(b"*IDN?\n")
            identity = self.sock.recv(1024).decode(errors="ignore").strip()
            if not identity:
                raise TimeoutError("TCP端口可连接，但设备未响应 *IDN? 查询")
            self.is_connected = True
            self._fail_count = 0
            print(f"[*] NGI 83624A ({self.ip}) 通讯握手成功: {identity}")
            return True
        except Exception as e:
            print(f"[NGI83624] 通讯握手失败 ({self.ip}): {e}")
            try:
                if self.sock:
                    self.sock.close()
            except:
                pass
            self.sock = None
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
                print(f"[NGI83624] 发送失败 (尝试 {i+1}): {e}")
                self.is_connected = False
                time.sleep(0.2)
        return False

    def set_voltage(self, channel: int, voltage: float, logger=None) -> bool:
        with self._lock:
            try:
                if channel == 0:
                    ch_str = ",".join(str(i) for i in range(1, self.max_channels + 1))
                    cmd = f"SOUR:VOLT {voltage}(@{ch_str})\n"
                else:
                    cmd = f"SOUR{channel}:VOLT {voltage}\n"
                
                if not self._safe_send(cmd.encode(), logger=logger): return False
                time.sleep(0.02) 
                
                if logger and channel == 0: logger(f"[IP: {self.ip}] [广播] 设置所有通道电压: {voltage}V")
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电压异常: {e}")
                return False

    def set_current_limit(self, channel: int, current: float, logger=None):
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                # NGI 83624 SCPI current limit setting expects mA, so convert A to mA
                curr_ma = current * 1000.0
                if channel == 0:
                    ch_str = ",".join(str(i) for i in range(1, self.max_channels + 1))
                    cmd = f"SOUR:OUTCURR {curr_ma:.2f}(@{ch_str})\n"
                else:
                    cmd = f"SOUR{channel}:OUTCURR {curr_ma:.2f}\n"
                
                self._safe_send(cmd.encode(), logger=logger)
                time.sleep(0.02)
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置电流异常: {e}")
                self.is_connected = False
                return False

    def set_range(self, channel: int, range_str: str, logger=None) -> bool:
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                range_val = "0"
                if "LOW" in range_str.upper():
                    range_val = "2"
                elif "AUTO" in range_str.upper():
                    range_val = "3"
                    
                if channel == 0:
                    ch_str = ",".join(str(i) for i in range(1, self.max_channels + 1))
                    cmd = f"SOUR:RANG {range_val}(@{ch_str})\n"
                else:
                    cmd = f"SOUR{channel}:RANG {range_val}\n"
                    
                self._safe_send(cmd.encode(), logger=logger)
                time.sleep(0.02)
                return True
            except Exception as e:
                if logger: logger(f"[IP: {self.ip}] [!] 设置量程异常: {e}")
                self.is_connected = False
                return False

    def output_control(self, channel: int, state: bool, logger=None) -> bool:
        for attempt in range(2):
            if not self._ensure_connected():
                if attempt == 1: return False
                time.sleep(0.5)
                continue
                
            with self._lock:
                try:
                    val = 1 if state else 0
                    if channel == 0:
                        ch_str = ",".join(str(i) for i in range(1, self.max_channels + 1))
                        cmd = f"OUTP:ONOFF {val}(@{ch_str})\n"
                    else:
                        cmd = f"OUTP{channel}:ONOFF {val}\n"
                        
                    if not self._safe_send(cmd.encode(), logger=logger):
                        self.is_connected = False
                    else:
                        time.sleep(0.05)
                        # 回读校验
                        if channel != 0:
                            self._clear_buffer()
                            qcmd = f"OUTP{channel}:ONOFF?\n"
                            self.sock.send(qcmd.encode())
                            data = self.sock.recv(1024).decode(errors="ignore").strip().upper()
                            is_on = data in ("1", "ON", "TRUE")
                            if is_on == state:
                                return True
                            else:
                                if logger: logger(f"[IP: {self.ip}] [!] 通道 {channel} 输出状态校验失败，准备重试")
                                self.is_connected = False
                        else:
                            if logger: logger(f"[IP: {self.ip}] [广播] {'开启' if state else '关闭'}所有通道输出")
                            return True
                except Exception as e:
                    if logger: logger(f"[IP: {self.ip}] [!] 输出控制异常: {e}")
                    self.is_connected = False
                    
            time.sleep(0.5)
        return False

    def read_output_state(self, channel: int, logger=None):
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return None

            def query_one(ch: int):
                self._clear_buffer()
                cmd = f"OUTP{ch}:ONOFF?\n"
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode(errors="ignore").strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data}")
                text = data.upper()
                if text in ("1", "ON", "TRUE"):
                    return True
                if text in ("0", "OFF", "FALSE"):
                    return False
                try:
                    return bool(int(float(text.split(",")[0])))
                except Exception:
                    return None

            try:
                if channel == 0:
                    states = [query_one(ch) for ch in range(1, self.max_channels + 1)]
                    if any(state is None for state in states):
                        return None
                    return all(states)
                return query_one(channel)
            except Exception as e:
                self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取输出状态异常: {e}")
                return None

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
                if channel == 0: return -1.0
                cmd = f"MEAS{channel}:VOLT?\n"
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data} V")
                val = float(data)
                self._fail_count = 0  # 成功时清零计数器
                return val
            except Exception as e:
                self._fail_count += 1
                if self._fail_count >= 5:
                    self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取设定电压异常 (连续失败 {self._fail_count} 次): {e}")
                return -1.0

    def measure_current(self, channel: int, logger=None) -> float:
        with self._lock:
            if not self._ensure_connected():
                if logger: logger(f"[IP: {self.ip}] 错误: 模拟器未连接")
                return -1.0
            self._clear_buffer()
            try:
                if channel == 0: return -1.0
                cmd = f"MEAS{channel}:CURR?\n"
                if logger: logger(f"[IP: {self.ip}] [TX] {cmd.strip()}")
                self.sock.send(cmd.encode())
                data = self.sock.recv(1024).decode().strip()
                if logger: logger(f"[IP: {self.ip}] [RX] {data} mA")
                val = float(data)
                self._fail_count = 0  # 成功时清零计数器
                return val
            except Exception as e:
                self._fail_count += 1
                if self._fail_count >= 5:
                    self.is_connected = False
                if logger: logger(f"[IP: {self.ip}] [!] 读取设定电流异常 (连续失败 {self._fail_count} 次): {e}")
                return -1.0
