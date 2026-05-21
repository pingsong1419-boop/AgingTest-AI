import socket
import struct
import threading
import time
import random
import logging
import select

logger = logging.getLogger("S7PLC")

class ChamberController:
    """
    S7-200 Smart PLC ISO-on-TCP (S7 Comm) 通讯驱动 (纯 Python 实现)
    支持真实 S7-200 Smart PLC 网络读写与高仿真自适应模拟运行双模。
    
    点位映射机制：
    - V 区映射为 DB1 (例如 V0.5 -> DB1.DBX0.5, VD750 -> DB1.DBD750)
    - I 区 -> Area 0x82
    - Q 区 -> Area 0x83
    """
    def __init__(self, ip: str = "192.168.2.1", port: int = 102, slave_id: int = 1):
        self.ip = ip
        self.port = port
        self.sock = None
        self.lock = threading.Lock()
        self.is_connected = False
        self.use_simulation = True

        # 初始化 S7-200 Smart 41 个核心通讯点位寄存器缓存
        self.data_store = {
            # 1. 读写点位 (V / VD)
            "V0.5": False,      # 系统启动
            "V0.6": False,      # 系统停止
            "V699.0": False,    # 制冷、制热模式转换 (False=制冷, True=制热)
            "V699.2": False,    # 手动、自动模式转换 (False=手动, True=自动)
            "VD750": 25.0,      # 制冷设定温度
            "VD800": 25.0,      # 制热设定温度

            # 2. 只读状态点位 (Q / I)
            "Q1.5": False,      # 门禁状态 (False=安全, True=开门)
            "Q1.6": True,       # 灯状态
            "Q0.3": False,      # 高温机1状态
            "Q0.4": False,      # 低温机1状态
            "Q0.5": False,      # 冷风机1状态
            "Q1.0": False,      # 高温机2状态
            "Q1.1": False,      # 低温机2状态
            "Q1.2": False,      # 冷风机2状态
            "Q0.0": False,      # 加热器状态
            "Q0.1": False,      # 热风机状态
            "I2.4": True,       # 水流开关状态

            # 3. 只读温度点位 (VD - REAL)
            "VD720": 25.0,      # 库内实际温度 (高温箱实时温度)
            "VD220": 25.0,      # 板换1温度 (PT100实时温度 1)
            "VD224": 25.0,      # 板换2温度 (PT100实时温度 2)
            "VD228": 25.0,      # 冷却水温度

            # 4. 只读故障报警点位 (V - BOOL)
            "V15.1": False,     # 高温机1接触器故障
            "V15.2": False,     # 高温机1综合保护器故障
            "V15.3": False,     # 高温机1油压差开关信号报警
            "V15.5": False,     # 高温机1高、低压开关信号报警
            "V16.1": False,     # 低温机1接触器故障
            "V16.2": False,     # 低温机1综合保护器故障
            "V16.3": False,     # 低温机1油压差开关信号报警
            "V16.5": False,     # 低温机1高、低压开关信号报警
            "V17.1": False,     # 高温机2接触器故障
            "V17.2": False,     # 高温机2综合保护器故障
            "V17.3": False,     # 高温机2油压差开关信号报警
            "V17.5": False,     # 高温机2高、低压开关信号报警
            "V18.1": False,     # 低温机2接触器故障
            "V18.2": False,     # 低温机2综合保护器故障
            "V18.3": False,     # 低温机2油压差开关信号报警
            "V18.5": False,     # 低温机2高、低压开关信号报警
            "V21.0": False,     # 急停按钮动作
            "V21.1": False,     # 相序保护报警
            "V22.7": False,     # 加热器风机接触器吸合故障
            "V22.4": False,     # 水流开关故障
        }

        # 仿真温湿度渐变相关变量
        self.sim_system_on = False

    def connect(self) -> bool:
        """物理探测 S7-200 Smart TCP 端口并进行 ISO-on-TCP 两次握手 (严格使用 OP 类型的 TSAP 连接，释放 PG 供调试)"""
        if self.is_connected and not self.use_simulation and self.sock:
            return True

        with self.lock:
            # 严格使用 OP/HMI 类型 TSAP (Dst 必须是 02.xx)
            tsap_candidates = [
                (0x01, 0x00, 0x02, 0x00), # Src 01.00, Dst 02.00 (标准 OP 连接 1)
                (0x02, 0x00, 0x02, 0x00), # Src 02.00, Dst 02.00 (标准 OP 连接 2)
                (0x10, 0x00, 0x02, 0x00), # Src 10.00, Dst 02.00 (标准 OP 连接 3)
                (0x01, 0x00, 0x02, 0x01), # Src 01.00, Dst 02.01 (OP 扩展通道 1)
                (0x02, 0x00, 0x02, 0x01), # Src 02.00, Dst 02.01 (OP 扩展通道 2)
                (0x10, 0x00, 0x02, 0x01), # Src 10.00, Dst 02.01 (OP 扩展通道 3)
            ]

            for src_h, src_l, dst_h, dst_l in tsap_candidates:
                try:
                    if self.sock:
                        try: self.sock.close()
                        except: pass
                    
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.setblocking(False)
                    
                    try:
                        self.sock.connect((self.ip, self.port))
                    except Exception:
                        pass
                    
                    ready = select.select([], [self.sock], [], 0.5)
                    if not ready[1]:
                        continue
                        
                    err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if err != 0:
                        continue
                        
                    self.sock.setblocking(True)
                    self.sock.settimeout(1.0)
                    
                    # 第一步握手: Send COTP Connection Request (CR)
                    cr_packet = bytearray([
                        0x03, 0x00, 0x00, 0x16,  # RFC 1006 Header
                        0x11, 0xe0, 0x00, 0x00, 0x00, 0x01, 0x00,  # COTP Header
                        0xc0, 0x01, 0x0a, 
                        0xc1, 0x02, src_h, src_l,  # TSAP Src
                        0xc2, 0x02, dst_h, dst_l   # TSAP Dst (OP 类型 02.xx)
                    ])
                    self.sock.send(cr_packet)
                    resp = self.sock.recv(1024)
                    if len(resp) < 10 or resp[5] != 0xd0:
                        continue 
                        
                    # 第二步握手: Send S7 Setup Communication Request
                    setup_packet = bytearray([
                        0x03, 0x00, 0x00, 0x19,  # RFC 1006 Header
                        0x02, 0xf0, 0x80,        # COTP Header
                        0x32, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00,  # S7 Header
                        0xf0, 0x00, 0x00, 0x01, 0x00, 0x01, 0x03, 0xc0  # Params: Max PDU 960
                    ])
                    self.sock.send(setup_packet)
                    resp = self.sock.recv(1024)
                    if len(resp) < 20 or resp[17] != 0x00:
                        continue 
                        
                    # 握手完全成功！
                    self.is_connected = True
                    self.use_simulation = False
                    logger.info(f"成功连上真实 S7-200 Smart PLC (OP 类型): {self.ip}:{self.port} (TSAP Src={src_h:02x}.{src_l:02x}, Dst={dst_h:02x}.{dst_l:02x})")
                    return True
                except Exception as e:
                    continue
            
            # 若所有 TSAP 均告失败，自动降级为高保真自适应仿真模式
            self.is_connected = True
            self.use_simulation = True
            logger.info("所有 OP TSAP 握手协商均告失败，已自动降级启用高保真自适应仿真模式")
            return True

    def disconnect(self):
        with self.lock:
            self._handle_socket_error()

    def _handle_socket_error(self):
        """异常安全地重置 socket 状态并标记离线，以便下次 tick 自动重连"""
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        self.sock = None
        self.is_connected = False

    def read_bytes(self, area: int, db_number: int, start_byte: int, length: int) -> bytes:
        """从 S7-200 Smart 物理读取一个字节数据块"""
        if self.use_simulation or not self.sock:
            return b""
            
        with self.lock:
            try:
                bit_offset = start_byte * 8
                addr_2 = (bit_offset >> 16) & 0xFF
                addr_1 = (bit_offset >> 8) & 0xFF
                addr_0 = bit_offset & 0xFF
                
                pdu_ref = random.randint(1, 65535)
                
                packet = bytearray([
                    0x03, 0x00, 0x00, 0x1f,  # TPKT: length = 31 bytes
                    0x02, 0xf0, 0x80,        # COTP
                    0x32, 0x01,              # S7 ID (0x32), Msg Type (0x01 Job Request)
                    0x00, 0x00,              # Reserved
                    (pdu_ref >> 8) & 0xFF, pdu_ref & 0xFF, # PDU Reference
                    0x00, 0x0e,              # Parameter Length (14)
                    0x00, 0x00,              # Data Length (0)
                    
                    # --- Parameter Field ---
                    0x04,                    # Function: Read Var
                    0x01,                    # Item Count: 1
                    0x12,                    # Specification Type: Var Specification
                    0x0a,                    # Length of Rest
                    0x10,                    # Syntax ID: Any-pointer
                    0x02,                    # Transport size: Byte
                    (length >> 8) & 0xFF, length & 0xFF, # Length to read
                    (db_number >> 8) & 0xFF, db_number & 0xFF, # DB Number (DB1 for V area)
                    area,                    # Area code (0x84 = DB/V, 0x83 = Q, 0x82 = I)
                    addr_2, addr_1, addr_0   # Address offset in bits
                ])
                
                self.sock.send(packet)
                resp = self.sock.recv(2048)
                
                if len(resp) < 25:
                    return b""
                    
                if resp[8] != 0x03:
                    return b""
                    
                if resp[17] != 0x00 or resp[18] != 0x00:
                    return b""
                    
                param_len = struct.unpack(">H", resp[13:15])[0]
                data_offset = 7 + 12 + param_len
                if data_offset + 4 > len(resp):
                    return b""
                    
                return_code = resp[data_offset]
                if return_code != 0xFF:
                    return b""
                    
                payload_offset = data_offset + 4
                byte_len = length
                # Some S7 stacks return BYTE read lengths in bits. The mapping file
                # uses byte lengths, so byte length is primary and bit length is fallback.
                remaining = len(resp) - payload_offset
                if byte_len > remaining:
                    length_field = struct.unpack(">H", resp[data_offset + 2: data_offset + 4])[0]
                    byte_len = length_field // 8

                if payload_offset + byte_len > len(resp):
                    return b""
                    
                return bytes(resp[payload_offset: payload_offset + byte_len])
            except Exception as e:
                logger.error(f"[S7PLC] read_bytes 异常, 正在自动断开重建: {e}")
                self._handle_socket_error()
                return b""

    def write_s7_data(self, area: int, db_number: int, start_byte: int, bit: int, is_bit: bool, payload: bytes) -> bool:
        """物理向 S7-200 Smart 写入一个变量 (BOOL 或 REAL)"""
        if self.use_simulation or not self.sock:
            return True
            
        with self.lock:
            try:
                bit_offset = start_byte * 8
                if is_bit:
                    bit_offset += bit
                    
                addr_2 = (bit_offset >> 16) & 0xFF
                addr_1 = (bit_offset >> 8) & 0xFF
                addr_0 = bit_offset & 0xFF
                
                data_len = 4 + len(payload)
                total_len = 35 + len(payload)
                pdu_ref = random.randint(1, 65535)
                
                transport_size_param = 0x01 if is_bit else 0x02
                length_param = 1 if is_bit else len(payload)
                
                transport_size_data = 0x03 if is_bit else 0x04
                length_data_field = len(payload) if is_bit else len(payload) * 8
                
                packet = bytearray([
                    0x03, 0x00, (total_len >> 8) & 0xFF, total_len & 0xFF, # TPKT
                    0x02, 0xf0, 0x80,        # COTP
                    0x32, 0x01,              # S7 Job Request
                    0x00, 0x00,              # Reserved
                    (pdu_ref >> 8) & 0xFF, pdu_ref & 0xFF, # PDU Reference
                    0x00, 0x0e,              # Parameter Length (14)
                    (data_len >> 8) & 0xFF, data_len & 0xFF, # Data Length
                    
                    # --- Parameter Field ---
                    0x05,                    # Function: Write Var
                    0x01,                    # Item Count: 1
                    0x12,                    # Specification Type: Var Specification
                    0x0a,                    # Length of Rest
                    0x10,                    # Syntax ID: Any-pointer
                    transport_size_param,    # Transport size in parameter
                    (length_param >> 8) & 0xFF, length_param & 0xFF, # Length in parameter
                    (db_number >> 8) & 0xFF, db_number & 0xFF, # DB Number (DB1 for V area)
                    area,                    # Area code (0x84 = DB/V)
                    addr_2, addr_1, addr_0,  # Address offset in bits
                    
                    # --- Data Field ---
                    0x00,                    # Return Code
                    transport_size_data,     # Transport size in data
                    (length_data_field >> 8) & 0xFF, length_data_field & 0xFF # Data length in bytes
                ])
                packet.extend(payload)
                
                self.sock.send(packet)
                resp = self.sock.recv(1024)
                
                if len(resp) < 22:
                    return False
                    
                if resp[8] != 0x03:
                    return False
                    
                if resp[17] != 0x00 or resp[18] != 0x00:
                    return False
                    
                param_len = struct.unpack(">H", resp[13:15])[0]
                data_offset = 7 + 12 + param_len
                if data_offset < len(resp) and resp[data_offset] == 0xFF:
                    return True
                    
                return False
            except Exception as e:
                logger.error(f"[S7PLC] write_s7_data 异常, 正在自动断开重建: {e}")
                self._handle_socket_error()
                return False

    def write_bit(self, name: str, value: bool) -> bool:
        """写入 BOOL 变量 (系统启动/停止/模式等)"""
        paired_write = None
        with self.lock:
            self.data_store[name] = value
            
            # 手动系统启停联动逻辑 (仅作为本地缓存参考)
            if name == "V0.5" and value:
                self.data_store["V0.6"] = False
                self.sim_system_on = True
                paired_write = ("V0.6", False)
            elif name == "V0.6" and value:
                self.data_store["V0.5"] = False
                self.sim_system_on = False
                paired_write = ("V0.5", False)

        if not self.use_simulation and self.sock:
            ok = True
            if paired_write:
                ok = self._write_bit_physical(*paired_write) and ok
            ok = self._write_bit_physical(name, value) and ok
            return ok
        return True

    def _write_bit_physical(self, name: str, value: bool) -> bool:
        try:
            parts = name.replace("V", "").split(".")
            start_byte = int(parts[0])
            bit = int(parts[1])
            payload = b"\x01" if value else b"\x00"
            return self.write_s7_data(area=0x84, db_number=1, start_byte=start_byte, bit=bit, is_bit=True, payload=payload)
        except Exception as e:
            logger.error(f"[S7PLC] 写入 {name} 失败: {e}")
            return False

    def write_real(self, name: str, value: float) -> bool:
        """写入 REAL 实数变量 (设定温度)"""
        with self.lock:
            self.data_store[name] = round(value, 1)

        if not self.use_simulation and self.sock:
            try:
                start_byte = int(name.replace("VD", ""))
                payload = struct.pack(">f", value)
                return self.write_s7_data(area=0x84, db_number=1, start_byte=start_byte, bit=0, is_bit=False, payload=payload)
            except Exception as e:
                logger.error(f"[S7PLC] 写入 {name} 失败: {e}")
                return False
        return True

    def get_all_data(self) -> dict:
        """定时拉取并同步所有的点位状态数据 (已深度合并与优化，添加 20ms 电序延时保护)"""
        if self.use_simulation or not self.sock:
            self._update_simulation_logic()
            return self.data_store.copy()
            
        try:
            # 1. 读取 V 区前半部分报警与状态 (V0 - V23, 24 bytes)
            v_bits_0_23 = self.read_bytes(area=0x84, db_number=1, start_byte=0, length=24)
            if v_bits_0_23 and len(v_bits_0_23) >= 24:
                self.data_store["V0.5"] = bool(v_bits_0_23[0] & (1 << 5))
                self.data_store["V0.6"] = bool(v_bits_0_23[0] & (1 << 6))
                
                # 解析 V15
                self.data_store["V15.1"] = bool(v_bits_0_23[15] & (1 << 1))
                self.data_store["V15.2"] = bool(v_bits_0_23[15] & (1 << 2))
                self.data_store["V15.3"] = bool(v_bits_0_23[15] & (1 << 3))
                self.data_store["V15.5"] = bool(v_bits_0_23[15] & (1 << 5))
                
                # 解析 V16
                self.data_store["V16.1"] = bool(v_bits_0_23[16] & (1 << 1))
                self.data_store["V16.2"] = bool(v_bits_0_23[16] & (1 << 2))
                self.data_store["V16.3"] = bool(v_bits_0_23[16] & (1 << 3))
                self.data_store["V16.5"] = bool(v_bits_0_23[16] & (1 << 5))
                
                # 解析 V17
                self.data_store["V17.1"] = bool(v_bits_0_23[17] & (1 << 1))
                self.data_store["V17.2"] = bool(v_bits_0_23[17] & (1 << 2))
                self.data_store["V17.3"] = bool(v_bits_0_23[17] & (1 << 3))
                self.data_store["V17.5"] = bool(v_bits_0_23[17] & (1 << 5))
                
                # 解析 V18
                self.data_store["V18.1"] = bool(v_bits_0_23[18] & (1 << 1))
                self.data_store["V18.2"] = bool(v_bits_0_23[18] & (1 << 2))
                self.data_store["V18.3"] = bool(v_bits_0_23[18] & (1 << 3))
                self.data_store["V18.5"] = bool(v_bits_0_23[18] & (1 << 5))
                
                # 解析 V21
                self.data_store["V21.0"] = bool(v_bits_0_23[21] & (1 << 0))
                self.data_store["V21.1"] = bool(v_bits_0_23[21] & (1 << 1))
                
                # 解析 V22
                self.data_store["V22.7"] = bool(v_bits_0_23[22] & (1 << 7))
                self.data_store["V22.4"] = bool(v_bits_0_23[22] & (1 << 4))
                
            # 给 PLC CPU 留出 20ms 的处理空闲，防止高频 TCP 数据粘连
            time.sleep(0.02)
                
            # 2. 读取 PT100 实际温度 VD220, VD224, VD228 (12 bytes)
            v_reals_220 = self.read_bytes(area=0x84, db_number=1, start_byte=220, length=12)
            if v_reals_220 and len(v_reals_220) >= 12:
                self.data_store["VD220"] = struct.unpack(">f", v_reals_220[0:4])[0]
                self.data_store["VD224"] = struct.unpack(">f", v_reals_220[4:8])[0]
                self.data_store["VD228"] = struct.unpack(">f", v_reals_220[8:12])[0]
                
            time.sleep(0.02)
            
            # 3. 核心高度合并：读取 V699.0-VD803 (105 bytes: 包含 V699、VD720、VD750、VD800)
            v_combo_699 = self.read_bytes(area=0x84, db_number=1, start_byte=699, length=105)
            if v_combo_699 and len(v_combo_699) >= 105:
                # 解析 V699
                self.data_store["V699.0"] = bool(v_combo_699[0] & (1 << 0))
                self.data_store["V699.2"] = bool(v_combo_699[0] & (1 << 2))
                
                # 解析 reals (偏移量 = byte_idx - 699)
                self.data_store["VD720"] = struct.unpack(">f", v_combo_699[21:25])[0]
                self.data_store["VD750"] = struct.unpack(">f", v_combo_699[51:55])[0]
                self.data_store["VD800"] = struct.unpack(">f", v_combo_699[101:105])[0]
                
            time.sleep(0.02)
                
            # 4. 读取 Q 区继电器 (Q0 to Q1, 2 bytes)
            q_bits = self.read_bytes(area=0x83, db_number=0, start_byte=0, length=2)
            if q_bits and len(q_bits) >= 2:
                self.data_store["Q0.0"] = bool(q_bits[0] & (1 << 0))
                self.data_store["Q0.1"] = bool(q_bits[0] & (1 << 1))
                self.data_store["Q0.3"] = bool(q_bits[0] & (1 << 5)) # 冷风机1 Q0.5 -> 映射图第9项
                self.data_store["Q0.3"] = bool(q_bits[0] & (1 << 3)) # 高温机1 Q0.3 -> 映射图第7项
                self.data_store["Q0.4"] = bool(q_bits[0] & (1 << 4)) # 低温机1 Q0.4 -> 映射图第8项
                self.data_store["Q0.5"] = bool(q_bits[0] & (1 << 5)) # 冷风机1 Q0.5 -> 映射图第9项
                
                self.data_store["Q1.0"] = bool(q_bits[1] & (1 << 0))
                self.data_store["Q1.1"] = bool(q_bits[1] & (1 << 1))
                self.data_store["Q1.2"] = bool(q_bits[1] & (1 << 2))
                self.data_store["Q1.5"] = bool(q_bits[1] & (1 << 5))
                self.data_store["Q1.6"] = bool(q_bits[1] & (1 << 6))
                
            time.sleep(0.02)
                
            # 5. 读取 I 区开关量 (I0 to I2, 3 bytes)
            i_bits = self.read_bytes(area=0x82, db_number=0, start_byte=0, length=3)
            if i_bits and len(i_bits) >= 3:
                self.data_store["I2.4"] = bool(i_bits[2] & (1 << 4))
                
        except Exception as e:
            logger.error(f"[S7PLC] get_all_data 物理抓取失败: {e}")
            self._handle_socket_error()
            
        for k in ["VD720", "VD220", "VD224", "VD228", "VD750"]:
            try:
                self.data_store[k] = round(self.data_store[k], 1)
            except:
                pass
                
        return self.data_store.copy()

    def _update_simulation_logic(self):
        """高保真 PLC 仿真运行逻辑机"""
        is_on = self.data_store["V0.5"] and not self.data_store["V0.6"]
        mode_heat = self.data_store["V699.0"]
        target_temp = self.data_store["VD800"] if mode_heat else self.data_store["VD750"]
        current_temp = self.data_store["VD720"]

        rate = 0.6
        if is_on:
            if current_temp < target_temp:
                self.data_store["VD720"] = min(target_temp, current_temp + rate + random.uniform(-0.02, 0.02))
            elif current_temp > target_temp:
                self.data_store["VD720"] = max(target_temp, current_temp - rate + random.uniform(-0.02, 0.02))
            else:
                self.data_store["VD720"] += random.uniform(-0.05, 0.05)
                
            actual = self.data_store["VD720"]
            self.data_store["Q1.5"] = False
            self.data_store["I2.4"] = True
            self.data_store["Q1.6"] = True
            
            if mode_heat:
                if actual < target_temp - 0.2:
                    self.data_store["Q0.0"] = True
                    self.data_store["Q0.1"] = True
                else:
                    self.data_store["Q0.0"] = random.choice([True, False])
                    self.data_store["Q0.1"] = True
                self.data_store["Q0.3"] = False
                self.data_store["Q0.4"] = False
                self.data_store["Q0.5"] = False
                self.data_store["Q1.0"] = False
                self.data_store["Q1.1"] = False
                self.data_store["Q1.2"] = False
            else:
                self.data_store["Q0.0"] = False
                self.data_store["Q0.1"] = False
                if actual > target_temp + 0.5:
                    self.data_store["Q0.3"] = True
                    self.data_store["Q0.4"] = True
                    self.data_store["Q0.5"] = True
                    if target_temp < 0:
                        self.data_store["Q1.0"] = True
                        self.data_store["Q1.1"] = True
                        self.data_store["Q1.2"] = True
                    else:
                        self.data_store["Q1.0"] = False
                        self.data_store["Q1.1"] = False
                        self.data_store["Q1.2"] = False
                else:
                    self.data_store["Q0.3"] = False
                    self.data_store["Q0.4"] = False
                    self.data_store["Q0.5"] = True
                    self.data_store["Q1.0"] = False
                    self.data_store["Q1.1"] = False
                    self.data_store["Q1.2"] = False

            actual_temp = self.data_store["VD720"]
            if self.data_store["Q0.3"]:
                self.data_store["VD220"] = actual_temp - 8.0 + random.uniform(-0.1, 0.1)
                self.data_store["VD224"] = actual_temp - 12.0 + random.uniform(-0.1, 0.1)
            else:
                self.data_store["VD220"] = actual_temp + random.uniform(-0.2, 0.2)
                self.data_store["VD224"] = actual_temp + random.uniform(-0.2, 0.2)
                
            if self.data_store["Q0.3"] or self.data_store["Q1.0"]:
                self.data_store["VD228"] = min(35.0, self.data_store["VD228"] + 0.1)
            else:
                self.data_store["VD228"] = max(26.0, self.data_store["VD228"] - 0.05)
        else:
            self.data_store["Q0.0"] = False
            self.data_store["Q0.1"] = False
            self.data_store["Q0.3"] = False
            self.data_store["Q0.4"] = False
            self.data_store["Q0.5"] = False
            self.data_store["Q1.0"] = False
            self.data_store["Q1.1"] = False
            self.data_store["Q1.2"] = False
            self.data_store["Q1.5"] = True
            self.data_store["Q1.6"] = False
            
            if current_temp < 25.0:
                self.data_store["VD720"] = min(25.0, current_temp + 0.15)
            elif current_temp > 25.0:
                self.data_store["VD720"] = max(25.0, current_temp - 0.15)
            
            self.data_store["VD220"] = self.data_store["VD720"]
            self.data_store["VD224"] = self.data_store["VD720"]
            self.data_store["VD228"] = max(25.0, self.data_store["VD228"] - 0.05)
