from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType
import socket
import logging
import time

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AgingBoardDriver")

class AgingBoardController:
    """
    老化功能板驱动 (独立版)
    负责控制 60 路通道对应的继电器切换
    """
    
    # 继电器位定义 (基于 Modbus 线圈地址)
    RELAY_MAP = {
        "KL15": 0x00,
        "CC1_2K_12V": 0x01,
        "ISO_NEG_SHORT": 0x02,
        "CHAOJI_CC_1K": 0x03,
        "IN1_OUT1": 0x04,
        "IN2_OUT2": 0x05,
        "IN3_OUT3": 0x06,
        "CAN_MATCH": 0x07,
        "SIG1_SIG2_SHORT": 0x08,
        "SIG3_SHORT": 0x09,
        "CAN1": 0x0A,
        "CAN2": 0x0B,
        "CAN3": 0x0C,
        "CAN4": 0x0D,
        "HV": 0x0E,
        "ISOD_30K_1M": 0x0F,
        "ISOD_1M_30K": 0x10,
        "LINK_PACK_SHORT": 0x11,
        "FACH_PACK_SHORT": 0x12,
        "DC_DC_100K": 0x13,
        "DC_DC_500K": 0x14,
        "HALL_POWER": 0x15
    }

    def __init__(self, ip: str, port: int = 502, slave_id: int = 1):
        """
        初始化驱动
        :param ip: 板卡 IP 地址
        :param port: Modbus TCP 端口 (默认为 502)
        :param slave_id: 从机 ID (通常为 1)
        """
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.client = ModbusTcpClient(
            self.ip, 
            port=self.port,
            framer=FramerType.SOCKET,
            timeout=2.0
        )
        self.is_connected = False
        # 初始化继电器状态追踪 (对齐参考项目)
        self.relay_states = {addr: False for addr in self.RELAY_MAP.values()}

    def connect(self) -> bool:
        """建立 Modbus TCP 连接 (带物理探测与协议校验)"""
        try:
            # 1. 物理探测，防止 Modbus 库在 IP 不通时长时间挂起
            with socket.create_connection((self.ip, self.port), timeout=0.8) as s:
                pass
            
            # 2. 检查并重建客户端 (对齐参考项目)
            if self.client.comm_params.host != self.ip or self.client.comm_params.port != self.port:
                try: self.client.close()
                except: pass
                self.client = ModbusTcpClient(
                    self.ip, 
                    port=self.port,
                    framer=FramerType.SOCKET,
                    timeout=2.0
                )

            # 3. 建立 Modbus 连接与协议级校验
            if self.client.connect():
                # 尝试读取 1 个线圈作为协议握手
                try:
                    result = self.client.read_coils(address=0, count=1, device_id=self.slave_id)
                    if not result.isError():
                        self.is_connected = True
                        logger.info(f"功能板 {self.ip} 连接成功")
                        return True
                    
                    # 兼容性处理：检查是否收到设备异常响应 (对齐参考项目)
                    from pymodbus.pdu import ExceptionResponse
                    if isinstance(result, ExceptionResponse):
                        self.is_connected = True
                        logger.info(f"功能板 {self.ip} 协议校验通过 (收到异常响应)")
                        return True
                except Exception as e:
                    logger.warning(f"功能板 {self.ip} TCP 已连接，但 Modbus 握手失败: {e}")
                    # 只要 TCP 通了，我们先认为是在线的，后续指令执行时会再次尝试
                    self.is_connected = True
                    return True

            return False
        except Exception as e:
            logger.error(f"功能板 {self.ip} 连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.client.close()
        self.is_connected = False
        logger.info(f"功能板 {self.ip} 已断开连接")

    def set_relay_by_name(self, name: str, state: bool) -> bool:
        """根据继电器名称控制开关 (如 'KL15')"""
        if name not in self.RELAY_MAP:
            logger.error(f"未知继电器名称: {name}")
            return False
        return self.write_relay(self.RELAY_MAP[name], state)

    def write_relay(self, address: int, state: bool) -> bool:
        """根据线圈地址写入单个继电器 (带自动重试与链路自愈)"""
        for attempt in range(2): # 最多尝试 2 次
            try:
                if not self.is_connected or not self.client.is_socket_open():
                    if not self.connect():
                        if attempt == 1: return False # 第二次还连不上就放弃
                        continue

                result = self.client.write_coil(address=address, value=state, device_id=self.slave_id)
                if result and not result.isError():
                    self.relay_states[address] = state
                    return True
                
                # 如果是 Modbus 错误，尝试重置连接后在下一次循环中重试
                logger.warning(f"写入线圈 {address} 失败 (Modbus Error), 正在尝试重连重试...")
                self.disconnect()
            except Exception as e:
                logger.error(f"写入线圈 {address} 异常 (Attempt {attempt+1}): {e}")
                self.disconnect() # 发生异常必须断开以触发下次重连
                time.sleep(0.1)
        return False

    def read_relays(self, count: int = 22) -> list:
        """读取所有继电器当前状态 (0-21)"""
        if not self.is_connected:
            return []
        try:
            result = self.client.read_coils(address=0, count=count, device_id=self.slave_id)
            if result.isError():
                return []
            return result.bits[:count]
        except Exception as e:
            logger.error(f"读取老化板状态失败: {e}")
            return []

    def write_all_off(self) -> bool:
        """批量关闭本板卡所有 22 路继电器"""
        if not self.is_connected:
            return False
        try:
            result = self.client.write_coils(address=0, values=[False] * 22, device_id=self.slave_id)
            if not result.isError():
                # 重置本地状态缓存
                for addr in self.relay_states:
                    self.relay_states[addr] = False
                return True
            return False
        except Exception as e:
            logger.error(f"批量关闭失败: {e}")
            return False
    
    # 兼容性别名
    def all_off(self):
        return self.write_all_off()

# --- 使用示例 ---
if __name__ == "__main__":
    # 请根据实际情况修改 IP
    TEST_IP = "192.168.1.10"
    
    board = AgingBoardController(TEST_IP)
    if board.connect():
        print("--- 开始测试 ---")
        # 1. 控制 KL15
        board.set_relay_by_name("KL15", True)
        time.sleep(1)
        
        # 2. 控制霍尔电源
        board.set_relay_by_name("HALL_POWER", True)
        time.sleep(1)
        
        # 3. 全部关闭
        board.all_off()
        
        board.disconnect()
