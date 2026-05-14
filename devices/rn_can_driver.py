import socket
import struct
import threading
import time
import queue
from collections import deque
from typing import Optional, Callable

class RNCANDriver:
    """
    RNCAN (CAN-TCP Gateway) 驱动
    支持多通道 CAN/CANFD 透明转发
    """
    MAGIC = 0xAA55
    
    # CAN 类型定义
    CAN_TYPE_CLASSIC = 0x00
    CAN_TYPE_FD = 0x01
    CAN_TYPE_FD_BRS = 0x02
    
    def __init__(self, ip: str = "192.168.1.10", port: int = 5001):
        self.ip = ip
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.is_connected = False
        self.lock = threading.Lock()
        
        self.msg_queue = queue.Queue(maxsize=10000)
        self.on_message_received: Optional[Callable] = None # 可选的回调
        self._receive_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._rx_history = deque(maxlen=2000)
        self._rx_condition = threading.Condition()

        # CRC16-CCITT 查找表 (多项式 0x1021)
        self.crc_table = self._generate_crc_table()

    def _generate_crc_table(self):
        poly = 0x1021
        table = []
        for i in range(256):
            crc = i << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ poly
                else:
                    crc = crc << 1
                crc &= 0xFFFF
            table.append(crc)
        return table

    def calculate_crc16(self, data: bytes) -> int:
        crc = 0x0000
        for byte in data:
            tbl_idx = ((crc >> 8) ^ byte) & 0xFF
            crc = ((crc << 8) ^ self.crc_table[tbl_idx]) & 0xFFFF
        return crc

    def connect(self, ip: Optional[str] = None, port: Optional[int] = None) -> bool:
        if ip: self.ip = ip
        if port: self.port = port
        with self.lock:
            try:
                if self.sock:
                    self.disconnect()
                
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(2.0)
                self.sock.connect((self.ip, self.port))
                self.sock.settimeout(None) # 切换到阻塞模式或由线程处理
                self.is_connected = True
                
                self._stop_event.clear()
                self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self._receive_thread.start()
                
                print(f"[RNCAN] Connected to {self.ip}:{self.port}")
                return True
            except Exception as e:
                print(f"[RNCAN] Connection failed: {e}")
                self.is_connected = False
                return False

    def disconnect(self):
        self._stop_event.set()
        self.is_connected = False
        with self.lock:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                    self.sock.close()
                except:
                    pass
                self.sock = None
        print("[RNCAN] Disconnected")

    def _receive_loop(self):
        """流式接收并解析 TCP 帧"""
        buffer = b""
        while not self._stop_event.is_set():
            try:
                # 阻塞式接收
                data = self.sock.recv(4096)
                if not data:
                    print("[RNCAN] Remote host closed connection")
                    self.is_connected = False
                    break
                
                buffer += data
                
                while len(buffer) >= 5: # Header size: Magic(2) + Ch(1) + Len(2)
                    # 查找 Magic Number 0xAA55
                    magic_pos = buffer.find(b'\xAA\x55')
                    if magic_pos == -1:
                        if len(buffer) > 2048:
                            buffer = buffer[-5:]
                        break
                    
                    if magic_pos > 0:
                        buffer = buffer[magic_pos:]
                    
                    if len(buffer) < 5:
                        break
                    
                    magic, channel_id, frame_length = struct.unpack('>HBH', buffer[:5])
                    
                    # 检查是否有完整的一帧
                    total_frame_size = 5 + frame_length
                    if len(buffer) < total_frame_size:
                        break
                    
                    # 提取完整帧内容 (Type 到 CRC)
                    frame_body = buffer[5:total_frame_size]
                    
                    # 解析内容
                    can_type = frame_body[0]
                    can_id = struct.unpack('>I', frame_body[1:5])[0]
                    dlc = frame_body[5]
                    
                    # DLC 转换数据长度
                    data_len = self.dlc_to_length(dlc)
                    
                    msg_data = frame_body[6:6+data_len]
                    timestamp = struct.unpack('>I', frame_body[6+data_len:10+data_len])[0]
                    crc_received = struct.unpack('>H', frame_body[10+data_len:12+data_len])[0]
                    
                    # 校验 CRC (校验范围: Type 到 Timestamp)
                    crc_calc = self.calculate_crc16(frame_body[:10+data_len])
                    
                    if crc_received == crc_calc:
                        msg_info = {
                            'timestamp_rel': time.time(),
                            'channel': channel_id,
                            'can_id': can_id,
                            'can_type': can_type,
                            'dlc': dlc,
                            'data': msg_data,
                            'timestamp': timestamp,
                            'direction': 'RX'
                        }
                        if not self.msg_queue.full():
                            self.msg_queue.put(msg_info)
                        with self._rx_condition:
                            self._rx_history.append(msg_info)
                            self._rx_condition.notify_all()
                        if self.on_message_received:
                            self.on_message_received(msg_info)

                    # 移除已处理的帧
                    buffer = buffer[total_frame_size:]
                    
            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[RNCAN] Receive error: {e}")
                self.is_connected = False
                break

    def send_can_message(self, channel_id: int, can_id: int, can_type: int, dlc: int, data: bytes) -> bool:
        if not self.is_connected:
            return False
            
        try:
            target_len = self.dlc_to_length(dlc)
            if len(data) < target_len:
                data = data.ljust(target_len, b'\x00')
            elif len(data) > target_len:
                data = data[:target_len]
            
            timestamp = 0 
            
            # 构建 CRC 校验数据 (CAN Type + CAN ID + DLC + Data + Timestamp)
            crc_data = struct.pack('>B', can_type)
            crc_data += struct.pack('>I', can_id)
            crc_data += struct.pack('B', dlc)
            crc_data += data
            crc_data += struct.pack('>I', timestamp)
            
            crc16 = self.calculate_crc16(crc_data)
            
            # 组装完整帧
            frame_length = len(crc_data) + 2 # + CRC16
            
            packet = struct.pack('>H', self.MAGIC)
            packet += struct.pack('B', channel_id)
            packet += struct.pack('>H', frame_length)
            packet += crc_data
            packet += struct.pack('>H', crc16)
            
            with self.lock:
                if self.sock:
                    self.sock.sendall(packet)
                    # 触发本地回调以显示在发送日志中
                    msg_info = {
                        'timestamp_rel': time.time(),
                        'channel': channel_id,
                        'can_id': can_id,
                        'can_type': can_type,
                        'dlc': dlc,
                        'data': data,
                        'timestamp': int(time.time()*1000) % 0xFFFFFFFF,
                        'direction': 'TX'
                    }
                    if not self.msg_queue.full():
                        self.msg_queue.put(msg_info)
                    if self.on_message_received:
                        self.on_message_received(msg_info)
                    return True
            return False
        except Exception as e:
            print(f"[RNCAN] Send error: {e}")
            return False

    def clear_rx_history(self, can_id: Optional[int] = None):
        with self._rx_condition:
            if can_id is None:
                self._rx_history.clear()
            else:
                self._rx_history = deque(
                    (msg for msg in self._rx_history if msg.get('can_id') != can_id),
                    maxlen=self._rx_history.maxlen
                )

    def wait_for_message(self, can_id: Optional[int] = None, channel_id: Optional[int] = None,
                         predicate: Optional[Callable] = None, timeout: float = 1.0):
        deadline = time.time() + max(0.0, timeout)
        seen_index = 0
        with self._rx_condition:
            while True:
                history = list(self._rx_history)
                for msg in history[seen_index:]:
                    if can_id is not None and msg.get('can_id') != can_id:
                        continue
                    if channel_id is not None and msg.get('channel') != channel_id:
                        continue
                    if predicate and not predicate(msg):
                        continue
                    return msg
                seen_index = len(history)

                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._rx_condition.wait(remaining)

    def send_and_wait_response(self, channel_id: int, can_id: int, can_type: int, dlc: int,
                               data: bytes, response_id: int, timeout: float = 1.0,
                               matcher: Optional[Callable] = None):
        self.clear_rx_history(response_id)
        if not self.send_can_message(channel_id, can_id, can_type, dlc, data):
            return None
        return self.wait_for_message(
            can_id=response_id,
            channel_id=channel_id,
            predicate=matcher,
            timeout=timeout
        )

    def dlc_to_length(self, dlc: int) -> int:
        if dlc <= 8:
            return dlc
        dlc_map = {9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64}
        return dlc_map.get(dlc, 8)

    def length_to_dlc(self, length: int) -> int:
        if length <= 8: return length
        if length <= 12: return 9
        if length <= 16: return 10
        if length <= 20: return 11
        if length <= 24: return 12
        if length <= 32: return 13
        if length <= 48: return 14
        return 15
