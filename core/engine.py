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
    reached_barrier = Signal(int) # 新增：到达同步屏障信号

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
        
        # 集成好的功能：支持 # 屏蔽逻辑
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
                self.reached_barrier.emit(self.channel_id)
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
                    if "全部开启" in params.get("action", ""): success = mgr.broadcast_output(True)
                    elif "全部关闭" in params.get("action", ""): success = mgr.broadcast_output(False)

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
                
                elif "afe" in device or "main_power" in device or "hv_source" in device:
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
                        target_dev = mgr.afe_power_1 if "afe" in device else mgr.mainboard_power
                        act = params.get("action", "")
                        if "输出控制" in act:
                            state = "开启" in p_str or "ON" in p_str.upper()
                            success = target_dev.output_control(state, logger=hw_logger)
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

                elif "easy320" in device:
                    if ":" in p_str:
                        actions = p_str.split(",")
                        for act in actions:
                            if ":" in act:
                                ch_str, state_str = act.split(":")
                                ch_idx = int(self._parse_numeric(ch_str)) - 1
                                state = "ON" in state_str.upper() or "开启" in state_str
                                success = success and mgr.easy320.write_relay(ch_idx, state)

                elif "ca550" in device:
                    if "V" in p_str.upper():
                        mgr.ca550.set_source_func(0)
                        mgr.ca550.set_source_data(self._parse_numeric(p_str))
                        success = mgr.ca550.set_source_output(True)
                    elif "A" in p_str.upper():
                        mgr.ca550.set_source_func(1)
                        mgr.ca550.set_source_data(self._parse_numeric(p_str))
                        success = mgr.ca550.set_source_output(True)
                    elif "关闭" in p_str or "OFF" in p_str.upper():
                        success = mgr.ca550.set_source_output(False)

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
                
                elif "afe" in device or "main_power" in device or "hv_source" in device:
                    if "hv_source" in device:
                        if "电压" in p_str:
                            result_value = mgr.hv_source.measure_voltage(channel=target_ch, logger=hw_logger)
                        elif "电流" in p_str:
                            result_value = mgr.hv_source.measure_current(channel=target_ch, logger=hw_logger)
                        success = result_value >= 0
                    else:
                        target_dev = mgr.afe_power_1 if "afe" in device else mgr.mainboard_power
                        if "电压" in p_str: result_value = target_dev.read_voltage(logger=hw_logger)
                        elif "电流" in p_str: result_value = target_dev.read_current(logger=hw_logger)
                        success = result_value >= 0

                elif "ca550" in device:
                    res_str = mgr.ca550.read_measure_data()
                    result_value = self._parse_numeric(res_str)
                    success = True

                elif "easy320" in device:
                    states = mgr.easy320.read_relays()
                    result_value = str(states)
                    success = len(states) > 0

                if success and self.db_manager and self.test_id != -1 and result_value is not None:
                    v = result_value if "电压" in p_str else -1
                    c = result_value if "电流" in p_str else -1
                    self.db_manager.log_detail(self.test_id, self.steps[self.current_step_index].name, v, c, "--")

            elif sub_step.type == SubStepType.CAN_SEND:
                board = mgr.boards.get(self.channel_id)
                if board:
                    if not board.is_connected: board.connect()
                    success = board.can.send_can_message(
                        channel_id=0,
                        can_id=params.get("id"),
                        can_type=0,
                        dlc=8,
                        data=bytes(params.get("data", []))
                    )
                else: success = False

            elif sub_step.type == SubStepType.CAN_INTERACT:
                pass

            elif sub_step.type == SubStepType.WAIT:
                delay = int(self._parse_numeric(params.get("delay_ms", 1000)))
                QTimer.singleShot(delay, self.on_sub_step_complete)
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

    def handle_barrier_reached(self, channel_id: int):
        """当某个 Worker 到达同步屏障时被调用"""
        with self._lock:
            self.sync_barrier_channels.add(channel_id)
            total_active = len(self.workers)
            waiting_count = len(self.sync_barrier_channels)
            
            print(f"[!] 通道 {channel_id} 到达同步屏障. 进度: {waiting_count}/{total_active}")
            self.barrier_status_changed.emit(waiting_count, total_active)
            self.channel_sync_status_changed.emit(channel_id, True)
            
            if waiting_count >= total_active and total_active > 0:
                print(f"[*] 所有活动通道 ({total_active}) 已到齐，正在释放同步锁...")
                for ch_id in list(self.sync_barrier_channels):
                    if ch_id in self.workers:
                        self.workers[ch_id].resume_from_sync()
                        self.channel_sync_status_changed.emit(ch_id, False)
                self.sync_barrier_channels.clear()
                self.barrier_status_changed.emit(0, total_active)

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
