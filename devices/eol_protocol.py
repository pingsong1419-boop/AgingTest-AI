from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


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
                 timeout: float = 1.0, decoder: Optional[Callable[[bytes], Any]] = None) -> EOLResult:
        payload = (payload or b"")[:4].ljust(4, b"\x00")
        request_data = bytes([self.REQUEST_PREFIX, device_id & 0xFF, operation & 0xFF, 0x00]) + payload

        def matcher(msg):
            data = msg.get("data", b"")
            return (
                len(data) >= 4
                and data[0] == self.RESPONSE_PREFIX
                and data[1] == (device_id & 0xFF)
                and data[2] == (operation & 0xFF)
            )

        msg = self.can_driver.send_and_wait_response(
            channel_id=self.channel_id,
            can_id=self.REQUEST_ID,
            can_type=0,
            dlc=8,
            data=request_data,
            response_id=self.RESPONSE_ID,
            timeout=timeout,
            matcher=matcher
        )
        if not msg:
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

    def execute(self, op_name: str, timeout: float = 1.0, **kwargs) -> EOLResult:
        op_key = op_name.strip().lower()
        spec = self.operations.get(op_key)
        if not spec:
            return EOLResult(False, error=f"未知EOL操作: {op_name}")

        try:
            payload = spec.get("payload", lambda _kw: b"")(kwargs)
            return self.transact(
                spec["device_id"],
                spec["operation"],
                payload=payload,
                timeout=timeout,
                decoder=spec.get("decoder")
            )
        except Exception as e:
            return EOLResult(False, error=f"EOL参数错误: {e}")

    def _build_operations(self) -> Dict[str, Dict[str, Any]]:
        return {
            "0x03_insulation_control": {"device_id": 0x03, "operation": 0x01, "payload": lambda kw: bytes([0x01, self._int_arg(kw, "STATE", "VALUE")])},
            "insulation_control": {"device_id": 0x03, "operation": 0x01, "payload": lambda kw: bytes([0x01, self._int_arg(kw, "STATE", "VALUE")])},
            "0x03_read_insulation": {"device_id": 0x03, "operation": 0x03, "decoder": self._decode_insulation},
            "read_insulation": {"device_id": 0x03, "operation": 0x03, "decoder": self._decode_insulation},
            "0x04_read_gpio": {"device_id": 0x04, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX")]), "decoder": self._decode_index_value},
            "read_gpio": {"device_id": 0x04, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX")]), "decoder": self._decode_index_value},
            "0x04_write_gpio": {"device_id": 0x04, "operation": 0x05, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX"), self._int_arg(kw, "LEVEL", "VALUE")])},
            "write_gpio": {"device_id": 0x04, "operation": 0x05, "payload": lambda kw: bytes([self._int_arg(kw, "GPIO", "INDEX"), self._int_arg(kw, "LEVEL", "VALUE")])},
            "0x05_read_pwm_duty": {"device_id": 0x05, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_byte4},
            "read_pwm_duty": {"device_id": 0x05, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_byte4},
            "0x05_read_pwm_freq": {"device_id": 0x05, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_data_u32},
            "read_pwm_freq": {"device_id": 0x05, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "PWM", "CHANNEL", "INDEX")]), "decoder": self._decode_data_u32},
            "0x06_read_adc_raw": {"device_id": 0x06, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "ADC", "INDEX")]), "decoder": self._decode_index_u16},
            "read_adc_raw": {"device_id": 0x06, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "ADC", "INDEX")]), "decoder": self._decode_index_u16},
            "0x06_read_adc_value": {"device_id": 0x06, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "ADC", "INDEX")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            "read_adc_value": {"device_id": 0x06, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "ADC", "INDEX")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            "0x07_set_csc_node_count": {"device_id": 0x07, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "COUNT", "VALUE")])},
            "set_csc_node_count": {"device_id": 0x07, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "COUNT", "VALUE")])},
            "0x07_read_csc_hv": {"device_id": 0x07, "operation": 0x02, "decoder": lambda raw: self._decode_data_u32(raw) * 0.001},
            "read_csc_hv": {"device_id": 0x07, "operation": 0x02, "decoder": lambda raw: self._decode_data_u32(raw) * 0.001},
            "0x07_csc_balance_control": {"device_id": 0x07, "operation": 0x03, "payload": lambda kw: bytes([self._int_arg(kw, "CELL", "INDEX"), self._int_arg(kw, "STATE", "VALUE")])},
            "csc_balance_control": {"device_id": 0x07, "operation": 0x03, "payload": lambda kw: bytes([self._int_arg(kw, "CELL", "INDEX"), self._int_arg(kw, "STATE", "VALUE")])},
            "0x07_read_cell_voltage": {"device_id": 0x07, "operation": 0x04, "payload": lambda kw: bytes([self._int_arg(kw, "CELL", "INDEX")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            "read_cell_voltage": {"device_id": 0x07, "operation": 0x04, "payload": lambda kw: bytes([self._int_arg(kw, "CELL", "INDEX")]), "decoder": lambda raw: self._decode_index_u16(raw) * 0.001},
            "0x07_read_stack_voltage": {"device_id": 0x07, "operation": 0x05, "decoder": lambda raw: self._decode_data_u32(raw) * 0.001},
            "read_stack_voltage": {"device_id": 0x07, "operation": 0x05, "decoder": lambda raw: self._decode_data_u32(raw) * 0.001},
            "0x07_read_fast_charge_impedance": {"device_id": 0x07, "operation": 0x06, "decoder": self._decode_data_u32},
            "read_fast_charge_impedance": {"device_id": 0x07, "operation": 0x06, "decoder": self._decode_data_u32},
            "0x08_read_crash_pwm_duty": {"device_id": 0x08, "operation": 0x01, "decoder": self._decode_byte4},
            "read_crash_pwm_duty": {"device_id": 0x08, "operation": 0x01, "decoder": self._decode_byte4},
            "0x08_read_crash_pwm_freq": {"device_id": 0x08, "operation": 0x02, "decoder": self._decode_data_u32},
            "read_crash_pwm_freq": {"device_id": 0x08, "operation": 0x02, "decoder": self._decode_data_u32},
            "0x08_read_crash_impedance": {"device_id": 0x08, "operation": 0x03, "decoder": self._decode_data_u32},
            "read_crash_impedance": {"device_id": 0x08, "operation": 0x03, "decoder": self._decode_data_u32},
            "0x08_read_crash_pulse_width": {"device_id": 0x08, "operation": 0x04, "decoder": self._decode_data_u32},
            "read_crash_pulse_width": {"device_id": 0x08, "operation": 0x04, "decoder": self._decode_data_u32},
            "0x09_read_rtc_time": {"device_id": 0x09, "operation": 0x01, "decoder": self._decode_payload_hex},
            "read_rtc_time": {"device_id": 0x09, "operation": 0x01, "decoder": self._decode_payload_hex},
            "0x09_set_rtc_wakeup": {"device_id": 0x09, "operation": 0x02, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "set_rtc_wakeup": {"device_id": 0x09, "operation": 0x02, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "0x09_set_rtc_time": {"device_id": 0x09, "operation": 0x03, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "set_rtc_time": {"device_id": 0x09, "operation": 0x03, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "0x10_read_cell_temp": {"device_id": 0x10, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "read_cell_temp": {"device_id": 0x10, "operation": 0x01, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "0x10_read_pcb_temp": {"device_id": 0x10, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "read_pcb_temp": {"device_id": 0x10, "operation": 0x02, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "0x10_read_host_temp": {"device_id": 0x10, "operation": 0x03, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "read_host_temp": {"device_id": 0x10, "operation": 0x03, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "0x10_read_host_pcb_temp": {"device_id": 0x10, "operation": 0x04, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "read_host_pcb_temp": {"device_id": 0x10, "operation": 0x04, "payload": lambda kw: bytes([self._int_arg(kw, "INDEX", "NTC")]), "decoder": self._decode_temp},
            "0x0a_set_eeprom_address": {"device_id": 0x0A, "operation": 0x01, "payload": lambda kw: self._int_arg(kw, "ADDRESS", length=4).to_bytes(4, "big")},
            "set_eeprom_address": {"device_id": 0x0A, "operation": 0x01, "payload": lambda kw: self._int_arg(kw, "ADDRESS", length=4).to_bytes(4, "big")},
            "0x0a_read_eeprom_data": {"device_id": 0x0A, "operation": 0x02, "decoder": self._decode_payload_hex},
            "read_eeprom_data": {"device_id": 0x0A, "operation": 0x02, "decoder": self._decode_payload_hex},
            "0x0a_write_eeprom_data": {"device_id": 0x0A, "operation": 0x03, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "write_eeprom_data": {"device_id": 0x0A, "operation": 0x03, "payload": lambda kw: self._bytes_arg(kw, "DATA", length=4)},
            "0x0b_read_hall_current": {"device_id": 0x0B, "operation": 0x01, "decoder": self._decode_current},
            "read_hall_current": {"device_id": 0x0B, "operation": 0x01, "decoder": self._decode_current},
            "0x0b_read_hall_current_2": {"device_id": 0x0B, "operation": 0x03, "decoder": self._decode_current},
            "read_hall_current_2": {"device_id": 0x0B, "operation": 0x03, "decoder": self._decode_current},
            "0xff_read_wakeup_source": {"device_id": 0xFF, "operation": 0x01, "decoder": self._decode_payload_hex},
            "read_wakeup_source": {"device_id": 0xFF, "operation": 0x01, "decoder": self._decode_payload_hex},
            "0xff_read_pressure_sensor": {"device_id": 0xFF, "operation": 0x02, "decoder": self._decode_data_u32},
            "read_pressure_sensor": {"device_id": 0xFF, "operation": 0x02, "decoder": self._decode_data_u32},
            "0xff_read_hsd_load_voltage": {"device_id": 0xFF, "operation": 0x03, "decoder": self._decode_data_u32},
            "read_hsd_load_voltage": {"device_id": 0xFF, "operation": 0x03, "decoder": self._decode_data_u32},
        }

    def _int_arg(self, kwargs, *names, length: Optional[int] = None) -> int:
        for name in names:
            if name in kwargs:
                value = kwargs[name]
                if isinstance(value, int):
                    return value
                return int(str(value), 0)
        raise ValueError(f"缺少参数: {'/'.join(names)}")

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
        if len(raw) < 7:
            return 0
        return (raw[5] << 8) | raw[6]

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
