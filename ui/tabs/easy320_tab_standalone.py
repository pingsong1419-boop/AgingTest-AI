import sys
import time
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QPushButton, QLabel, QGroupBox, QLineEdit, QScrollArea, QFrame, QMessageBox)
from PySide6.QtCore import Qt, QTimer

# 导入之前提取的独立驱动
from devices.easy320_driver import Easy320Controller

class Easy320StandaloneTab(QWidget):
    def __init__(self, driver):
        super().__init__()
        self.setWindowTitle("Easy320 继电器控制测试")
        self.resize(1000, 600)
        
        # 使用传入的驱动实例
        self.easy320 = driver
        self.relay_buttons = []
        
        self._init_ui()
        
        # 定时同步状态 (5秒一次)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync_status)
        self.timer.start(5000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # --- 1. 顶部通讯配置 ---
        group_comm = QGroupBox("Easy320 继电器控制 (Modbus TCP)")
        comm_layout = QHBoxLayout()
        
        comm_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit(self.easy320.ip)
        self.edit_ip.setFixedWidth(150)
        comm_layout.addWidget(self.edit_ip)
        
        comm_layout.addWidget(QLabel("端口:"))
        self.edit_port = QLineEdit(str(self.easy320.port))
        self.edit_port.setFixedWidth(60)
        comm_layout.addWidget(self.edit_port)
        
        btn_connect = QPushButton("连接设备")
        btn_connect.setFixedSize(100, 32)
        btn_connect.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        btn_connect.clicked.connect(self.connect_device)
        
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.setFixedSize(100, 32)
        btn_disconnect.clicked.connect(self.disconnect_device)
        
        comm_layout.addWidget(btn_connect)
        comm_layout.addWidget(btn_disconnect)
        comm_layout.addStretch()
        
        self.lbl_status = QLabel("状态: 未连接")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        comm_layout.addWidget(self.lbl_status)
        
        group_comm.setLayout(comm_layout)
        main_layout.addWidget(group_comm)

        # --- 2. 继电器控制面板 ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        panel_widget = QWidget()
        scroll.setWidget(panel_widget)
        panel_layout = QVBoxLayout(panel_widget)
        
        group_relays = QGroupBox("继电器状态控制")
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        for i in range(32):
            btn = QPushButton(f"CH-{i+1:02d}\n(OFF)")
            btn.setCheckable(True)
            btn.setFixedSize(100, 50)
            btn.setStyleSheet("background-color: #f0f0f0; color: #333;")
            btn.clicked.connect(lambda checked, idx=i: self.on_relay_clicked(idx, checked))
            grid_layout.addWidget(btn, i // 8, i % 8)
            self.relay_buttons.append(btn)
            
        group_relays.setLayout(grid_layout)
        panel_layout.addWidget(group_relays)
        
        # --- 3. 批量操作 ---
        batch_layout = QHBoxLayout()
        btn_all_on = QPushButton("全部开启")
        btn_all_on.clicked.connect(lambda: self.batch_control(True))
        btn_all_off = QPushButton("全部关闭")
        btn_all_off.clicked.connect(lambda: self.batch_control(False))
        batch_layout.addWidget(btn_all_on)
        batch_layout.addWidget(btn_all_off)
        batch_layout.addStretch()
        panel_layout.addLayout(batch_layout)
        
        panel_layout.addStretch()

    def connect_device(self):
        ip = self.edit_ip.text().strip()
        try:
            port = int(self.edit_port.text().strip())
        except:
            port = 502
            
        self.easy320.ip = ip
        self.easy320.port = port
        self.easy320.disconnect()
        
        if self.easy320.connect():
            self.lbl_status.setText("状态: 已连接")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
            self.sync_status()
        else:
            QMessageBox.critical(self, "错误", "连接设备失败，请检查网络设置。")

    def disconnect_device(self):
        self.easy320.disconnect()
        self.lbl_status.setText("状态: 已断开")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")

    def on_relay_clicked(self, index, checked):
        if not self.easy320.is_connected:
            QMessageBox.warning(self, "提醒", "请先连接设备")
            self.relay_buttons[index].setChecked(not checked)
            return
            
        if self.easy320.write_relay(index, checked):
            self._update_btn_style(index, checked)
        else:
            self.relay_buttons[index].setChecked(not checked)
            QMessageBox.warning(self, "失败", f"控制继电器 {index+1} 失败")

    def _update_btn_style(self, index, state):
        btn = self.relay_buttons[index]
        if state:
            btn.setText(f"CH-{index+1:02d}\n(ON)")
            btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        else:
            btn.setText(f"CH-{index+1:02d}\n(OFF)")
            btn.setStyleSheet("background-color: #f0f0f0; color: #333;")

    def batch_control(self, state):
        if not self.easy320.is_connected: return
        for i in range(32):
            if self.easy320.write_relay(i, state):
                self.relay_buttons[i].setChecked(state)
                self._update_btn_style(i, state)
            QApplication.processEvents() # 保持界面响应
            time.sleep(0.05)

    def sync_status(self):
        if not self.easy320.is_connected: return
        states = self.easy320.read_relays(32)
        if states:
            for i, s in enumerate(states):
                if i < len(self.relay_buttons):
                    self.relay_buttons[i].setChecked(s)
                    self._update_btn_style(i, s)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Easy320StandaloneTab()
    window.show()
    sys.exit(app.exec())
