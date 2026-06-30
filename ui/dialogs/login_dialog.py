import sys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox)
from PySide6.QtCore import Qt

class LoginDialog(QDialog):
    """
    高级权限登录验证弹窗 (用户名选择 + 密码输入)
    """
    def __init__(self, users_dict: dict, parent=None):
        super().__init__(parent)
        self.users_dict = users_dict or {}
        self.selected_user = None
        
        self.setWindowTitle("高级权限验证")
        self.setFixedSize(350, 180)
        self.setModal(True)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 提示语
        tip_lbl = QLabel("请选择高级账号并输入密码解锁权限：")
        tip_lbl.setStyleSheet("color: #CCCCCC; font-size: 13px; font-weight: bold;")
        layout.addWidget(tip_lbl)
        
        # 用户名选择
        user_layout = QHBoxLayout()
        user_lbl = QLabel("用户名:")
        user_lbl.setMinimumWidth(50)
        user_lbl.setStyleSheet("color: #FFFFFF;")
        
        self.combo_user = QComboBox()
        self.combo_user.setMinimumHeight(28)
        self.combo_user.setStyleSheet("""
            QComboBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding-left: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #2D2D30;
                color: #FFFFFF;
                selection-background-color: #007ACC;
            }
        """)
        
        # 筛选出 role 为 admin 或 engineer 的高级账号
        advanced_users = []
        for uname, uinfo in self.users_dict.items():
            if isinstance(uinfo, dict) and uinfo.get("role") in ["admin", "engineer"]:
                advanced_users.append(uname)
        
        # 排序，保证 admin 永远在最上面，接着是其他账号
        advanced_users.sort(key=lambda x: (0 if x == "admin" else 1, x))
        
        self.combo_user.addItems(advanced_users)
        user_layout.addWidget(user_lbl)
        user_layout.addWidget(self.combo_user)
        layout.addLayout(user_layout)
        
        # 密码输入
        pwd_layout = QHBoxLayout()
        pwd_lbl = QLabel("密  码:")
        pwd_lbl.setMinimumWidth(50)
        pwd_lbl.setStyleSheet("color: #FFFFFF;")
        
        self.edit_pwd = QLineEdit()
        self.edit_pwd.setEchoMode(QLineEdit.Password)
        self.edit_pwd.setMinimumHeight(28)
        self.edit_pwd.setPlaceholderText("请输入密码")
        self.edit_pwd.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding-left: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #007ACC;
            }
        """)
        pwd_layout.addWidget(pwd_lbl)
        pwd_layout.addWidget(self.edit_pwd)
        layout.addLayout(pwd_layout)
        
        layout.addSpacing(5)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        
        self.btn_login = QPushButton("验证登录")
        self.btn_login.setMinimumHeight(30)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.btn_login.clicked.connect(self.handle_login)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumHeight(30)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: #FFFFFF;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def handle_login(self):
        uname = self.combo_user.currentText()
        pwd = self.edit_pwd.text().strip()
        
        if not uname:
            QMessageBox.warning(self, "提示", "请选择要登录的用户名！")
            return
            
        uinfo = self.users_dict.get(uname)
        if isinstance(uinfo, dict) and uinfo.get("password") == pwd:
            self.selected_user = uname
            self.accept()
        else:
            QMessageBox.critical(self, "验证失败", "密码错误，请重新输入！")
