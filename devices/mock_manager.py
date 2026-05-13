import random
import time

class MockDeviceManager:
    """
    虚拟设备管理器 - 用于脱机仿真 (Dry Run)
    完全模拟 DeviceManager 的接口，但不进行实际硬件通讯。
    """
    def __init__(self):
        self.is_virtual = True
        self.afe_power_1 = type('MockPower', (), {'set_voltage': lambda *a, **k: True, 'output_control': lambda *a, **k: True, 'read_voltage': lambda *a, **k: 12.0, 'read_current': lambda *a, **k: 1.0, 'is_connected': True})()
        self.mainboard_power = type('MockPower', (), {'set_voltage': lambda *a, **k: True, 'output_control': lambda *a, **k: True, 'read_voltage': lambda *a, **k: 12.0, 'read_current': lambda *a, **k: 1.0, 'is_connected': True})()
        self.hv_source = type('MockPower', (), {'set_voltage': lambda *a, **k: True, 'output_control': lambda *a, **k: True, 'read_voltage': lambda *a, **k: 12.0, 'read_current': lambda *a, **k: 1.0, 'is_connected': True})()
        self.aging_board = type('MockAging', (), {'set_relay_by_name': lambda *a, **k: True, 'all_off': lambda *a, **k: True})()
        self.easy320 = type('MockEasy', (), {'write_relay': lambda *a, **k: True, 'read_relays': lambda *a, **k: [True]*32})()
        self.ca550 = type('MockCA550', (), {'set_source_func': lambda *a, **k: True, 'set_source_data': lambda *a, **k: True, 'set_source_output': lambda *a, **k: True, 'read_measure_data': lambda *a, **k: "12.345"})()
        
    def set_voltage(self, global_ch, voltage, logger=None):
        if logger: logger(f"[仿真] 设置通道 {global_ch} 电压为 {voltage}V")
        return True

    def set_current(self, global_ch, current, logger=None):
        if logger: logger(f"[仿真] 设置通道 {global_ch} 电流为 {current}A")
        return True

    def output_control(self, global_ch, state, logger=None):
        if logger: logger(f"[仿真] 通道 {global_ch} 输出 {'开启' if state else '关闭'}")
        return True

    def measure_voltage(self, global_ch, logger=None):
        val = 12.0 + random.uniform(-0.1, 0.1)
        if logger: logger(f"[仿真] 读取通道 {global_ch} 电压: {val:.3f}V")
        return val

    def measure_current(self, global_ch, logger=None):
        val = 1.5 + random.uniform(-0.05, 0.05)
        if logger: logger(f"[仿真] 读取通道 {global_ch} 电流: {val:.3f}A")
        return val

    def broadcast_output(self, state):
        print(f"[仿真] 全局输出控制: {state}")
        return True

    def init_all_devices(self):
        print("[仿真] 正在初始化虚拟硬件...")
        return True

    def disconnect_all(self):
        print("[仿真] 正在断开虚拟硬件...")
