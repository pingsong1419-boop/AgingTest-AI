from enum import Enum
import re
import threading
from typing import List, Dict, Optional, Any
from PySide6.QtCore import QObject, Signal, QThread, QTimer

class NGStrategy(Enum):
    STOP_ON_ANY = "任何NG停止"
    STOP_ON_CRITICAL = "关键NG停止"
    CONTINUE_ON_NG = "NG继续"

class StepType(Enum):
    CHARGE = "充电"
    DISCHARGE = "放电"
    REST = "静置"
    OCV_CHECK = "OCV检查"
    CUSTOM = "自定义工步"

class SubStepType(Enum):
    SET_INSTRUMENT = "设置仪表"
    READ_INSTRUMENT = "读取仪表"
    CAN_SEND = "CAN发送"
    CAN_INTERACT = "CAN交互"
    WAIT = "等待"
    BARRIER = "同步屏障" # 新增：同步点

class SubStepFailStrategy(Enum):
    STOP = "失败停止"
    CONTINUE = "忽略继续"
    RETRY_3 = "重试3次"

class SubStep:
    def __init__(self, type: SubStepType, params: Dict, fail_strategy: SubStepFailStrategy = SubStepFailStrategy.STOP):
        self.type = type
        self.params = params
        self.fail_strategy = fail_strategy

class TestStep:
    def __init__(self, name: str, step_type: StepType, ng_strategy: NGStrategy = NGStrategy.STOP_ON_ANY):
        self.name = name
        self.step_type = step_type
        self.ng_strategy = ng_strategy
        self.sub_steps: List[SubStep] = []
        self.min_limit = None
        self.max_limit = None

    def add_sub_step(self, sub_step: SubStep):
        self.sub_steps.append(sub_step)

class ChannelWorker(QObject):
    """
    单个通道的测试执行器
    """
    step_started = Signal(int, str)
    progress_updated = Signal(int, float, dict)
    step_finished = Signal(int, str, bool)
    sub_step_finished = Signal(int, int, int, str, object)
    test_finished = Signal(int, bool)
    log_message = Signal(int, str)
    reached_barrier = Signal(int, object) # 新增：到达同步屏障信号 (channel_id, sub_step)

    def __init__(self, channel_id: int, steps: List[TestStep], device_manager=None, db_manager=None, engine=None):
        super().__init__()
        self.channel_id = channel_id
        self.steps = steps
        self.device_manager = device_manager
        self.db_manager = db_manager
        self.engine = engine # 保持对 Engine 的引用以请求资源
        self.is_running = False
        self.is_waiting_for_sync = False # 新增：等待同步标志
        self.current_step_index = 0
        self.current_sub_step_index = 0
        self.current_step_results = []
        self.test_id = -1
        self._retry_count = 0
        self.last_hw_log = ""

    def set_test_info(self, test_id: int):
        self.test_id = test_id

    def start(self):
        self.is_running = True
        self.is_waiting_for_sync = False
        self.current_step_index = 0
        self.log_message.emit(self.channel_id, f"[*] 测试开始，数据库ID: {self.test_id}")
        self.run_next_step()

    def stop(self):
        self.is_running = False
        self.is_waiting_for_sync = False
        # 如果停止时占用了资源，需释放
        if self.engine:
            self.engine.release_resource("ca550", self.channel_id)
        self.log_message.emit(self.channel_id, "[!] 收到停止指令")

    def resume_from_sync(self):
        """由 Engine 调用：释放同步锁/资源锁，继续执行"""
        if self.is_waiting_for_sync:
            self.is_waiting_for_sync = False
            self.log_message.emit(self.channel_id, "[*] 资源/同步释放，继续执行下一步")
            self.on_sub_step_complete()

    def run_next_step(self):
        if not self.is_running or self.is_waiting_for_sync:
            return

        if self.current_step_index >= len(self.steps):
            self.test_finished.emit(self.channel_id, True)
            if self.db_manager and self.test_id != -1:
                self.db_manager.finish_test(self.test_id, "PASS" if self.is_running else "STOPPED")
            return

        step = self.steps[self.current_step_index]
        
        # 集成好的功能：支持 # 屏蔽逻辑 (从原项目保留并优化)
        if step.name.strip().startswith("#"):
            self.log_message.emit(self.channel_id, f"[*] 测试项被屏蔽，跳过执行: {step.name}")
            self.current_step_index += 1
            self.run_next_step()
            return
            
        self.step_started.emit(self.channel_id, step.name)
        self.current_sub_step_index = 0
        self.current_step_results = []
        self.run_next_sub_step()

    def run_next_sub_step(self):
        if not self.is_running or self.is_waiting_for_sync: return
        
        step = self.steps[self.current_step_index]
        if self.current_sub_step_index >= len(step.sub_steps):
            # 在步段结束时，如果占用了互斥资源，应在此处释放
            if self.engine:
                self.engine.release_resource("ca550", self.channel_id)
            self.on_step_complete()
            return

        sub_step = step.sub_steps[self.current_sub_step_index]
        self.execute_sub_step(sub_step)

    def _parse_numeric(self, s: Any) -> float:
        """从字符串中提取数值，鲁棒性增强"""
        if isinstance(s, (int, float)): return float(s)
        try:
            res = re.findall(r"[-+]?\d*\.\d+|\d+", str(s))
            return float(res[0]) if res else 0.0
        except: return 0.0

    def execute_sub_step(self, sub_step: SubStep):
        if not self.is_running: return
        
        mgr = self.device_manager
        params = sub_step.params
        
        retry_tag = f" [重试 {self._retry_count}]" if self._retry_count > 0 else ""
        self.log_message.emit(self.channel_id, f"-> {sub_step.type.value}{retry_tag}: {params.get('device', '')} {params.get('action', '')}")
        
        success = True
        result_value = None
        
        try:
            if not mgr: raise ValueError("设备管理器未初始化")
            
            def hw_logger(msg):
                self.last_hw_log = msg
                self.log_message.emit(self.channel_id, f"      {msg}")

            if sub_step.type == SubStepType.BARRIER:
                # 触发同步屏障：通知 Engine 并挂起自己
                self.is_waiting_for_sync = True
                self.reached_barrier.emit(self.channel_id, sub_step) # 传递 sub_step 以便执行全局动作
                self.log_message.emit(self.channel_id, "[#] 进入同步屏障，等待其他通道...")
                return # 停止当前执行链，等待外部调用 resume_from_sync

            elif sub_step.type == SubStepType.SET_INSTRUMENT:
                device = params.get("device", "").lower()
                p_str = str(params.get("params", ""))
                
                # [关键] CA550 互斥资源申请逻辑
                if "ca550" in device and self.engine:
                    if not self.engine.request_resource("ca550", self.channel_id):
                        self.is_waiting_for_sync = True
                        self.log_message.emit(self.channel_id, "[#] CA550 资源忙，进入排队等待...")
                        return # 挂起，等待 Engine 回调 resume_from_sync
                
                if "simulator" in device:
                    action = params.get("action", "")
                    if "快捷批量配置" in action:
                        # 1. 解析参数字符串 (格式: 3.8V / 1000mA / ON / Range:HIGH / CH:ALL)
                        volt = self._parse_numeric(p_str.split("V")[0])
                        curr_ma = 0.0
                        if "mA" in p_str:
                            ma_match = re.search(r"([\d\.]+)mA", p_str)
                            if ma_match: curr_ma = float(ma_match.group(1))
                        curr_a = curr_ma / 1000.0
                        output_on = "ON" in p_str
                        range_str = "HIGH" if "Range:HIGH" in p_str else "LOW"
                        ch_str = "ALL"
                        if "CH:" in p_str:
                            ch_str = p_str.split("CH:")[-1].strip().upper()
                        
                        # 2. 执行逻辑
                        if ch_str == "ALL":
                            # 使用已优化的广播方法 (带 1-18 循环回退)
                            mgr.broadcast_voltage(volt, logger=hw_logger)
                            mgr.broadcast_current(curr_a, logger=hw_logger)
                            mgr.broadcast_range(range_str, logger=hw_logger)
                            success = mgr.broadcast_output(output_on, logger=hw_logger)
                        else:
                            # 针对特定通道列表
                            try:
                                parts = ch_str.replace("，", ",").split(",")
                                target_channels = [int(p.strip()) for p in parts if p.strip()]
                                for sim in mgr.simulators:
                                    if not sim.is_connected: continue
                                    for ch in target_channels:
                                        if 1 <= ch <= 18:
                                            sim.set_voltage(ch, volt)
                                            sim.set_current_limit(ch, curr_a)
                                            sim.set_range(ch, range_str)
                                            sim.output_control(ch, output_on)
                            except Exception as e:
                                hw_logger(f"解析通道列表失败: {e}")
                                success = False
                        
                        self.on_sub_step_complete()
                        return

                target_ch = None
                if "CH:" in p_str:
                    ch_match = re.search(r"CH:(\d+)", p_str)
                    if ch_match: target_ch = int(ch_match.group(1))

                if "simulator" in device:
                    ch_to_use = target_ch if target_ch is not None else self.channel_id
                    if "V" in p_str:
                        success = success and mgr.set_voltage(ch_to_use, self._parse_numeric(p_str.split("V")[0]), logger=hw_logger)
                    if "A" in p_str:
                        a_match = re.search(r"([\d\.]+)\s*A", p_str)
                        if a_match:
                            success = success and mgr.set_current(ch_to_use, float(a_match.group(1)), logger=hw_logger)
                    if "开启输出" in p_str: success = success and mgr.output_control(ch_to_use, True, logger=hw_logger)
                    elif "关闭输出" in p_str: success = success and mgr.output_control(ch_to_use, False, logger=hw_logger)
                
                elif any(x in device for x in ["afe", "main", "hv_source", "control power", "控制板"]):
                    if "hv_source" in device:
                        act = params.get("action", "")
                        if "输出控制" in act:
                            state = "开启" in p_str or "ON" in p_str.upper()
                            success = mgr.hv_source.output_control(state, channel=target_ch, logger=hw_logger)
                        elif "清除保护" in act:
                            success = mgr.hv_source.clear_errors(logger=hw_logger)
                        else:
                            success = mgr.hv_source.set_voltage(self._parse_numeric(p_str), channel=target_ch, logger=hw_logger)
                    else:
                        # 1. 确定目标设备
                        if "afe" in device:
                            if "2#" in device: target_dev = mgr.afe_pwr_2
                            elif "3#" in device: target_dev = mgr.afe_pwr_3
                            else: target_dev = mgr.afe_power_1
                        elif "main" in device:
                            target_dev = mgr.dut_power
                        elif "control power" in device or "控制板" in device:
                            target_dev = mgr.ctrl_board_power
                            
                        if not target_dev:
                            hw_logger(f"错误: 目标设备 {device} 未初始化")
                            success = False
                        else:
                            act = params.get("action", "")
                            # 2. 支持复合指令 (如 100V 5A ON)
                            if any(x in p_str.upper() for x in ["V", "A", "ON", "OFF"]) or "开启" in p_str or "关闭" in p_str:
                                if "V" in p_str.upper():
                                    v_val = self._parse_numeric(p_str.upper().split("V")[0])
                                    success = success and target_dev.set_voltage(v_val, logger=hw_logger)
                                if "A" in p_str.upper():
                                    a_match = re.search(r"([\d\.]+)\s*A", p_str.upper())
                                    if a_match:
                                        success = success and target_dev.set_current(float(a_match.group(1)), logger=hw_logger)
                                if "开启" in p_str or "ON" in p_str.upper(): 
                                    success = success and target_dev.output_control(True, logger=hw_logger)
                                elif "关闭" in p_str or "OFF" in p_str.upper(): 
                                    success = success and target_dev.output_control(False, logger=hw_logger)
                            
                            # 3. 如果不是复合指令，则按原 action 逻辑执行
                            else:
                                if "输出控制" in act:
                                    state = "开启" in p_str or "ON" in p_str.upper()
                                    success = target_dev.output_control(state, logger=hw_logger)
                                elif "设置电流" in act:
                                    success = target_dev.set_current(self._parse_numeric(p_str), logger=hw_logger)
                                elif "清除保护" in act:
                                    if hasattr(target_dev, "clear_errors"): success = target_dev.clear_errors(logger=hw_logger)
                                    else: success = True
                                else:
                                    success = target_dev.set_voltage(self._parse_numeric(p_str), logger=hw_logger)

                elif "aging_board" in device:
                    board = mgr.boards.get(self.channel_id)
                    if board:
                        if ":" in p_str:
                            actions = p_str.split(",")
                            for act in actions:
                                if ":" in act:
                                    name, state_str = act.split(":")
                                    state = "ON" in state_str.upper() or "开启" in state_str
                                    success = success and board.relays.set_relay_by_name(name.strip(), state)
                        elif "全部关闭" in params.get("action", ""):
                            success = board.relays.all_off()
                    else:
                        success = False
                        if logger: logger(f"错误: 找不到通道 {self.channel_id} 对应的控制板")

                elif "老化" in device:
                    board = mgr.boards.get(self.channel_id)
                    if board:
                        act = params.get("action", "")
                        if "全部断开" in act:
                            success = board.relays.all_off()
                        else:
                            state = "闭合" in act
                            channels = p_str.split(",")
                            for ch in channels:
                                if ch.strip():
                                    try:
                                        ch_idx = int(self._parse_numeric(ch)) - 1
                                        success = success and board.relays.write_relay(ch_idx, state)
                                    except: pass
                    else:
                        if logger: logger(f"错误: 找不到通道 {self.channel_id} 对应的老化板")

                elif "easy320" in device:
                    act = params.get("action", "")
                    if "全部断开" in act:
                        success = mgr.easy320.batch_control(False)
                    else:
                        state = "闭合" in act
                        channels = p_str.split(",")
                        for ch in channels:
                            if ch.strip():
                                try:
                                    ch_idx = int(self._parse_numeric(ch)) - 1
                                    success = success and mgr.easy320.write_relay(ch_idx, state)
                                except: pass

                elif "ca550" in device:
                    # 处理新格式: Type:V / Val:3.5 / Range:10V / Output:开启输出
                    if "Type:" in p_str:
                        # 1. 设置功能类型 (Function)
                        func_code = 0 # 默认 DCV
                        if "MA" in p_str.upper(): func_code = 1
                        elif "OHM" in p_str.upper(): func_code = 2
                        elif "RTD" in p_str.upper(): func_code = 3
                        elif "TC" in p_str.upper(): func_code = 4
                        elif "MV" in p_str.upper(): func_code = 0 
                        
                        mgr.ca550.set_source_func(func_code)
                        
                        # 2. 设置量程 (Range)
                        if "Range:" in p_str:
                            range_code = 0
                            if "1V" in p_str: range_code = 1
                            elif "5V" in p_str: range_code = 2
                            elif "10V" in p_str: range_code = 2
                            elif "30V" in p_str: range_code = 3
                            elif "20MA" in p_str.upper(): range_code = 0
                            mgr.ca550.set_source_range(range_code)
                            
                        # 3. 设置数据 (Data)
                        if "Val:" in p_str:
                            mgr.ca550.set_source_data(float(self._parse_numeric(p_str.split("Val:")[-1])))
                            
                        # 4. 控制输出 (Output)
                        if "Output:开启" in p_str:
                            success = mgr.ca550.set_source_output(1)
                        elif "Output:关闭" in p_str:
                            success = mgr.ca550.set_source_output(0)
                        else:
                            success = True
                    else:
                        # 兼容老格式 (仅数值或简单的开关指令)
                        if "关闭" in p_str or "OFF" in p_str.upper():
                            success = mgr.ca550.set_source_output(0)
                        else:
                            mgr.ca550.set_source_func(0 if "V" in p_str.upper() else 1)
                            mgr.ca550.set_source_data(self._parse_numeric(p_str))
                            success = mgr.ca550.set_source_output(1)

            elif sub_step.type == SubStepType.READ_INSTRUMENT:
                device = params.get("device", "").lower()
                p_str = str(params.get("params", ""))
                target_ch = None
                if "CH:" in p_str:
                    ch_match = re.search(r"CH:(\d+)", p_str)
                    if ch_match: target_ch = int(ch_match.group(1))

                if "simulator" in device:
                    ch_to_use = target_ch if target_ch is not None else self.channel_id
                    if "电压" in p_str:
                        result_value = mgr.measure_voltage(ch_to_use, logger=hw_logger)
                        success = result_value >= 0
                    elif "电流" in p_str:
                        result_value = mgr.measure_current(ch_to_use, logger=hw_logger)
                        success = result_value > -500
                
                elif any(x in device for x in ["afe", "main", "hv_source", "control power", "控制板"]):
                    if "hv_source" in device:
                        if "电压" in p_str:
                            result_value = mgr.hv_source.measure_voltage(channel=target_ch, logger=hw_logger)
                        elif "电流" in p_str:
                            result_value = mgr.hv_source.measure_current(channel=target_ch, logger=hw_logger)
                        success = result_value >= 0
                    else:
                        # 确定目标设备
                        if "afe" in device:
                            if "2#" in device: target_dev = mgr.afe_pwr_2
                            elif "3#" in device: target_dev = mgr.afe_pwr_3
                            else: target_dev = mgr.afe_power_1
                        elif "main" in device:
                            target_dev = mgr.dut_power
                        elif "control power" in device or "控制板" in device:
                            target_dev = mgr.ctrl_board_power
                        
                        if not target_dev:
                            hw_logger(f"错误: 目标设备 {device} 未初始化")
                            success = False
                        else:
                            if "电压" in p_str: result_value = target_dev.measure_voltage(logger=hw_logger)
                            elif "电流" in p_str: result_value = target_dev.measure_current(logger=hw_logger)
                            success = result_value >= 0

                elif "ca550" in device:
                    raw_data = mgr.ca550.read_measure_data()
                    try:
                        # CA550 返回的通常是带单位的字符串，如 "10.0000 V"
                        result_value = self._parse_numeric(raw_data)
                        success = True
                    except:
                        result_value = raw_data
                        success = False

                if success and self.db_manager and self.test_id != -1 and result_value is not None:
                    v = result_value if "电压" in p_str else -1
                    c = result_value if "电流" in p_str else -1
                    self.db_manager.log_detail(self.test_id, self.steps[self.current_step_index].name, v, c, "--")

            elif sub_step.type in [SubStepType.CAN_SEND, SubStepType.CAN_INTERACT]:
                board = mgr.boards.get(self.channel_id)
                if board:
                    if not board.is_connected: board.connect()
                    p_str = str(params.get("params", ""))
                    # 解析 ID:0x123 / Data:00 11 22
                    try:
                        id_str = re.search(r"ID:([0-9a-fA-FXx]+)", p_str).group(1)
                        can_id = int(id_str, 16)
                    except: can_id = 0
                    try:
                        data_match = re.search(r"Data:([0-9a-fA-F\s]+)", p_str)
                        hex_data = data_match.group(1).strip().replace(" ", "").split("/")[0]
                        can_data = bytes.fromhex(hex_data)
                    except: can_data = b'\x00' * 8
                    
                    success = board.can.send_can_message(
                        channel_id=0, can_id=can_id, can_type=0, 
                        dlc=board.can.length_to_dlc(len(can_data)), data=can_data
                    )
                    
                    if success and sub_step.type == SubStepType.CAN_INTERACT:
                        try:
                            wait_id_str = re.search(r"WaitID:([0-9a-fA-FXx]+)", p_str).group(1)
                            wait_id = int(wait_id_str, 16)
                        except: wait_id = None
                        if wait_id is not None:
                            import time as pytime
                            start_t = pytime.time()
                            found = False
                            while pytime.time() - start_t < 3.0:
                                if not board.can.msg_queue.empty():
                                    msg = board.can.msg_queue.get()
                                    if msg['can_id'] == wait_id:
                                        found = True; break
                                pytime.sleep(0.01)
                            success = found
                else: success = False


            elif sub_step.type == SubStepType.WAIT:
                total_ms = int(self._parse_numeric(params.get("params", 1000)))
                
                # 如果延时较短（小于 2s），直接单次定时
                if total_ms < 2000:
                    QTimer.singleShot(total_ms, self.on_sub_step_complete)
                else:
                    # 如果延时较长，实现简单的倒计时日志反馈
                    remaining = total_ms
                    def tick():
                        nonlocal remaining
                        if not self.is_running: return
                        
                        if remaining <= 0:
                            self.on_sub_step_complete()
                        else:
                            if remaining % 1000 == 0 or remaining == total_ms:
                                self.log_message.emit(self.channel_id, f"      [倒计时] 剩余 {remaining/1000:.0f}s...")
                            
                            interval = min(1000, remaining)
                            remaining -= interval
                            QTimer.singleShot(interval, tick)
                    
                    tick()
                return

        except Exception as e:
            self.log_message.emit(self.channel_id, f"[!] 执行异常: {str(e)}")
            success = False

        if success and params.get("is_judgment") and result_value is not None:
            self.current_step_results.append(result_value)
            
        self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, 
                                   "PASS" if success else "FAIL", result_value)

        if success:
            self._retry_count = 0
            self.on_sub_step_complete()
        else:
            if sub_step.fail_strategy == SubStepFailStrategy.RETRY_3 and self._retry_count < 3:
                self._retry_count += 1
                self.log_message.emit(self.channel_id, f"[!] 子工步执行失败，准备进行第 {self._retry_count} 次重试...")
                QTimer.singleShot(500, lambda: self.execute_sub_step(sub_step))
                return
            self._retry_count = 0
            if sub_step.fail_strategy == SubStepFailStrategy.CONTINUE:
                self.log_message.emit(self.channel_id, f"[!] 子工步执行失败，策略为【忽略】，继续下一步")
                self.on_sub_step_complete()
            else:
                self.on_step_complete(is_pass=False)

    def on_sub_step_complete(self):
        if not self.is_running: return
        self.current_sub_step_index += 1
        self.run_next_sub_step()

    def on_step_complete(self, is_pass: bool = True):
        if not self.is_running: return
        step = self.steps[self.current_step_index]
        if is_pass and self.current_step_results:
            for val in self.current_step_results:
                f_val = self._parse_numeric(val)
                if step.min_limit is not None and f_val < float(step.min_limit): is_pass = False
                if step.max_limit is not None and f_val > float(step.max_limit): is_pass = False
        
        if (step.min_limit or step.max_limit) and self.db_manager and self.test_id != -1:
            val = self.current_step_results[0] if self.current_step_results else 0.0
            self.db_manager.log_item_result(self.test_id, step.name, 
                                          float(step.min_limit or 0), float(step.max_limit or 0), 
                                          self._parse_numeric(val), "PASS" if is_pass else "NG")

        self.step_finished.emit(self.channel_id, step.name, is_pass)
        
        if not is_pass and step.ng_strategy == NGStrategy.STOP_ON_ANY:
            self.log_message.emit(self.channel_id, f"[!] 触发NG停止策略: {step.name} | 通讯详情: {self.last_hw_log}")
            if self.db_manager and self.test_id != -1:
                self.db_manager.finish_test(self.test_id, f"NG STOP at {step.name}")
            self.test_finished.emit(self.channel_id, False)
            self.is_running = False
            return

        self.current_step_index += 1
        self.run_next_step()

class TestEngine(QObject):
    # 信号定义
    all_channels_finished = Signal()
    barrier_status_changed = Signal(int, int) # (已到人数, 总需人数)
    channel_sync_status_changed = Signal(int, bool) # (通道ID, 是否在等待)
    def __init__(self, device_manager=None, db_manager=None):
        super().__init__()
        self.device_manager = device_manager
        self.db_manager = db_manager
        self.workers: Dict[int, ChannelWorker] = {}
        self.threads: Dict[int, QThread] = {}
        self.zombie_threads: List[QThread] = []
        self._lock = threading.RLock()
        
        # 新增：同步协调逻辑
        self.sync_barrier_channels = set()
        
        # 新增：硬件资源互斥锁（如 CA550 时分复用）
        self.resource_locks: Dict[str, Optional[int]] = {"ca550": None}
        self.resource_queues: Dict[str, List[int]] = {"ca550": []}

    def request_resource(self, resource_name: str, channel_id: int) -> bool:
        """申请硬件资源使用权 (如 CA550)"""
        with self._lock:
            if self.resource_locks.get(resource_name) is None:
                self.resource_locks[resource_name] = channel_id
                print(f"[*] 资源 {resource_name} 已分配给通道 {channel_id}")
                return True
            else:
                if channel_id not in self.resource_queues[resource_name]:
                    self.resource_queues[resource_name].append(channel_id)
                print(f"[#] 资源 {resource_name} 正忙，通道 {channel_id} 已进入排队队列")
                return False

    def release_resource(self, resource_name: str, channel_id: int):
        """释放硬件资源使用权"""
        with self._lock:
            if self.resource_locks.get(resource_name) == channel_id:
                self.resource_locks[resource_name] = None
                print(f"[*] 通道 {channel_id} 已释放资源 {resource_name}")
                
                # 检查队列中是否有等待者
                if self.resource_queues[resource_name]:
                    next_ch = self.resource_queues[resource_name].pop(0)
                    self.resource_locks[resource_name] = next_ch
                    print(f"[*] 资源 {resource_name} 已自动分配给队列中的通道 {next_ch}")
                    if next_ch in self.workers:
                        # 假设 Worker 有一个回调或信号来处理资源获得，
                        # 此处复用 resume_from_sync 逻辑或专门的逻辑
                        self.workers[next_ch].resume_from_sync()

    def handle_barrier_reached(self, channel_id: int, sub_step: SubStep = None):
        """当某个 Worker 到达同步屏障时被调用"""
        with self._lock:
            # 记录第一个到达屏障的工步参数（假设所有通道脚本一致）
            if not self.sync_barrier_channels:
                self._current_barrier_sub_step = sub_step

            self.sync_barrier_channels.add(channel_id)
            total_active = len(self.workers)
            waiting_count = len(self.sync_barrier_channels)
            
            print(f"[!] 通道 {channel_id} 到达同步屏障. 进度: {waiting_count}/{total_active}")
            self.barrier_status_changed.emit(waiting_count, total_active)
            self.channel_sync_status_changed.emit(channel_id, True)
            
            if waiting_count >= total_active and total_active > 0:
                print(f"[*] 所有活动通道 ({total_active}) 已到齐，准备执行全局动作并释放...")
                
                # 1. 执行全局动作 (方案1核心)
                if hasattr(self, '_current_barrier_sub_step') and self._current_barrier_sub_step:
                    global_action = self._current_barrier_sub_step.params.get("global_action")
                    if global_action:
                        self._execute_global_action(global_action)
                
                # 2. 释放所有通道
                for ch_id in list(self.sync_barrier_channels):
                    if ch_id in self.workers:
                        self.workers[ch_id].resume_from_sync()
                        self.channel_sync_status_changed.emit(ch_id, False)
                
                self.sync_barrier_channels.clear()
                self._current_barrier_sub_step = None
                self.barrier_status_changed.emit(0, total_active)

    def _execute_global_action(self, action_params: Dict):
        """执行屏障处的全局统一动作"""
        mgr = self.device_manager
        if not mgr: return
        
        device = action_params.get("device", "").lower()
        action = action_params.get("action", "")
        value_str = str(action_params.get("value", "0"))
        
        # 定义一个简单的内部解析器
        def parse_val(s):
            try: return float(re.findall(r"[-+]?\d*\.\d+|\d+", str(s))[0])
            except: return 0.0

        print(f"[#] 正在执行全局同步动作: {device} {action} {value_str}")
        
        try:
            if "hv_source" in device:
                if "设置电压" in action:
                    mgr.hv_source.set_voltage(parse_val(value_str))
                elif "输出控制" in action:
                    state = "开启" in value_str or "ON" in value_str.upper()
                    mgr.hv_source.output_control(state)
            
            elif "simulator" in device:
                if "全部开启" in action: mgr.broadcast_output(True)
                elif "全部关闭" in action: mgr.broadcast_output(False)
                elif "同步设置电压" in action: mgr.broadcast_voltage(parse_val(value_str))
                elif "同步设置电流" in action: mgr.broadcast_current(parse_val(value_str))
            
            elif "afe" in device or "main_power" in device:
                # 确定目标设备
                if "afe" in device:
                    if "2#" in device: target_dev = mgr.afe_pwr_2
                    elif "3#" in device: target_dev = mgr.afe_pwr_3
                    else: target_dev = mgr.afe_power_1
                else:
                    target_dev = mgr.dut_power
                
                if target_dev:
                    if "设置电压" in action: target_dev.set_voltage(parse_val(value_str))
                    elif "设置电流" in action: target_dev.set_current(parse_val(value_str))
                    elif "输出控制" in action:
                        state = "开启" in value_str or "ON" in value_str.upper()
                        target_dev.output_control(state)
        except Exception as e:
            print(f"[!] 全局同步动作执行异常: {e}")

    def release_barrier(self):
        """释放同步锁，让所有 Worker 继续执行"""
        with self._lock:
            # 在释放前，可以根据配方上下文执行全局硬件操作（如升压）
            # 此处逻辑可扩展
            for cid in list(self.sync_barrier_channels):
                if cid in self.workers:
                    self.workers[cid].resume_from_sync()
            self.sync_barrier_channels.clear()

    def start_channel_test(self, channel_id: int, recipe_data: List[Dict], test_id: int = -1):
        steps = []
        for item in recipe_data:
            strategy_str = item.get('strategy', "任何NG停止")
            strategy = NGStrategy.STOP_ON_ANY
            for s in NGStrategy:
                if s.value == strategy_str:
                    strategy = s
                    break
            
            step = TestStep(item['name'], StepType.CUSTOM, ng_strategy=strategy)
            step.min_limit = item.get('min') if item.get('min') != "--" else None
            step.max_limit = item.get('max') if item.get('max') != "--" else None

            for sub in item.get('sub_steps', []):
                stype = SubStepType.SET_INSTRUMENT
                t_str = sub.get('type', "")
                if "读取" in t_str: stype = SubStepType.READ_INSTRUMENT
                elif "CAN发送" in t_str: stype = SubStepType.CAN_SEND
                elif "CAN交互" in t_str: stype = SubStepType.CAN_INTERACT
                elif "等待" in t_str: stype = SubStepType.WAIT
                elif "同步屏障" in t_str: stype = SubStepType.BARRIER
                
                fail_strategy_str = sub.get('fail_strategy', "失败停止")
                fail_strategy = SubStepFailStrategy.STOP
                for fs in SubStepFailStrategy:
                    if fs.value == fail_strategy_str:
                        fail_strategy = fs
                        break
                step.add_sub_step(SubStep(stype, sub.copy(), fail_strategy=fail_strategy))
            steps.append(step)

        with self._lock:
            if channel_id in self.workers: self.stop_channel_test(channel_id)

        thread = QThread()
        worker = ChannelWorker(channel_id, steps, self.device_manager, self.db_manager, engine=self)
        worker.set_test_info(test_id)
        worker.moveToThread(thread)
        
        # 绑定同步屏障信号
        worker.reached_barrier.connect(self.handle_barrier_reached)
        thread.started.connect(worker.start)
        from PySide6.QtCore import Qt
        worker.test_finished.connect(lambda: self.stop_channel_test(channel_id), Qt.QueuedConnection)
        self.workers[channel_id] = worker
        self.threads[channel_id] = thread
        thread.start()

    def stop_channel_test(self, channel_id: int):
        with self._lock:
            if channel_id in self.sync_barrier_channels:
                self.sync_barrier_channels.remove(channel_id)
                
            if channel_id in self.threads:
                thread = self.threads[channel_id]
                worker = self.workers[channel_id]
                try: worker.test_finished.disconnect()
                except: pass
                worker.stop()
                thread.quit()
                if QThread.currentThread() != thread:
                    if not thread.wait(500):
                        print(f"[!] 通道 {channel_id} 线程未能在 500ms 内停止")
                del self.workers[channel_id]
                del self.threads[channel_id]
                self.zombie_threads.append(thread)
                thread.finished.connect(thread.deleteLater)
                thread.finished.connect(lambda t=thread: self._cleanup_zombie(t))
                worker.deleteLater()

    def _cleanup_zombie(self, thread):
        with self._lock:
            if thread in self.zombie_threads: self.zombie_threads.remove(thread)

    def stop_all(self):
        with self._lock:
            ids = list(self.threads.keys())
            for cid in ids: self.stop_channel_test(cid)
            import time
            start_time = time.time()
            while self.threads and time.time() - start_time < 2.0:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                time.sleep(0.1)
