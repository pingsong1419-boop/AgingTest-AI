from .lingtu_66100 import Lingtu66100
from .ngi_n3618 import NGIN3618
from .afe_power_ru36 import AFEPowerRU36
from .mainboard_power_ru60 import MainboardPowerRU60
from .can_bus import CANBus
from .aging_board_driver import AgingBoardController
from .ca550_driver import CA550Controller
from .easy320_driver import Easy320Controller
from .afe_power_driver import AFEPowerController
from .rn_can_driver import RNCANDriver
from .power_board_ru12 import PowerBoardRU12


class DeviceManager:
    """
    设备驱动统一管理类 (单例模式)
    负责解耦和管理所有的硬件仪器：电池模拟器、高压源、AFE电源、主机电源、CAN等。
    """
    def __init__(self):
        # 1. 领图 66100 电池模拟器 (三台设备)
        self.simulators = [
            Lingtu66100(ip="192.168.1.210"), # Unit 1 (CH 1-18)
            Lingtu66100(ip="192.168.1.211"), # Unit 2 (CH 19-36)
            Lingtu66100(ip="192.168.1.212"), # Unit 3 (CH 37-54)
            Lingtu66100(ip="192.168.1.213")  # Unit 4
        ]
        
        # 2. NGI N3618 高压直流电源
        self.hv_source = NGIN3618(ip="192.168.1.190", port=7000)
        
        # 3. 1#AFE 供电电源 (RU36-100V36A)
        self.afe_power_1 = AFEPowerRU36(ip="192.168.1.200", port=2000)
        
        # 4. 主机供电电源 (RU60-30V200A)
        self.mainboard_power = MainboardPowerRU60(ip="192.168.1.201", port=2000)
        
        # 5. CAN 总线适配器
        self.can_bus = CANBus(channel="CAN1")

        # 6. 老化功能板 (继电器矩阵)
        self.aging_board = AgingBoardController(ip="192.168.1.10")

        # 7. Easy320 继电器控制板
        self.easy320 = Easy320Controller(ip="192.168.1.88")

        # 8. 横河 CA550 校准仪
        self.ca550 = CA550Controller(port="COM5")

        # 9. AFE 电源 (使用 afe_power_driver.py)
        self.afe_pwr_standalone = AFEPowerController(ip="192.168.1.203")

        # 10. RNCAN 网关
        self.rn_can = RNCANDriver(ip="192.168.1.10")

        # 11. 功能测试板电源 (RU12-3040)
        self.power_board_ru12 = PowerBoardRU12(ip="192.168.1.202", port=2000)

    def _get_sim_and_ch(self, global_ch: int):
        """
        根据全局通道号 (1-60) 自动路由到具体的物理设备和物理通道
        """
        unit_index = (global_ch - 1) // 18
        local_ch = (global_ch - 1) % 18 + 1
        
        if unit_index < len(self.simulators):
            return self.simulators[unit_index], local_ch
        return None, None

    def set_voltage(self, global_ch: int, voltage: float, logger=None):
        sim, ch = self._get_sim_and_ch(global_ch)
        if sim: return sim.set_voltage(ch, voltage, logger)
        if logger: logger(f"错误: 找不到通道 {global_ch} 对应的模拟器")
        return False

    def set_current(self, global_ch: int, current: float, logger=None):
        sim, ch = self._get_sim_and_ch(global_ch)
        if sim: return sim.set_current_limit(ch, current, logger)
        if logger: logger(f"错误: 找不到通道 {global_ch} 对应的模拟器")
        return False

    def output_control(self, global_ch: int, state: bool, logger=None):
        sim, ch = self._get_sim_and_ch(global_ch)
        if sim: return sim.output_control(ch, state, logger)
        if logger: logger(f"错误: 找不到通道 {global_ch} 对应的模拟器")
        return False

    def measure_voltage(self, global_ch: int, logger=None) -> float:
        sim, ch = self._get_sim_and_ch(global_ch)
        if sim: return sim.measure_voltage(ch, logger)
        if logger: logger(f"错误: 找不到通道 {global_ch} 对应的模拟器")
        return -1.0

    def measure_current(self, global_ch: int, logger=None) -> float:
        sim, ch = self._get_sim_and_ch(global_ch)
        if sim: return sim.measure_current(ch, logger)
        if logger: logger(f"错误: 找不到通道 {global_ch} 对应的模拟器")
        return -1.0

    def broadcast_voltage(self, voltage: float) -> bool:
        """
        全系统广播设置电压：对所有连接的模拟器发送 0 号通道指令
        """
        print(f"[*] 全系统同步设置电压: {voltage}V")
        success = True
        for sim in self.simulators:
            if sim.is_connected:
                if not sim.set_voltage(0, voltage):
                    success = False
        return success

    def broadcast_current(self, current: float) -> bool:
        """
        全系统广播设置电流
        """
        print(f"[*] 全系统同步设置电流限制: {current}A")
        success = True
        for sim in self.simulators:
            if sim.is_connected:
                sim.set_current_limit(0, current)
        return success

    def broadcast_output(self, state: bool) -> bool:
        """
        全系统广播输出控制：开启/关闭所有模拟器输出
        """
        print(f"[*] 全系统同步输出控制: {state}")
        success = True
        for sim in self.simulators:
            if sim.is_connected:
                if not sim.output_control(0, state):
                    success = False
        return success

    def init_all_devices(self):
        """初始化连接所有硬件"""
        results = []
        results.append(self.can_bus.connect())
        results.append(self.aging_board.connect())
        results.append(self.easy320.connect())
        # CA550 串口连接
        results.append(self.ca550.connect())
        
        for sim in self.simulators:
            results.append(sim.connect())
            
        return all(results)

    def disconnect_all(self):
        """安全断开所有硬件连接"""
        print("正在断开所有硬件设备连接...")
        for sim in self.simulators:
            sim.disconnect()
        self.hv_source.disconnect()
        self.afe_power_1.disconnect()
        self.mainboard_power.disconnect()
        self.can_bus.disconnect()
        self.aging_board.disconnect()
        self.easy320.disconnect()
        self.ca550.disconnect()
        self.afe_pwr_standalone.disconnect()
        self.rn_can.disconnect()
        self.power_board_ru12.disconnect()

    def emergency_stop(self):
        """紧急停止：关闭所有电源输出"""
        print("!!! 触发紧急停止 !!!")
        self.broadcast_output(False)
        if self.afe_power_1.is_connected:
            self.afe_power_1.output_control(False)
        if self.mainboard_power.is_connected:
            self.mainboard_power.output_control(False)
