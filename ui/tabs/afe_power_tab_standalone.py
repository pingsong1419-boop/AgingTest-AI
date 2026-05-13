import sys
import time
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QDoubleSpinBox, 
                               QGridLayout, QMessageBox)
from PySide6.QtCore import Qt, QTimer

# 导入之前提取的独立驱动
from devices.afe_power_driver import AFEPowerController

class AFEPowerStandaloneTab(QWidget):
    def __init__(self, driver):
        super().__init__()
        self.setWindowTitle("2# AFE 供电电源调试界面 (RU12-10012)")
        self.resize(600, 500)
        
        # 使用传入的驱动实例
        self.pwr = driver
        self._init_ui()
        
        # 定时更新回读信息
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(1000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 网络配置
        config_group = QGroupBox("网络配置 (Modbus TCP)")
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit("192.168.1.203")
        config_layout.addWidget(self.edit_ip)
        
        config_layout.addWidget(QLabel("端口:"))
        self.edit_port = QLineEdit("10001")
        self.edit_port.setFixedWidth(60)
        config_layout.addWidget(self.edit_port)
        
        btn_connect = QPushButton("连接设备")
        btn_connect.setStyleSheet("background-color: #007BFF; color: white;")
        btn_connect.clicked.connect(self.connect_device)
        config_layout.addWidget(btn_connect)
        
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.setStyleSheet("background-color: #6C757D; color: white;")
        btn_disconnect.clicked.connect(self.disconnect_device)
        config_layout.addWidget(btn_disconnect)
        
        self.lbl_status = QLabel("●")
        self.lbl_status.setStyleSheet("color: red; font-size: 20px;")
        config_layout.addWidget(self.lbl_status)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 2. 控制面板
        ctrl_group = QGroupBox("电源输出控制")
        ctrl_layout = QGridLayout()
        
        ctrl_layout.addWidget(QLabel("设定电压 (V):"), 0, 0)
        self.spin_volt = QDoubleSpinBox()
        self.spin_volt.setRange(0, 100)
        self.spin_volt.setDecimals(2)
        ctrl_layout.addWidget(self.spin_volt, 0, 1)
        
        btn_set_volt = QPushButton("下发电压")
        btn_set_volt.clicked.connect(lambda: self.pwr.set_voltage(self.spin_volt.value()))
        ctrl_layout.addWidget(btn_set_volt, 0, 2)
        
        ctrl_layout.addWidget(QLabel("设定电流 (A):"), 1, 0)
        self.spin_curr = QDoubleSpinBox()
        self.spin_curr.setRange(0, 12)
        self.spin_curr.setDecimals(3)
        ctrl_layout.addWidget(self.spin_curr, 1, 1)
        
        btn_set_curr = QPushButton("下发电流")
        btn_set_curr.clicked.connect(lambda: self.pwr.set_current(self.spin_curr.value()))
        ctrl_layout.addWidget(btn_set_curr, 1, 2)
        
        self.btn_on = QPushButton("开启输出")
        self.btn_on.setFixedHeight(40)
        self.btn_on.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_on.clicked.connect(lambda: self.pwr.output_control(True))
        ctrl_layout.addWidget(self.btn_on, 2, 0, 1, 2)
        
        self.btn_off = QPushButton("关闭输出")
        self.btn_off.setFixedHeight(40)
        self.btn_off.clicked.connect(lambda: self.pwr.output_control(False))
        ctrl_layout.addWidget(self.btn_off, 2, 2)
        
        ctrl_group.setLayout(ctrl_layout)
        layout.addWidget(ctrl_group)
        
        # 3. 实时回读
        read_group = QGroupBox("实时回读数据")
        read_layout = QGridLayout()
        read_layout.addWidget(QLabel("实时电压:"), 0, 0)
        self.lbl_volt = QLabel("0.00 V")
        self.lbl_volt.setStyleSheet("font-size: 30px; color: #00E5FF; font-weight: bold;")
        read_layout.addWidget(self.lbl_volt, 0, 1)
        
        read_layout.addWidget(QLabel("实时电流:"), 1, 0)
        self.lbl_curr = QLabel("0.00 A")
        self.lbl_curr.setStyleSheet("font-size: 30px; color: #76FF03; font-weight: bold;")
        read_layout.addWidget(self.lbl_curr, 1, 1)
        read_group.setLayout(read_layout)
        layout.addWidget(read_group)
        
        layout.addStretch()

    def connect_device(self):
        self.pwr.ip = self.edit_ip.text().strip()
        try: self.pwr.port = int(self.edit_port.text().strip())
        except: pass
        
        if self.pwr.connect():
            self.lbl_status.setStyleSheet("color: green; font-size: 20px;")
        else:
            QMessageBox.critical(self, "错误", "无法连接到电源。")

    def disconnect_device(self):
        if hasattr(self.pwr, 'disconnect'):
            self.pwr.disconnect()
        self.lbl_status.setStyleSheet("color: red; font-size: 20px;")

    def update_readings(self):
        if self.pwr.is_connected:
            v = self.pwr.measure_voltage()
            i = self.pwr.measure_current()
            if v >= 0: self.lbl_volt.setText(f"{v:.2f} V")
            if i >= 0: self.lbl_curr.setText(f"{i:.2f} A")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AFEPowerStandaloneTab()
    window.show()
    sys.exit(app.exec())
