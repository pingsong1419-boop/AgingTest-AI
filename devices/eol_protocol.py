import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class EOLResult:
    success: bool
    response_code: Optional[int] = None
    payload: bytes = b""
    raw_data: bytes = b""
    value: Any = None
    error: str = ""


class EOLProtocol:
    REQUEST_ID = 0x7F0
    RESPONSE_ID = 0x7F8
    REQUEST_PREFIX = 0x10
    RESPONSE_PREFIX = 0x11
    POSITIVE_RESPONSE = 0x40
    NEGATIVE_RESPONSE = 0x80

    def __init__(self, can_driver, channel_id: int = 0):
        self.can_driver = can_driver
        self.channel_id = channel_id
        self.operations = self._build_operations()

    def transact(self, device_id: int, operation: int, payload: Optional[bytes] = None,
                 timeout: float = 1.0, decoder: Optional[Callable[[bytes], Any]] = None,
                 request_id: Optional[int] = None, response_id: Optional[int] = None,
                 can_type: int = 0, dlc: int = 8,
                 logger: Callable[[str], None] = None) -> EOLResult:
        req_id = request_id if request_id is not None else self.REQUEST_ID
        resp_id = response_id if response_id is not None else self.RESPONSE_ID
        payload_data = (payload or b"")[:4].ljust(4, b"\x00")
        request_data = bytes([self.REQUEST_PREFIX, device_id & 0xFF, operation & 0xFF, 0x00]) + payload_data
        
        # 记录发送日志
        log_msg = f"CAN TX CH:{self.channel_id} ID={hex(req_id).upper()} DATA={request_data.hex(' ').upper()}"
        if logger: 
            logger(log_msg)
        else:
            print(log_msg)

        def matcher(msg):
            mid = msg.get('can_id')
            data = msg.get("data", b"")
            # 记录所有进入 matcher 的报文，排查 seen_index 是否正常
            # print(f"[MATCHER-TRACE] ID=0x{mid:X} DATA={data.hex(' ').upper()}")
            
            match = (
                len(data) >= 4
                and data[0] == self.RESPONSE_PREFIX
                and data[1] == (device_id & 0xFF)
                and data[2] == (operation & 0xFF)
            )
            # 调试：打印所有 ID 匹配的报文内容，确认匹配逻辑是否失效
            # if mid == resp_id:
            #     print(f"[EOL-DEBUG] Candidate Message: ID=0x{mid:X} DATA={data.hex(' ').upper()} Match={match} (Expected: {hex(self.RESPONSE_PREFIX)} {hex(device_id)} {hex(operation)})")
            return match

        def local_log(msg):
            if logger: logger(msg)
            else: print(msg)

        # 增加重试机制，应对网络抖动或硬件繁忙
        import time
        for attempt in range(2):
            if attempt > 0:
                local_log(f"EOL 重试 {attempt}...")
                time.sleep(0.2) # 重试前稍作等待

            local_log(f"Waiting for EOL response (ID=0x{resp_id:X}, timeout={timeout}s)...")
            send_time = time.time()
            if not self.can_driver.send_can_message(self.channel_id, req_id, can_type, dlc, request_data):
                if attempt == 1: return EOLResult(False, error="CAN发送失败")
                continue

            msg = self.can_driver.wait_for_message(
                can_id=resp_id,
                channel_id=None, 
                predicate=matcher,
                timeout=timeout,
                since_time=send_time
            )
            if msg:
                break
        else:
            return EOLResult(False, error="EOL响应超时")

        raw = msg.get("data", b"")
        response_code = raw[3] if len(raw) >= 4 else None
        payload = raw[4:] if len(raw) > 4 else b""
        if response_code != self.POSITIVE_RESPONSE:
            return EOLResult(False, response_code=response_code, payload=payload, raw_data=raw, error=f"EOL否定响应: 0x{response_code:02X}" if response_code is not None else "EOL响应格式错误")

        value = payload.hex(" ").upper()
        if decoder:
            value = decoder(raw)
        return EOLResult(True, response_code=response_code, payload=payload, raw_data=raw, value=value)

    def execute(self, op_name: str, timeout: float = 1.0, logger: Callable[[str], None] = None, **kwargs) -> EOLResult:
        if op_name not in self.operations:
            return EOLResult(False, error=f"不支持的EOL操作: {op_name}")
        
        spec = self.operations[op_name]
        try:
            payload = spec.get("payload")(kwargs) if callable(spec.get("payload")) else spec.get("payload")
            tx_id = self._int_arg(kwargs, "TX_ID", "发送ID") if "TX_ID" in kwargs or "发送ID" in kwargs else None
            rx_id = self._int_arg(kwargs, "RX_ID", "接收ID") if "RX_ID" in kwargs or "接收ID" in kwargs else None
            
            # 提取 TYPE 和 DLC (由 StepDialog 传入)
            can_type = self._int_arg(kwargs, "TYPE", "CAN类型") if "TYPE" in kwargs or "CAN类型" in kwargs else 0
            dlc = self._int_arg(kwargs, "DLC", "长度") if "DLC" in kwargs or "长度" in kwargs else 8
            
            # ADC 读取模式特殊处理 (0x06)
            op_code = spec.get("operation", 0)
            if "0x06" in op_name:
                # ADC: 0x01 raw, 0x02 value
                mode_str = str(kwargs.get("读取模式", kwargs.get("MODE", ""))).upper()
                op_code = 0x01 if "RAW" in mode_str or "原始" in mode_str else 0x02

            return self.transact(
                device_id=spec.get("device_id"),
                operation=op_code,
                payload=payload,
                timeout=timeout,
                decoder=spec.get("decoder"),
                request_id=tx_id,
                response_id=rx_id,
                can_type=can_type,
                dlc=dlc,
                logger=logger
            )
        except Exception as e:
            return EOLResult(False, error=f"EOL参数错误: {e}")

    def _build_operations(self) -> Dict[str, Dict[str, Any]]:
        return {
            # --- 0x03 绝缘 ---
            "0x03_insulation_control": {"device_id": 0x03, "operation": 0x01, "payload": lambda kw: bytes([0x01, self._int_arg(kw, "STATE", "VALUE")])},
            "0x03 绝缘控制写入": {"device_id": 0x03, "operation": 0x01, "payload": lambda kw: bytes([0x01, self._int_arg(kw, "STATE", "VALUE")])},
            "0x03_read_insulation": {"device_id": 0x03, "operation": 0x03, "decoder": self._decode_insulation},
            "0x03 绝缘控制读取": {"device_id": 0x03, "operation": 0x03, "decoder": self._decode_insulation},
            
            # --- 0x04 GPIO ---
            "0x04_read_gpio": {"device_id": 0x04, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX")]), "decoder": self._decode_index_value},
            "0x04 GPIO控制读取": {"device_id": 0x04, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX")]), "decoder": self._decode_index_value},
            "0x04_write_gpio": {"device_id": 0x04, "operation": 0x05, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX"), self._int_arg(kw, "LEVEL", "VALUE")])},
            "0x04 GPIO控制写入": {"device_id": 0x04, "operation": 0x05, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX"), self._int_arg(kw, "LEVEL", "VALUE")])},
            
            # --- 0x05 PWM ---
            "0x05_read_pwm_duty": {"device_id": 0x05, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_byte4},
            "0x05 PWM读取": {"device_id": 0x05, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_byte4},
            
            # --- 0x06 ADC ---
            "0x06_read_adc_value": {"device_id": 0x06, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "ADC")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            "0x06 ADC读取": {"device_id": 0x06, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "ADC")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            
            # --- 0x07 CSC ---
            "0x07 CSC控制读取": {"device_id": 0x07, "operation": 0x0E, "payload": lambda kw: self._int_arg(kw, "CELL", "INDEX", "TYPE").to_bytes(2, "big"), "decoder": lambda raw: self._decode_data_u32(raw) * 0.001},
            "0x07 CSC控制写入": {"device_id": 0x07, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "COUNT", "STATE", "TYPE")])},
            
            # --- 0x08 CRASH ---
            "0x08 CRASH读取": {"device_id": 0x08, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "TYPE")]), "decoder": self._decode_data_u32},
            
            # --- 0x09 RTC ---
            "0x09 RTC控制读取": {"device_id": 0x09, "operation": 0x04, "decoder": self._decode_payload_hex},
            "0x09 RTC控制写入": {"device_id": 0x09, "operation": 0x07, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            
            # --- 0x10 NTC ---
            "0x10 NTC读取": {"device_id": 0x10, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            
            # --- 0x0A EEPROM ---
            "0x0A EEPROM控制读取": {"device_id": 0x0A, "operation": 0x03, "decoder": self._decode_payload_hex},
            "0x0A EEPROM控制写入": {"device_id": 0x0A, "operation": 0x05, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            
            # --- 0x0B 霍尔电流 ---
            "0x0B 霍尔电流读取": {"device_id": 0x0B, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "HALL", "CHANNEL")]), "decoder": self._decode_current},
            
            # --- 0xFF 唤醒源 ---
            "0xFF 唤醒源读取": {"device_id": 0xFF, "operation": 0x06, "decoder": self._decode_byte4},
        }

    def _int_arg(self, kwargs, *names, length: Optional[int] = None) -> int:
        # 扩展搜索名称，增加通用回退项
        search_names = list(names)
        search_names.extend([
            "INDEX", "索引", "VALUE", "数值", "STATE", "状态", "参数1", "参数2", "ARG1", "ARG2",
            "PWM通道", "GPIO通道", "ADC选择", "ADC", "读取模式", "MODE", "NTC索引", "霍尔通道", "读取项", "子索引/状态", "控制值"
        ])
        
        for name in search_names:
            u_name = name.upper()
            if u_name in kwargs:
                value = kwargs[u_name]
                if isinstance(value, int):
                    return value
                try:
                    return int(str(value).strip(), 0)
                except:
                    continue
        raise ValueError(f"缺少参数: {'/'.join(names)} (当前可用: {list(kwargs.keys())})")

    def _bytes_arg(self, kwargs, name: str, length: Optional[int] = None) -> bytes:
        if name not in kwargs:
            raise ValueError(f"缺少参数: {name}")
        value = kwargs[name]
        if isinstance(value, bytes):
            data = value
        else:
            text = str(value).replace("0x", "").replace(" ", "").replace(",", "")
            data = bytes.fromhex(text)
        if length is not None:
            data = data[:length].ljust(length, b"\x00")
        return data

    def _decode_payload_hex(self, raw: bytes):
        return raw[4:8].hex(" ").upper() if len(raw) > 4 else ""

    def _decode_byte4(self, raw: bytes):
        return raw[4] if len(raw) > 4 else None

    def _decode_index_value(self, raw: bytes):
        return raw[5] if len(raw) > 5 else None

    def _decode_index_u16(self, raw: bytes):
        """解析返回报文中的 U16 数据 (通常在 Byte 5, 6)"""
        if len(raw) < 7:
            return 0
        # 高位在前，低位在后 (Big Endian)
        val = (raw[5] << 8) | raw[6]
        return val

    def _decode_data_u32(self, raw: bytes):
        data = raw[4:8]
        return int.from_bytes(data.ljust(4, b"\x00"), "big")

    def _decode_insulation(self, raw: bytes):
        if len(raw) < 8:
            return 0.0
        value = (raw[4] << 16) | (raw[5] << 8) | raw[6]
        sign = -1 if raw[7] == 1 else 1
        return sign * value * 0.001

    def _decode_temp(self, raw: bytes):
        if len(raw) < 6:
            return None
        return raw[5] - 50

    def _decode_current(self, raw: bytes):
        value = self._decode_data_u32(raw)
        return value * 0.001 - 800
