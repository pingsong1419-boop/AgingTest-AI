from .lingtu_66100 import Lingtu66100
from .ngi_n3618 import NGIN3618
from .afe_power_ru36 import AFEPowerRU36
from .mainboard_power_ru60 import MainboardPowerRU60
from .mainboard_power_ru60 import MainboardPowerRU60
from .aging_board_driver import AgingBoardController
from .ca550_driver import CA550Controller
from .easy320_driver import Easy320Controller
from .afe_power_driver import AFEPowerController
from .power_board_ru12 import PowerBoardRU12
from .control_board import ControlBoard


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
        self.dut_power = None
        self.ctrl_board_power = None
        self.ca550 = None
        self.easy320 = None
        
        
        
        self.boards = {} # {channel_id: ControlBoard}
        
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

        # 4. 被测物供电电源 (DUT Power)
        dut_ip = cfg.get("dut_pwr_ip", "192.168.1.201")
        dut_port = int(cfg.get("dut_pwr_port", 2000))
        self.dut_power = MainboardPowerRU60(dut_ip, dut_port)

        # 5. 老化控制板供电电源 (Control Board Power)
        ctrl_pwr_ip = cfg.get("ctrl_pwr_ip", "192.168.1.202")
        ctrl_pwr_port = int(cfg.get("ctrl_pwr_port", 10001))
        self.ctrl_board_power = PowerBoardRU12(ctrl_pwr_ip, ctrl_pwr_port)

        # 6. CA550
        ca_com = cfg.get("ca550_com", "COM5")
        self.ca550 = CA550Controller(port=ca_com)

        # 7. Easy320
        e320_ip = cfg.get("easy320_ip", "192.168.1.88")
        self.easy320 = Easy320Controller(e320_ip)

        # 8. 60路老化控制板 (分布式)
        ch_configs = []
        if self.db_manager:
            ch_configs = self.db_manager.load_channel_config() or []
        
        base_ip = cfg.get("board_base_ip", "192.168.1.")
        start_suffix = int(cfg.get("board_start_suffix", 101))
        
        # 建立一个映射字典供快速查询
        db_ips = {c["channel_id"]: c["board_ip"] for c in ch_configs if c.get("board_ip")}

        for i in range(1, 61):
            ip = db_ips.get(i) or f"{base_ip}{start_suffix + i - 1}"
            self.boards[i] = ControlBoard(ip, i)

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

    def init_all_devices(self, logger=None):
        """
        初始化连接所有硬件，遵循方案书要求的顺序启动防浪涌逻辑
        """
        if logger: logger("[*] 开始系统硬件全量初始化...")
        
        # 1. 基础控制与校准设备初始化
        if self.easy320: self.easy320.connect()
        if self.ca550: self.ca550.connect()
        
        # 2. 电源类设备初始化
        if self.hv_source: self.hv_source.connect()
        if self.afe_power_1: self.afe_power_1.connect()
        if self.afe_pwr_standalone: self.afe_pwr_standalone.connect()
        if self.afe_pwr_3: self.afe_pwr_3.connect()
        if self.dut_power: self.dut_power.connect()
        if self.ctrl_board_power: self.ctrl_board_power.connect()
        
        # 3. 电池模拟器初始化
        for sim in self.simulators:
            sim.connect()
            
        # 4. [关键] 老化板分级顺序启动防浪涌逻辑
        if self.easy320 and self.easy320.is_connected:
            if logger: logger("[*] 触发分级上电逻辑 (PLC Easy320)...")
            # 假设每路继电器控制一个老化架或一组老化板，分批启动
            # 此处演示为 1-16 路继电器，每 500ms 开启一个
            import time
            for i in range(16):
                self.easy320.write_relay(i, True)
                time.sleep(0.5) 
            if logger: logger("[*] 分级上电指令发送完毕。")
        
        # 5. [关键] 逻辑自检：确认老化板 TCP 握手在线状态
        if logger: logger("[*] 开始扫描 60 路老化板在线状态 (TCP 握手)...")
        online_count = 0
        # 考虑到 60 个连接可能较慢，实际建议改为多线程扫描，此处先串行演示逻辑
        for i, board in self.boards.items():
            if board.connect():
                online_count += 1
                if i % 10 == 0 and logger: # 减少日志冗余
                    logger(f"    - 进度: 已检测 {i}/60 通道")
        
        if logger: 
            logger(f"[*] 硬件初始化完成。在线老化板: {online_count} / 60")
            if online_count < 60:
                logger(f"[!] 警告: 有 {60 - online_count} 个通道目前处于离线状态")
        return True

    def get_all_device_status(self):
        """获取所有设备的连接状态列表，供 UI 展示"""
        status_list = []
        
        # 定义辅助函数
        def add_status(name, device, info=""):
            is_conn = getattr(device, "is_connected", False) if device else False
            status_list.append({
                "name": name,
                "info": info or (getattr(device, "ip", "") if device else ""),
                "status": "已联机" if is_conn else "离线",
                "color": "#28A745" if is_conn else "#DC3545"
            })

        connected_boards = sum(1 for b in self.boards.values() if b.is_connected)
        add_status("老化控制板 (分布式)", None, f"已联机: {connected_boards} / 60")
        
        if self.hv_source: add_status("NGI 高压源", self.hv_source)
        if self.afe_power_1: add_status("1# AFE 供电电源", self.afe_power_1)
        if self.afe_pwr_standalone: add_status("2# AFE 调试电源", self.afe_pwr_standalone)
        if self.dut_power: add_status("被测物供电电源 (DUT)", self.dut_power)
        if self.ctrl_board_power: add_status("控制板供电电源 (Ctrl Board)", self.ctrl_board_power)
        if self.ca550: add_status("CA550 校准源", self.ca550, self.ca550.port)
        if self.easy320: add_status("Easy320 继电器", self.easy320)
        
        for i, sim in enumerate(self.simulators):
            add_status(f"{i+1}# 电池模拟器 (18CH)", sim)
            
        return status_list

    def disconnect_all(self):
        """安全断开所有硬件连接"""
        print("正在断开所有硬件设备连接...")
        for sim in self.simulators:
            sim.disconnect()
        if self.hv_source: self.hv_source.disconnect()
        if self.afe_power_1: self.afe_power_1.disconnect()
        if self.afe_pwr_standalone: self.afe_pwr_standalone.disconnect()
        if self.afe_pwr_3: self.afe_pwr_3.disconnect()
        if self.dut_power: self.dut_power.disconnect()
        if self.ctrl_board_power: self.ctrl_board_power.disconnect()
        for board in self.boards.values():
            board.disconnect()
            
        if self.easy320: self.easy320.disconnect()
        if self.ca550: self.ca550.disconnect()

    def emergency_stop(self):
        """紧急停止：关闭所有电源输出"""
        print("!!! 触发紧急停止 !!!")
        self.broadcast_output(False)
        if self.afe_power_1 and self.afe_power_1.is_connected:
            self.afe_power_1.output_control(False)
        if self.dut_power and self.dut_power.is_connected:
            self.dut_power.output_control(False)
        if self.hv_source and self.hv_source.is_connected:
            self.hv_source.output_control(False)
