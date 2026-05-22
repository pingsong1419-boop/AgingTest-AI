from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QListWidget, QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer
import re

class ScanDialog(QDialog):
    """
    扫码入站核心对话框
    工作流：
    1. 扫描货架码 -> 自动匹配通道号 (依据硬件配置表)并填入临时货架编号输入框
    2. 扫描主机码 -> 绑定主 BMS 并填入临时主机编码输入框
    3. 扫描从机码 (根据拓扑配置数量) -> 绑定从 BMS 并填入临时从机编码输入框
    4. 扫完后可手动编辑修改，最后点击“确认提交并入站”或自动延时提交至主界面对应卡片
    """
    scan_completed = Signal(int, str, str, object) # channel_id, shelf, master, slaves

    def __init__(self, parent=None, db_manager=None, slaves_count=0, checked_channels=None, already_completed=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.slaves_count = slaves_count
        self.checked_channels = checked_channels or []
        self.completed_channels = set(already_completed or [])
        
        self.setWindowTitle("扫码入站绑定")
        # 增加整体宽高，留出充裕的垂直视觉空间，防止拥挤
        self.setFixedSize(800, 720)
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
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # 顶部提示
        self.lbl_step = QLabel("请扫描【货架二维码】以定位测试通道")
        self.lbl_step.setStyleSheet("font-size: 16px; font-weight: bold; color: #00E5FF;")
        self.lbl_step.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_step)
        
        # 扫描输入框 (保持焦点)
        self.scan_input = QLineEdit()
        self.scan_input.setFixedHeight(48)
        self.scan_input.setPlaceholderText(">>> 请在此处扫码 <<<")
        self.scan_input.setStyleSheet("""
            QLineEdit {
                font-size: 20px; 
                font-family: 'Consolas', 'Monaco', monospace;
                border: 2px solid #00E5FF; 
                border-radius: 8px; 
                padding: 5px 12px;
                background-color: #0F0F1E;
                color: #00FF00;
            }
        """)
        self.scan_input.returnPressed.connect(self.process_scan)
        layout.addWidget(self.scan_input)
        
        # 扫码槽位显示区 (动态生成)
        self.slots_frame = QFrame()
        self.slots_frame.setStyleSheet("background-color: #16213E; border-radius: 12px;")
        slots_layout = QVBoxLayout(self.slots_frame)
        slots_layout.setContentsMargins(20, 20, 20, 20)
        slots_layout.setSpacing(12)  # 各输入框槽位之间的间距
        
        self.lbl_ch_info = QLabel("测试通道: --")
        self.lbl_ch_info.setStyleSheet("font-size: 20px; font-weight: bold; color: #00E5FF; padding-bottom: 5px;")
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
        btn_layout.setSpacing(15)
        
        btn_style = """
            QPushButton {
                font-size: 14px; 
                padding: 10px 24px; 
                border-radius: 6px; 
                font-weight: bold;
            }
        """
        
        self.btn_submit = QPushButton("确认提交并入站")
        self.btn_submit.setStyleSheet(btn_style + "background-color: #28A745; border: 1px solid #1e7e34; color: white;")
        # 关键修复：禁用 AutoDefault 和 Default 属性，防止 QDialog 拦截 Enter 键误触发提交
        self.btn_submit.setAutoDefault(False)
        self.btn_submit.setDefault(False)
        self.btn_submit.clicked.connect(self.finalize_scan)
        btn_layout.addWidget(self.btn_submit)
        
        self.btn_reset = QPushButton("重置扫码")
        self.btn_reset.setStyleSheet(btn_style + "background-color: #6C757D; border: 1px solid #545b62; color: white;")
        self.btn_reset.setAutoDefault(False)
        self.btn_reset.setDefault(False)
        self.btn_reset.clicked.connect(self.reset_scan)
        btn_layout.addWidget(self.btn_reset)
        
        self.btn_cancel = QPushButton("退出")
        self.btn_cancel.setStyleSheet(btn_style + "background-color: #DC3545; border: 1px solid #bd2130; color: white;")
        self.btn_cancel.setAutoDefault(False)
        self.btn_cancel.setDefault(False)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.scan_input.setFocus()

    def _create_slot_widget(self, title):
        frame = QFrame()
        frame.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 6px;")
        
        lyt = QHBoxLayout(frame)
        # 关键修复：显式设定 Slot 卡片内部布局的边距，防止默认大边距导致垂直挤压
        lyt.setContentsMargins(12, 6, 12, 6)
        lyt.setSpacing(10)
        
        lbl_title = QLabel(title)
        lbl_title.setFixedWidth(140)
        lbl_title.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        lyt.addWidget(lbl_title)
        
        val_input = QLineEdit()
        val_input.setPlaceholderText("等待扫码输入...")
        val_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px; 
                color: #FFFFFF; 
                font-family: 'Consolas', monospace;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #1F1F35;
            }
            QLineEdit:focus {
                border: 1px solid #00E5FF;
            }
        """)
        lyt.addWidget(val_input)
        
        frame.title_label = lbl_title
        frame.val_input = val_input
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
        """根据当前状态更新顶部提示语并进行语音播报"""
        if self.target_channel == -1:
            self.lbl_step.setText("🔍 [第一步] 请扫描【货架二维码】")
            self.lbl_step.setStyleSheet("color: #00E5FF; font-size: 22px; font-weight: bold;")
            speak_msg = "请扫描货架二维码"
        elif not self.master_code:
            self.lbl_step.setText("🔍 [第二步] 请扫描【主机条码】")
            self.lbl_step.setStyleSheet("color: #FFD700; font-size: 22px; font-weight: bold;")
            speak_msg = "请扫描主机条码"
        elif len(self.slave_codes) < self.slaves_count:
            curr = len(self.slave_codes) + 1
            self.lbl_step.setText(f"🔍 [第三步] 请扫描【从机条码】({curr}/{self.slaves_count})")
            self.lbl_step.setStyleSheet("color: #FF8C00; font-size: 22px; font-weight: bold;")
            speak_msg = f"请扫描从机条码{curr}"
        else:
            self.lbl_step.setText("✅ 扫码完成！可确认提交")
            self.lbl_step.setStyleSheet("color: #00FF00; font-size: 22px; font-weight: bold;")
            speak_msg = "扫码完成"
            
        self.speak_text(speak_msg)

    def process_scan(self):
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code: return
        
        # 第一步：货架码
        if self.target_channel == -1:
            ch_id = self.parse_shelf_code(code)
            if ch_id != -1:
                # 校验是否是已勾选通道
                if self.checked_channels and ch_id not in self.checked_channels:
                    self.lbl_step.setText(f"❌ 通道 CH-{ch_id:02d} 未勾选，无法扫码入站！")
                    self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 20px;")
                    self.speak_text("该通道未勾选")
                    return
                
                self.target_channel = ch_id
                self.shelf_code = code
                self.lbl_ch_info.setText(f"测试通道: CH-{self.target_channel:02d}")
                self.slot_shelf.val_input.setText(code)
                self.slot_shelf.val_input.setStyleSheet("""
                    QLineEdit {
                        font-size: 14px; 
                        color: #00FF00; 
                        font-weight: bold; 
                        font-family: 'Consolas', monospace;
                        border: 2px solid #00FF00;
                        background-color: #0F2A1A;
                    }
                """)
                self.slot_shelf.setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 6px;")
                self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 货架码不符规则: {code}")
                self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 20px;")
                self.speak_text("条码规则不符合要求")
            return

        # 第二步：主机码
        if not self.master_code:
            if re.match(self.rules["master"], code):
                self.master_code = code
                self.slot_master.val_input.setText(code)
                self.slot_master.val_input.setStyleSheet("""
                    QLineEdit {
                        font-size: 14px; 
                        color: #00FF00; 
                        font-weight: bold; 
                        font-family: 'Consolas', monospace;
                        border: 2px solid #00FF00;
                        background-color: #0F2A1A;
                    }
                """)
                self.slot_master.setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 6px;")
                
                if self.slaves_count == 0:
                    self.finalize_scan()
                else:
                    self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 主机码不符规则")
                self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 20px;")
                self.speak_text("条码规则不符合要求")
            return

        # 第三步：从机码
        if len(self.slave_codes) < self.slaves_count:
            if re.match(self.rules["slave"], code):
                idx = len(self.slave_codes)
                self.slave_codes.append(code)
                
                self.slave_slots[idx].val_input.setText(code)
                self.slave_slots[idx].val_input.setStyleSheet("""
                    QLineEdit {
                        font-size: 14px; 
                        color: #00FF00; 
                        font-weight: bold; 
                        font-family: 'Consolas', monospace;
                        border: 2px solid #00FF00;
                        background-color: #0F2A1A;
                    }
                """)
                self.slave_slots[idx].setStyleSheet("background-color: #0F2A1A; border: 2px solid #00FF00; border-radius: 6px;")
                
                if len(self.slave_codes) == self.slaves_count:
                    self.finalize_scan()
                else:
                    self._update_step_prompt()
            else:
                self.lbl_step.setText(f"❌ 从机码不符规则")
                self.lbl_step.setStyleSheet("color: #FF4D4D; font-size: 20px;")
                self.speak_text("条码规则不符合要求")
            return

    def finalize_scan(self):
        # 从输入框获取最终的条码数据（以防用户进行了手动修改）
        shelf = self.slot_shelf.val_input.text().strip()
        master = self.slot_master.val_input.text().strip()
        slaves = [slot.val_input.text().strip() for slot in self.slave_slots]
        
        # 校验最基本的必填项
        if not shelf:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验失败", "货架编号不能为空！")
            return
        if not master:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验失败", "主机编码不能为空！")
            return
        for i, sv in enumerate(slaves):
            if not sv:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "校验失败", f"从机编码 #{i+1} 不能为空！")
                return

        # 如果用户修改了货架号，需要重新解析通道ID
        ch_id = self.parse_shelf_code(shelf)
        if ch_id == -1:
            self.speak_text("条码规则不符合要求")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验失败", f"货架编号不符合规则，无法解析通道号！")
            return
            
        if self.checked_channels and ch_id not in self.checked_channels:
            self.speak_text("该通道未勾选")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验失败", f"通道 CH-{ch_id:02d} 未勾选，无法入站！")
            return
            
        self.target_channel = ch_id

        self.lbl_step.setText("✅ 扫码匹配成功！正在入站...")
        self.lbl_step.setStyleSheet("color: #00FF00; font-size: 22px; font-weight: bold;")
        
        print(f"[DEBUG] finalize_scan: emitting scan_completed signal for channel {self.target_channel}")
        print(f"[DEBUG] parameters: shelf={shelf}, master={master}, slaves={slaves}")
        # 发射信号将条码下发并填充到主界面对应的卡片条码框
        self.scan_completed.emit(self.target_channel, shelf, master, slaves)
        print(f"[DEBUG] finalize_scan: scan_completed signal emitted successfully!")
        # 记录已完成的通道
        self.completed_channels.add(self.target_channel)
        
        # 检查是否所有勾选通道都已完成
        all_completed = True
        for ch in self.checked_channels:
            if ch not in self.completed_channels:
                all_completed = False
                break
                
        if all_completed:
            self.speak_text("全部通道扫码完成")
            QTimer.singleShot(1500, self.accept)
        else:
            # 自动重置以准备下一个货架的扫描绑定
            QTimer.singleShot(1500, self.reset_scan)

    def reset_scan(self):
        self.target_channel = -1
        self.shelf_code = ""
        self.master_code = ""
        self.slave_codes = []
        
        self.lbl_ch_info.setText("测试通道: --")
        
        self.slot_shelf.val_input.setText("")
        self.slot_shelf.val_input.setPlaceholderText("等待扫码输入...")
        self.slot_shelf.val_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px; 
                color: #FFFFFF; 
                font-family: 'Consolas', monospace;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #1F1F35;
            }
            QLineEdit:focus {
                border: 1px solid #00E5FF;
            }
        """)
        self.slot_shelf.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 6px;")
        
        self.slot_master.val_input.setText("")
        self.slot_master.val_input.setPlaceholderText("等待扫码输入...")
        self.slot_master.val_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px; 
                color: #FFFFFF; 
                font-family: 'Consolas', monospace;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #1F1F35;
            }
            QLineEdit:focus {
                border: 1px solid #00E5FF;
            }
        """)
        self.slot_master.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 6px;")
        
        for slot in self.slave_slots:
            slot.val_input.setText("")
            slot.val_input.setPlaceholderText("等待扫码输入...")
            slot.val_input.setStyleSheet("""
                QLineEdit {
                    font-size: 14px; 
                    color: #FFFFFF; 
                    font-family: 'Consolas', monospace;
                    border: 1px solid #3E3E5C;
                    border-radius: 4px;
                    padding: 4px 8px;
                    background-color: #1F1F35;
                }
                QLineEdit:focus {
                    border: 1px solid #00E5FF;
                }
            """)
            slot.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 6px;")
            
        self._update_step_prompt()
        self.scan_input.setFocus()

    def speak_text(self, text):
        import threading
        import subprocess
        def run():
            cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 4; $synth.Speak('{text}')"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=run, daemon=True).start()
