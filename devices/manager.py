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
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.simulators = []
        self.hv_source = None
        self.afe_power_1 = None
        self.afe_pwr_standalone = None
        self.afe_pwr_3 = None
        self.mainboard_power = None
        self.power_board_ru12 = None
        self.ca550 = None
        self.easy320 = None
        
        self.can_bus = CANBus(channel="CAN1")
        self.aging_board = AgingBoardController(ip="192.168.1.10")
        self.rn_can = RNCANDriver(ip="192.168.1.10")
        
        self.update_config()

    def update_config(self):
        """根据数据库配置更新/重新初始化设备实例"""
        cfg = {}
        if self.db_manager:
            cfg = self.db_manager.load_sys_config() or {}

        # 1. 模拟电池
        sim1_ip = cfg.get("sim1_ip", "192.168.1.210")
        sim1_port = int(cfg.get("sim1_port", 5025))
        sim2_ip = cfg.get("sim2_ip", "192.168.1.211")
        sim2_port = int(cfg.get("sim2_port", 5025))
        sim3_ip = cfg.get("sim3_ip", "192.168.1.212")
        sim3_port = int(cfg.get("sim3_port", 5025))
        
        self.simulators = [
            Lingtu66100(sim1_ip, sim1_port),
            Lingtu66100(sim2_ip, sim2_port),
            Lingtu66100(sim3_ip, sim3_port)
        ]

        # 2. NGI 高压源
        hv_ip = cfg.get("hv_ip", "192.168.1.190")
        hv_port = int(cfg.get("hv_port", 7000))
        self.hv_source = NGIN3618(hv_ip, hv_port)

        # 3. AFE 电源
        afe1_ip = cfg.get("afe1_ip", "192.168.1.200")
        afe1_port = int(cfg.get("afe1_port", 2000))
        self.afe_power_1 = AFEPowerRU36(afe1_ip, afe1_port)

        afe2_ip = cfg.get("afe2_ip", "192.168.1.203")
        afe2_port = int(cfg.get("afe2_port", 10001))
        self.afe_pwr_standalone = AFEPowerController(afe2_ip, afe2_port)

        afe3_ip = cfg.get("afe3_ip", "192.168.1.203")
        afe3_port = int(cfg.get("afe3_port", 10001))
        self.afe_pwr_3 = AFEPowerController(afe3_ip, afe3_port)

        # 4. 主机板电源
        main_ip = cfg.get("main_ip", "192.168.1.201")
        main_port = int(cfg.get("main_port", 2000))
        self.mainboard_power = MainboardPowerRU60(main_ip, main_port)

        # 5. 功能测试板电源
        pb_ip = cfg.get("pwr_board_ip", "192.168.1.202")
        pb_port = int(cfg.get("pwr_board_port", 10001))
        self.power_board_ru12 = PowerBoardRU12(pb_ip, pb_port)

        # 6. CA550
        ca_com = cfg.get("ca550_com", "COM5")
        self.ca550 = CA550Controller(port=ca_com)

        # 7. Easy320
        e320_ip = cfg.get("easy320_ip", "192.168.1.88")
        self.easy320 = Easy320Controller(e320_ip)

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

    def broadcast_voltage(self, voltage: float, logger=None) -> bool:
        """
        全系统广播设置电压：对所有连接的模拟器发送 0 号通道指令
        """
        if logger: logger(f"[*] 全系统同步设置电压: {voltage}V")
        success = True
        connected_sims = 0
        for sim in self.simulators:
            if sim.is_connected:
                connected_sims += 1
                if not sim.set_voltage(0, voltage):
                    success = False
        if connected_sims == 0:
            if logger: logger("错误：所有模拟器均未连接")
            return False
        return success

    def broadcast_current(self, current: float, logger=None) -> bool:
        """
        全系统广播设置电流
        """
        if logger: logger(f"[*] 全系统同步设置电流限制: {current}A")
        success = True
        connected_sims = 0
        for sim in self.simulators:
            if sim.is_connected:
                connected_sims += 1
                if not sim.set_current_limit(0, current):
                    success = False
        if connected_sims == 0:
            if logger: logger("错误：所有模拟器均未连接")
            return False
        return success

    def broadcast_output(self, state: bool, logger=None) -> bool:
        """
        全系统广播输出控制：开启/关闭所有模拟器输出
        """
        if logger: logger(f"[*] 全系统同步输出控制: {state}")
        success = True
        connected_sims = 0
        for sim in self.simulators:
            if sim.is_connected:
                connected_sims += 1
                if not sim.output_control(0, state):
                    success = False
        if connected_sims == 0:
            if logger: logger("错误：所有模拟器均未连接")
            return False
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
        if self.hv_source: self.hv_source.disconnect()
        if self.afe_power_1: self.afe_power_1.disconnect()
        if self.mainboard_power: self.mainboard_power.disconnect()
        self.can_bus.disconnect()
        self.aging_board.disconnect()
        if self.easy320: self.easy320.disconnect()
        if self.ca550: self.ca550.disconnect()
        if self.afe_pwr_standalone: self.afe_pwr_standalone.disconnect()
        self.rn_can.disconnect()
        if self.power_board_ru12: self.power_board_ru12.disconnect()

    def emergency_stop(self):
        """紧急停止：关闭所有电源输出"""
        print("!!! 触发紧急停止 !!!")
        self.broadcast_output(False)
        if self.afe_power_1 and self.afe_power_1.is_connected:
            self.afe_power_1.output_control(False)
        if self.mainboard_power and self.mainboard_power.is_connected:
            self.mainboard_power.output_control(False)
