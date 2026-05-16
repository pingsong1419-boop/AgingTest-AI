from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QListWidget, QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer
import re

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
        self.setFixedSize(750, 650)
        self.setStyleSheet("background-color: #1A1A2E; color: white;")
        
        # 数据缓存
        self.target_channel = -1
        self.shelf_code = ""
        self.master_code = ""
        self.slave_codes = []

        # 扫码校验规则 (可配置)
        self.rules = {
            "shelf": r"^(\d{2})-([ABC])(\d{2})$",
            "master": r".+", # 默认允许任意非空
            "slave": r".+"   # 默认允许任意非空
        }
        
        self._init_ui()
        self._update_step_prompt()
        
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
        
        # 扫码槽位显示区 (动态生成)
        self.slots_frame = QFrame()
        self.slots_frame.setStyleSheet("background-color: #16213E; border-radius: 10px; padding: 15px;")
        slots_layout = QVBoxLayout(self.slots_frame)
        
        self.lbl_ch_info = QLabel("测试通道: --")
        self.lbl_ch_info.setStyleSheet("font-size: 22px; font-weight: bold; color: #00E5FF;")
        self.lbl_ch_info.setAlignment(Qt.AlignCenter)
        slots_layout.addWidget(self.lbl_ch_info)
        
        # 货架码槽位
        self.slot_shelf = self._create_slot_widget("货架编号 [必扫]")
        slots_layout.addWidget(self.slot_shelf)
        
        # 主机码槽位
        self.slot_master = self._create_slot_widget("主机编码 [必扫]")
        slots_layout.addWidget(self.slot_master)
        
        # 从机码槽位 (根据 slaves_count 动态添加)
        self.slave_slots = []
        for i in range(self.slaves_count):
            slot = self._create_slot_widget(f"从机编码 #{i+1}")
            slots_layout.addWidget(slot)
            self.slave_slots.append(slot)
            
        layout.addWidget(self.slots_frame)
        
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

    def _create_slot_widget(self, title):
        frame = QFrame()
        frame.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 5px; padding: 5px;")
        lyt = QHBoxLayout(frame)
        
        lbl_title = QLabel(title)
        lbl_title.setFixedWidth(120)
        lbl_title.setStyleSheet("color: #AAAAAA; font-weight: bold;")
        lyt.addWidget(lbl_title)
        
        lbl_val = QLabel("--")
        lbl_val.setStyleSheet("font-size: 16px; color: #FFFFFF; font-family: 'Consolas';")
        lyt.addWidget(lbl_val)
        
        frame.title_label = lbl_title
        frame.val_label = lbl_val
        return frame

    def parse_shelf_code(self, code):
        """
        货架码规则: XX-YZZ (如 01-A02)
        01-A01 -> CH-01, 01-A16 -> CH-16
        01-B01 -> CH-17, 01-B16 -> CH-32
        01-C01 -> CH-33, 01-C16 -> CH-48
        CH-49及以上禁用
        """
        match = re.match(r"^(\d{2})-([ABC])(\d{2})$", code)
        if not match:
            return -1
        cabinet, car, slot = match.groups()
        if cabinet != "01": # 目前固定为1号
            return -1
        
        slot_num = int(slot)
        if not (1 <= slot_num <= 16):
            return -1
            
        offset = {"A": 0, "B": 16, "C": 32}
        channel_id = offset[car] + slot_num
        
        if channel_id > 48:
            return -1
            
        return channel_id

    def _update_step_prompt(self):
        """根据当前状态更新顶部提示语"""
        if self.target_channel == -1:
            self.lbl_step.setText("🔍 [第一步] 请扫描【货架二维码】")
            self.lbl_step.setStyleSheet("color: #00E5FF; font-size: 22px; font-weight: bold;")
        elif not self.master_code:
            self.lbl_step.setText("🔍 [第二步] 请扫描【主机条码】")
            self.lbl_step.setStyleSheet("color: #FFD700; font-size: 22px; font-weight: bold;")
        elif len(self.slave_codes) < self.slaves_count:
            curr = len(self.slave_codes) + 1
            self.lbl_step.setText(f"🔍 [第三步] 请扫描【从机条码】({curr}/{self.slaves_count})")
            self.lbl_step.setStyleSheet("color: #FF8C00; font-size: 22px; font-weight: bold;")
        else:
            self.lbl_step.setText("✅ 扫码完成！正在提交...")
            self.lbl_step.setStyleSheet("color: #00FF00; font-size: 22px; font-weight: bold;")

    def process_scan(self):
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code: return
        
        # 第一步：货架码
        if self.target_channel == -1:
            ch_id = self.parse_shelf_code(code)
            if ch_id != -1:
                self.target_channel = ch_id
                self.shelf_code = code
                self.lbl_ch_info.setText(f"测试通道: CH-{self.target_channel:02d}")
                self.slot_shelf.val_label.setText(code)
                self.slot_shelf.val_label.setStyleSheet("font-size: 18px; color: #00FF00; font-weight: bold; font-family: 'Consolas';")
                self.slot_shelf.setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 5px;")
                self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 货架码不符规则: {code}")
                self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 20px;")
            return

        # 第二步：主机码
        if not self.master_code:
            if re.match(self.rules["master"], code):
                self.master_code = code
                self.slot_master.val_label.setText(code)
                self.slot_master.val_label.setStyleSheet("font-size: 18px; color: #00FF00; font-weight: bold; font-family: 'Consolas';")
                self.slot_master.setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 5px;")
                
                if self.slaves_count == 0:
                    self.finalize_scan()
                else:
                    self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 主机码不符规则")
            return

        # 第三步：从机码
        if len(self.slave_codes) < self.slaves_count:
            if re.match(self.rules["slave"], code):
                idx = len(self.slave_codes)
                self.slave_codes.append(code)
                
                self.slave_slots[idx].val_label.setText(code)
                self.slave_slots[idx].val_label.setStyleSheet("font-size: 18px; color: #00FF00; font-weight: bold; font-family: 'Consolas';")
                self.slave_slots[idx].setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 5px;")
                
                if len(self.slave_codes) == self.slaves_count:
                    self.finalize_scan()
                else:
                    self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 从机码不符规则")
            return

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
        
        self.slot_shelf.val_label.setText("--")
        self.slot_shelf.val_label.setStyleSheet("font-size: 16px; color: #FFFFFF; font-family: 'Consolas';")
        self.slot_shelf.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 5px;")
        
        self.slot_master.val_label.setText("--")
        self.slot_master.val_label.setStyleSheet("font-size: 16px; color: #FFFFFF; font-family: 'Consolas';")
        self.slot_master.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 5px;")
        
        for slot in self.slave_slots:
            slot.val_label.setText("--")
            slot.val_label.setStyleSheet("font-size: 16px; color: #FFFFFF; font-family: 'Consolas';")
            slot.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 5px;")
            
        self._update_step_prompt()
        self.scan_input.setFocus()
