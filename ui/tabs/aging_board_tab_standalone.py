import sys
import time
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QPushButton, QLabel, QScrollArea, QFrame, QGroupBox, 
                                QComboBox, QMessageBox, QLineEdit)
from PySide6.QtCore import Qt, QTimer

# 导入之前提取的独立驱动
from devices.aging_board_driver import AgingBoardController

class AgingBoardStandaloneTab(QWidget):
    def __init__(self, driver):
        super().__init__()
        self.setWindowTitle("老化功能板测试界面")
        self.resize(1000, 700)
        
        # 使用传入的驱动实例
        self.board = driver
        self.btn_groups = {} # 用于追踪 UI 控件以便更新状态
        self._init_ui()
        
        # 定时同步状态 (3秒一次)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync_status)
        self.timer.start(3000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- 1. 通讯配置 ---
        group_comm = QGroupBox("功能板通讯配置 (Modbus TCP)")
        comm_layout = QHBoxLayout()
        comm_layout.addWidget(QLabel("IP 地址:"))
        self.edit_ip = QLineEdit(self.board.ip)
        comm_layout.addWidget(self.edit_ip)
        
        btn_connect = QPushButton("连接板卡")
        btn_connect.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        btn_connect.clicked.connect(self.connect_device)
        comm_layout.addWidget(btn_connect)
        
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.clicked.connect(self.disconnect_device)
        comm_layout.addWidget(btn_disconnect)
        
        self.lbl_status = QLabel("状态: 未连接")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        comm_layout.addWidget(self.lbl_status)
        group_comm.setLayout(comm_layout)
        main_layout.addWidget(group_comm)

        # --- 2. 继电器控制矩阵 ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        relay_box = QGroupBox("继电器控制矩阵")
        grid_layout = QGridLayout(relay_box)
        grid_layout.setSpacing(10)
        
        # 获取驱动中的定义
        relay_names = self.board.RELAY_MAP
        row, col = 0, 0
        for name, addr in relay_names.items():
            btn_group = QGroupBox(name)
            btn_layout = QHBoxLayout(btn_group)
            
            btn_on = QPushButton("开启")
            btn_on.setFixedSize(60, 30)
            btn_on.clicked.connect(lambda checked, a=addr, n=name: self.on_relay_clicked(a, True, n))
            
            btn_off = QPushButton("关闭")
            btn_off.setFixedSize(60, 30)
            btn_off.clicked.connect(lambda checked, a=addr, n=name: self.on_relay_clicked(a, False, n))
            
            btn_layout.addWidget(btn_on)
            btn_layout.addWidget(btn_off)
            
            self.btn_groups[addr] = (btn_on, btn_off)
            
            grid_layout.addWidget(btn_group, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        container_layout.addWidget(relay_box)
        
        # 批量操作
        btn_all_off = QPushButton("全部紧急切断 (All OFF)")
        btn_all_off.setFixedHeight(50)
        btn_all_off.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; font-size: 16px;")
        btn_all_off.clicked.connect(self.board.all_off)
        container_layout.addWidget(btn_all_off)
        
        container_layout.addStretch()
        scroll.setWidget(container)

    def connect_device(self):
        self.board.ip = self.edit_ip.text().strip()
        if self.board.connect():
            self.lbl_status.setText("状态: 已连接")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            QMessageBox.critical(self, "错误", f"无法连接到板卡 {self.board.ip}")

    def disconnect_device(self):
        self.board.disconnect()
        self.lbl_status.setText("状态: 已断开")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")

    def on_relay_clicked(self, address, state, name):
        if not self.board.is_connected:
            QMessageBox.warning(self, "提醒", "请先连接设备")
            return
            
        if self.board.write_relay(address, state):
            print(f"[UI] 继电器 {name} (地址 {address}) 设置为 {state}")
            self._update_relay_style(address, state)
        else:
            QMessageBox.warning(self, "失败", f"控制继电器 {name} 失败")

    def _update_relay_style(self, address, state):
        if address in self.btn_groups:
            btn_on, btn_off = self.btn_groups[address]
            if state:
                btn_on.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
                btn_off.setStyleSheet("")
            else:
                btn_on.setStyleSheet("")
                btn_off.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")

    def sync_status(self):
        """同步板卡所有继电器状态"""
        if not self.board.is_connected: return
        states = self.board.read_relays(22)
        if states:
            for addr, state in enumerate(states):
                self._update_relay_style(addr, state)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AgingBoardStandaloneTab()
    window.show()
    sys.exit(app.exec())
