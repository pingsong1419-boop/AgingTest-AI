from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QGroupBox, QTextEdit, 
                               QGridLayout, QFrame, QTabWidget)
from PySide6.QtCore import Qt

class SingleChannelDebugTab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        
    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # --- 左侧：控制与状态区 ---
        left_panel = QVBoxLayout()
        
        # 1. 通道选择
        select_group = QGroupBox("调试通道选择")
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("当前通道:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([f"Channel {i+1}" for i in range(60)])
        select_layout.addWidget(self.channel_combo)
        self.btn_connect = QPushButton("连接/开启监听")
        self.btn_connect.setStyleSheet("background-color: #28A745; color: white;")
        select_layout.addWidget(self.btn_connect)
        select_group.setLayout(select_layout)
        left_panel.addWidget(select_group)
        
        # 2. 实时状态监控 (看板)
        monitor_group = QGroupBox("实时数据看板")
        monitor_layout = QGridLayout()
        
        # 模拟几个大字显示数据
        self.labels = {}
        items = [("总电压 (V)", "0.00", "cyan"), ("电流 (A)", "0.0", "lime"), 
                 ("最高温 (℃)", "25.0", "orange"), ("SOC (%)", "0.0", "yellow")]
        
        for i, (name, val, color) in enumerate(items):
            lbl_name = QLabel(name)
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {color}; font-family: 'Consolas';")
            monitor_layout.addWidget(lbl_name, i // 2 * 2, i % 2)
            monitor_layout.addWidget(lbl_val, i // 2 * 2 + 1, i % 2)
            self.labels[name] = lbl_val
            
        monitor_group.setLayout(monitor_layout)
        left_panel.addWidget(monitor_group)
        
        # 3. 手动控制指令
        ctrl_group = QGroupBox("手动控制指令")
        ctrl_layout = QGridLayout()
        
        cmds = ["闭合主继电器", "断开主继电器", "强制充电开始", "强制放电开始", 
                "清除报警", "读取版本信息", "系统复位"]
        for i, cmd in enumerate(cmds):
            btn = QPushButton(cmd)
            btn.setMinimumHeight(40)
            ctrl_layout.addWidget(btn, i // 2, i % 2)
            
        ctrl_group.setLayout(ctrl_layout)
        left_panel.addWidget(ctrl_group)
        left_panel.addStretch()
        
        main_layout.addLayout(left_panel, 2)
        
        # --- 右侧：报文日志区 ---
        right_panel = QVBoxLayout()
        log_group = QGroupBox("底层通讯报文监控 (Raw Data)")
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            background-color: #000000; 
            color: #00FF00; 
            font-family: 'Consolas'; 
            font-size: 11px;
        """)
        self.log_output.append("[System] 调试控制台就绪...")
        self.log_output.append("[Log] 2026-05-11 11:22:34 RX: 7E 01 02 03 04 05 FF 0D")
        
        log_layout.addWidget(self.log_output)
        
        btn_log_layout = QHBoxLayout()
        btn_log_layout.addWidget(QPushButton("清空日志"))
        btn_log_layout.addWidget(QPushButton("导出当前日志"))
        log_layout.addLayout(btn_log_layout)
        
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)
        
        main_layout.addLayout(right_panel, 3)

class DebugTab(QWidget):
    """
    硬件调试主容器 Tab
    内部包含一个 QTabWidget，集成所有单项硬件的调试页面
    """
    def __init__(self, device_manager=None):
        super().__init__()
        self.mgr = device_manager
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.sub_tabs = QTabWidget()
        # 设置 Tab 样式为左侧显示或顶部显示（根据用户习惯，通常顶部更直观）
        self.sub_tabs.setTabPosition(QTabWidget.North)
        
        # 1. 原始的单通道调试 (CAN/BMS)
        self.tab_single_ch = SingleChannelDebugTab()
        self.sub_tabs.addTab(self.tab_single_ch, "BMS 单通道调试")
        
        layout.addWidget(self.sub_tabs)

    def add_debug_tab(self, widget, label):
        """外部调用：向调试中心添加子页面"""
        self.sub_tabs.addTab(widget, label)
