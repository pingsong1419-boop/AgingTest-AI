from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QDoubleSpinBox, 
                               QGridLayout)
from PySide6.QtCore import Qt, QTimer

class HVSourceTab(QWidget):
    def __init__(self, device_manager=None):
        super().__init__()
        self.mgr = device_manager
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 网络配置
        config_group = QGroupBox("NGI N3618 高压源配置 (TCP/IP)")
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit("192.168.1.190")
        config_layout.addWidget(self.edit_ip)
        
        config_layout.addWidget(QLabel("端口:"))
        self.edit_port = QLineEdit("7000")

        self.edit_port.setFixedWidth(60)
        config_layout.addWidget(self.edit_port)
        
        self.btn_connect = QPushButton("连接设备")

        self.btn_connect.setStyleSheet("background-color: #007BFF;")
        self.btn_connect.clicked.connect(self.connect_hv)
        config_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("断开连接")
        self.btn_disconnect.setStyleSheet("background-color: #6C757D;")
        self.btn_disconnect.clicked.connect(self.disconnect_hv)
        self.btn_disconnect.setEnabled(False)
        config_layout.addWidget(self.btn_disconnect)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 2. 控制面板
        ctrl_group = QGroupBox("高压输出控制")
        ctrl_layout = QGridLayout()
        
        ctrl_layout.addWidget(QLabel("设定电压 (V):"), 0, 0)
        self.spin_volt = QDoubleSpinBox()
        self.spin_volt.setRange(0, 1200)
        self.spin_volt.setDecimals(2)
        self.spin_volt.setValue(0.00)
        ctrl_layout.addWidget(self.spin_volt, 0, 1)

        
        self.btn_set_volt = QPushButton("设置电压")
        self.btn_set_volt.clicked.connect(self.set_hv_volt)
        ctrl_layout.addWidget(self.btn_set_volt, 0, 2)
        
        ctrl_layout.addWidget(QLabel("设定电流 (A):"), 1, 0)
        self.spin_curr = QDoubleSpinBox()
        self.spin_curr.setRange(0, 50)
        self.spin_curr.setDecimals(3)
        self.spin_curr.setValue(1.000)
        ctrl_layout.addWidget(self.spin_curr, 1, 1)
        
        self.btn_set_curr = QPushButton("设置电流")
        self.btn_set_curr.clicked.connect(self.set_hv_curr)
        ctrl_layout.addWidget(self.btn_set_curr, 1, 2)
        
        self.btn_on = QPushButton("🔥 开启高压输出")
        self.btn_on.setFixedHeight(40)
        self.btn_on.setStyleSheet("background-color: #C82333; font-weight: bold;")
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
        read_group = QGroupBox("实时回读数据")
        read_layout = QGridLayout()
        
        read_layout.addWidget(QLabel("实时电压 (V):"), 0, 0)
        self.lbl_volt = QLabel("0.00")
        self.lbl_volt.setStyleSheet("font-size: 32px; color: #00E5FF; font-weight: bold;")
        read_layout.addWidget(self.lbl_volt, 0, 1)
        
        read_layout.addWidget(QLabel("实时电流 (A):"), 1, 0)
        self.lbl_curr = QLabel("0.000")
        self.lbl_curr.setStyleSheet("font-size: 32px; color: #76FF03; font-weight: bold;")
        read_layout.addWidget(self.lbl_curr, 1, 1)
        
        read_group.setLayout(read_layout)
        layout.addWidget(read_group)
        
        layout.addStretch()
        
        # 定时器用于回读数据
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_readings)
        self.timer.setInterval(1000)

    def connect_hv(self):
        if self.mgr:
            self.mgr.hv_source.ip = self.edit_ip.text()
            try:
                self.mgr.hv_source.port = int(self.edit_port.text())
            except:
                self.mgr.hv_source.port = 5025
                
            if self.mgr.hv_source.connect():

                self.btn_connect.setText("已连接")
                self.btn_connect.setStyleSheet("background-color: #28A745;")
                self.btn_connect.setEnabled(False)
                self.btn_disconnect.setEnabled(True)
                self.timer.start()
                self._notify_status("NGI 高压源连接成功")

    def disconnect_hv(self):
        if self.mgr:
            self.mgr.hv_source.disconnect()
            self.btn_connect.setText("连接设备")
            self.btn_connect.setStyleSheet("background-color: #007BFF;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.timer.stop()
            self._notify_status("NGI 高压源已断开")

    def set_hv_volt(self):
        if self.mgr:
            v = self.spin_volt.value()
            self.btn_set_volt.setText("⏳ 执行中...")
            self.btn_set_volt.setEnabled(False)
            
            res = self.mgr.hv_source.set_voltage(v)
            
            if res:
                self.btn_set_volt.setText("✅ 成功")
                self.btn_set_volt.setStyleSheet("background-color: #28A745; color: white;")
            else:
                self.btn_set_volt.setText("❌ 失败")
                self.btn_set_volt.setStyleSheet("background-color: #C82333; color: white;")
            
            self._notify_status(f"NGI 高压源：设压 {v}V {'成功' if res else '失败'}")
            QTimer.singleShot(2000, lambda: self._reset_btn(self.btn_set_volt, "设置电压", ""))

    def set_hv_curr(self):
        if self.mgr:
            c = self.spin_curr.value()
            self.btn_set_curr.setText("⏳ 执行中...")
            self.btn_set_curr.setEnabled(False)
            
            res = self.mgr.hv_source.set_current(c)
            
            if res:
                self.btn_set_curr.setText("✅ 成功")
                self.btn_set_curr.setStyleSheet("background-color: #28A745; color: white;")
            else:
                self.btn_set_curr.setText("❌ 失败")
                self.btn_set_curr.setStyleSheet("background-color: #C82333; color: white;")
                
            self._notify_status(f"NGI 高压源：设流 {c}A {'成功' if res else '失败'}")
            QTimer.singleShot(2000, lambda: self._reset_btn(self.btn_set_curr, "设置电流", ""))

    def control_output(self, state):
        if self.mgr:
            target_btn = self.btn_on if state else self.btn_off
            original_text = target_btn.text()
            original_style = target_btn.styleSheet()
            
            target_btn.setText("⏳ 执行中...")
            res = self.mgr.hv_source.output_control(state)
            
            if res:
                target_btn.setText("✅ 成功")
                target_btn.setStyleSheet("background-color: #28A745; color: white;")
            else:
                target_btn.setText("❌ 失败")
                target_btn.setStyleSheet("background-color: #C82333; color: white;")
            
            action = "开启" if state else "关闭"
            self._notify_status(f"NGI 高压源：{action}输出 {'成功' if res else '失败'}")
            QTimer.singleShot(2000, lambda: self._reset_btn(target_btn, original_text, original_style))

    def _reset_btn(self, btn, text, style):
        btn.setText(text)
        btn.setEnabled(True)
        btn.setStyleSheet(style)


    def update_readings(self):
        if self.mgr and self.mgr.hv_source.is_connected:
            v = self.mgr.hv_source.measure_voltage()
            c = self.mgr.hv_source.measure_current()
            if v >= 0: self.lbl_volt.setText(f"{v:.2f}")
            if c >= 0: self.lbl_curr.setText(f"{c:.3f}")

    def _notify_status(self, msg):
        p = self.parent()
        while p:
            if hasattr(p, "show_status"):
                p.show_status(msg)
                break
            p = p.parent()
