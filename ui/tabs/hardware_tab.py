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
        self.edit_hv_ip = QLineEdit("192.168.1.190")
        self.edit_afe_ip = QLineEdit("192.168.1.200")
        form_left.addRow("NGI 高压源 IP:", self.edit_hv_ip)
        form_left.addRow("1# AFE 电源 IP:", self.edit_afe_ip)
        
        form_right = QFormLayout()
        self.edit_main_ip = QLineEdit("192.168.1.201")
        self.edit_voice_com = QLineEdit("COM3")
        self.edit_scanner_com = QLineEdit("COM4")
        form_right.addRow("主机板电源 IP:", self.edit_main_ip)
        form_right.addRow("语音模块端口:", self.edit_voice_com)
        form_right.addRow("扫码枪端口:", self.edit_scanner_com)
        
        global_layout.addLayout(form_left)
        global_layout.addLayout(form_right)
        
        btn_v_layout = QVBoxLayout()
        self.btn_save_global = QPushButton("保存全局配置")
        self.btn_save_global.setFixedWidth(120)
        self.btn_save_global.clicked.connect(self.save_global_config)
        self.btn_save_global.setStyleSheet("background-color: #007BFF; font-weight: bold;")
        btn_v_layout.addWidget(self.btn_save_global)
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
            self.edit_hv_ip.setText(sys_cfg.get("hv_ip", ""))
            self.edit_afe_ip.setText(sys_cfg.get("afe_ip", ""))
            self.edit_main_ip.setText(sys_cfg.get("main_ip", ""))
            self.edit_voice_com.setText(sys_cfg.get("voice_com", "COM3"))
            self.edit_scanner_com.setText(sys_cfg.get("scanner_com", "COM4"))
            
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
            "hv_ip": self.edit_hv_ip.text(),
            "afe_ip": self.edit_afe_ip.text(),
            "main_ip": self.edit_main_ip.text(),
            "voice_com": self.edit_voice_com.text(),
            "scanner_com": self.edit_scanner_com.text()
        }
        if self.db_manager.save_sys_config(data):
            QMessageBox.information(self, "成功", "全局设备配置已保存。")

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
