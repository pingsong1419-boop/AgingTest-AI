import re
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget
from PySide6.QtCore import Qt

class BarcodeLearnDialog(QDialog):
    def __init__(self, parent=None, title="智能学习条码规则 (多样本对比)"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(480, 420)
        self.setStyleSheet("background-color: #1A1A2E; color: white;")
        self.generated_regex = ""
        self.samples = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        lbl_hint = QLabel("请使用扫码枪连续扫描 2 个以上的不同实物条码：")
        lbl_hint.setStyleSheet("font-size: 14px; font-weight: bold; color: #00E5FF;")
        layout.addWidget(lbl_hint)
        
        self.scan_input = QLineEdit()
        self.scan_input.setFixedHeight(45)
        self.scan_input.setPlaceholderText(">>> 等待扫码输入 <<<")
        self.scan_input.setStyleSheet("""
            QLineEdit {
                font-size: 18px; 
                background-color: #0F2A1A; 
                border: 2px solid #00FF00;
                font-weight: bold;
                padding-left: 10px;
            }
        """)
        self.scan_input.returnPressed.connect(self.process_scan)
        layout.addWidget(self.scan_input)
        
        self.lbl_samples_status = QLabel("已采集样本: 0")
        self.lbl_samples_status.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.lbl_samples_status)
        
        self.list_samples = QListWidget()
        self.list_samples.setFixedHeight(80)
        self.list_samples.setStyleSheet("""
            QListWidget {
                background-color: #2A2A3E; 
                border: 1px solid #5A5A5A;
                font-size: 14px;
                color: #FFFFFF;
                padding: 4px;
            }
        """)
        layout.addWidget(self.list_samples)
        
        lbl_res_hint = QLabel("智能推演出的正则表达式：")
        lbl_res_hint.setStyleSheet("margin-top: 10px; color: #AAAAAA;")
        layout.addWidget(lbl_res_hint)
        
        self.regex_output = QLineEdit()
        self.regex_output.setFixedHeight(40)
        self.regex_output.setReadOnly(True)
        self.regex_output.setStyleSheet("font-size: 16px; background-color: #2A2A3E; border: 1px solid #5A5A5A; color: #FFD700;")
        layout.addWidget(self.regex_output)
        
        btn_layout = QHBoxLayout()
        self.btn_confirm = QPushButton("✅ 确认使用此规则")
        self.btn_confirm.setFixedHeight(40)
        self.btn_confirm.setAutoDefault(False)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #28A745; 
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        self.btn_confirm.clicked.connect(self.accept)
        self.btn_confirm.setEnabled(False)
        
        self.btn_clear = QPushButton("🗑 清空重来")
        self.btn_clear.setFixedHeight(40)
        self.btn_clear.setAutoDefault(False)
        self.btn_clear.setStyleSheet("background-color: #FF8C00; font-weight: bold; font-size: 14px;")
        self.btn_clear.clicked.connect(self.clear_samples)
        
        btn_cancel = QPushButton("❌ 取消")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setAutoDefault(False)
        btn_cancel.setStyleSheet("background-color: #DC3545; font-weight: bold; font-size: 14px;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def keyPressEvent(self, event):
        # 强制把所有按键事件（包括扫码枪输入的字符）抓取到输入框
        if not self.scan_input.hasFocus():
            self.scan_input.setFocus()
        super().keyPressEvent(event)

    def clear_samples(self):
        self.samples.clear()
        self.list_samples.clear()
        self.lbl_samples_status.setText("已采集样本: 0")
        self.regex_output.clear()
        self.generated_regex = ""
        self.btn_confirm.setEnabled(False)
        self.scan_input.setFocus()

    def process_scan(self):
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code: return
        
        if code not in self.samples:
            self.samples.append(code)
            self.list_samples.addItem(f"{len(self.samples)}. {code}")
            
        self.lbl_samples_status.setText(f"已采集样本: {len(self.samples)}")
        
        self.generated_regex = self.infer_regex(self.samples)
        self.regex_output.setText(self.generated_regex)
        
        if len(self.samples) >= 1:
            self.btn_confirm.setEnabled(True)

    def infer_regex(self, samples):
        if not samples: return ""
        
        if len(samples) == 1:
            code = samples[0]
            match = re.match(r"^([a-zA-Z_-]+)(\d*)$", code)
            if match:
                prefix = re.escape(match.group(1))
                return f"^{prefix}\\d{{{len(match.group(2))}}}$" if match.group(2) else f"^{prefix}.*"
            if code.isdigit():
                return f"^\\d{{{len(code)}}}$"
            return f"^.{{{len(code)}}}$"
            
        # 多样本交叉比对
        prefix = os.path.commonprefix(samples)
        
        # 智能边界向左回退：如果差异部分切分在数字中，把连续数字都归为变动部分
        while prefix and prefix[-1].isdigit():
            prefix = prefix[:-1]
            
        # 找公共后缀
        rev_samples = [s[::-1] for s in samples]
        suffix_rev = os.path.commonprefix(rev_samples)
        suffix = suffix_rev[::-1]
        
        # 同样，后缀若切分在数字中，向右回退
        while suffix and suffix[0].isdigit():
            suffix = suffix[1:]
            
        # 提取各个样本的中间变动部分
        var_parts = []
        for s in samples:
            if len(prefix) + len(suffix) <= len(s):
                if suffix:
                    var_parts.append(s[len(prefix):-len(suffix)])
                else:
                    var_parts.append(s[len(prefix):])
            else:
                var_parts.append("") # 极端异常降级
                
        # 分析中间变动部分的类型与长度
        if all(v.isdigit() for v in var_parts if v):
            lengths = set(len(v) for v in var_parts if v)
            if len(lengths) == 1:
                var_pattern = f"\\d{{{lengths.pop()}}}"
            else:
                var_pattern = "\\d+"
        elif all(v.isalpha() for v in var_parts if v):
            lengths = set(len(v) for v in var_parts if v)
            if len(lengths) == 1:
                var_pattern = f"[A-Za-z]{{{lengths.pop()}}}"
            else:
                var_pattern = "[A-Za-z]+"
        else:
            lengths = set(len(v) for v in var_parts if v)
            if len(lengths) == 1:
                var_pattern = f".{{{lengths.pop()}}}"
            else:
                var_pattern = ".*"
                
        escaped_prefix = re.escape(prefix)
        escaped_suffix = re.escape(suffix)
        return f"^{escaped_prefix}{var_pattern}{escaped_suffix}$"
