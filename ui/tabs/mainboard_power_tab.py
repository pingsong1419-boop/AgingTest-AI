from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QDoubleSpinBox, 
                               QGridLayout)
from PySide6.QtCore import Qt, QTimer, QThread, Signal

class ConnectWorker(QThread):
    finished = Signal(bool)
    def __init__(self, device):
        super().__init__()
        self.device = device
    def run(self):
        res = self.device.connect()
        self.finished.emit(res)

class ControlWorker(QThread):
    finished = Signal(bool, str, object)
    def __init__(self, device, action, *args):
        super().__init__()
        self.device = device
        self.action = action
        self.args = args
    def run(self):
        try:
            func = getattr(self.device, self.action)
            res = func(*self.args)
            self.finished.emit(res, self.action, self.args)
        except:
            self.finished.emit(False, self.action, self.args)

class ReadWorker(QThread):
    finished = Signal(float, float)
    def __init__(self, device):
        super().__init__()
        self.device = device
    def run(self):
        v = self.device.measure_voltage()
        c = self.device.measure_current()
        self.finished.emit(v, c)

class MainboardPowerTab(QWidget):
    """
    主机供电电源控制页 (RU60 30V200A)
    复用 AFEPowerRU36 驱动逻辑
    """
    def __init__(self, device_manager=None):
        super().__init__()
        self.mgr = device_manager
        self.conn_worker = None
        self.ctrl_worker = None
        self.read_worker = None
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 网络配置
        config_group = QGroupBox("主机供电电源配置 (RU60 30V200A)")
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit("192.168.1.201")
        config_layout.addWidget(self.edit_ip)
        
        config_layout.addWidget(QLabel("端口:"))
        self.edit_port = QLineEdit("2000")
        self.edit_port.setFixedWidth(60)
        config_layout.addWidget(self.edit_port)
        
        self.btn_connect = QPushButton("连接设备")
        self.btn_connect.setStyleSheet("background-color: #007BFF;")
        self.btn_connect.clicked.connect(self.connect_device)
        config_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("断开连接")
        self.btn_disconnect.setStyleSheet("background-color: #6C757D;")
        self.btn_disconnect.clicked.connect(self.disconnect_device)
        self.btn_disconnect.setEnabled(False)
        config_layout.addWidget(self.btn_disconnect)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 2. 控制面板
        ctrl_group = QGroupBox("电源输出控制")
        ctrl_layout = QGridLayout()
        
        ctrl_layout.addWidget(QLabel("设定电压 (V):"), 0, 0)
        self.spin_volt = QDoubleSpinBox()
        self.spin_volt.setRange(0, 30)
        self.spin_volt.setDecimals(2)
        self.spin_volt.setValue(0.00)
        ctrl_layout.addWidget(self.spin_volt, 0, 1)
        
        self.btn_set_volt = QPushButton("设置电压")
        self.btn_set_volt.clicked.connect(self.set_volt)
        ctrl_layout.addWidget(self.btn_set_volt, 0, 2)
        
        ctrl_layout.addWidget(QLabel("设定电流 (A):"), 1, 0)
        self.spin_curr = QDoubleSpinBox()
        self.spin_curr.setRange(0, 200)
        self.spin_curr.setDecimals(2)
        self.spin_curr.setValue(10.00)
        ctrl_layout.addWidget(self.spin_curr, 1, 1)
        
        self.btn_set_curr = QPushButton("设置电流")
        self.btn_set_curr.clicked.connect(self.set_curr)
        ctrl_layout.addWidget(self.btn_set_curr, 1, 2)
        
        self.btn_on = QPushButton("开启电源输出")
        self.btn_on.setFixedHeight(40)
        self.btn_on.setStyleSheet("background-color: #28A745; font-weight: bold;")
        self.btn_on.clicked.connect(lambda: self.control_output(True))
        ctrl_layout.addWidget(self.btn_on, 2, 0, 1, 2)
        
        self.btn_off = QPushButton("关闭输出")
        self.btn_off.setFixedHeight(40)
        self.btn_off.setStyleSheet("background-color: #6C757D;")
        self.btn_off.clicked.connect(lambda: self.control_output(False))
        ctrl_layout.addWidget(self.btn_off, 2, 2)
        
        ctrl_group.setLayout(ctrl_layout)
        layout.addWidget(ctrl_group)
        
        # 3. 实时回读
        read_group = QGroupBox("实时监控数据")
        read_layout = QGridLayout()
        read_layout.addWidget(QLabel("实时电压 (V):"), 0, 0)
        self.lbl_volt = QLabel("0.00")
        self.lbl_volt.setStyleSheet("font-size: 32px; color: #00E5FF; font-weight: bold;")
        read_layout.addWidget(self.lbl_volt, 0, 1)
        read_layout.addWidget(QLabel("实时电流 (A):"), 1, 0)
        self.lbl_curr = QLabel("0.00")
        self.lbl_curr.setStyleSheet("font-size: 32px; color: #76FF03; font-weight: bold;")
        read_layout.addWidget(self.lbl_curr, 1, 1)
        read_group.setLayout(read_layout)
        layout.addWidget(read_group)
        
        layout.addStretch()
        self.timer = QTimer()
        self.timer.timeout.connect(self.start_reading)
        self.timer.setInterval(1000)

    def connect_device(self):
        if not self.mgr: return
        self.mgr.mainboard_power.ip = self.edit_ip.text()
        try: self.mgr.mainboard_power.port = int(self.edit_port.text())
        except: self.mgr.mainboard_power.port = 2000
        
        self.btn_connect.setText("⏳ 正在连接...")
        self.btn_connect.setEnabled(False)
        self.conn_worker = ConnectWorker(self.mgr.mainboard_power)
        self.conn_worker.finished.connect(self.on_connect_finished)
        self.conn_worker.start()

    def on_connect_finished(self, success):
        if success:
            self.btn_connect.setText("已连接")
            self.btn_connect.setStyleSheet("background-color: #28A745;")
            self.btn_disconnect.setEnabled(True)
            self.timer.start()
        else:
            self.btn_connect.setText("连接失败")
            self.btn_connect.setStyleSheet("background-color: #C82333;")
            self.btn_connect.setEnabled(True)

    def disconnect_device(self):
        if self.mgr:
            self.timer.stop()
            self.mgr.mainboard_power.disconnect()
            self.btn_connect.setText("连接设备")
            self.btn_connect.setStyleSheet("background-color: #007BFF;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def start_reading(self):
        if self.mgr and self.mgr.mainboard_power.is_connected:
            if hasattr(self, "_reading_in_progress") and self._reading_in_progress:
                return
            
            self._reading_in_progress = True
            self.read_worker = ReadWorker(self.mgr.mainboard_power)
            self.read_worker.finished.connect(self.on_read_finished)
            self.read_worker.start()

    def on_read_finished(self, v, c):
        self._reading_in_progress = False
        if v >= 0: 
            self.lbl_volt.setText(f"{v:.2f}")
        else:
            self.lbl_volt.setText("---")
            
        if c >= 0: 
            self.lbl_curr.setText(f"{c:.2f}")
        else:
            self.lbl_curr.setText("---")

    def set_volt(self):
        self._run_control("set_voltage", self.spin_volt.value(), self.btn_set_volt, "设置电压")

    def set_curr(self):
        self._run_control("set_current", self.spin_curr.value(), self.btn_set_curr, "设置电流")

    def control_output(self, state):
        btn = self.btn_on if state else self.btn_off
        self._run_control("output_control", state, btn, "开启电源输出" if state else "关闭输出")

    def _run_control(self, action, value, btn, original_text):
        if not self.mgr or not self.mgr.mainboard_power.is_connected: return
        btn.setText("⏳ 执行中...")
        btn.setEnabled(False)
        self.ctrl_worker = ControlWorker(self.mgr.mainboard_power, action, value)
        self.ctrl_worker.finished.connect(lambda res, act, args: self.on_control_finished(res, btn, original_text))
        self.ctrl_worker.start()

    def on_control_finished(self, success, btn, original_text):
        btn.setEnabled(True)
        if success:
            btn.setText("✅ 成功")
            btn.setStyleSheet("background-color: #28A745; color: white;")
        else:
            btn.setText("❌ 失败")
            btn.setStyleSheet("background-color: #C82333; color: white;")
        QTimer.singleShot(2000, lambda: self._reset_btn(btn, original_text))

    def _reset_btn(self, btn, text):
        btn.setText(text)
        if "开启" in text: btn.setStyleSheet("background-color: #28A745; font-weight: bold;")
        elif "关闭" in text: btn.setStyleSheet("background-color: #6C757D;")
        else: btn.setStyleSheet("")
