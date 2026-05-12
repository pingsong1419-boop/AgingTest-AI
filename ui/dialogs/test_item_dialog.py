from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QDoubleSpinBox, QComboBox)

class TestItemDialog(QDialog):
    """
    测试项编辑对话框 (包含判定范围和 NG 策略)
    """
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("编辑测试项 (判定条件)")
        self.setFixedSize(350, 380) # 稍微增加高度以容纳策略下拉框
        self.setStyleSheet("background-color: #1F1F35; color: white;")
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("测试项名称:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如: 放电电量测试")
        layout.addWidget(self.name_edit)
        
        layout.addWidget(QLabel("判定下限 (Min):"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-99999, 99999)
        self.min_spin.setDecimals(3)
        layout.addWidget(self.min_spin)
        
        layout.addWidget(QLabel("判定上限 (Max):"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-99999, 99999)
        self.max_spin.setDecimals(3)
        layout.addWidget(self.max_spin)

        layout.addWidget(QLabel("NG 停止策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["任何NG停止", "关键NG停止", "NG继续"])
        layout.addWidget(self.strategy_combo)
        
        # 如果传入了数据，则填充
        if data:
            self.name_edit.setText(data.get('name', ''))
            try:
                self.min_spin.setValue(float(data.get('min', 0)))
                self.max_spin.setValue(float(data.get('max', 0)))
            except: pass
            
            strategy = data.get('strategy', '任何NG停止')
            self.strategy_combo.setCurrentText(strategy)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_ok.setStyleSheet("background-color: #28A745;")
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("取消")
        btn_layout.addWidget(self.btn_cancel)
        self.btn_cancel.clicked.connect(self.reject)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            'name': self.name_edit.text(),
            'min': self.min_spin.value(),
            'max': self.max_spin.value(),
            'strategy': self.strategy_combo.currentText()
        }
