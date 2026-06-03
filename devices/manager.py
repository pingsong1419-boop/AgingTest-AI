from .lingtu_66100 import Lingtu66100
from .ngi_n3618 import NGIN3618
from .afe_power_ru36 import AFEPowerRU36
from .mainboard_power_ru60 import MainboardPowerRU60
from .aging_board_driver import AgingBoardController
from .ca550_driver import CA550Controller
from .easy320_driver import Easy320Controller
from .power_board_ru12 import PowerBoardRU12
from .control_board import ControlBoard
from .chamber_driver import ChamberController


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
        self.afe_pwr_2 = None
        self.afe_pwr_3 = None
        self.dut_power = None
        self.ctrl_board_power = None
        self.ca550 = None
        self.easy320 = None
        self.chamber = None
        
        
        
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
            Lingtu66100(sim1_ip, sim1_port, max_channels=18),
            Lingtu66100(sim2_ip, sim2_port, max_channels=18),
            Lingtu66100(sim3_ip, sim3_port, max_channels=18)
        ]
        # BUG-11修复: 删除后台线程connect，避免与init_all_devices的串行connect产生竞态

        # 2. NGI 高压源
        hv_ip = cfg.get("hv_ip", "192.168.1.190")
        hv_port = int(cfg.get("hv_port", 7000))
        self.hv_source = NGIN3618(hv_ip, hv_port)

        # 3. AFE 电源
        afe1_ip = cfg.get("afe1_ip", "192.168.1.200")
        afe1_port = int(cfg.get("afe1_port", 2000))
        self.afe_power_1 = AFEPowerRU36(afe1_ip, afe1_port)

        afe2_ip = cfg.get("afe2_ip", "192.168.1.204")
        afe2_port = int(cfg.get("afe2_port", 2000))
        self.afe_pwr_2 = AFEPowerRU36(afe2_ip, afe2_port)

        afe3_ip = cfg.get("afe3_ip", "192.168.1.203")
        afe3_port = int(cfg.get("afe3_port", 2000))
        self.afe_pwr_3 = AFEPowerRU36(afe3_ip, afe3_port)

        # 4. 被测物供电电源 (DUT Power)
        dut_ip = cfg.get("dut_pwr_ip", "192.168.1.201")
        dut_port = int(cfg.get("dut_pwr_port", 2000))
        self.dut_power = MainboardPowerRU60(dut_ip, dut_port)

        # 5. 控制板供电电源 (Control Board Power)
        ctrl_pwr_ip = cfg.get("ctrl_pwr_ip", "192.168.1.202")
        ctrl_pwr_port = int(cfg.get("ctrl_pwr_port", 10001))
        self.ctrl_board_power = PowerBoardRU12(ctrl_pwr_ip, ctrl_pwr_port)

        # 6. CA550
        ca_com = cfg.get("ca550_com", "")
        self.ca550 = CA550Controller(port=ca_com)

        # 7. Easy320
        e320_ip = cfg.get("easy320_ip", "192.168.1.88")
        self.easy320 = Easy320Controller(e320_ip)

        # 8. 高低温老化箱
        chamber_ip = cfg.get("chamber_ip", "192.168.1.150")
        chamber_port = int(cfg.get("chamber_port", 502))
        self.chamber = ChamberController(chamber_ip, chamber_port)

        # 9. 60路老化控制板 (分布式)
        ch_configs = []
        if self.db_manager:
            ch_configs = self.db_manager.load_channel_config() or []
        
        base_ip = cfg.get("board_base_ip", "192.168.1.")
        start_suffix = int(cfg.get("board_start_suffix", 10))
        
        # 建立一个映射字典供快速查询
        db_ips = {c["channel_id"]: c["board_ip"] for c in ch_configs if c.get("board_ip")}

        for i in range(1, 49):
            ip = db_ips.get(i) or f"{base_ip}{start_suffix + i - 1}"
            self.boards[i] = ControlBoard(ip, i)

    def _get_sim_and_ch(self, global_ch: int):
        """
        根据全局通道号 (1-48) 自动路由到具体的物理设备和物理通道
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
        """全系统广播设置电压：对所有模拟器的 1-18 通道执行设置"""
        if logger: logger(f"[*] 全系统同步设置电压: {voltage}V")
        success = True
        for i, sim in enumerate(self.simulators):
            if sim.is_connected:
                if not sim.set_voltage(0, voltage): success = False
        return success

    def broadcast_current(self, current: float, logger=None) -> bool:
        """全系统广播设置电流：对所有模拟器的 1-18 通道执行设置"""
        if logger: logger(f"[*] 全系统同步设置电流限制: {current}A")
        success = True
        for i, sim in enumerate(self.simulators):
            if sim.is_connected:
                if not sim.set_current_limit(0, current): success = False
        return success

    def broadcast_range(self, range_str: str, logger=None) -> bool:
        """全系统广播设置量程: HIGH / LOW"""
        if logger: logger(f"[*] 全系统同步设置量程: {range_str}")
        success = True
        for i, sim in enumerate(self.simulators):
            if sim.is_connected:
                if not sim.set_range(0, range_str): success = False
        return success

    def broadcast_output(self, state: bool, logger=None) -> bool:
        """全系统广播输出控制"""
        if logger: logger(f"[*] 全系统同步输出控制: {'开启' if state else '关闭'}")
        success = True
        for i, sim in enumerate(self.simulators):
            if sim.is_connected:
                if not sim.output_control(0, state): success = False
        return success

    def init_all_devices(self, logger=None):
        """
        初始化连接所有硬件，遵循方案书要求的顺序启动防浪涌逻辑
        """
        if logger: logger("[*] 开始系统硬件全量初始化...")
        
        # 1. 基础控制与校准设备初始化
        if self.easy320: 
            self.easy320.connect()
            if logger: logger(f"[*] Easy320 PLC 状态: {'已联机' if self.easy320.is_connected else '离线'}")
        if self.ca550: 
            self.ca550.connect()
            if logger: logger(f"[*] CA550 校准源 状态: {'已联机' if self.ca550.is_connected else '离线'}")
        if self.chamber: 
            self.chamber.connect()
            if logger: logger(f"[*] 高低温老化箱 状态: {'已联机' if self.chamber.is_connected else '离线'}")
        
        # 2. 电源类设备初始化
        if self.hv_source: 
            self.hv_source.connect()
            if logger: logger(f"[*] NGI 高压源 状态: {'已联机' if self.hv_source.is_connected else '离线'}")
        if self.afe_power_1: 
            self.afe_power_1.connect()
            if logger: logger(f"[*] 1# AFE 供电电源 状态: {'已联机' if self.afe_power_1.is_connected else '离线'}")
        if hasattr(self, 'afe_pwr_2') and self.afe_pwr_2: 
            self.afe_pwr_2.connect()
            if logger: logger(f"[*] 2# AFE 供电电源 状态: {'已联机' if self.afe_pwr_2.is_connected else '离线'}")
        if self.afe_pwr_3: 
            self.afe_pwr_3.connect()
            if logger: logger(f"[*] 3# AFE 供电电源 状态: {'已联机' if self.afe_pwr_3.is_connected else '离线'}")
        
        if self.dut_power: 
            self.dut_power.connect()
            if logger: logger(f"[*] DUT 供电主电源 状态: {'已联机' if self.dut_power.is_connected else '离线'}")
            
        if self.ctrl_board_power: 
            self.ctrl_board_power.connect()
            if logger: logger(f"[*] 控制板主电源 状态: {'已联机' if self.ctrl_board_power.is_connected else '离线'}")
        
        # 3. 电池模拟器初始化
        sim_conn_count = 0
        for sim in self.simulators:
            if sim.connect():
                sim_conn_count += 1
        if logger: logger(f"[*] 电池模拟器 状态: {sim_conn_count} / {len(self.simulators)} 已联机")
            
        # 4. [关键] 功能板上电与 Easy320 分级上电逻辑
        power_ok = False
        if self.ctrl_board_power and self.ctrl_board_power.is_connected:
            if logger: logger("[*] 正在初始化控制板供电电源: 设定 24.0V / 40.0A ...")
            self.ctrl_board_power.set_voltage(24.0)
            self.ctrl_board_power.set_current(40.0)
            if self.ctrl_board_power.output_control(True):
                # 等待电压建立时间
                import time
                time.sleep(1.5) 
                v_meas = self.ctrl_board_power.measure_voltage()
                if logger: logger(f"[*] 控制板供电电源实时电压反馈: {v_meas:.2f}V")
                
                # 判定输出是否正常 (24V 允许 +/- 10% 误差)
                if 21.0 <= v_meas <= 27.0:
                    power_ok = True
                    if logger: logger("[+] 控制板供电电源输出正常，准备闭合继电器。")
                else:
                    if logger: logger(f"[!] 警告: 功能板电压异常 ({v_meas:.2f}V)，禁止启动后续继电器！")
            else:
                if logger: logger("[!] 错误: 无法开启功能板电源输出。")
        else:
            if logger: logger("[!] 错误: 功能板电源未联机，无法进行安全上电检查。")

        # 只有电源正常才允许操作 PLC 继电器
        if power_ok and self.easy320 and self.easy320.is_connected:
            if logger: logger("[*] 触发分级上电逻辑 (PLC Easy320 前16路)...")
            import time
            for i in range(16):
                if self.easy320.write_relay(i, True):
                    time.sleep(0.5) 
                else:
                    if logger: logger(f"[!] 警告: PLC 继电器 {i+1} 写入失败")
            if logger: logger("[*] 分级上电指令发送完毕。")
        elif not power_ok:
            if logger: logger("[!] 由于控制板供电电源异常，已跳过 PLC 继电器分级上电流程。")
        
        # 5. [关键] 逻辑自检：并行扫描 48 路老化板在线状态
        if logger: logger("[*] 开始并行扫描 48 路老化板在线状态 (TCP 握手)...")
        from concurrent.futures import ThreadPoolExecutor
        
        online_count = 0
        def check_board(b_tuple):
            idx, board = b_tuple
            if board.connect():
                return (idx, True, getattr(board, "ip", "Unknown IP"))
            return (idx, False, getattr(board, "ip", "Unknown IP"))

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(check_board, self.boards.items()))
            online_count = sum(1 for _, ok, _ in results if ok)
            offline_details = [f"CH{idx}({ip})" for idx, ok, ip in results if not ok]
        
        if logger: 
            logger(f"[*] 硬件初始化完成。在线老化板: {online_count} / 48")
            if online_count < 48:
                logger(f"[!] 警告: 有 {48 - online_count} 个通道目前处于离线状态")
                logger(f"[!] 离线通道详情: {', '.join(offline_details)}")
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
        add_status("老化控制板 (分布式)", None, f"已联机: {connected_boards} / 48")
        
        if self.hv_source: add_status("NGI 高压源", self.hv_source)
        if self.afe_power_1: add_status("1# AFE 供电电源", self.afe_power_1)
        if hasattr(self, 'afe_pwr_2') and self.afe_pwr_2: add_status("2# AFE 供电电源", self.afe_pwr_2)
        if hasattr(self, 'afe_pwr_3') and self.afe_pwr_3: add_status("3# AFE 供电电源", self.afe_pwr_3)
        if self.dut_power: add_status("被测物供电电源 (DUT)", self.dut_power)
        if self.ctrl_board_power: add_status("控制板供电电源 (Ctrl Board)", self.ctrl_board_power)
        if self.ca550: add_status("CA550 校准源", self.ca550, self.ca550.port)
        if self.easy320: add_status("Easy320 继电器", self.easy320)
        if self.chamber: add_status("高低温老化箱", self.chamber)
        
        for i, sim in enumerate(self.simulators):
            add_status(f"{i+1}# 电池模拟器 (18CH)", sim)
            
        return status_list

    def disconnect_all(self):
        """断开所有设备的连接并释放资源 (新增系统安全退出逻辑)"""
        print("[DeviceManager] 正在执行系统安全退出下电流程...")
        
        # 1. 优先关闭分级供电的继电器 (Easy320)
        if getattr(self, "easy320", None) and self.easy320.is_connected:
            try:
                for i in range(16):
                    self.easy320.write_relay(i, False)
                print("[DeviceManager] 已成功关闭分级供电的继电器。")
            except Exception as e:
                print(f"[DeviceManager] 继电器下电异常: {e}")
                
        # 2. 其次关闭控制板供电电源
        if getattr(self, "ctrl_board_power", None) and self.ctrl_board_power.is_connected:
            try:
                self.ctrl_board_power.output_control(False)
                print("[DeviceManager] 已成功关闭控制板供电电源。")
            except Exception as e:
                print(f"[DeviceManager] 控制板电源下电异常: {e}")

        # 3. 关闭被测物供电电源 (DUT Power)
        if getattr(self, "dut_power", None) and self.dut_power.is_connected:
            try:
                self.dut_power.output_control(False)
                print("[DeviceManager] 已成功关闭被测物(DUT)供电电源。")
            except Exception as e:
                print(f"[DeviceManager] 被测物(DUT)电源下电异常: {e}")

        if getattr(self, "chamber", None):
            try: self.chamber.disconnect()
            except: pass
        if getattr(self, "afe_system", None):
            try: self.afe_system.disconnect()
            except: pass
            
        for cid, board in self.boards.items():
            try: board.relays.disconnect()
            except: pass
            
        # 释放所有电源设备
        power_devices = [
            getattr(self, "hv_source", None),
            getattr(self, "dut_power", None),
            getattr(self, "ctrl_board_power", None),
            getattr(self, "afe_power_1", None),
            getattr(self, "afe_pwr_2", None),
            getattr(self, "afe_pwr_3", None)
        ]
        for pwr in power_devices:
            if pwr:
                try: pwr.disconnect()
                except: pass

        # 释放其他设备
        if getattr(self, "easy320", None):
            try: self.easy320.disconnect()
            except: pass
        if getattr(self, "ca550", None):
            try: self.ca550.disconnect()
            except: pass
            
        # 释放所有电池模拟器
        for sim in getattr(self, "simulators", []):
            try: sim.disconnect()
            except: pass
            
        print("[DeviceManager] 所有硬件设备通讯句柄已安全释放")

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
