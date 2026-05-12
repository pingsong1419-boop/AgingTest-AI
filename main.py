import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # 加载全局工业风深色样式
    import os
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    # 实例化主窗口并显示
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
