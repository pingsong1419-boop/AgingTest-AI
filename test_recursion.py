import sys
sys.path.append('.')
from devices.eol_protocol import EOLProtocol

class DummyDriver:
    def send_can_message(self, *args, **kwargs):
        return True
    def wait_for_message(self, *args, **kwargs):
        # 模拟响应 11 07 0E 40 00 00 09 C3
        return {"data": bytes.fromhex("11 07 0E 40 00 00 09 C3")}
    def clear_rx_history(self, *args, **kwargs):
        pass

protocol = EOLProtocol(DummyDriver())

kwargs = {'EOL': '0x07 CSC控制读取', 'PARAM1': '0x0E', 'PARAM2': '0x00', 'PARAM3': '0', 'PARAM4': '169', 'OP': '0x0E', 'INDEX': '0xA9', 'TIMEOUT': '1000', 'CH': '0', 'TYPE': '0', 'DLC': '8', 'TX_ID': '0x7F0', 'RX_ID': '0x7F8'}

def dummy_logger(msg):
    pass

try:
    res = protocol.execute('0x07 CSC控制读取', timeout=1.0, logger=dummy_logger, **kwargs)
    print("SUCCESS", res)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR", e)
