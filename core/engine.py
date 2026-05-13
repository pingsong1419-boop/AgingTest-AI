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

    def __init__(self, channel_id: int, steps: List[TestStep], device_manager=None, db_manager=None):
        super().__init__()
        self.channel_id = channel_id
        self.steps = steps
        self.device_manager = device_manager
        self.db_manager = db_manager
        self.is_running = False
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
        self.current_step_index = 0
        self.log_message.emit(self.channel_id, f"[*] 测试开始，数据库ID: {self.test_id}")
        self.run_next_step()

    def stop(self):
        self.is_running = False
        self.log_message.emit(self.channel_id, "[!] 收到停止指令")

    def run_next_step(self):
        if not self.is_running or self.current_step_index >= len(self.steps):
            is_pass = all(getattr(self, '_all_steps_pass', [True])) # Simplified
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
        if not self.is_running: return
        
        step = self.steps[self.current_step_index]
        if self.current_sub_step_index >= len(step.sub_steps):
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
        
        # 记录执行日志
        retry_tag = f" [重试 {self._retry_count}]" if self._retry_count > 0 else ""
        self.log_message.emit(self.channel_id, f"-> {sub_step.type.value}{retry_tag}: {params.get('device', '')} {params.get('action', '')}")
        
        success = True
        result_value = None
        
        try:
            if not mgr: raise ValueError("设备管理器未初始化")
            
            # 创建日志回调
            def hw_logger(msg):
                self.last_hw_log = msg
                self.log_message.emit(self.channel_id, f"      {msg}")

            if sub_step.type == SubStepType.SET_INSTRUMENT:
                device = params.get("device", "").lower()
                p_str = str(params.get("params", ""))
                action = params.get("action", "")
                
                if "simulator" in device:
                    if "全部" in action:
                        if "开启" in action: success = mgr.broadcast_output(True, logger=hw_logger)
                        elif "关闭" in action: success = mgr.broadcast_output(False, logger=hw_logger)
                        else:
                            # 全部通道设置参数
                            if "V" in p_str:
                                val = self._parse_numeric(p_str.split("V")[0])
                                success = success and mgr.broadcast_voltage(val, logger=hw_logger)
                            if "A" in p_str:
                                a_match = re.search(r"([\d\.]+)\s*A", p_str)
                                if a_match:
                                    val = float(a_match.group(1))
                                    success = success and mgr.broadcast_current(val, logger=hw_logger)
                            if "开启输出" in p_str: success = success and mgr.broadcast_output(True, logger=hw_logger)
                            elif "关闭输出" in p_str: success = success and mgr.broadcast_output(False, logger=hw_logger)
                    else:
                        # 改进的参数解析 (单通道)
                        if "V" in p_str:
                            val = self._parse_numeric(p_str.split("V")[0])
                            success = success and mgr.set_voltage(self.channel_id, val, logger=hw_logger)
                        if "A" in p_str:
                            a_match = re.search(r"([\d\.]+)\s*A", p_str)
                            if a_match:
                                val = float(a_match.group(1))
                                success = success and mgr.set_current(self.channel_id, val, logger=hw_logger)
                        if "开启输出" in p_str: success = success and mgr.output_control(self.channel_id, True, logger=hw_logger)
                        elif "关闭输出" in p_str: success = success and mgr.output_control(self.channel_id, False, logger=hw_logger)
                
                elif any(x in device for x in ["afe", "main power", "hv source", "power board"]):
                    pwr_inst = None
                    if "afe 1" in device or "1# afe" in device: pwr_inst = mgr.afe_power_1
                    elif "afe 2" in device or "2# afe" in device: pwr_inst = mgr.afe_pwr_standalone
                    elif "afe 3" in device or "3# afe" in device:
                        hw_logger("警告: 3# AFE 电源尚未接入系统。")
                        success = False
                    elif "main" in device: pwr_inst = mgr.mainboard_power
                    elif "hv" in device: pwr_inst = mgr.hv_source
                    elif "power board" in device: pwr_inst = getattr(mgr, 'power_board_ru12', None)
                    
                    if pwr_inst:
                        if "V" in p_str:
                            val = self._parse_numeric(p_str.split("V")[0])
                            if hasattr(pwr_inst, 'set_voltage'): success = success and pwr_inst.set_voltage(val)
                        if "A" in p_str:
                            a_match = re.search(r"([\d\.]+)\s*A", p_str)
                            if a_match and hasattr(pwr_inst, 'set_current'):
                                success = success and pwr_inst.set_current(float(a_match.group(1)))
                        if "开启输出" in p_str: success = success and pwr_inst.output_control(True)
                        elif "关闭输出" in p_str: success = success and pwr_inst.output_control(False)
                    else:
                        success = False
                        hw_logger(f"错误: 找不到 {device} 设备实例。")

                elif "继电器" in device or "easy320" in device or "aging board" in device:
                    relay_inst = getattr(mgr, 'easy320', None) if "easy320" in device else getattr(mgr, 'aging_board', None)
                    ch_match = re.search(r"CH:(\d+)", p_str)
                    ch = int(ch_match.group(1)) if ch_match else 1
                    if relay_inst:
                        if "全部断开" in action and hasattr(relay_inst, 'write_all_off'): success = relay_inst.write_all_off()
                        elif "闭合" in action and hasattr(relay_inst, 'close_channel'): success = relay_inst.close_channel(ch)
                        elif "断开" in action and hasattr(relay_inst, 'open_channel'): success = relay_inst.open_channel(ch)
                        else: success = False
                    else: success = False
                
                elif "ca550" in device:
                    if "设置输出" in action:
                        type_match = re.search(r'Type:([^\s/]+)', p_str)
                        val_match = re.search(r'Val:([\d.-]+)', p_str)
                        if type_match and val_match and hasattr(mgr.ca550, 'set_output'):
                            success = mgr.ca550.set_output(type_match.group(1), float(val_match.group(1)))
                    elif "开启" in action and hasattr(mgr.ca550, 'set_output_state'): success = mgr.ca550.set_output_state(True)
                    elif "关闭" in action and hasattr(mgr.ca550, 'set_output_state'): success = mgr.ca550.set_output_state(False)
                    else: success = False

            elif sub_step.type == SubStepType.READ_INSTRUMENT:
                device = params.get("device", "").lower()
                p_str = str(params.get("params", ""))
                
                if "simulator" in device:
                    if "电压" in p_str:
                        result_value = mgr.measure_voltage(self.channel_id, logger=hw_logger)
                        success = result_value >= 0
                    elif "电流" in p_str:
                        result_value = mgr.measure_current(self.channel_id, logger=hw_logger)
                        success = result_value > -500
                elif any(x in device for x in ["afe", "main power", "hv source", "power board"]):
                    pwr_inst = None
                    if "afe 1" in device or "1# afe" in device: pwr_inst = mgr.afe_power_1
                    elif "afe 2" in device or "2# afe" in device: pwr_inst = mgr.afe_pwr_standalone
                    elif "main" in device: pwr_inst = mgr.mainboard_power
                    elif "hv" in device: pwr_inst = mgr.hv_source
                    elif "power board" in device: pwr_inst = getattr(mgr, 'power_board_ru12', None)
                    
                    if pwr_inst:
                        if "电压" in p_str and hasattr(pwr_inst, 'measure_voltage'):
                            result_value = pwr_inst.measure_voltage()
                            success = result_value >= 0
                        elif "电流" in p_str and hasattr(pwr_inst, 'measure_current'):
                            result_value = pwr_inst.measure_current()
                            success = result_value >= 0
                    else:
                        success = False

                # 采样数据存库
                if success and self.db_manager and self.test_id != -1 and result_value is not None:
                    # 模拟读取电压电流
                    v = result_value if "电压" in p_str else -1
                    c = result_value if "电流" in p_str else -1
                    self.db_manager.log_detail(self.test_id, self.steps[self.current_step_index].name, v, c, "--")

            elif sub_step.type == SubStepType.CAN_SEND:
                success = mgr.can_bus.send_frame(params.get("id"), params.get("data"), logger=hw_logger)

            elif sub_step.type == SubStepType.CAN_INTERACT:
                res = mgr.can_bus.send_and_wait(params.get("send_id"), params.get("send_data"), params.get("wait_id"), logger=hw_logger)
                if res: result_value = str(res)
                else: success = False

            elif sub_step.type == SubStepType.WAIT:
                delay = int(self._parse_numeric(params.get("delay_ms", 1000)))
                QTimer.singleShot(delay, self.on_sub_step_complete)
                return

        except Exception as e:
            self.log_message.emit(self.channel_id, f"[!] 执行异常: {str(e)}")
            success = False

        # 结果判定收集
        if success and params.get("is_judgment") and result_value is not None:
            self.current_step_results.append(result_value)
            
        self.sub_step_finished.emit(self.channel_id, self.current_step_index, self.current_sub_step_index, 
                                   "PASS" if success else "FAIL", result_value)

        if success:
            self._retry_count = 0 # 重置重试计数
            self.on_sub_step_complete()
        else:
            # 失败处理逻辑
            if sub_step.fail_strategy == SubStepFailStrategy.RETRY_3 and self._retry_count < 3:
                self._retry_count += 1
                self.log_message.emit(self.channel_id, f"[!] 子工步执行失败，准备进行第 {self._retry_count} 次重试...")
                # 延迟一下再重试，避免瞬间连续失败
                QTimer.singleShot(500, lambda: self.execute_sub_step(sub_step))
                return
            
            self._retry_count = 0 # 最终失败或非重试模式，重置计数
            
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
        
        # 范围判定
        if is_pass and self.current_step_results:
            for val in self.current_step_results:
                f_val = self._parse_numeric(val)
                if step.min_limit is not None and f_val < float(step.min_limit): is_pass = False
                if step.max_limit is not None and f_val > float(step.max_limit): is_pass = False
        
        # 记录判定项结果到数据库
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
    """
    多通道并行测试引擎
    """
    def __init__(self, device_manager=None, db_manager=None):
        super().__init__()
        self.device_manager = device_manager
        self.db_manager = db_manager
        self.workers: Dict[int, ChannelWorker] = {}
        self.threads: Dict[int, QThread] = {}
        self.zombie_threads: List[QThread] = [] # 保持对正在退出的线程的引用，防止被过早垃圾回收
        self._lock = threading.RLock()

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
                
                # 映射子工步策略
                fail_strategy_str = sub.get('fail_strategy', "失败停止")
                fail_strategy = SubStepFailStrategy.STOP
                for fs in SubStepFailStrategy:
                    if fs.value == fail_strategy_str:
                        fail_strategy = fs
                        break
                        
                step.add_sub_step(SubStep(stype, sub.copy(), fail_strategy=fail_strategy))
            steps.append(step)

        with self._lock:
            if channel_id in self.workers:
                self.stop_channel_test(channel_id)

        thread = QThread()
        worker = ChannelWorker(channel_id, steps, self.device_manager, self.db_manager)
        worker.set_test_info(test_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        
        # 自动清理线程：强制使用 QueuedConnection，确保在主线程执行清理
        from PySide6.QtCore import Qt
        worker.test_finished.connect(lambda: self.stop_channel_test(channel_id), Qt.QueuedConnection)
        
        self.workers[channel_id] = worker
        self.threads[channel_id] = thread
        thread.start()

    def stop_channel_test(self, channel_id: int):
        with self._lock:
            if channel_id in self.threads:
                thread = self.threads[channel_id]
                worker = self.workers[channel_id]
                
                # 断开所有信号连接，防止过时的信号触发 UI 更新或重复清理
                try:
                    worker.test_finished.disconnect()
                except:
                    pass
                
                worker.stop()
                thread.quit()
                
                # 只有在主线程且不是线程本身时才等待，否则会导致死锁
                if QThread.currentThread() != thread:
                    # 使用较短的 wait，如果没停下来，就交给垃圾回收前抛弃
                    # 但为了防止 "Destroyed while running"，我们不立即 del
                    if not thread.wait(500):
                        print(f"[!] 通道 {channel_id} 线程未能在 500ms 内停止，将其设为游离状态")
                
                # 从活动字典移除，但让对象在 thread.finished 后自动销毁
                del self.workers[channel_id]
                del self.threads[channel_id]
                
                # 关键：将 thread 放入游离列表，保持 Python 引用，防止 garbage collection
                self.zombie_threads.append(thread)
                
                # 让线程在完全结束后自己清理引用，避免垃圾回收过早介入
                thread.finished.connect(thread.deleteLater)
                thread.finished.connect(lambda t=thread: self._cleanup_zombie(t))
                worker.deleteLater()

    def _cleanup_zombie(self, thread):
        with self._lock:
            if thread in self.zombie_threads:
                self.zombie_threads.remove(thread)

    def stop_all(self):
        """停止所有正在运行的测试通道"""
        with self._lock:
            ids = list(self.threads.keys())
            for cid in ids:
                self.stop_channel_test(cid)
            
            # 额外等待一段时间确保所有线程有时间退出
            import time
            start_time = time.time()
            while self.threads and time.time() - start_time < 2.0:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                time.sleep(0.1)
