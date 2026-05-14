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
    EOL_PROTOCOL = "智界EOL协议"
    WAIT = "等待"
    BARRIER = "同步屏障"

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
    step_started = Signal(int, str)
    progress_updated = Signal(int, float, dict)
    step_finished = Signal(int, str, bool)
    sub_step_finished = Signal(int, int, int, str, object)
    test_finished = Signal(int, bool)
    log_message = Signal(int, str)
    reached_barrier = Signal(int, object)

    def __init__(self, channel_id: int, steps: List[TestStep], device_manager=None, db_manager=None, engine=None):
        super().__init__()
        self.channel_id = channel_id
        self.steps = steps
        self.device_manager = device_manager
        self.db_manager = db_manager
        self.engine = engine
        self.is_running = False
        self.is_waiting_for_sync = False
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
        if self.engine:
            self.engine.release_resource("ca550", self.channel_id)
        self.log_message.emit(self.channel_id, "[!] 收到停止指令")

    def resume_from_sync(self):
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
            if self.engine:
                self.engine.release_resource("ca550", self.channel_id)
            self.on_step_complete()
            return
        sub_step = step.sub_steps[self.current_sub_step_index]
        self.execute_sub_step(sub_step)

    def _parse_numeric(self, s: Any) -> float:
        if isinstance(s, (int, float)): return float(s)
        try:
            res = re.findall(r"[-+]?\d*\.\d+|\d+", str(s))
            return float(res[0]) if res else 0.0
        except: return 0.0

    def _parse_key_values(self, params: str) -> Dict[str, str]:
        values = {}
        for part in str(params).replace("；", "/").replace("，", "/").split("/"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            key, value = part.split(":", 1)
            values[key.strip().upper()] = value.strip()
        return values

    def _parse_int(self, value: Any, default: int = 0) -> int:
        if value is None or value == "": return default
        if isinstance(value, int): return value
        return int(str(value).strip(), 0)

    def _parse_hex_bytes(self, value: Any, default_len: int = 8) -> bytes:
        if value is None: return bytes(default_len)
        if isinstance(value, bytes): return value
        if isinstance(value, (list, tuple)): return bytes(int(v) & 0xFF for v in value)
        text = str(value).strip()
        if not text: return bytes(default_len)
        text = text.replace("0x", "").replace("0X", "").replace(" ", "")
        text = re.sub(r"[^0-9a-fA-F]", "", text)
        return bytes.fromhex(text) if text else bytes(default_len)

    def _parse_can_params(self, params: Dict) -> Dict[str, Any]:
        kv = self._parse_key_values(params.get("params", ""))
        data = params.get("data") if "data" in params else kv.get("DATA")
        parsed_data = self._parse_hex_bytes(data)
        dlc = self._parse_int(params.get("dlc", kv.get("DLC")), len(parsed_data) or 8)
        return {
            "channel_id": self._parse_int(params.get("channel_id", kv.get("CH")), 1),
            "can_id": self._parse_int(params.get("id", params.get("can_id", kv.get("ID"))), 0),
            "can_type": self._parse_int(params.get("can_type", kv.get("TYPE")), 0),
            "dlc": dlc,
            "data": parsed_data,
            "wait_id": self._parse_int(params.get("wait_id", kv.get("WAIT_ID")), -1),
            "timeout": self._parse_int(params.get("timeout_ms", kv.get("TIMEOUT")), 1000) / 1000.0,
        }

    def _parse_eol_params(self, params: Dict) -> Optional[Dict[str, Any]]:
        kv = self._parse_key_values(params.get("params", ""))
        if "EOL" not in kv: return None
        return {
            "op_name": kv.pop("EOL").strip(),
            "timeout": self._parse_int(kv.pop("TIMEOUT", 1000), 1000) / 1000.0,
            "channel_id": self._parse_int(kv.pop("CH", 1), 1),
            "kwargs": kv,
        }

    def _get_can_board(self, mgr):
        board = mgr.boards.get(self.channel_id)
        if not board: raise ValueError(f"找不到通道 {self.channel_id} 对应的CAN控制板")
        if not board.is_connected: board.connect()
        if not board.is_connected: raise ValueError(f"通道 {self.channel_id} CAN未连接")
        return board

    def _execute_eol_protocol(self, mgr, params, hw_logger):
        eol_cfg = self._parse_eol_params(params)
        if not eol_cfg: raise ValueError("EOL参数缺失")
        board = self._get_can_board(mgr)
        from devices.eol_protocol import EOLProtocol
        eol = EOLProtocol(board.can, channel_id=eol_cfg["channel_id"])
        result = eol.execute(eol_cfg["op_name"], timeout=eol_cfg["timeout"], **eol_cfg["kwargs"])
        result_value = result.value if result.success else result.error
        hw_logger(f"EOL {eol_cfg['op_name']} => {'PASS' if result.success else 'FAIL'} {result_value}")
        return result.success, result_value

    def execute_sub_step(self, sub_step: SubStep):
        if not self.is_running: return
        mgr = self.device_manager
        params = sub_step.params
        retry_tag = f" [重试 {self._retry_count}]" if self._retry_count > 0 else ""
        self.log_message.emit(self.channel_id, f"-> {sub_step.type.value}{retry_tag}: {params.get('device', '')} {params.get('action', '')}")
        success, result_value = True, None
        try:
            if not mgr: raise ValueError("设备管理器未初始化")
            def hw_logger(msg):
                self.last_hw_log = msg
                self.log_message.emit(self.channel_id, f"      {msg}")

            if sub_step.type == SubStepType.BARRIER:
                self.is_waiting_for_sync = True
                self.reached_barrier.emit(self.channel_id, sub_step)
                self.log_message.emit(self.channel_id, "[#] 进入同步屏障，等待其他通道...")
                return

            elif sub_step.type == SubStepType.SET_INSTRUMENT:
                device, p_str = params.get("device", "").lower(), str(params.get("params", ""))
                if "ca550" in device and self.engine:
                    if not self.engine.request_resource("ca550", self.channel_id):
                        self.is_waiting_for_sync = True
                        self.log_message.emit(self.channel_id, "[#] CA550 资源忙，进入排队等待...")
                        return
                
                target_ch = None
                if "CH:" in p_str:
                    ch_match = re.search(r"CH:(\d+)", p_str)
                    if ch_match: target_ch = int(ch_match.group(1))

                if "simulator" in device:
                    action = params.get("action", "")
                    if "快捷批量配置" in action:
                        volt = self._parse_numeric(p_str.split("V")[0])
                        curr_ma = float(re.search(r"([\d\.]+)mA", p_str).group(1)) if "mA" in p_str else 0.0
                        output_on = "ON" in p_str
                        range_str = "HIGH" if "Range:HIGH" in p_str else "LOW"
                        ch_str = p_str.split("CH:")[-1].strip().upper() if "CH:" in p_str else "ALL"
                        if ch_str == "ALL":
                            mgr.broadcast_voltage(volt, logger=hw_logger)
                            mgr.broadcast_current(curr_ma/1000.0, logger=hw_logger)
                            mgr.broadcast_range(range_str, logger=hw_logger)
                            success = mgr.broadcast_output(output_on, logger=hw_logger)
                        else:
                            try:
                                target_channels = [int(p.strip()) for p in ch_str.replace("，", ",").split(",") if p.strip()]
                                for sim in mgr.simulators:
                                    if not sim.is_connected: continue
                                    for ch in target_channels:
                                        if 1 <= ch <= 18:
                                            sim.set_voltage(ch, volt)
                                            sim.set_current_limit(ch, curr_ma/1000.0)
                                            sim.set_range(ch, range_str)
                                            sim.output_control(ch, output_on)
                            except: success = False
                        self.on_sub_step_complete(); return

                    ch_to_use = target_ch if target_ch is not None else self.channel_id
                    if "V" in p_str: success = success and mgr.set_voltage(ch_to_use, self._parse_numeric(p_str.split("V")[0]), logger=hw_logger)
                    if "A" in p_str:
                        a_match = re.search(r"([\d\.]+)\s*A", p_str)
                        if a_match: success = success and mgr.set_current(ch_to_use, float(a_match.group(1)), logger=hw_logger)
                    if "开启输出" in p_str: success = success and mgr.output_control(ch_to_use, True, logger=hw_logger)
                    elif "关闭输出" in p_str: success = success and mgr.output_control(ch_to_use, False, logger=hw_logger)
                
                elif any(x in device for x in ["afe", "main", "hv_source", "control power", "控制板"]):
                    if "hv_source" in device:
                        if "输出控制" in params.get("action", ""):
                            success = mgr.hv_source.output_control("开启" in p_str or "ON" in p_str.upper(), channel=target_ch, logger=hw_logger)
                        elif "清除保护" in params.get("action", ""): success = mgr.hv_source.clear_errors(logger=hw_logger)
                        else: success = mgr.hv_source.set_voltage(self._parse_numeric(p_str), channel=target_ch, logger=hw_logger)
                    else:
                        if "2#" in device: target_dev = mgr.afe_pwr_2
                        elif "3#" in device: target_dev = mgr.afe_pwr_3
                        elif "afe" in device: target_dev = mgr.afe_power_1
                        elif "main" in device: target_dev = mgr.dut_power
                        else: target_dev = mgr.ctrl_board_power
                        if not target_dev: hw_logger(f"错误: {device} 未初始化"); success = False
                        else:
                            if any(x in p_str.upper() for x in ["V", "A", "ON", "OFF"]) or "开启" in p_str or "关闭" in p_str:
                                if "V" in p_str.upper(): target_dev.set_voltage(self._parse_numeric(p_str.upper().split("V")[0]), logger=hw_logger)
                                if "A" in p_str.upper():
                                    a_m = re.search(r"([\d\.]+)\s*A", p_str.upper())
                                    if a_m: target_dev.set_current(float(a_m.group(1)), logger=hw_logger)
                                if "开启" in p_str or "ON" in p_str.upper(): target_dev.output_control(True, logger=hw_logger)
                                elif "关闭" in p_str or "OFF" in p_str.upper(): target_dev.output_control(False, logger=hw_logger)
                            else:
                                act = params.get("action", "")
                                if "输出控制" in act: target_dev.output_control("开启" in p_str or "ON" in p_str.upper(), logger=hw_logger)
                                elif "设置电流" in act: target_dev.set_current(self._parse_numeric(p_str), logger=hw_logger)
                                elif "清除保护" in act and hasattr(target_dev, "clear_errors"): target_dev.clear_errors(logger=hw_logger)
                                else: target_dev.set_voltage(self._parse_numeric(p_str), logger=hw_logger)

                elif "aging_board" in device or "老化" in device:
                    board = mgr.boards.get(self.channel_id)
                    if board:
                        if ":" in p_str:
                            for act in p_str.split(","):
                                if ":" in act:
                                    n, s = act.split(":")
                                    board.relays.set_relay_by_name(n.strip(), "ON" in s.upper() or "开启" in s)
                        elif "全部" in params.get("action", ""): board.relays.all_off()
                        else:
                            state = "闭合" in params.get("action", "")
                            for ch in p_str.split(","):
                                if ch.strip(): board.relays.write_relay(int(self._parse_numeric(ch))-1, state)
                    else: success = False

                elif "easy320" in device:
                    if "全部" in params.get("action", ""): mgr.easy320.batch_control(False)
                    else:
                        state = "闭合" in params.get("action", "")
                        for ch in p_str.split(","):
                            if ch.strip(): mgr.easy320.write_relay(int(self._parse_numeric(ch))-1, state)

                elif "ca550" in device:
                    if "Type:" in p_str:
                        f_code = 1 if "MA" in p_str.upper() else 2 if "OHM" in p_str.upper() else 3 if "RTD" in p_str.upper() else 4 if "TC" in p_str.upper() else 0
                        mgr.ca550.set_source_func(f_code)
                        if "Range:" in p_str:
                            r_code = 1 if "1V" in p_str else 2 if ("5V" in p_str or "10V" in p_str) else 3 if "30V" in p_str else 0
                            mgr.ca550.set_source_range(r_code)
                        if "Val:" in p_str: mgr.ca550.set_source_data(float(self._parse_numeric(p_str.split("Val:")[-1])))
                        if "Output:开启" in p_str: mgr.ca550.set_source_output(1)
                        elif "Output:关闭" in p_str: mgr.ca550.set_source_output(0)
                    else:
                        if "关闭" in p_str or "OFF" in p_str.upper(): mgr.ca550.set_source_output(0)
                        else:
                            mgr.ca550.set_source_func(0 if "V" in p_str.upper() else 1)
                            mgr.ca550.set_source_data(self._parse_numeric(p_str))
                            mgr.ca550.set_source_output(1)

            elif sub_step.type == SubStepType.READ_INSTRUMENT:
                device, p_str = params.get("device", "").lower(), str(params.get("params", ""))
                target_ch = int(re.search(r"CH:(\d+)", p_str).group(1)) if "CH:" in p_str else None
                if "simulator" in device:
                    ch = target_ch if target_ch is not None else self.channel_id
                    result_value = mgr.measure_voltage(ch) if "电压" in p_str else mgr.measure_current(ch)
                    success = result_value >= 0
                elif any(x in device for x in ["afe", "main", "hv_source", "control power", "控制板"]):
                    if "2#" in device: dev = mgr.afe_pwr_2
                    elif "3#" in device: dev = mgr.afe_pwr_3
                    elif "afe" in device: dev = mgr.afe_power_1
                    elif "main" in device: dev = mgr.dut_power
                    elif "hv_source" in device: dev = mgr.hv_source
                    else: dev = mgr.ctrl_board_power
                    if dev:
                        result_value = dev.measure_voltage(channel=target_ch) if "电压" in p_str else dev.measure_current(channel=target_ch)
                        success = result_value is not None
                elif "ca550" in device:
                    result_value = self._parse_numeric(mgr.ca550.read_measure_data())
                    success = True

            elif sub_step.type == SubStepType.CAN_SEND:
                board = self._get_can_board(mgr)
                cfg = self._parse_can_params(params)
                success = board.can.send_can_message(cfg["channel_id"], cfg["can_id"], cfg["can_type"], cfg["dlc"], cfg["data"])
                hw_logger(f"CAN TX ID=0x{cfg['can_id']:X} DATA={cfg['data'].hex(' ').upper()}")

            elif sub_step.type == SubStepType.CAN_INTERACT:
                eol_cfg = self._parse_eol_params(params)
                if eol_cfg: success, result_value = self._execute_eol_protocol(mgr, params, hw_logger)
                else:
                    board = self._get_can_board(mgr)
                    cfg = self._parse_can_params(params)
                    w_id = cfg["wait_id"] if cfg["wait_id"] >= 0 else cfg["can_id"]
                    msg = board.can.send_and_wait_response(cfg["channel_id"], cfg["can_id"], cfg["can_type"], cfg["dlc"], cfg["data"], w_id, cfg["timeout"])
                    success = msg is not None
                    result_value = msg.get("data", b"").hex(" ").upper() if msg else "TIMEOUT"
                    hw_logger(f"CAN REQ ID=0x{cfg['can_id']:X} WAIT=0x{w_id:X} => {result_value}")

            elif sub_step.type == SubStepType.EOL_PROTOCOL:
                success, result_value = self._execute_eol_protocol(mgr, params, hw_logger)

            elif sub_step.type == SubStepType.WAIT:
                ms = int(self._parse_numeric(params.get("params", 1000)))
                if ms < 2000: QTimer.singleShot(ms, self.on_sub_step_complete)
                else:
                    rem = ms
                    def tick():
                        nonlocal rem
                        if not self.is_running: return
                        if rem <= 0: self.on_sub_step_complete()
                        else:
                            if rem % 1000 == 0 or rem == ms: self.log_message.emit(self.channel_id, f"      [倒计时] 剩余 {rem/1000:.0f}s...")
                            i = min(1000, rem); rem -= i; QTimer.singleShot(i, tick)
                    tick()
                return

        except Exception as e:
            self.log_message.emit(self.channel_id, f"[!] 执行异常: {str(e)}"); success = False

        if success and params.get("is_judgment") and result_value is not None:
            self.current_step_results.append(result_value)
        self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, "PASS" if success else "FAIL", result_value)
        if success: self._retry_count = 0; self.on_sub_step_complete()
        else:
            if sub_step.fail_strategy == SubStepFailStrategy.RETRY_3 and self._retry_count < 3:
                self._retry_count += 1
                self.log_message.emit(self.channel_id, f"[!] 子工步执行失败，第 {self._retry_count} 次重试...")
                QTimer.singleShot(500, lambda: self.execute_sub_step(sub_step))
                return
            self._retry_count = 0
            if sub_step.fail_strategy == SubStepFailStrategy.CONTINUE: self.on_sub_step_complete()
            else: self.on_step_complete(is_pass=False)

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
            self.db_manager.log_item_result(self.test_id, step.name, float(step.min_limit or 0), float(step.max_limit or 0), self._parse_numeric(val), "PASS" if is_pass else "NG")
        self.step_finished.emit(self.channel_id, step.name, is_pass)
        if not is_pass and step.ng_strategy == NGStrategy.STOP_ON_ANY:
            self.log_message.emit(self.channel_id, f"[!] 触发NG停止策略: {step.name}"); self.test_finished.emit(self.channel_id, False); self.is_running = False; return
        self.current_step_index += 1; self.run_next_step()

class TestEngine(QObject):
    all_channels_finished = Signal()
    barrier_status_changed = Signal(int, int)
    channel_sync_status_changed = Signal(int, bool)
    def __init__(self, device_manager=None, db_manager=None):
        super().__init__()
        self.device_manager, self.db_manager = device_manager, db_manager
        self.workers, self.threads, self.zombie_threads = {}, {}, []
        self._lock = threading.RLock()
        self.sync_barrier_channels = set()
        self.resource_locks = {"ca550": None}
        self.resource_queues = {"ca550": []}

    def request_resource(self, name, cid) -> bool:
        with self._lock:
            if self.resource_locks.get(name) is None: self.resource_locks[name] = cid; return True
            if cid not in self.resource_queues[name]: self.resource_queues[name].append(cid)
            return False

    def release_resource(self, name, cid):
        with self._lock:
            if self.resource_locks.get(name) == cid:
                self.resource_locks[name] = None
                if self.resource_queues[name]:
                    next_ch = self.resource_queues[name].pop(0)
                    self.resource_locks[name] = next_ch
                    if next_ch in self.workers: self.workers[next_ch].resume_from_sync()

    def handle_barrier_reached(self, cid, sub_step=None):
        with self._lock:
            if not self.sync_barrier_channels: self._current_barrier_sub_step = sub_step
            self.sync_barrier_channels.add(cid)
            total, waiting = len(self.workers), len(self.sync_barrier_channels)
            self.barrier_status_changed.emit(waiting, total)
            self.channel_sync_status_changed.emit(cid, True)
            if waiting >= total > 0:
                if hasattr(self, '_current_barrier_sub_step') and self._current_barrier_sub_step:
                    ga = self._current_barrier_sub_step.params.get("global_action")
                    if ga: self._execute_global_action(ga)
                for ch_id in list(self.sync_barrier_channels):
                    if ch_id in self.workers: self.workers[ch_id].resume_from_sync(); self.channel_sync_status_changed.emit(ch_id, False)
                self.sync_barrier_channels.clear(); self._current_barrier_sub_step = None; self.barrier_status_changed.emit(0, total)

    def _execute_global_action(self, ga):
        mgr = self.device_manager
        if not mgr: return
        dev, act, val = ga.get("device", "").lower(), ga.get("action", ""), self.workers[next(iter(self.workers))]._parse_numeric(ga.get("value", "0"))
        try:
            if "hv_source" in dev:
                if "设置电压" in act: mgr.hv_source.set_voltage(val)
                elif "输出控制" in act: mgr.hv_source.output_control("开启" in ga.get("value", "") or "ON" in ga.get("value", "").upper())
            elif "simulator" in dev:
                if "全部开启" in act: mgr.broadcast_output(True)
                elif "全部关闭" in act: mgr.broadcast_output(False)
                elif "电压" in act: mgr.broadcast_voltage(val)
                elif "电流" in act: mgr.broadcast_current(val)
        except Exception as e: print(f"Global action error: {e}")

    def start_channel_test(self, cid, recipe_data, test_id=-1):
        steps = []
        for item in recipe_data:
            s_str = item.get('strategy', "任何NG停止")
            strategy = NGStrategy.STOP_ON_ANY
            for s in NGStrategy:
                if s.value == s_str: strategy = s; break
            step = TestStep(item['name'], StepType.CUSTOM, ng_strategy=strategy)
            step.min_limit = item.get('min') if item.get('min') != "--" else None
            step.max_limit = item.get('max') if item.get('max') != "--" else None
            for sub in item.get('sub_steps', []):
                stype, t_str, p_str = SubStepType.SET_INSTRUMENT, sub.get('type', ""), str(sub.get('params', ""))
                if "智界EOL" in t_str or "EOL协议" in t_str: stype = SubStepType.EOL_PROTOCOL
                elif "读取" in t_str: stype = SubStepType.READ_INSTRUMENT
                elif "CAN发送" in t_str: stype = SubStepType.CAN_SEND
                elif "CAN交互" in t_str: stype = SubStepType.EOL_PROTOCOL if "EOL:" in p_str.upper() else SubStepType.CAN_INTERACT
                elif "等待" in t_str: stype = SubStepType.WAIT
                elif "同步屏障" in t_str: stype = SubStepType.BARRIER
                fs_str, fs = sub.get('fail_strategy', "失败停止"), SubStepFailStrategy.STOP
                for f in SubStepFailStrategy:
                    if f.value == fs_str: fs = f; break
                step.add_sub_step(SubStep(stype, sub.copy(), fail_strategy=fs))
            steps.append(step)
        with self._lock:
            if cid in self.workers: self.stop_channel_test(cid)
        t = QThread(); w = ChannelWorker(cid, steps, self.device_manager, self.db_manager, engine=self)
        w.set_test_info(test_id); w.moveToThread(t); w.reached_barrier.connect(self.handle_barrier_reached)
        t.started.connect(w.start); from PySide6.QtCore import Qt
        w.test_finished.connect(lambda: self.stop_channel_test(cid), Qt.QueuedConnection)
        self.workers[cid], self.threads[cid] = w, t; t.start()

    def stop_channel_test(self, cid):
        with self._lock:
            if cid in self.sync_barrier_channels: self.sync_barrier_channels.remove(cid)
            if cid in self.threads:
                t, w = self.threads[cid], self.workers[cid]
                try: w.test_finished.disconnect()
                except: pass
                w.stop(); t.quit()
                if QThread.currentThread() != t: t.wait(500)
                del self.workers[cid]; del self.threads[cid]; self.zombie_threads.append(t)
                t.finished.connect(t.deleteLater); t.finished.connect(lambda tt=t: self._cleanup_zombie(tt)); w.deleteLater()

    def _cleanup_zombie(self, t):
        with self._lock:
            if t in self.zombie_threads: self.zombie_threads.remove(t)

    def stop_all(self):
        with self._lock:
            for cid in list(self.threads.keys()): self.stop_channel_test(cid)
            import time; s = time.time()
            while self.threads and time.time() - s < 2.0:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents(); time.sleep(0.1)
