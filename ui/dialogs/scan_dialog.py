from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QListWidget, QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer

class ScanDialog(QDialog):
    """
    扫码入站核心对话框
    工作流：
    1. 扫描货架码 -> 自动匹配通道号 (依据硬件配置表)
    2. 扫描主机码 -> 绑定主 BMS
    3. 扫描从机码 (根据拓扑配置数量) -> 绑定从 BMS
    """
    scan_completed = Signal(int, str, str, list) # channel_id, shelf, master, slaves

    def __init__(self, parent=None, db_manager=None, slaves_count=0):
        super().__init__(parent)
        self.db_manager = db_manager
        self.slaves_count = slaves_count
        
        self.setWindowTitle("扫码入站绑定")
        self.setFixedSize(750, 600)
        self.setStyleSheet("background-color: #1A1A2E; color: white;")
        
        # 数据缓存
        self.target_channel = -1
        self.shelf_code = ""
        self.master_code = ""
        self.slave_codes = []
        
        # 加载货架映射
        self.shelf_mapping = {}
        if self.db_manager:
            configs = self.db_manager.load_channel_config()
            for cfg in configs:
                s_code = cfg.get("shelf_code", "").strip()
                if s_code:
                    self.shelf_mapping[s_code] = int(cfg.get("channel_id", -1))

        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # 顶部提示
        self.lbl_step = QLabel("请扫描【货架二维码】以定位测试通道")
        self.lbl_step.setStyleSheet("font-size: 16px; font-weight: bold; color: #00E5FF;")
        self.lbl_step.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_step)
        
        # 扫描输入框 (保持焦点)
        self.scan_input = QLineEdit()
        self.scan_input.setFixedHeight(50)
        self.scan_input.setPlaceholderText(">>> 请在此处扫码 <<<")
        self.scan_input.setStyleSheet("""
            QLineEdit {
                font-size: 24px; 
                font-family: 'Consolas', 'Monaco', monospace;
                border: 2px solid #00E5FF; 
                border-radius: 8px; 
                padding: 10px;
                background-color: #0F0F1E;
                color: #00FF00;
            }
        """)
        self.scan_input.returnPressed.connect(self.process_scan)
        layout.addWidget(self.scan_input)
        
        # 详细信息预览区
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #16213E; border-radius: 10px; padding: 15px;")
        info_layout = QVBoxLayout(info_frame)
        
        self.lbl_ch_info = QLabel("测试通道: --")
        self.lbl_ch_info.setStyleSheet("font-size: 20px; font-weight: bold; color: #4ECCA3;")
        info_layout.addWidget(self.lbl_ch_info)
        
        self.lbl_shelf_info = QLabel("货架编号: --")
        self.lbl_shelf_info.setStyleSheet("font-size: 16px; color: #AAAAAA;")
        self.lbl_shelf_info.setWordWrap(True)
        info_layout.addWidget(self.lbl_shelf_info)
        
        self.lbl_master_info = QLabel("主机编码: --")
        self.lbl_master_info.setStyleSheet("font-size: 18px; font-weight: bold; border-top: 1px solid #3E3E5C; padding-top: 10px;")
        self.lbl_master_info.setWordWrap(True)
        self.lbl_master_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_layout.addWidget(self.lbl_master_info)
        
        slave_lbl = QLabel("从机列表:")
        slave_lbl.setStyleSheet("font-size: 14px; color: #888888;")
        info_layout.addWidget(slave_lbl)
        
        self.list_slaves = QListWidget()
        self.list_slaves.setFixedHeight(120)
        self.list_slaves.setStyleSheet("""
            QListWidget {
                font-size: 14px;
                background: #1A1A2E; 
                border: 1px solid #3E3E5C;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #2A2A3E;
            }
        """)
        info_layout.addWidget(self.list_slaves)
        
        layout.addWidget(info_frame)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("重置当前扫码")
        self.btn_reset.clicked.connect(self.reset_scan)
        btn_layout.addWidget(self.btn_reset)
        
        self.btn_cancel = QPushButton("退出")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.scan_input.setFocus()

    def process_scan(self):
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code: return
        
        # 状态机逻辑
        print(f"[DEBUG] 扫码输入: {code}, 当前目标通道: {self.target_channel}")
        
        if self.target_channel == -1:
            # 第一步：识别货架码
            if code in self.shelf_mapping:
                self.target_channel = self.shelf_mapping[code]
                self.shelf_code = code
                self.lbl_ch_info.setText(f"测试通道: CH-{self.target_channel:02d}")
                self.lbl_shelf_info.setText(f"货架编号: {code}")
                self.lbl_step.setText("✅ 货架已识别！请扫描【主机条码】")
                self.lbl_step.setStyleSheet("color: #FFD700; font-size: 20px;")
                print(f"[DEBUG] 识别到货架: {code} -> 通道: {self.target_channel}")
            else:
                self.lbl_step.setText(f"❌ 未识别货架码: {code}")
                self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 18px;")
                print(f"[DEBUG] 未识别的货架码: {code}")
                
        elif not self.master_code:
            # 第二步：扫主机
            self.master_code = code
            self.lbl_master_info.setText(f"主机编码: {code}")
            if self.slaves_count > 0:
                self.lbl_step.setText(f"请继续扫描【从机条码】(1/{self.slaves_count})")
            else:
                self.finalize_scan()
                
        elif len(self.slave_codes) < self.slaves_count:
            # 第三步：扫从机
            self.slave_codes.append(code)
            self.list_slaves.addItem(f"Slave {len(self.slave_codes)}: {code}")
            
            if len(self.slave_codes) < self.slaves_count:
                self.lbl_step.setText(f"请继续扫描【从机条码】({len(self.slave_codes) + 1}/{self.slaves_count})")
            else:
                self.finalize_scan()

    def finalize_scan(self):
        self.lbl_step.setText("✅ 扫码匹配成功！正在入站...")
        self.lbl_step.setStyleSheet("color: #00FF00;")
        # 发射信号
        self.scan_completed.emit(self.target_channel, self.shelf_code, self.master_code, self.slave_codes)
        # 自动重置以准备下一个货架
        QTimer.singleShot(1000, self.reset_scan)

    def reset_scan(self):
        self.target_channel = -1
        self.shelf_code = ""
        self.master_code = ""
        self.slave_codes = []
        self.lbl_ch_info.setText("测试通道: --")
        self.lbl_shelf_info.setText("货架编号: --")
        self.lbl_master_info.setText("主机编码: --")
        self.list_slaves.clear()
        self.lbl_step.setText("请扫描【货架二维码】以定位测试通道")
        self.lbl_step.setStyleSheet("color: #00E5FF; font-size: 16px;")
        self.scan_input.setFocus()
