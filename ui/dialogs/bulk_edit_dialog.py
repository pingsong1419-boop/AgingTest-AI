from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QComboBox, QCheckBox, QGroupBox)
from PySide6.QtCore import Qt

class BulkEditDialog(QDialog):
    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量修改工步参数")
        self.setMinimumWidth(400)
        self.devices = devices
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 过滤条件
        filter_group = QGroupBox("1. 筛选范围")
        filter_layout = QVBoxLayout(filter_group)
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("限定设备:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["-- 全部设备 --"] + self.devices)
        h1.addWidget(self.device_combo)
        filter_layout.addLayout(h1)
        
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("工步动作包含:"))
        self.action_filter = QLineEdit()
        self.action_filter.setPlaceholderText("如：设置、读取 (留空表示不限)")
        h2.addWidget(self.action_filter)
        filter_layout.addLayout(h2)
        
        layout.addWidget(filter_group)
        
        # 2. 修改内容
        edit_group = QGroupBox("2. 修改操作")
        edit_layout = QVBoxLayout(edit_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["查找并替换参数字符串", "统一设置参数值为...", "统一修改失败策略为..."])
        edit_layout.addWidget(self.mode_combo)
        
        self.input_find = QLineEdit()
        self.input_find.setPlaceholderText("查找内容 (仅替换模式有效)")
        edit_layout.addWidget(self.input_find)
        
        self.input_replace = QLineEdit()
        self.input_replace.setPlaceholderText("替换为 / 设置为...")
        edit_layout.addWidget(self.input_replace)
        
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["失败停止", "忽略继续", "重试3次"])
        self.strategy_combo.hide()
        edit_layout.addWidget(self.strategy_combo)
        
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        
        layout.addWidget(edit_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("执行修改")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #28A745; color: white; height: 30px;")
        
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _on_mode_changed(self, index):
        self.input_find.setVisible(index == 0)
        self.input_replace.setVisible(index < 2)
        self.strategy_combo.setVisible(index == 2)

    def get_config(self):
        return {
            "device_filter": self.device_combo.currentText(),
            "action_filter": self.action_filter.text(),
            "mode": self.mode_combo.currentIndex(),
            "find_text": self.input_find.text(),
            "replace_text": self.input_replace.text(),
            "strategy": self.strategy_combo.currentText()
        }
