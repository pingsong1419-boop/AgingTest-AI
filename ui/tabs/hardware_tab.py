from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                                 QLabel, QTableWidget, QTableWidgetItem, 
                                 QHeaderView, QGroupBox, QLineEdit, QPushButton,
                                 QFormLayout, QFrame, QMessageBox, QScrollArea, QTabWidget)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, QTimer

class HardwareTab(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.device_manager = None # 将由 MainWindow 注入
        self._init_ui()
        self.load_config()
        
        # 状态刷新定时器
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_hardware_status)
        self.status_timer.start(3000) 
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 使用子 Tab 页签来分离功能，增加空间感
        self.sub_tabs = QTabWidget()
        main_layout.addWidget(self.sub_tabs)
        
        # --- 子页签 1: 硬件联机与全局配置 ---
        tab_mgr = QWidget()
        mgr_layout = QVBoxLayout(tab_mgr)
        
        # A. 实时状态
        status_group = QGroupBox("系统硬件实时状态 (Hardware Status)")
        status_v = QVBoxLayout()
        ctrl_bar = QHBoxLayout()
        self.btn_init_all = QPushButton("⚡ 一键初始化所有硬件")
        self.btn_init_all.setStyleSheet("background-color: #28A745; height: 40px; font-weight: bold;")
        self.btn_init_all.clicked.connect(self.init_all_hardware)
        self.btn_disconnect_all = QPushButton("🛑 断开所有连接")
        self.btn_disconnect_all.clicked.connect(self.disconnect_all_hardware)
        ctrl_bar.addWidget(self.btn_init_all, 2); ctrl_bar.addWidget(self.btn_disconnect_all, 1)
        status_v.addLayout(ctrl_bar)
        
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels(["硬件名称", "通讯地址/参数", "连接状态", "操作"])
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        status_v.addWidget(self.status_table)
        status_group.setLayout(status_v)
        mgr_layout.addWidget(status_group, 3)  # 增加权重
        
        # B. 通讯配置
        config_group = QGroupBox("公共设备通讯参数配置")
        config_group.setMaximumHeight(220) # 限制高度
        config_main_layout = QHBoxLayout()
        
        # 左侧列: AFE 电源配置 (IP + 端口 并排)
        form_afe = QFormLayout()
        
        def create_ip_port_row(ip_edit, port_edit):
            layout = QHBoxLayout()
            ip_edit.setPlaceholderText("0.0.0.0")
            port_edit.setFixedWidth(60)
            port_edit.setPlaceholderText("2000")
            layout.addWidget(ip_edit)
            layout.addWidget(QLabel("端口:"))
            layout.addWidget(port_edit)
            return layout

        self.edit_afe1_ip = QLineEdit(); self.edit_afe1_port = QLineEdit()
        form_afe.addRow("1# AFE IP:", create_ip_port_row(self.edit_afe1_ip, self.edit_afe1_port))
        
        self.edit_afe2_ip = QLineEdit(); self.edit_afe2_port = QLineEdit()
        form_afe.addRow("2# AFE IP:", create_ip_port_row(self.edit_afe2_ip, self.edit_afe2_port))
        
        self.edit_afe3_ip = QLineEdit(); self.edit_afe3_port = QLineEdit()
        form_afe.addRow("3# AFE IP:", create_ip_port_row(self.edit_afe3_ip, self.edit_afe3_port))
        
        # 右侧列: 其它设备
        form_others = QFormLayout()
        self.edit_dut_ip = QLineEdit(); self.edit_hv_ip = QLineEdit()
        form_others.addRow("DUT供电 IP:", self.edit_dut_ip)
        form_others.addRow("NGI 高压 IP:", self.edit_hv_ip)
        
        self.edit_sim1_ip = QLineEdit(); self.edit_sim2_ip = QLineEdit(); self.edit_sim3_ip = QLineEdit()
        form_others.addRow("1# 模拟器 IP:", self.edit_sim1_ip)
        form_others.addRow("2# 模拟器 IP:", self.edit_sim2_ip)
        form_others.addRow("3# 模拟器 IP:", self.edit_sim3_ip)

        self.edit_ctrl_pwr_ip = QLineEdit(); self.edit_easy320_ip = QLineEdit()
        form_others.addRow("控制板电源 IP:", self.edit_ctrl_pwr_ip)
        form_others.addRow("Easy320 PLC IP:", self.edit_easy320_ip)
        
        self.edit_ca550_com = QLineEdit()
        form_others.addRow("CA550 串口号:", self.edit_ca550_com)

        config_main_layout.addLayout(form_afe, 2)
        config_main_layout.addLayout(form_others, 3)
        
        btn_save = QPushButton("💾 保存\n全局参数")
        btn_save.setFixedSize(100, 100)
        btn_save.setStyleSheet("font-weight: bold; background-color: #4B4B6A;")
        btn_save.clicked.connect(self.save_global_config)
        config_main_layout.addWidget(btn_save)
        
        config_group.setLayout(config_main_layout)
        mgr_layout.addWidget(config_group, 1)
        
        self.sub_tabs.addTab(tab_mgr, "1. 硬件状态与全局配置")
        
        # --- 子页签 3: 分布式老化板监控 ---
        tab_boards = QWidget()
        boards_layout = QVBoxLayout(tab_boards)
        
        self.board_table = QTableWidget()
        self.board_table.setColumnCount(6)
        self.board_table.setHorizontalHeaderLabels(["通道", "货架二维码", "控制板 IP", "继电器通讯", "CAN通讯", "操作"])
        self.board_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.board_table.setRowCount(60)
        for i in range(60):
            ch_item = QTableWidgetItem(f"CH-{i+1:02d}")
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.board_table.setItem(i, 0, ch_item)
            # 按钮
            btn = QPushButton("手动重连")
            btn.setFixedSize(80, 24)
            btn.clicked.connect(lambda checked=False, ch=i+1: self.reconnect_board(ch))
            self.board_table.setCellWidget(i, 5, btn)
            
        boards_layout.addWidget(self.board_table)

        # 新增：保存按钮
        self.btn_save_boards = QPushButton("💾 保存控制板配置 (Save Board Config)")
        self.btn_save_boards.setFixedHeight(40)
        self.btn_save_boards.setStyleSheet("font-weight: bold; background-color: #007BFF; color: white;")
        self.btn_save_boards.clicked.connect(self.save_board_monitor_config)
        boards_layout.addWidget(self.btn_save_boards)

        self.sub_tabs.addTab(tab_boards, "2. 分布式控制板监控 (60路)")

    def set_device_manager(self, manager):
        self.device_manager = manager
        self.refresh_hardware_status()

    def refresh_hardware_status(self):
        if not self.device_manager: return
        status_list = self.device_manager.get_all_device_status()
        if self.status_table.rowCount() != len(status_list):
            self.status_table.setRowCount(len(status_list))
            for i in range(len(status_list)):
                for j in range(3): self.status_table.setItem(i, j, QTableWidgetItem(""))
                btn = QPushButton("尝试重连")
                btn.setFixedSize(80, 24); btn.clicked.connect(self.init_all_hardware)
                self.status_table.setCellWidget(i, 3, btn)

        self.status_table.setUpdatesEnabled(False)
        for i, info in enumerate(status_list):
            it0 = self.status_table.item(i, 0); it1 = self.status_table.item(i, 1); it2 = self.status_table.item(i, 2)
            if it0.text() != info["name"]: it0.setText(info["name"])
            if it1.text() != info["info"]: it1.setText(info["info"])
            if it2.text() != info["status"]:
                it2.setText(info["status"]); it2.setForeground(QColor(info["color"]))
                it2.setTextAlignment(Qt.AlignCenter)
        self.status_table.setUpdatesEnabled(True)
        
        # 刷新 60 路控制板状态
        self.board_table.setUpdatesEnabled(False)
        # 获取通道配置以获取货架码
        ch_configs = self.db_manager.load_channel_config() or []
        ch_map = {c["channel_id"]: c for c in ch_configs}

        for i in range(1, 61):
            board = self.device_manager.boards.get(i)
            config = ch_map.get(i, {})
            
            # Shelf Code (Editable)
            it_shelf = self.board_table.item(i-1, 1) or QTableWidgetItem()
            shelf_code = config.get("shelf_code", "")
            if not self.board_table.item(i-1, 1): # 仅在初始化时设置值，避免正在编辑时被刷新覆盖
                it_shelf.setText(shelf_code)
                self.board_table.setItem(i-1, 1, it_shelf)

            # IP (Editable)
            it_ip = self.board_table.item(i-1, 2) or QTableWidgetItem()
            ip = board.ip if board else config.get("board_ip", "")
            if not self.board_table.item(i-1, 2):
                it_ip.setText(ip)
                self.board_table.setItem(i-1, 2, it_ip)
            
            # Relay Status
            it_r = self.board_table.item(i-1, 3) or QTableWidgetItem()
            r_ok = board.relays.is_connected if board else False
            txt = "在线" if r_ok else "离线"
            if it_r.text() != txt:
                it_r.setText(txt); it_r.setForeground(QColor("#28A745" if r_ok else "#DC3545"))
                it_r.setTextAlignment(Qt.AlignCenter)
            self.board_table.setItem(i-1, 3, it_r)
            
            # CAN Status
            it_c = self.board_table.item(i-1, 4) or QTableWidgetItem()
            c_ok = board.can.is_connected if board else False
            txt = "在线" if c_ok else "离线"
            if it_c.text() != txt:
                it_c.setText(txt); it_c.setForeground(QColor("#28A745" if c_ok else "#DC3545"))
                it_c.setTextAlignment(Qt.AlignCenter)
            self.board_table.setItem(i-1, 4, it_c)
            
        self.board_table.setUpdatesEnabled(True)

    def reconnect_board(self, channel_id):
        if not self.device_manager: return
        board = self.device_manager.boards.get(channel_id)
        if board:
            board.connect()
            self.refresh_hardware_status()

    def init_all_hardware(self):
        if not self.device_manager: return
        
        self.btn_init_all.setEnabled(False)
        self.btn_init_all.setText("⚡ 正在全量初始化硬件 (请稍候)...")
        
        import threading
        def task():
            try:
                # 执行耗时的初始化逻辑
                self.device_manager.init_all_devices(logger=print)
            finally:
                # 恢复按钮状态（需在主线程执行）
                QTimer.singleShot(0, lambda: self.btn_init_all.setEnabled(True))
                QTimer.singleShot(0, lambda: self.btn_init_all.setText("⚡ 一键初始化所有硬件"))
        
        threading.Thread(target=task, daemon=True).start()

    def disconnect_all_hardware(self):
        if self.device_manager: self.device_manager.disconnect_all(); self.refresh_hardware_status()

    def load_config(self):
        cfg = self.db_manager.load_sys_config() or {}
        self.edit_afe1_ip.setText(cfg.get("afe1_ip", "192.168.1.200"))
        self.edit_afe1_port.setText(str(cfg.get("afe1_port", "2000")))
        self.edit_afe2_ip.setText(cfg.get("afe2_ip", "192.168.1.204"))
        self.edit_afe2_port.setText(str(cfg.get("afe2_port", "2000")))
        self.edit_afe3_ip.setText(cfg.get("afe3_ip", "192.168.1.203"))
        self.edit_afe3_port.setText(str(cfg.get("afe3_port", "2000")))
        self.edit_dut_ip.setText(cfg.get("dut_pwr_ip", "192.168.1.201"))
        self.edit_hv_ip.setText(cfg.get("hv_ip", "192.168.1.190"))
        self.edit_sim1_ip.setText(cfg.get("sim1_ip", "192.168.1.210"))
        self.edit_sim2_ip.setText(cfg.get("sim2_ip", "192.168.1.211"))
        self.edit_sim3_ip.setText(cfg.get("sim3_ip", "192.168.1.212"))
        self.edit_ctrl_pwr_ip.setText(cfg.get("ctrl_pwr_ip", "192.168.1.202"))
        self.edit_easy320_ip.setText(cfg.get("easy320_ip", "192.168.1.88"))
        self.edit_ca550_com.setText(cfg.get("ca550_com", ""))

        ch_cfgs = self.db_manager.load_channel_config() or []

    def save_global_config(self):
        data = {
            "afe1_ip": self.edit_afe1_ip.text(),
            "afe1_port": self.edit_afe1_port.text(),
            "afe2_ip": self.edit_afe2_ip.text(),
            "afe2_port": self.edit_afe2_port.text(),
            "afe3_ip": self.edit_afe3_ip.text(),
            "afe3_port": self.edit_afe3_port.text(),
            "dut_pwr_ip": self.edit_dut_ip.text(),
            "hv_ip": self.edit_hv_ip.text(),
            "sim1_ip": self.edit_sim1_ip.text(),
            "sim2_ip": self.edit_sim2_ip.text(),
            "sim3_ip": self.edit_sim3_ip.text(),
            "ctrl_pwr_ip": self.edit_ctrl_pwr_ip.text(),
            "easy320_ip": self.edit_easy320_ip.text(),
            "ca550_com": self.edit_ca550_com.text()
        }
        if self.db_manager.save_sys_config(data):
            if self.device_manager: self.device_manager.update_config()
            QMessageBox.information(self, "成功", "全局配置已保存。")

    def save_board_monitor_config(self):
        """从监控表格中收集修改后的货架码和 IP 并保存到配置文件"""
        configs = []
        for i in range(60):
            item_shelf = self.board_table.item(i, 1)
            item_ip = self.board_table.item(i, 2)
            configs.append({
                "channel_id": i + 1,
                "shelf_code": item_shelf.text() if item_shelf else "",
                "board_ip": item_ip.text() if item_ip else "",
                "unit": (i // 18) + 1, # 保持默认逻辑
                "addr": (i % 18) + 1
            })
        
        if self.db_manager.save_channel_config(configs):
            if self.device_manager:
                self.device_manager.update_config() # 立即应用新 IP
            QMessageBox.information(self, "保存成功", "老化控制板的货架码与 IP 配置已更新。")

    def save_channel_config(self):
        pass

    def auto_fill_ips(self):
        """示例：根据起始 IP 批量填充"""
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "批量生成 IP", "请输入起始 IP (如 192.168.1.1):")
        if ok and text:
            try:
                base = ".".join(text.split(".")[:3])
                start = int(text.split(".")[-1])
                for i in range(self.table.rowCount()):
                    self.table.setItem(i, 2, QTableWidgetItem(f"{base}.{start + i}"))
            except:
                QMessageBox.warning(self, "错误", "IP 格式不正确。")
