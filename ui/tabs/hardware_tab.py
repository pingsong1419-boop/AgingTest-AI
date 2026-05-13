from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                                QLabel, QTableWidget, QTableWidgetItem, 
                                QHeaderView, QGroupBox, QLineEdit, QPushButton,
                                QFormLayout, QFrame, QMessageBox)
from PySide6.QtCore import Qt

class HardwareTab(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._init_ui()
        self.load_config()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 顶部：全局公共测试设备配置
        global_group = QGroupBox("1. 全局公共测试设备配置 (IP/串口)")
        global_layout = QHBoxLayout()
        
        # 使用表单布局排列全局设备
        form_left = QFormLayout()
        self.edit_afe1_ip = QLineEdit("192.168.1.200")
        self.edit_afe1_port = QLineEdit("2000")
        self.edit_afe2_ip = QLineEdit("192.168.1.203")
        self.edit_afe2_port = QLineEdit("10001")
        self.edit_afe3_ip = QLineEdit("192.168.1.203")
        self.edit_afe3_port = QLineEdit("10001")
        self.edit_main_ip = QLineEdit("192.168.1.201")
        self.edit_main_port = QLineEdit("2000")
        self.edit_pwr_board_ip = QLineEdit("192.168.1.202")
        self.edit_pwr_board_port = QLineEdit("10001")
        
        form_left.addRow("1# AFE 电源 IP:", self.edit_afe1_ip)
        form_left.addRow("1# AFE 端口:", self.edit_afe1_port)
        form_left.addRow("2# AFE 电源 IP:", self.edit_afe2_ip)
        form_left.addRow("2# AFE 端口:", self.edit_afe2_port)
        form_left.addRow("3# AFE 电源 IP:", self.edit_afe3_ip)
        form_left.addRow("3# AFE 端口:", self.edit_afe3_port)
        form_left.addRow("主机板电源 IP:", self.edit_main_ip)
        form_left.addRow("主机板端口:", self.edit_main_port)
        form_left.addRow("功能板电源 IP:", self.edit_pwr_board_ip)
        form_left.addRow("功能板端口:", self.edit_pwr_board_port)
        
        form_right = QFormLayout()
        self.edit_hv_ip = QLineEdit("192.168.1.190")
        self.edit_hv_port = QLineEdit("7000")
        self.edit_ca550_com = QLineEdit("")
        self.edit_easy320_ip = QLineEdit("192.168.1.88")
        self.edit_sim1_ip = QLineEdit("192.168.1.210")
        self.edit_sim1_port = QLineEdit("5025")
        self.edit_sim2_ip = QLineEdit("192.168.1.211")
        self.edit_sim2_port = QLineEdit("5025")
        self.edit_sim3_ip = QLineEdit("192.168.1.212")
        self.edit_sim3_port = QLineEdit("5025")
        
        form_right.addRow("NGI 高压源 IP:", self.edit_hv_ip)
        form_right.addRow("NGI 端口:", self.edit_hv_port)
        form_right.addRow("CA550 串口:", self.edit_ca550_com)
        form_right.addRow("Easy320 IP:", self.edit_easy320_ip)
        form_right.addRow("1# 模拟电池 IP:", self.edit_sim1_ip)
        form_right.addRow("1# 电池端口:", self.edit_sim1_port)
        form_right.addRow("2# 模拟电池 IP:", self.edit_sim2_ip)
        form_right.addRow("2# 电池端口:", self.edit_sim2_port)
        form_right.addRow("3# 模拟电池 IP:", self.edit_sim3_ip)
        form_right.addRow("3# 电池端口:", self.edit_sim3_port)
        
        global_layout.addLayout(form_left)
        global_layout.addLayout(form_right)
        
        btn_v_layout = QVBoxLayout()
        self.btn_save_global = QPushButton("💾 保存全局配置")
        self.btn_save_global.setFixedWidth(130)
        self.btn_save_global.setFixedHeight(50)
        self.btn_save_global.clicked.connect(self.save_global_config)
        self.btn_save_global.setStyleSheet("background-color: #007BFF; font-weight: bold; font-size: 14px;")
        btn_v_layout.addWidget(self.btn_save_global)
        btn_v_layout.addStretch()
        global_layout.addLayout(btn_v_layout)
        
        global_group.setLayout(global_layout)
        layout.addWidget(global_group)
        
        # 2. 中部：通道映射与功能板配置
        channel_group = QGroupBox("2. 通道硬件映射与功能板 IP 配置 (48~60 通道)")
        channel_layout = QVBoxLayout()
        
        header_tips = QLabel("说明：【货架二维码】用于扫码入站匹配；【功能板 IP】为每个通道独立控制板的地址；【物理单元/地址】对应后端通信逻辑。")
        header_tips.setStyleSheet("color: #FFC107; font-size: 12px; margin-bottom: 5px;")
        channel_layout.addWidget(header_tips)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "通道号", "货架二维码 (扫码触发)", "功能板 IP 地址", "物理单元", "子地址", "状态"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        
        self.table.setRowCount(60)
        for i in range(60):
            # 通道号列 (不可编辑)
            ch_item = QTableWidgetItem(f"CH-{i+1:02d}")
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
            ch_item.setBackground(Qt.black)
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, ch_item)
            
            # 初始化默认数据
            self.table.setItem(i, 1, QTableWidgetItem(f"SHELF-A-{i+1:02d}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"192.168.1.{210 + (i // 18)}")) # 示例分配
            self.table.setItem(i, 3, QTableWidgetItem(str((i // 18) + 1)))
            self.table.setItem(i, 4, QTableWidgetItem(str((i % 18) + 1)))
            
            status_item = QTableWidgetItem("离线")
            status_item.setForeground(Qt.gray)
            self.table.setItem(i, 5, status_item)
            
        channel_layout.addWidget(self.table)
        
        # 通道操作按钮
        ch_btn_layout = QHBoxLayout()
        self.btn_save_channels = QPushButton("💾 保存通道映射配置")
        self.btn_save_channels.setFixedHeight(35)
        self.btn_save_channels.setStyleSheet("background-color: #28A745; font-weight: bold;")
        self.btn_save_channels.clicked.connect(self.save_channel_config)
        
        self.btn_auto_fill = QPushButton("🪄 批量生成 IP")
        self.btn_auto_fill.setFixedWidth(100)
        self.btn_auto_fill.clicked.connect(self.auto_fill_ips)
        
        ch_btn_layout.addWidget(self.btn_save_channels, 1)
        ch_btn_layout.addWidget(self.btn_auto_fill)
        channel_layout.addLayout(ch_btn_layout)
        
        channel_group.setLayout(channel_layout)
        layout.addWidget(channel_group)

    def load_config(self):
        """从数据库/文件加载配置"""
        # 加载全局配置
        sys_cfg = self.db_manager.load_sys_config()
        if sys_cfg:
            self.edit_afe1_ip.setText(sys_cfg.get("afe1_ip", "192.168.1.200"))
            self.edit_afe1_port.setText(str(sys_cfg.get("afe1_port", "2000")))
            self.edit_afe2_ip.setText(sys_cfg.get("afe2_ip", "192.168.1.203"))
            self.edit_afe2_port.setText(str(sys_cfg.get("afe2_port", "10001")))
            self.edit_afe3_ip.setText(sys_cfg.get("afe3_ip", "192.168.1.203"))
            self.edit_afe3_port.setText(str(sys_cfg.get("afe3_port", "10001")))
            self.edit_main_ip.setText(sys_cfg.get("main_ip", "192.168.1.201"))
            self.edit_main_port.setText(str(sys_cfg.get("main_port", "2000")))
            self.edit_pwr_board_ip.setText(sys_cfg.get("pwr_board_ip", "192.168.1.202"))
            self.edit_pwr_board_port.setText(str(sys_cfg.get("pwr_board_port", "10001")))
            self.edit_hv_ip.setText(sys_cfg.get("hv_ip", "192.168.1.190"))
            self.edit_hv_port.setText(str(sys_cfg.get("hv_port", "7000")))
            self.edit_ca550_com.setText(sys_cfg.get("ca550_com", ""))
            self.edit_easy320_ip.setText(sys_cfg.get("easy320_ip", "192.168.1.88"))
            self.edit_sim1_ip.setText(sys_cfg.get("sim1_ip", "192.168.1.210"))
            self.edit_sim1_port.setText(str(sys_cfg.get("sim1_port", "5025")))
            self.edit_sim2_ip.setText(sys_cfg.get("sim2_ip", "192.168.1.211"))
            self.edit_sim2_port.setText(str(sys_cfg.get("sim2_port", "5025")))
            self.edit_sim3_ip.setText(sys_cfg.get("sim3_ip", "192.168.1.212"))
            self.edit_sim3_port.setText(str(sys_cfg.get("sim3_port", "5025")))
            
        # 加载通道配置
        ch_cfgs = self.db_manager.load_channel_config()
        if ch_cfgs:
            for i, cfg in enumerate(ch_cfgs):
                if i >= self.table.rowCount(): break
                self.table.setItem(i, 1, QTableWidgetItem(cfg.get("shelf_code", "")))
                self.table.setItem(i, 2, QTableWidgetItem(cfg.get("board_ip", "")))
                self.table.setItem(i, 3, QTableWidgetItem(str(cfg.get("unit", ""))))
                self.table.setItem(i, 4, QTableWidgetItem(str(cfg.get("addr", ""))))

    def save_global_config(self):
        data = {
            "afe1_ip": self.edit_afe1_ip.text(),
            "afe1_port": self.edit_afe1_port.text(),
            "afe2_ip": self.edit_afe2_ip.text(),
            "afe2_port": self.edit_afe2_port.text(),
            "afe3_ip": self.edit_afe3_ip.text(),
            "afe3_port": self.edit_afe3_port.text(),
            "main_ip": self.edit_main_ip.text(),
            "main_port": self.edit_main_port.text(),
            "pwr_board_ip": self.edit_pwr_board_ip.text(),
            "pwr_board_port": self.edit_pwr_board_port.text(),
            "hv_ip": self.edit_hv_ip.text(),
            "hv_port": self.edit_hv_port.text(),
            "ca550_com": self.edit_ca550_com.text(),
            "easy320_ip": self.edit_easy320_ip.text(),
            "sim1_ip": self.edit_sim1_ip.text(),
            "sim1_port": self.edit_sim1_port.text(),
            "sim2_ip": self.edit_sim2_ip.text(),
            "sim2_port": self.edit_sim2_port.text(),
            "sim3_ip": self.edit_sim3_ip.text(),
            "sim3_port": self.edit_sim3_port.text()
        }
        if self.db_manager.save_sys_config(data):
            # 动态通知设备管理器更新配置
            try:
                from PySide6.QtWidgets import QApplication
                main_win = None
                for widget in QApplication.topLevelWidgets():
                    if hasattr(widget, "device_manager"):
                        main_win = widget
                        break
                if main_win:
                    main_win.device_manager.update_config()
                    QMessageBox.information(self, "成功", "全局设备配置已保存并实时生效。")
                else:
                    QMessageBox.information(self, "成功", "全局设备配置已保存（下次启动生效）。")
            except Exception as e:
                QMessageBox.warning(self, "保存成功但更新失败", f"配置已保存，但实时更新失败: {e}")

    def save_channel_config(self):
        configs = []
        for i in range(self.table.rowCount()):
            cfg = {
                "channel_id": i + 1,
                "shelf_code": self.table.item(i, 1).text(),
                "board_ip": self.table.item(i, 2).text(),
                "unit": self.table.item(i, 3).text(),
                "addr": self.table.item(i, 4).text()
            }
            configs.append(cfg)
        
        if self.db_manager.save_channel_config(configs):
            QMessageBox.information(self, "成功", "通道硬件映射表已保存。")

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
