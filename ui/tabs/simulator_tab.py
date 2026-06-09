from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QLineEdit, QPushButton, QGroupBox, QDoubleSpinBox, 
                                QGridLayout, QSpinBox, QComboBox, QTableWidget, 
                                QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, QThread, Signal

class ConnectWorker(QThread):
    finished = Signal(bool, str)
    def __init__(self, simulator):
        super().__init__()
        self.sim = simulator
    def run(self):
        res = self.sim.connect()
        self.finished.emit(res, "" if res else "连接失败")

class ReadAllWorker(QThread):
    """
    后台回读线程，避免阻塞 UI
    """
    progress = Signal(int, float) # ch, voltage
    finished = Signal()
    def __init__(self, simulator):
        super().__init__()
        self.sim = simulator
    def run(self):
        for i in range(1, 25):
            v = self.sim.measure_voltage(i)
            self.progress.emit(i, v)
        self.finished.emit()

class SimulatorTab(QWidget):
    def __init__(self, device_manager=None):
        super().__init__()
        self.mgr = device_manager
        self.worker = None
        self.read_all_worker = None
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        

        # 1. 网络连接配置
        net_group = QGroupBox("电池模拟器网络配置 (TCP/IP)")
        net_layout = QHBoxLayout()
        net_layout.addWidget(QLabel("设备:"))
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["设备 #1 (CH 1-24)", "设备 #2 (CH 25-48)"])
        self.combo_unit.currentIndexChanged.connect(self.update_net_info)
        net_layout.addWidget(self.combo_unit)
        
        net_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit("192.168.1.210")
        net_layout.addWidget(self.edit_ip)
        
        net_layout.addWidget(QLabel("端口:"))
        self.edit_port = QLineEdit("7000")
        self.edit_port.setFixedWidth(60)
        net_layout.addWidget(self.edit_port)
        
        self.btn_connect = QPushButton("连接该设备")
        self.btn_connect.setStyleSheet("background-color: #007BFF;")
        self.btn_connect.clicked.connect(self.connect_sim)
        net_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("断开连接")
        self.btn_disconnect.setStyleSheet("background-color: #6C757D;")
        self.btn_disconnect.clicked.connect(self.disconnect_sim)
        self.btn_disconnect.setEnabled(False)
        net_layout.addWidget(self.btn_disconnect)
        net_group.setLayout(net_layout)
        layout.addWidget(net_group)
        
        # 2. 中间部分：左侧手动控制，右侧全通道回读表
        mid_layout = QHBoxLayout()
        
        # 2.1 左侧手动控制
        left_ctrl_layout = QVBoxLayout()
        single_group = QGroupBox("单通道调试 (1-24)")
        single_layout = QGridLayout()
        single_layout.addWidget(QLabel("本地通道:"), 0, 0)
        self.spin_ch = QSpinBox()
        self.spin_ch.setRange(1, 24)
        single_layout.addWidget(self.spin_ch, 0, 1)
        
        single_layout.addWidget(QLabel("设置电压(V):"), 1, 0)
        self.spin_volt = QDoubleSpinBox()
        self.spin_volt.setRange(0, 15)
        self.spin_volt.setDecimals(3)
        self.spin_volt.setValue(3.700)
        single_layout.addWidget(self.spin_volt, 1, 1)
        
        self.btn_set_volt = QPushButton("执行设置")
        self.btn_set_volt.clicked.connect(self.set_sim_volt)
        single_layout.addWidget(self.btn_set_volt, 1, 2)
        
        self.btn_on = QPushButton("开启输出")
        self.btn_on.setStyleSheet("background-color: #218838;")
        self.btn_on.clicked.connect(lambda: self.control_output(True))
        single_layout.addWidget(self.btn_on, 2, 0)
        
        self.btn_off = QPushButton("关闭输出")
        self.btn_off.setStyleSheet("background-color: #C82333;")
        self.btn_off.clicked.connect(lambda: self.control_output(False))
        single_layout.addWidget(self.btn_off, 2, 1)
        
        self.btn_read = QPushButton("单路回读")
        self.btn_read.clicked.connect(self.read_sim_volt)
        single_layout.addWidget(self.btn_read, 2, 2)
        single_group.setLayout(single_layout)
        left_ctrl_layout.addWidget(single_group)
        
        batch_group = QGroupBox("本台机批量操作")
        batch_layout = QVBoxLayout()
        self.btn_all_on = QPushButton("一键开启本台")
        self.btn_all_on.setStyleSheet("background-color: #17A2B8;")
        self.btn_all_on.clicked.connect(lambda: self.batch_control(True))
        self.btn_all_off = QPushButton("一键关闭本台")
        self.btn_all_off.setStyleSheet("background-color: #6C757D;")
        self.btn_all_off.clicked.connect(lambda: self.batch_control(False))
        batch_layout.addWidget(self.btn_all_on)
        batch_layout.addWidget(self.btn_all_off)
        batch_group.setLayout(batch_layout)
        left_ctrl_layout.addWidget(batch_group)
        mid_layout.addLayout(left_ctrl_layout, 1)
        
        # 2.2 右侧全通道回读表
        table_group = QGroupBox("本台机 24 通道实时状态回读")
        table_layout = QVBoxLayout()
        self.table = QTableWidget(24, 2)
        self.table.setHorizontalHeaderLabels(["通道", "设定电压 (V)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i in range(24):
            self.table.setItem(i, 0, QTableWidgetItem(f"CH {i+1}"))
            self.table.setItem(i, 1, QTableWidgetItem("--.----"))
        table_layout.addWidget(self.table)
        
        self.btn_read_all = QPushButton("🔄 一键刷新本台所有通道电压")
        self.btn_read_all.setFixedHeight(40)
        self.btn_read_all.setStyleSheet("background-color: #007BFF; font-weight: bold;")
        self.btn_read_all.clicked.connect(self.read_all_channels)
        table_layout.addWidget(self.btn_read_all)
        table_group.setLayout(table_layout)
        mid_layout.addWidget(table_group, 2)
        
        layout.addLayout(mid_layout)

        # 3. 本台设备批量同步 (单设备全通道)
        global_group = QGroupBox("本台设备批量同步 (当前选中设备的所有通道)")
        global_group.setStyleSheet("QGroupBox { border: 2px solid #FFC107; padding-top: 15px; }")
        global_layout = QGridLayout()
        global_layout.addWidget(QLabel("本台电压设定 (V):"), 0, 0)
        self.spin_global_volt = QDoubleSpinBox()
        self.spin_global_volt.setRange(0, 15)
        self.spin_global_volt.setDecimals(3)
        self.spin_global_volt.setValue(3.800)
        global_layout.addWidget(self.spin_global_volt, 0, 1)
        self.btn_global_set = QPushButton("❗ 本台同步设置")
        self.btn_global_set.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")
        self.btn_global_set.clicked.connect(self.global_broadcast_volt)
        global_layout.addWidget(self.btn_global_set, 0, 2)
        self.btn_global_on = QPushButton("❗ 本台同步开启输出")
        self.btn_global_on.setStyleSheet("background-color: #FD7E14; font-weight: bold;")
        self.btn_global_on.clicked.connect(lambda: self.global_broadcast_output(True))
        global_layout.addWidget(self.btn_global_on, 1, 0, 1, 2)
        self.btn_global_off = QPushButton("❗ 本台同步关闭输出")
        self.btn_global_off.setStyleSheet("background-color: #6C757D; font-weight: bold;")
        self.btn_global_off.clicked.connect(lambda: self.global_broadcast_output(False))
        global_layout.addWidget(self.btn_global_off, 1, 2)
        global_group.setLayout(global_layout)
        layout.addWidget(global_group)

        self.btn_one_key = QPushButton("🚀 一键本台：设定电压 + 开启输出")
        self.btn_one_key.setFixedHeight(50)
        self.btn_one_key.setStyleSheet("background-color: #6F42C1; color: white; font-size: 18px; font-weight: bold; border-radius: 8px;")
        self.btn_one_key.clicked.connect(self.one_key_global_action)
        layout.addWidget(self.btn_one_key)
        
        layout.addStretch()

    def update_net_info(self, index):
        if self.mgr and index < len(self.mgr.simulators):
            sim = self.mgr.simulators[index]
            self.edit_ip.setText(sim.ip)
            self.edit_port.setText(str(sim.port))
            is_conn = sim.is_connected

            self.btn_connect.setEnabled(not is_conn)
            self.btn_disconnect.setEnabled(is_conn)
            if is_conn:
                self.btn_connect.setText("已连接")
                self.btn_connect.setStyleSheet("background-color: #28A745;")
            else:
                self.btn_connect.setText("连接该设备")
                self.btn_connect.setStyleSheet("background-color: #007BFF;")

    def connect_sim(self):
        index = self.combo_unit.currentIndex()
        if not self.mgr: return
        sim = self.mgr.simulators[index]
        sim.ip = self.edit_ip.text()
        try:
            sim.port = int(self.edit_port.text())
        except:
            sim.port = 7000
            
        self.btn_connect.setText("正在连接...")

        self.btn_connect.setEnabled(False)
        self.worker = ConnectWorker(sim)
        self.worker.finished.connect(self.on_connect_finished)
        self.worker.start()

    def disconnect_sim(self):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            self.mgr.simulators[index].disconnect()
            self.update_net_info(index)

    def on_connect_finished(self, success, error_msg):
        self.update_net_info(self.combo_unit.currentIndex())
        if success: self._notify_status("连接成功")
        else: self._notify_status("连接失败")

    def set_sim_volt(self):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            ch, volt = self.spin_ch.value(), self.spin_volt.value()
            res = self.mgr.simulators[index].set_voltage(ch, volt)
            self._notify_status(f"通道{ch} 设压 {'成功' if res else '失败'}")

    def control_output(self, state):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            ch = self.spin_ch.value()
            res = self.mgr.simulators[index].output_control(ch, state)
            self._notify_status(f"通道{ch} {'开启' if state else '关闭'}输出 {'成功' if res else '失败'}")

    def read_sim_volt(self):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            ch = self.spin_ch.value()
            v = self.mgr.simulators[index].measure_voltage(ch)
            if v >= 0:
                self.table.setItem(ch-1, 1, QTableWidgetItem(f"{v:.4f}"))
                self._notify_status(f"通道{ch} 回读成功: {v:.4f}V")
            else:
                self._notify_status(f"通道{ch} 回读超时")

    def read_all_channels(self):
        """异步回读当前物理设备的所有 18 个通道"""
        index = self.combo_unit.currentIndex()
        if not self.mgr: return
        sim = self.mgr.simulators[index]
        if not sim.is_connected:
            self._notify_status("请先连接设备！")
            return
        
        self.btn_read_all.setText("正在扫描 24 个通道...")
        self.btn_read_all.setEnabled(False)
        
        self.read_all_worker = ReadAllWorker(sim)
        self.read_all_worker.progress.connect(self.on_read_all_progress)
        self.read_all_worker.finished.connect(self.on_read_all_finished)
        self.read_all_worker.start()

    def on_read_all_progress(self, ch, v):
        if v >= 0:
            self.table.setItem(ch-1, 1, QTableWidgetItem(f"{v:.4f}"))
        else:
            self.table.setItem(ch-1, 1, QTableWidgetItem("Error"))

    def on_read_all_finished(self):
        self.btn_read_all.setText("🔄 一键刷新本台所有通道电压")
        self.btn_read_all.setEnabled(True)
        index = self.combo_unit.currentIndex()
        self._notify_status(f"设备#{index+1} 所有通道刷新完成")

    def batch_control(self, state):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            res = self.mgr.simulators[index].output_control(0, state)
            self._notify_status(f"本台批量{'开启' if state else '关闭'} {'成功' if res else '失败'}")

    def global_broadcast_volt(self):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            v = self.spin_global_volt.value()
            res = self.mgr.simulators[index].set_voltage(0, v)
            self._notify_status(f"本台批量设压 {'成功' if res else '失败'}")

    def global_broadcast_output(self, state):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            res = self.mgr.simulators[index].output_control(0, state)
            self._notify_status(f"本台批量{'开启' if state else '关闭'}输出 {'成功' if res else '失败'}")

    def one_key_global_action(self):
        index = self.combo_unit.currentIndex()
        if self.mgr:
            v = self.spin_global_volt.value()
            self.btn_one_key.setText("⏳ 正在同步执行...")
            self.btn_one_key.setEnabled(False)
            sim = self.mgr.simulators[index]
            sim.set_voltage(0, v)
            QThread.msleep(150)
            res = sim.output_control(0, True)
            self.btn_one_key.setText("🚀 一键本台：设定电压 + 开启输出")
            self.btn_one_key.setEnabled(True)
            self._notify_status(f"本台一键操作{'成功' if res else '失败'}")


    def _notify_status(self, msg):
        import datetime
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [Simulator] {msg}")

        p = self.parent()
        while p:
            if hasattr(p, "show_status"):
                p.show_status(msg)
                break
            p = p.parent()
