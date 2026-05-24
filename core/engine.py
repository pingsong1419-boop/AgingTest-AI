from enum import Enum
import re
import threading
from typing import List, Dict, Optional, Any
from PySide6.QtCore import QObject, Signal, QThread, QTimer, Slot
from core.api_client import AgingApiClient

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
    CAN_RECEIVE = "CAN接收"
    EOL_PROTOCOL = "3.5HEOL协议"
    WAIT = "等待"
    BARRIER = "同步屏障"
    READ_VAR = "读取变量"
    ACQUIRE_SEQ_LOCK = "申请顺序锁"
    RELEASE_SEQ_LOCK = "释放顺序锁"

class SubStepFailStrategy(Enum):
    STOP = "失败停止"
    CONTINUE = "忽略继续"
    RETRY_3 = "重试3次"

class SubStep:
    def __init__(self, type: SubStepType, params: Dict, fail_strategy: SubStepFailStrategy = SubStepFailStrategy.STOP):
        self.type = type
        self.params = params
        self.fail_strategy = fail_strategy
        self.is_sync = params.get("sync_exec", False) # 是否为同步执行工步

class TestStep:
    def __init__(self, name: str, step_type: StepType, ng_strategy: NGStrategy = NGStrategy.STOP_ON_ANY):
        self.name = name
        self.step_type = step_type
        self.ng_strategy = ng_strategy
        self.sub_steps: List[SubStep] = []
        self.min_limit = None
        self.max_limit = None
        self.standard_type = "数值"
        self.retry_count = "不复测"
        self.unit = "NULL"
        self.skip_runtime = False
        self.exec_mode = "并行执行"
        self.target_board = "主机"

    def add_sub_step(self, sub_step: SubStep):
        self.sub_steps.append(sub_step)

class ChannelWorker(QObject):
    step_started = Signal(int, str)
    progress_updated = Signal(int, float, dict)
    step_finished = Signal(int, str, bool, object)
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
        self._sync_timer_id = None
        self._is_waiting_for_sync = False
        self.current_step_index = 0
        self.current_sub_step_index = 0
        self.current_step_results = []
        self.test_id = -1
        self._retry_count = 0
        self.step_retry_count = 0
        self.last_hw_log = ""
        self.variables = {}
        self.is_suspended = False
        self.master_barcode = ""
        self.slave_barcodes = []
        
        # 绑定信号以自动在内存中存留全部状态以供监控窗口调阅
        self.log_history = []
        self.step_statuses = {}
        self.sub_step_statuses = {}
        self.step_measured_values = {}
        self.current_progress = 0.0
        self.step_start_times = {}
        self.log_message.connect(lambda _, msg: self.log_history.append(msg))
        self.step_finished.connect(lambda _, name, is_pass, val: (self.step_statuses.__setitem__(name, is_pass), self.step_measured_values.__setitem__(name, val)))
        self.sub_step_finished.connect(lambda _, step_idx, sub_idx, status, result: self.sub_step_statuses.__setitem__((step_idx, sub_idx), (status, result)))
        self.progress_updated.connect(lambda _, prog, __: setattr(self, "current_progress", prog))

    def set_test_info(self, test_id: int):
        self.test_id = test_id

    def start(self):
        self.is_running = True
        self.is_waiting_for_sync = False
        self.current_step_index = 0
        self.progress_updated.emit(self.channel_id, 0.0, {})
        self.log_message.emit(self.channel_id, f"[*] 测试开始，数据库ID: {self.test_id}")
        
        # 异步上报测试启动状态至大屏
        if self.engine and self.engine.api_client:
            def run_start():
                # 按照需求：点击开始测试的时候再将通道显示的条码发送 (prepare)
                slaves = getattr(self, "slave_barcodes", []) or []
                s1 = slaves[0] if len(slaves) > 0 else None
                s2 = slaves[1] if len(slaves) > 1 else None
                s3 = slaves[2] if len(slaves) > 2 else None
                master = getattr(self, "master_barcode", "")
                self.engine.api_client.prepare(self.channel_id, master, s1, s2, s3)
                
                # 随后立即发送 start_test 状态变更
                self.engine.api_client.start_test(self.channel_id)
            threading.Thread(target=run_start, daemon=True).start()
            
        self.run_next_step()

    def stop(self):
        self.is_running = False
        self.is_waiting_for_sync = False
        if self.engine:
            self.engine.release_resource("ca550", self.channel_id)
            self.engine.release_resource("seq_step_lock", self.channel_id)
            self.engine.release_resource("seq_block_lock", self.channel_id)
        self.log_message.emit(self.channel_id, "[!] 收到停止指令")
        
        # 立即关闭相关硬件输出
        try:
            if self.device_manager:
                sim, ch = self.device_manager._get_sim_and_ch(self.channel_id)
                if sim:
                    sim.output_control(ch, False)
                board = self.device_manager.boards.get(self.channel_id)
                if board:
                    board.relays.all_off()
        except Exception:
            pass

        if self.db_manager and self.test_id != -1:
            tid = self.test_id
            self.test_id = -1
            self.db_manager.finish_test(tid, "STOPPED")

        # 触发大屏数据上报与通道重置
        self._upload_final_data_and_reset(False)

    @property
    def is_waiting_for_sync(self) -> bool:
        return getattr(self, "_is_waiting_for_sync", False)

    @is_waiting_for_sync.setter
    def is_waiting_for_sync(self, value: bool):
        self._is_waiting_for_sync = value
        if value:
            self.start_sync_timeout(86400000)
        else:
            self.stop_sync_timeout()

    def start_sync_timeout(self, timeout_ms=60000):
        if getattr(self, "_sync_timer_id", None) is not None:
            try:
                self.killTimer(self._sync_timer_id)
            except Exception:
                pass
            self._sync_timer_id = None
        self._sync_timer_id = self.startTimer(timeout_ms)

    def stop_sync_timeout(self):
        if getattr(self, "_sync_timer_id", None) is not None:
            try:
                self.killTimer(self._sync_timer_id)
            except Exception:
                pass
            self._sync_timer_id = None

    def timerEvent(self, event):
        if getattr(self, "_sync_timer_id", None) is not None and event.timerId() == self._sync_timer_id:
            self.stop_sync_timeout()
            if self.is_waiting_for_sync:
                self.log_message.emit(self.channel_id, "[!] 同步/顺序执行等待超时！看门狗强制释放通道，防止整机卡死。")
                self.resume_from_sync(advance=True)

    def resume_from_sync(self, advance=True):
        if self.is_waiting_for_sync:
            self.is_waiting_for_sync = False
            self.log_message.emit(self.channel_id, "[*] 资源/同步释放，继续执行" + ("下一步" if advance else "当前步"))
            if advance:
                self.on_sub_step_complete()
            else:
                self.run_next_sub_step()

    def run_next_step(self):
        if not self.is_running or self.is_waiting_for_sync:
            return

        if self.current_step_index >= len(self.steps):
            self.progress_updated.emit(self.channel_id, 100.0, {})
            # 判定是否有任何一个测试项是不合格的 (is_pass == False)
            has_ng = False
            for step_name, is_pass in self.step_statuses.items():
                if not is_pass:
                    has_ng = True
                    break
            
            if self.db_manager and self.test_id != -1:
                tid = self.test_id
                self.test_id = -1
                final_status = "FAIL" if has_ng else "PASS"
                self.db_manager.finish_test(tid, final_status if self.is_running else "STOPPED")
                
            self.test_finished.emit(self.channel_id, not has_ng)
            self._upload_final_data_and_reset(not has_ng)
            return

        # 极速闪电跳过循环 (Lightning Skip Loop)：遇到带 "#" 的被屏蔽项，一瞬间登记并广播跳过，0ms 极速奔向下一个勾选项！
        while self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            if not step.name.strip().startswith("#") and not getattr(step, 'skip_runtime', False):
                break
            
            # 瞬间在 0ms 内完成当前项及其所有子步骤的状态登记与跳过广播！
            self.step_started.emit(self.channel_id, step.name)
            self.step_statuses[step.name] = True
            self.step_finished.emit(self.channel_id, step.name, True, "跳过")
            
            for sub_idx, sub in enumerate(step.sub_steps):
                self.sub_step_finished.emit(self.channel_id, self.current_step_index, sub_idx, "跳过", None)
            
            self.current_step_index += 1
            self.progress_updated.emit(self.channel_id, (self.current_step_index / max(1, len(self.steps))) * 100.0, {})

        # 若已完成全部测试项，直接进入 run_next_step 的正常收尾落库结算分支！
        if self.current_step_index >= len(self.steps):
            self.run_next_step()
            return
            
        step = self.steps[self.current_step_index]
        self.step_started.emit(self.channel_id, step.name)
        import time
        self.step_start_times[step.name] = time.time()
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
        for part in str(params).replace("；", "/").replace("，", "/").replace("  ", " ").split("/"):
            part = part.strip()
            if not part: continue
            part = part.replace("：", ":")
            if ":" not in part:
                # 兼容旧配方：如果没有冒号但它是纯数字，推测它是 INDEX
                if part.isdigit(): values["INDEX"] = part
                continue
            key, value = part.split(":", 1)
            # 清洗可能存在的重复冒号 (如 INDEX::0)
            value = value.strip().lstrip(":")
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
        params_str = params.get("params", "")
        kv = self._parse_key_values(params_str)
        hw_logger(f"[DEBUG] EOL RAW: {params_str}")
        hw_logger(f"[DEBUG] EOL KV: {kv}")
        
        eol_cfg = self._parse_eol_params(params)
        if not eol_cfg: raise ValueError("EOL参数缺失")
        board = self._get_can_board(mgr)
        from devices.eol_protocol import EOLProtocol
        eol = EOLProtocol(board.can, channel_id=eol_cfg["channel_id"])
        result = eol.execute(eol_cfg["op_name"], timeout=eol_cfg["timeout"], logger=hw_logger, **eol_cfg["kwargs"])
        result_value = result.value if result.success else result.error
        if result.success and eol_cfg["op_name"] == "绝缘测试":
            self.variables["正极绝缘"] = getattr(result, "rp", 0.0)
            self.variables["负极绝缘"] = getattr(result, "rn", 0.0)
        elif result.success and "0x10" in eol_cfg["op_name"] and eol_cfg["kwargs"].get("DIFF_AMBIENT") == "1":
            try:
                ambient = mgr.chamber.data_store.get("VD720", 25.0) if (mgr and mgr.chamber) else 25.0
                f_val = float(result_value)
                result_value = f"{f_val - ambient:.2f}"
                hw_logger(f"[NTC温差计算] NTC读取值: {f_val} ℃, 环境温度: {ambient} ℃, 温差: {result_value} ℃")
            except Exception as e:
                hw_logger(f"[NTC温差计算] 异常: {e}")

        hw_logger(f"EOL {eol_cfg['op_name']} => {'PASS' if result.success else 'FAIL'} {result_value}")
        return result.success, result_value

    def _execute_sub_step_logic(self, sub_step: SubStep, ignore_sync: bool = False):
        """核心执行逻辑，返回 (success, result_value)"""
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
                # 触发状态收集和广播，防止前台显示卡死
                self.current_step_results.append(("PASS", False))
                self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, "PASS", None)
                return True, None

            if sub_step.type == SubStepType.SET_INSTRUMENT:
                device, p_str = params.get("device", "").lower(), str(params.get("params", ""))
                action = params.get("action", "")
                
                # 定义通用校验逻辑 (增加 2s 稳定延时)
                def verify_and_wait(dev_obj, target_v, ch=None, delay=2.0, threshold=None):
                    if not dev_obj: return True
                    import time; time.sleep(delay)
                    if threshold is None: return True # 如果不指定阈值，则仅延时，不校验
                    try:
                        v_real = dev_obj.measure_voltage(ch, logger=hw_logger) if ch is not None else dev_obj.measure_voltage(logger=hw_logger)
                        if v_real is None or v_real < 0: return True 
                        if abs(v_real - target_v) > threshold:
                            hw_logger(f"[!] 电压校验失败: 设定 {target_v:.4f}V, 实测 {v_real:.4f}V, 误差 {abs(v_real-target_v):.4f}V > {threshold}V")
                            return False
                        hw_logger(f"[*] 电压校验通过: 实测 {v_real:.4f}V")
                        return True
                    except: return True

                if "ca550" in device and self.engine:
                    if not self.engine.request_resource("ca550", self.channel_id):
                        self.is_waiting_for_sync = True
                        self.log_message.emit(self.channel_id, "[#] CA550 资源忙，进入排队等待...")
                        return True, None
                
                target_ch = None
                if "CH:" in p_str:
                    ch_match = re.search(r"CH:(\d+)", p_str)
                    if ch_match: target_ch = int(ch_match.group(1))

                if "simulator" in device or "电池模拟器" in device:
                    target_sim = None
                    if "1#" in device: target_sim = mgr.simulators[0]
                    elif "2#" in device: target_sim = mgr.simulators[1]
                    elif "3#" in device: target_sim = mgr.simulators[2]
                    
                    if "快捷批量配置" in action:
                        volt = self._parse_numeric(p_str.split("V")[0])
                        curr_ma = float(re.search(r"([\d\.]+)mA", p_str).group(1)) if "mA" in p_str else 0.0
                        output_on = "ON" in p_str
                        range_str = "HIGH" if "Range:HIGH" in p_str else "LOW"
                        ch_str = p_str.split("CH:")[-1].strip().upper() if "CH:" in p_str else "ALL"
                        
                        if target_sim:
                            if ch_str == "ALL":
                                target_sim.set_voltage(0, volt, logger=hw_logger)
                                target_sim.set_current_limit(0, curr_ma/1000.0, logger=hw_logger)
                                target_sim.set_range(0, range_str, logger=hw_logger)
                                success = target_sim.output_control(0, output_on, logger=hw_logger)
                                if success and output_on: success = verify_and_wait(target_sim, volt, ch=1, threshold=0.002)
                            else:
                                try:
                                    target_channels = [int(p.strip()) for p in ch_str.replace("，", ",").split(",") if p.strip()]
                                    for ch in target_channels:
                                        if 1 <= ch <= target_sim.max_channels:
                                            target_sim.set_voltage(ch, volt)
                                            target_sim.output_control(ch, output_on)
                                            if output_on: success = success and verify_and_wait(target_sim, volt, ch=ch, threshold=0.002)
                                except: success = False
                        else:
                            if ch_str == "ALL":
                                mgr.broadcast_voltage(volt, logger=hw_logger)
                                success = mgr.broadcast_output(output_on, logger=hw_logger)
                                if success and output_on: success = verify_and_wait(mgr.simulators[0], volt, ch=1, threshold=0.002)
                            else: success = False
                        return success, None

                    ch_to_use = target_ch if target_ch is not None else self.channel_id
                    if target_sim:
                        physical_ch = (ch_to_use - 1) % 18 + 1
                        if "V" in p_str: 
                            v_val = self._parse_numeric(p_str.split("V")[0])
                            success = success and target_sim.set_voltage(physical_ch, v_val, logger=hw_logger)
                            if success: success = verify_and_wait(target_sim, v_val, ch=physical_ch, threshold=0.002)
                        if "开启输出" in p_str: success = success and target_sim.output_control(physical_ch, True, logger=hw_logger)
                        elif "关闭输出" in p_str: success = success and target_sim.output_control(physical_ch, False, logger=hw_logger)
                    else:
                        if "V" in p_str: 
                            v_val = self._parse_numeric(p_str.split("V")[0])
                            success = success and mgr.set_voltage(ch_to_use, v_val, logger=hw_logger)
                            if success:
                                sim, ch = mgr._get_sim_and_ch(ch_to_use)
                                success = verify_and_wait(sim, v_val, ch=ch, threshold=0.002)
                        if "开启输出" in p_str: success = success and mgr.output_control(ch_to_use, True, logger=hw_logger)

                elif any(x in device for x in ["afe", "main", "hv source", "hv_source", "control power", "控制板"]):
                    if "hv_source" in device or "hv source" in device:
                        act = params.get("action", "")
                        if "清除保护" in act:
                            if hasattr(mgr.hv_source, "clear_errors"):
                                success = mgr.hv_source.clear_errors(logger=hw_logger)
                            else:
                                success = True
                        else:
                            if any(x in p_str.upper() for x in ["V", "ON", "OFF"]) or "开启" in p_str or "关闭" in p_str:
                                if "V" in p_str.upper():
                                    v_val = self._parse_numeric(p_str.upper().split("V")[0])
                                    success = mgr.hv_source.set_voltage(v_val, logger=hw_logger)
                                    if success: success = verify_and_wait(mgr.hv_source, v_val)
                                if "开启" in p_str or "ON" in p_str.upper():
                                    success = success and mgr.hv_source.output_control(True, logger=hw_logger)
                                if "关闭" in p_str or "OFF" in p_str.upper():
                                    success = success and mgr.hv_source.output_control(False, logger=hw_logger)
                            else:
                                if "输出控制" in act:
                                    success = mgr.hv_source.output_control("开启" in p_str or "ON" in p_str.upper(), logger=hw_logger)
                                else:
                                    v_val = self._parse_numeric(p_str)
                                    success = mgr.hv_source.set_voltage(v_val, logger=hw_logger)
                                    if success: success = verify_and_wait(mgr.hv_source, v_val)
                    else:
                        target_dev = mgr.afe_pwr_2 if "2#" in device else mgr.afe_pwr_3 if "3#" in device else mgr.afe_power_1 if "afe" in device else mgr.dut_power if "main" in device else mgr.ctrl_board_power
                        if target_dev:
                            if any(x in p_str.upper() for x in ["V", "A", "ON", "OFF"]) or "开启" in p_str or "关闭" in p_str:
                                if "V" in p_str.upper():
                                    v_val = self._parse_numeric(p_str.upper().split("V")[0])
                                    success = target_dev.set_voltage(v_val, logger=hw_logger)
                                    if success: success = verify_and_wait(target_dev, v_val)
                                if "开启" in p_str or "ON" in p_str.upper(): target_dev.output_control(True, logger=hw_logger)
                                if "关闭" in p_str or "OFF" in p_str.upper(): target_dev.output_control(False, logger=hw_logger)
                            else:
                                act = params.get("action", "")
                                if "输出控制" in act: target_dev.output_control("开启" in p_str or "ON" in p_str.upper(), logger=hw_logger)
                                else:
                                    v_val = self._parse_numeric(p_str)
                                    success = target_dev.set_voltage(v_val, logger=hw_logger)
                                    if success: success = verify_and_wait(target_dev, v_val)

                elif "aging_board" in device or "aging board" in device or "老化" in device:
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
                    if not mgr.ca550.is_connected:
                        import data.db_manager as dbm
                        cfg = dbm.DBManager().load_sys_config()
                        com_port = cfg.get("ca550_com", "COM42")
                        mgr.ca550.port = com_port
                        mgr.ca550.connect()
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
                if "变量操作" in params.get("device", "") or "var:" in p_str.lower() or "读取变量" in params.get("action", ""):
                    kv = self._parse_key_values(p_str)
                    var_name = kv.get("VAR", "").strip()
                    val = self.variables.get(var_name, None)
                    if val is not None:
                        if isinstance(val, (int, float)):
                            result_value = f"{val:.1f}kΩ" if "绝缘" in var_name else f"{val:.2f}"
                        else:
                            result_value = str(val)
                        success = True
                    else:
                        result_value = "变量未找到"
                        success = False
                    hw_logger(f"读取变量 [{var_name}] => {result_value}")
                    return success, result_value
                target_ch = int(re.search(r"CH:(\d+)", p_str).group(1)) if "CH:" in p_str else None
                is_volt = "电压" in p_str or "volt" in p_str or "V" in p_str.upper()
                
                # 确定友好名称
                if "1#" in device and "sim" in device: f_name = "1#电池模拟器"
                elif "2#" in device and "sim" in device: f_name = "2#电池模拟器"
                elif "3#" in device and "sim" in device: f_name = "3#电池模拟器"
                elif "sim" in device: f_name = "电池模拟器"
                elif "2#" in device: f_name = "2# AFE电源"
                elif "3#" in device: f_name = "3# AFE电源"
                elif "afe" in device: f_name = "AFE电源"
                elif "main" in device or "dut" in device: f_name = "主板电源"
                elif "hv" in device or "ngi" in device: f_name = "NGI高压源"
                elif "control" in device: f_name = "控制板电源"
                elif "ca550" in device: f_name = "CA550校准仪"
                else: f_name = device.upper()

                if "simulator" in device or "电池模拟器" in device:
                    ch = target_ch if target_ch is not None else self.channel_id
                    target_sim = None
                    if "1#" in device: target_sim = mgr.simulators[0]
                    elif "2#" in device: target_sim = mgr.simulators[1]
                    elif "3#" in device: target_sim = mgr.simulators[2]
                    if target_sim:
                        physical_ch = (ch - 1) % 18 + 1
                        if is_volt:
                            total_v = 0.0
                            for i in range(1, target_sim.max_channels + 1):
                                v = target_sim.measure_voltage(i, logger=hw_logger)
                                if v >= 0: total_v += v
                            hw_logger(f"[1-{target_sim.max_channels}通道总和] 测得电压: {total_v:.2f}V")
                            result_value = total_v
                        else:
                            result_value = target_sim.measure_current(physical_ch)
                    else:
                        result_value = mgr.measure_voltage(ch) if is_volt else mgr.measure_current(ch)
                    success = result_value >= 0
                elif any(x in device for x in ["afe", "main", "hv_source", "hv source", "control power", "控制板"]):
                    if "2#" in device: dev = mgr.afe_pwr_2
                    elif "3#" in device: dev = mgr.afe_pwr_3
                    elif "afe" in device: dev = mgr.afe_power_1
                    elif "main" in device: dev = mgr.dut_power
                    elif "hv_source" in device or "hv source" in device: dev = mgr.hv_source
                    else: dev = mgr.ctrl_board_power
                    if dev:
                        result_value = dev.measure_voltage() if is_volt else dev.measure_current()
                        success = result_value is not None and result_value >= -999.0
                elif "ca550" in device:
                    if not mgr.ca550.is_connected:
                        import data.db_manager as dbm
                        cfg = dbm.DBManager().load_sys_config()
                        com_port = cfg.get("ca550_com", "COM42")
                        mgr.ca550.port = com_port
                        mgr.ca550.connect()
                    mode = "measure" if "测量" in p_str or "measure" in p_str.lower() else "source"
                    result_value = self._parse_numeric(mgr.ca550.read_measure_data(mode))
                    success = result_value is not None
                
                if success and result_value is not None:
                    unit = "V" if is_volt else "mA" if "ca550" in device else "A"
                    hw_logger(f"[回读成功] {f_name} => {result_value:.3f} {unit}")
                else:
                    hw_logger(f"[回读失败] {f_name} => 读取异常")

            elif sub_step.type == SubStepType.CAN_SEND:
                board = self._get_can_board(mgr)
                cfg = self._parse_can_params(params)
                success = board.can.send_can_message(cfg["channel_id"], cfg["can_id"], cfg["can_type"], cfg["dlc"], cfg["data"])
                hw_logger(f"CAN TX CH:{cfg['channel_id']} ID=0x{cfg['can_id']:X} DATA={cfg['data'].hex(' ').upper()}")

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
                    hw_logger(f"CAN REQ CH:{cfg['channel_id']} ID=0x{cfg['can_id']:X} WAIT=0x{w_id:X} => {result_value}")

            elif sub_step.type == SubStepType.CAN_RECEIVE:
                board = self._get_can_board(mgr)
                cfg = self._parse_can_params(params)
                board.can.clear_rx_history(cfg["can_id"])
                msg = board.can.wait_for_message(
                    can_id=cfg["can_id"],
                    channel_id=cfg["channel_id"],
                    timeout=cfg["timeout"]
                )
                success = msg is not None
                result_value = "PASS" if success else "FAIL"
                hw_logger(f"CAN RX_WAIT CH:{cfg['channel_id']} ID=0x{cfg['can_id']:X} => {result_value}")

            elif sub_step.type == SubStepType.EOL_PROTOCOL:
                success, result_value = self._execute_eol_protocol(mgr, params, hw_logger)

            elif sub_step.type == SubStepType.READ_VAR:
                params_str = params.get("params", "")
                kv = self._parse_key_values(params_str)
                var_name = kv.get("VAR", "").strip()
                
                # 新增逻辑：读取环境温度时直接从老化箱获取实时温度
                if var_name == "环境温度":
                    if mgr and mgr.chamber:
                        val = mgr.chamber.data_store.get("VD720", 25.0)
                    else:
                        val = 25.0
                else:
                    val = self.variables.get(var_name, None)
                    
                if val is not None:
                    if isinstance(val, (int, float)):
                        result_value = f"{val:.1f}kΩ" if "绝缘" in var_name else f"{val:.2f}"
                    else:
                        result_value = str(val)
                    success = True
                else:
                    result_value = "变量未找到"
                    success = False
                hw_logger(f"读取变量 [{var_name}] => {result_value}")

            elif sub_step.type == SubStepType.ACQUIRE_SEQ_LOCK:
                lock_name = params.get("lock_name", "seq_step_lock")
                if self.engine:
                    if not self.engine.request_resource(lock_name, self.channel_id):
                        self.is_waiting_for_sync = True
                        self.log_message.emit(self.channel_id, f"[#] 正在申请独占资源 [{lock_name}]...")
                        return True, None
                return True, "OK"

            elif sub_step.type == SubStepType.RELEASE_SEQ_LOCK:
                lock_name = params.get("lock_name", "seq_step_lock")
                if self.engine:
                    self.engine.release_resource(lock_name, self.channel_id)
                return True, "OK"

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
                # 触发状态收集和广播，防止前台显示卡死
                self.current_step_results.append(("OK", bool(sub_step.params.get("is_judgment", False))))
                self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, "PASS", "OK")
                return True, "OK"

        except Exception as e:
            self.log_message.emit(self.channel_id, f"[!] 执行异常: {str(e)}"); success = False

        # 无条件收集每一个子工步的执行结果与数据，由最终提取层进行智能精细化提取
        if success:
            val = result_value if result_value is not None and result_value != "" else "PASS"
        else:
            val = "FAIL"
        
        if sub_step.type == SubStepType.CAN_RECEIVE:
            val = "OK" if success else "NG"
            
        self.current_step_results.append((val, bool(sub_step.params.get("is_judgment", False))))

        self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, "PASS" if success else "FAIL", result_value)
        return success, result_value

    def execute_sub_step(self, sub_step: SubStep, ignore_sync: bool = False):
        if not self.is_running: return
        
        # --- 联动挂起暂停检测 ---
        if getattr(self, "is_suspended", False):
            # 每隔 1 秒重试一次，非阻塞式挂起
            QTimer.singleShot(1000, lambda: self.execute_sub_step(sub_step, ignore_sync))
            return
            
        params = sub_step.params
        is_sync = bool(params.get("sync_exec", False))
        is_seq = bool(params.get("seq_exec", False))
        if sub_step.type == SubStepType.WAIT:
            is_sync = False
        if (is_sync or is_seq) and not ignore_sync:
            self.is_waiting_for_sync = True
            self.log_message.emit(self.channel_id, f"      [{'同步' if is_sync else '顺序'}] 等待所有活跃通道集齐...")
            # 提前发射“同步等待中”的状态广播，防止前台显示待命/卡死
            self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, "同步等待", None)
            self.reached_barrier.emit(self.channel_id, sub_step)
            return

        success, result_value = self._execute_sub_step_logic(sub_step, ignore_sync)
        
        # 核心修复：如果是异步工步（延时）或正在等待同步，不在此处触发推进
        if sub_step.type == SubStepType.WAIT or self.is_waiting_for_sync:
            return
            
        if success: 
            self._retry_count = 0
            self.on_sub_step_complete()
        else:
            if sub_step.fail_strategy == SubStepFailStrategy.RETRY_3 and self._retry_count < 3:
                self._retry_count += 1
                self.log_message.emit(self.channel_id, f"[!] 子工步执行失败，第 {self._retry_count} 次重试...")
                # 重试时以 ignore_sync=True 执行，防止因重复进入同步挂起导致死锁卡死！
                QTimer.singleShot(500, lambda: self.execute_sub_step(sub_step, ignore_sync=True))
                return
            self._retry_count = 0
            if sub_step.fail_strategy == SubStepFailStrategy.CONTINUE: self.on_sub_step_complete()
            else: self.on_step_complete(is_pass=False)

    def on_sub_step_complete(self):
        if not self.is_running: return
        self.current_sub_step_index += 1
        # 使用 QTimer.singleShot(0) 将下一个子工步推迟到事件循环的下一次迭代，
        # 从而断开同步调用的栈堆积，彻底解决 maximum recursion depth exceeded
        QTimer.singleShot(0, self.run_next_sub_step)

    def on_step_complete(self, is_pass: bool = True):
        if not self.is_running: return
        
        # 强制在每次工步结束时释放可能持有的互斥锁，防止子工步提前报错跳出导致的死锁
        if self.engine:
            try: 
                self.engine.release_resource("ca550", self.channel_id)
                self.engine.release_resource("seq_step_lock", self.channel_id)
            except: pass
            
        step = self.steps[self.current_step_index]
        
        # 智能提取层：优先提取在配方中被勾选了“结果输出并参与判定(is_judgment)”的有效物理量结果
        val = None
        if self.current_step_results:
            # 1. 契约优先挑选：寻找被勾选参与判定且结果不为 None 且不为 PASS/FAIL/OK/NG 的真正物理值
            for r_val, is_judg in self.current_step_results:
                if is_judg:
                    if r_val not in (None, "", "PASS", "FAIL", "OK", "NG"):
                        val = r_val
                        break
            
            # 2. 契约次优挑选：如果勾选了参与判定的子步骤回传的是 PASS/FAIL/OK/NG 控制结论
            if val is None:
                for r_val, is_judg in self.current_step_results:
                    if is_judg:
                        if r_val not in (None, ""):
                            val = r_val
                            break

            # 3. 常规降级提取：若全步骤无勾选参与判定的有效数据，则按历史降级提取物理量
            if val is None:
                for r_val, is_judg in self.current_step_results:
                    if r_val not in (None, "", "PASS", "FAIL", "OK", "NG"):
                        val = r_val
                        break
            
            # 4. 终极控制兜底：若无任何子工步实际数据返回，则使用最后一个非 None 的执行结论作为测量值兜底
            if val is None:
                for r_val, is_judg in reversed(self.current_step_results):
                    if r_val is not None:
                        val = r_val
                        break

        # 确定最终记录的值
        if getattr(step, "standard_type", "数值") == "字符串":
            val_to_log = val
        else:
            # 智能识别非纯数字测量值（包含 PASS, FAIL, 字母等）
            if isinstance(val, str) and any(c.isalpha() for c in val) and val not in ("OK", "NG"):
                val_to_log = val
            elif val in ("OK", "NG"):
                val_to_log = val
            else:
                val_to_log = self._parse_numeric(val) if val is not None else None

        # 核心判定逻辑：如果前期执行正常 (is_pass == True)，则使用提取到的最终值进行范围判定
        if is_pass:
            std_type = getattr(step, "standard_type", "数值")
            if std_type == "不判断":
                pass  # 强制不判断，保留 is_pass = True
            elif std_type == "字符串":
                # 字符串精确相等比对 (不区分首尾空格)
                target = str(step.min_limit or "").strip()
                actual = str(val_to_log or "").strip()
                # 只有当配方中填写了非空的目标值才进行比对
                if target != "" and target != actual:
                    is_pass = False
            else:
                # 数值范围判定
                # 修复BUG：如果获取到的值是控制结论 "PASS" 或 "FAIL"，但测试项确实配置了上下限要求，应该判定为 NG，因为没有取到有效数值
                has_limits = step.min_limit is not None or step.max_limit is not None
                # 若提取的是纯控制字，但在配方中却配了具体的物理上下限，则视为错误，强制NG
                # 除非配方中明确填写的下限就是这个控制字（例如明确要等 OK）
                if val_to_log in ("PASS", "FAIL", "OK") and has_limits:
                    if str(step.min_limit).strip().upper() != str(val_to_log).upper():
                        is_pass = False
                elif val_to_log in ("FAIL", "NG"):
                    is_pass = False
                elif val_to_log not in ("PASS", "FAIL", "OK", "NG") and val_to_log is not None:
                    # 使用 _parse_numeric 提取出纯数字进行比较，忽略单位字符（如 kΩ、V 等）
                    f_val = self._parse_numeric(val_to_log)
                    try:
                        if step.min_limit is not None and str(step.min_limit).strip() != "" and f_val < float(step.min_limit): is_pass = False
                    except ValueError: pass
                    try:
                        if step.max_limit is not None and str(step.max_limit).strip() != "" and f_val > float(step.max_limit): is_pass = False
                    except ValueError: pass

        # 2. 检查 NG 复测策略
        import time
        max_retries = 0
        retry_str = getattr(step, "retry_count", "不复测")
        if retry_str == "复测1次": max_retries = 1
        elif retry_str == "复测3次": max_retries = 3
        
        if not is_pass and self.step_retry_count < max_retries:
            self.step_retry_count += 1
            self.log_message.emit(self.channel_id, f"[!] 测试项【{step.name}】判定为NG，触发复测机制 (当前第 {self.step_retry_count} 次复测，上限 {max_retries} 次)...")
            self.current_sub_step_index = 0
            self.current_step_results.clear()
            if not hasattr(self, "step_start_times"): self.step_start_times = {}
            self.step_start_times[step.name] = time.time()
            # 重新执行该工步的第一个子工步
            self.run_next_sub_step()
            return
            
        # 走到这里，要么 PASS，要么已经耗尽全部复测次数。重置当前测试项的复测计数
        self.step_retry_count = 0
                
        # 计算用时
        start_time = getattr(self, "step_start_times", {}).get(step.name, time.time())
        duration = round(time.time() - start_time, 2)

        # 3. 始终将测试项判定记录写入数据库，以供报告生成使用
        if self.db_manager and self.test_id != -1:
            std_type = getattr(step, "standard_type", "数值")
            if std_type == "字符串" or std_type == "不判断":
                min_lim = step.min_limit
                max_lim = step.max_limit
            else:
                try: min_lim = float(step.min_limit) if step.min_limit is not None else None
                except: min_lim = None
                try: max_lim = float(step.max_limit) if step.max_limit is not None else None
                except: max_lim = None
                
            self.db_manager.log_item_result(
                self.test_id, 
                step.name, 
                min_lim, 
                max_lim, 
                val_to_log, 
                "PASS" if is_pass else "NG",
                duration,
                unit=getattr(step, "unit", "NULL")
            )
            
            # 异步上报当前单步进度与物理测量数据至大屏
            if self.engine and self.engine.api_client:
                def run_progress():
                    barcode = getattr(step, "target_board", "主机")
                    test_value_str = str(val_to_log)
                    result_str = "PASS" if is_pass else "FAIL"
                    upper_limit_str = str(step.max_limit) if step.max_limit is not None else None
                    lower_limit_str = str(step.min_limit) if step.min_limit is not None else None
                    unit_str = getattr(step, "unit", None)
                    if unit_str == "NULL": 
                        unit_str = None
                    self.engine.api_client.report_progress(
                        channel_id=self.channel_id,
                        barcode=barcode,
                        name=step.name,
                        test_value=test_value_str,
                        result=result_str,
                        unit=unit_str,
                        upper_limit=upper_limit_str,
                        lower_limit=lower_limit_str,
                        index=str(self.current_step_index + 1)
                    )
                threading.Thread(target=run_progress, daemon=True).start()
            
        self.step_finished.emit(self.channel_id, step.name, is_pass, val_to_log)
        if not is_pass and step.ng_strategy == NGStrategy.STOP_ON_ANY:
            self.log_message.emit(self.channel_id, f"[!] 触发NG停止策略: {step.name}")
            if self.db_manager and self.test_id != -1:
                tid = self.test_id
                self.test_id = -1
                self.db_manager.finish_test(tid, "NG")
            self.test_finished.emit(self.channel_id, False)
            self.is_running = False
            
            # 触发大屏数据上报与通道重置 (不合格)
            self._upload_final_data_and_reset(False)
            return
        self.current_step_index += 1
        self.progress_updated.emit(self.channel_id, (self.current_step_index / max(1, len(self.steps))) * 100.0, {})
        QTimer.singleShot(0, self.run_next_step)

    def get_barcode_for_target_board(self, target_board: str) -> str:
        tb = str(target_board or "").strip()
        m_barcode = getattr(self, "master_barcode", "") or f"CH{self.channel_id}_MASTER_SN"
        slave_list = getattr(self, "slave_barcodes", []) or []
        
        if "主机" in tb or "MAIN" in tb.upper() or "DUT" in tb.upper():
            return m_barcode
        if "从机1" in tb or "从机 1" in tb or "SLAVE1" in tb.upper() or "SLAVE 1" in tb.upper():
            return slave_list[0] if len(slave_list) > 0 else f"CH{self.channel_id}_SLAVE1_SN"
        if "从机2" in tb or "从机 2" in tb or "SLAVE2" in tb.upper() or "SLAVE 2" in tb.upper():
            return slave_list[1] if len(slave_list) > 1 else f"CH{self.channel_id}_SLAVE2_SN"
        if "从机3" in tb or "从机 3" in tb or "SLAVE3" in tb.upper() or "SLAVE 3" in tb.upper():
            return slave_list[2] if len(slave_list) > 2 else f"CH{self.channel_id}_SLAVE3_SN"
        return m_barcode

    def _upload_final_data_and_reset(self, status: bool):
        """异步执行测试判定结果上传、通道测试数据完整上报、以及大屏通道重置流程，异常时不阻塞本地业务"""
        if not (self.engine and self.engine.api_client):
            return

        def run():
            client = self.engine.api_client
            cid = self.channel_id
            
            def safe_log(msg):
                try:
                    self.log_message.emit(cid, msg)
                except RuntimeError:
                    pass

            m_barcode = getattr(self, "master_barcode", "") or f"CH{cid}_MASTER_SN"
            slave_list = getattr(self, "slave_barcodes", []) or []
            
            # 映射三个可能从机 SN 条码
            s1 = slave_list[0] if len(slave_list) > 0 else None
            s2 = slave_list[1] if len(slave_list) > 1 else None
            s3 = slave_list[2] if len(slave_list) > 2 else None
            
            # 整理开始与结束时间
            import datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time_str = now_str
            if hasattr(self, "step_start_times") and self.step_start_times:
                try:
                    first_time = min(self.step_start_times.values())
                    start_time_str = datetime.datetime.fromtimestamp(first_time).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

            # 拼装全程已测项目的完整历史细节报文
            master_test_data = []
            for idx, step in enumerate(self.steps):
                if step.name.strip().startswith("#") or getattr(step, 'skip_runtime', False):
                    continue
                step_name = step.name
                is_pass = self.step_statuses.get(step_name, True)
                measured_val = self.step_measured_values.get(step_name, None)
                val_str = str(measured_val) if measured_val is not None else "--"
                
                master_test_data.append({
                    "name": step_name,
                    "testValue": val_str,
                    "unit": getattr(step, "unit", "NULL"),
                    "upperLimit": str(step.max_limit) if step.max_limit is not None else "--",
                    "lowerLimit": str(step.min_limit) if step.min_limit is not None else "--",
                    "result": "PASS" if is_pass else "FAIL",
                    "index": str(idx + 1),
                    "testclass": getattr(step, "target_board", "主机")
                })

            # 1. 发送完成信号至大屏
            safe_log(f"[*] 正在上报测试完成判定信号至大屏... 最终判定: {'合格(PASS)' if status else '不合格(FAIL)'}")
            f_res = client.finish_test(cid, status)
            if f_res:
                safe_log("[*] 大屏测试完成信号接收成功。")
            else:
                safe_log("[!] 警告: 大屏服务未连接，测试完成信号上报失败（本地继续）。")

            # 2. 上传整条通道的所有完整判定测试记录
            safe_log("[*] 正在上传本通道全部工步的最终测试报表数据...")
            d_res = client.upload_test_data(
                channel_id=cid,
                master_barcode=m_barcode,
                start_time=start_time_str,
                end_time=now_str,
                status=status,
                master_test_data=master_test_data,
                slave_barcode_1=s1,
                slave_barcode_2=s2,
                slave_barcode_3=s3
            )
            if d_res:
                safe_log("[*] 完整测试历史记录大屏上传成功。")
            else:
                safe_log("[!] 警告: 大屏服务未连接，历史数据上传失败。")

            # 测试完成后不重置通道，保留测试最终判定和图表数据，仅打印提示
            safe_log("[*] 测试已完成，大屏最终判定与图表数据已妥善留存。")

        threading.Thread(target=run, daemon=True).start()

class TestEngine(QObject):
    all_channels_finished = Signal()
    barrier_status_changed = Signal(int, int)
    channel_sync_status_changed = Signal(int, bool)
    seq_status_changed = Signal(int, int)
    channel_step_started = Signal(int, str)
    channel_test_finished = Signal(int, bool)
    api_log_message = Signal(str)

    def __init__(self, device_manager=None, db_manager=None):
        super().__init__()
        self.device_manager, self.db_manager = device_manager, db_manager
        self.workers, self.threads, self.zombie_threads = {}, {}, []
        self._lock = threading.RLock()
        self.sync_barrier_channels = set()
        self.sync_groups = {}
        self.resource_locks = {"ca550": None, "seq_step_lock": None, "seq_block_lock": None}
        self.resource_queues = {"ca550": [], "seq_step_lock": [], "seq_block_lock": []}
        self.batch_starting = False
        self._current_barrier_sub_step = {}

        # 初始化 API 客户端
        self.api_client = None
        self.update_api_client()

        # 启动后台心跳守护线程
        self.heartbeat_running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()

    def log_api_call(self, msg: str):
        """API 日志输出并触发 Qt 信号"""
        self.api_log_message.emit(msg)

    def update_api_client(self):
        """动态加载配置并更新 API 客户端"""
        with self._lock:
            cfg = self.db_manager.load_sys_config() if self.db_manager else {}
            host = cfg.get("api_host", "127.0.0.1")
            try:
                port = int(cfg.get("api_port", 8008))
            except:
                port = 8008
            self.api_client = AgingApiClient(host, port, logger=self.log_api_call)

    def _heartbeat_worker(self):
        """后台心跳工作线程，每 5 秒上报一次老化箱实时温度"""
        import time
        while self.heartbeat_running:
            try:
                # 获取实时老化温度箱温度
                temp = 25.0
                if self.device_manager and getattr(self.device_manager, 'chamber', None):
                    temp = self.device_manager.chamber.data_store.get("VD720", 25.0)
                
                # 发送心跳
                if self.api_client:
                    self.api_client.heartbeat(temp)
            except Exception as e:
                self.log_api_call(f"[API ERR] 心跳后台上报出现异常: {str(e)}")
            
            # 定时 5 秒
            for _ in range(50):
                if not self.heartbeat_running:
                    break
                time.sleep(0.1)

    def begin_batch_start(self):
        with self._lock: self.batch_starting = True
        
    def end_batch_start(self):
        with self._lock: 
            self.batch_starting = False
            self._check_and_release_barrier()

    def request_resource(self, name, cid) -> bool:
        with self._lock:
            if self.resource_locks.get(name) == cid: return True
            if self.resource_locks.get(name) is None: 
                self.resource_locks[name] = cid
                if name in ("seq_step_lock", "seq_block_lock"): self._emit_seq_queue_status()
                return True
            if cid not in self.resource_queues[name]: 
                self.resource_queues[name].append(cid)
                if name in ("seq_step_lock", "seq_block_lock"): self._emit_seq_queue_status()
            return False

    def release_resource(self, name, cid):
        with self._lock:
            if self.resource_locks.get(name) == cid:
                self.resource_locks[name] = None
                if self.resource_queues[name]:
                    next_ch = self.resource_queues[name].pop(0)
                    self.resource_locks[name] = next_ch
                    if next_ch in self.workers:
                        w = self.workers[next_ch]
                        QTimer.singleShot(0, w, lambda w=w: w.resume_from_sync(advance=False))
                if name in ("seq_step_lock", "seq_block_lock"): self._emit_seq_queue_status()

    def _emit_seq_queue_status(self):
        # 计算当前的顺序排队状态并发出信号
        executing_cid = self.resource_locks.get("seq_step_lock") or self.resource_locks.get("seq_block_lock")
        queue_len = len(self.resource_queues.get("seq_step_lock", [])) + len(self.resource_queues.get("seq_block_lock", []))
        if executing_cid is None:
            self.seq_status_changed.emit(-1, 0)
        else:
            self.seq_status_changed.emit(executing_cid, queue_len)

    def handle_barrier_reached(self, cid, sub_step=None):
        with self._lock:
            group = self.sync_groups.get(cid)
            group_key = frozenset(group) if group else frozenset({cid})
            if group_key not in self._current_barrier_sub_step:
                self._current_barrier_sub_step[group_key] = sub_step
            self.sync_barrier_channels.add(cid)
            self.channel_sync_status_changed.emit(cid, True)
            self._check_and_release_barrier()

    def _check_and_release_barrier(self):
        """BUG-04修复: 按同步组分组判定，防止不同组通道互相绑定导致死锁"""
        with self._lock:
            if not self.sync_barrier_channels or self.batch_starting:
                return

            # 将屏障中的通道按其同步组分组
            groups_waiting: dict = {}
            for cid in self.sync_barrier_channels:
                group = self.sync_groups.get(cid)
                group_key = frozenset(group) if group else frozenset({cid})
                groups_waiting.setdefault(group_key, set()).add(cid)

            for group_key, waiting_set in groups_waiting.items():
                active_in_group = [cid for cid in group_key if cid in self.workers]
                total = len(active_in_group)
                waiting = len(waiting_set)
                
                # 诊断日志：打印各组屏障等待状态，精确定位未到达的通道
                not_reached = [cid for cid in active_in_group if cid not in waiting_set]
                if not_reached:
                    sub_obj = self._current_barrier_sub_step.get(group_key)
                    sub_name = sub_obj.params.get("name", sub_obj.type.value) if (sub_obj and hasattr(sub_obj, "params")) else "未知屏障"
                    print(f"[TestEngine 诊断] 同步组 {list(group_key)} 正在等待屏障 '{sub_name}'。已到达: {list(waiting_set)}, 未到达: {not_reached}")
                
                self.barrier_status_changed.emit(waiting, total)

                if waiting >= total > 0:
                    # 该组已集齐，准备释放
                    channels_to_release = sorted(waiting_set)  # 排序保证确定性
                    for cid in channels_to_release:
                        self.sync_barrier_channels.discard(cid)
                    exec_cid = channels_to_release[0]  # 取最小 cid 为执行主体
                    sub = self._current_barrier_sub_step.pop(group_key, None)

                    def run_sync_op(exec_cid=exec_cid, channels_to_release=channels_to_release,
                                   sub=sub, total=total):
                        try:
                            master_success, master_result = True, None
                            if sub and hasattr(sub, "params") and sub.params.get("sync_exec"):
                                if exec_cid in self.workers:
                                    worker = self.workers[exec_cid]
                                    worker.log_message.emit(exec_cid, f"[*] 同步集齐 ({channels_to_release})，开始执行共享控制...")
                                    master_success, master_result = worker._execute_sub_step_logic(sub, ignore_sync=True)

                            for ch_id in channels_to_release:
                                if ch_id in self.workers:
                                    w = self.workers[ch_id]
                                    def make_release(target_w=w, success=master_success, res=master_result):
                                        def do_release():
                                            if target_w.channel_id != exec_cid:
                                                # 为 Slave 通道高保真追加真实测试结果，彻底防止误判NG
                                                val = "PASS" if success else "FAIL"
                                                if res is not None and res != "":
                                                    val = res
                                                is_judg = False
                                                if sub and hasattr(sub, "params"):
                                                    is_judg = bool(sub.params.get("is_judgment", False))
                                                target_w.current_step_results.append((val, is_judg))
                                                target_w.sub_step_finished.emit(target_w.channel_id, target_w.current_step_index, target_w.current_sub_step_index, "PASS" if success else "FAIL", res)
                                            target_w.resume_from_sync()
                                            self.channel_sync_status_changed.emit(target_w.channel_id, False)
                                        return do_release
                                    QTimer.singleShot(0, w, make_release())

                            QTimer.singleShot(0, self, lambda: self.barrier_status_changed.emit(0, total))
                        except Exception as e:
                            print(f"[TestEngine] 同步执行线程崩溃: {e}")
                            for ch_id in channels_to_release:
                                if ch_id in self.workers: QTimer.singleShot(0, self.workers[ch_id].resume_from_sync)

                    threading.Thread(target=run_sync_op, daemon=True).start()
                    break  # 一次只处理一个就绪组

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

    def start_channel_test(self, cid, recipe_data, test_id=-1, sync_group=None, master_barcode="", slaves=None):
        if sync_group:
            with self._lock:
                # 记录该通道所属的同步组 (即所有勾选的通道集合)
                group_set = set(sync_group)
                for member in group_set:
                    self.sync_groups[member] = group_set
                    
        steps = []
        for item in recipe_data:
            name = item.get('name', '')
            s_str = item.get('strategy', "任何NG停止")
            strategy = NGStrategy.STOP_ON_ANY
            for s in NGStrategy:
                if s.value == s_str: strategy = s; break
            step = TestStep(item['name'], StepType.CUSTOM, ng_strategy=strategy)
            step.skip_runtime = item.get('skip_runtime', False)
            step.min_limit = item.get('min') if item.get('min') != "--" else None
            step.max_limit = item.get('max') if item.get('max') != "--" else None
            step.standard_type = item.get('standard_type', "数值")
            step.retry_count = item.get('retry_count', "不复测")
            step.unit = item.get('unit', "NULL")
            step.exec_mode = item.get('exec_mode', "并行执行")
            step.target_board = item.get('target_board', '主机')
            is_block_start = item.get('is_block_start', False)
            is_block_end = item.get('is_block_end', False)
            
            # 块锁头部注入
            if is_block_start:
                step.add_sub_step(SubStep(SubStepType.BARRIER, {"sync_exec": False}))
                step.add_sub_step(SubStep(SubStepType.ACQUIRE_SEQ_LOCK, {"lock_name": "seq_block_lock"}))

            # 顺序执行的头部注入
            if step.exec_mode == "顺序执行":
                step.add_sub_step(SubStep(SubStepType.BARRIER, {"sync_exec": False}))
                step.add_sub_step(SubStep(SubStepType.ACQUIRE_SEQ_LOCK, {"lock_name": "seq_step_lock"}))

            for sub in item.get('sub_steps', []):
                stype, t_str, p_str = SubStepType.SET_INSTRUMENT, sub.get('type', ""), str(sub.get('params', ""))
                
                # 过滤掉缓存中因上次运行而自动注入的幽灵工步（屏障、顺序锁），防止多次点击运行后出现重复或变异（变成"设置仪表"）
                if t_str in (SubStepType.ACQUIRE_SEQ_LOCK.value, SubStepType.RELEASE_SEQ_LOCK.value):
                    continue
                if t_str == SubStepType.BARRIER.value and not sub.get('params', {}).get("sync_exec", False):
                    continue
                    
                dev_str, act_str = sub.get('device', ""), sub.get('action', "")
                if "3.5HEOL" in t_str or "EOL协议" in t_str: stype = SubStepType.EOL_PROTOCOL
                elif "读取变量" in t_str or "变量操作" in dev_str or "读取变量" in act_str or "VAR:" in p_str: stype = SubStepType.READ_VAR
                elif "读取" in t_str: stype = SubStepType.READ_INSTRUMENT
                elif "CAN发送" in t_str or "发送指令" in act_str: stype = SubStepType.CAN_SEND
                elif "CAN接收" in t_str or "接收指定帧ID" in t_str or "接收指定帧ID" in act_str: stype = SubStepType.CAN_RECEIVE
                elif "CAN交互" in t_str or "报文交互" in t_str: stype = SubStepType.EOL_PROTOCOL if "EOL:" in p_str.upper() else SubStepType.CAN_INTERACT
                elif "等待" in t_str: stype = SubStepType.WAIT
                elif "同步屏障" in t_str: stype = SubStepType.BARRIER
                
                fs_str, fs = sub.get('fail_strategy', "失败停止"), SubStepFailStrategy.STOP
                for f in SubStepFailStrategy:
                    if f.value == fs_str: fs = f; break
                    
                sub_params = sub.copy()
                # 防死锁：外层既然要求顺序执行，内部子工步强行剥离所有同步执行属性，避免互相干涉卡死
                if step.exec_mode == "顺序执行" and sub_params.get("sync_exec", False):
                    sub_params["sync_exec"] = False
                    
                step.add_sub_step(SubStep(stype, sub_params, fail_strategy=fs))
                
            # 顺序执行的尾部注入
            if step.exec_mode == "顺序执行":
                step.add_sub_step(SubStep(SubStepType.RELEASE_SEQ_LOCK, {"lock_name": "seq_step_lock"}))
                step.add_sub_step(SubStep(SubStepType.BARRIER, {"sync_exec": False}))
                
            # 块锁尾部注入
            if is_block_end:
                step.add_sub_step(SubStep(SubStepType.RELEASE_SEQ_LOCK, {"lock_name": "seq_block_lock"}))
                step.add_sub_step(SubStep(SubStepType.BARRIER, {"sync_exec": False}))
                
            steps.append(step)
        with self._lock:
            if cid in self.workers: self.stop_channel_test(cid)
        t = QThread(); w = ChannelWorker(cid, steps, self.device_manager, self.db_manager, engine=self)
        w.master_barcode = master_barcode
        w.slave_barcodes = slaves or []
        w.set_test_info(test_id); w.moveToThread(t); w.reached_barrier.connect(self.handle_barrier_reached)
        w.step_started.connect(self.channel_step_started)
        w.test_finished.connect(self.channel_test_finished)
        t.started.connect(w.start); from PySide6.QtCore import Qt
        w.test_finished.connect(self._on_worker_test_finished, Qt.QueuedConnection)
        self.workers[cid], self.threads[cid] = w, t; t.start()

    @Slot(int, bool)
    def _on_worker_test_finished(self, cid, success):
        self.stop_channel_test(cid)

    def stop_channel_test(self, cid):
        with self._lock:
            if cid in self.sync_barrier_channels:
                self.sync_barrier_channels.remove(cid)
            if cid in self.threads:
                t, w = self.threads[cid], self.workers[cid]
                try: w.test_finished.disconnect()
                except: pass
                w.stop(); t.quit()
                del self.workers[cid]; del self.threads[cid]; self.zombie_threads.append(t)
                if cid in self.sync_groups: del self.sync_groups[cid]
                t.finished.connect(t.deleteLater); t.finished.connect(lambda tt=t: self._cleanup_zombie(tt)); w.deleteLater()
            self._check_and_release_barrier() # 剔除 channel worker 后再检查集齐条件，防止死锁

    def _cleanup_zombie(self, t):
        with self._lock:
            if t in self.zombie_threads: self.zombie_threads.remove(t)

    def stop_all(self):
        self.heartbeat_running = False
        with self._lock:
            for cid in list(self.threads.keys()): self.stop_channel_test(cid)
            import time; s = time.time()
            while self.threads and time.time() - s < 2.0:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents(); time.sleep(0.1)
