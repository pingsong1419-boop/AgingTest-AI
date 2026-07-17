import sys
import os
import faulthandler
import traceback
from datetime import datetime
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

_crash_log_file = None

def setup_crash_logging():
    global _crash_log_file
    base_dir = os.path.abspath(os.path.dirname(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"runtime_crash_{datetime.now():%Y%m%d_%H%M%S}.log")
    _crash_log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    _crash_log_file.write(f"[START] {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    _crash_log_file.flush()
    faulthandler.enable(file=_crash_log_file, all_threads=True)

    def excepthook(exc_type, exc_value, exc_tb):
        _crash_log_file.write("[UNCAUGHT_EXCEPTION]\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_crash_log_file)
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook

def main():
    setup_crash_logging()
    
    # --- 开启终端通讯交互监控日志 ---
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stdout
    )
    # 对于过多杂乱的日志可以稍微过滤，但目前全开DEBUG以捕获PyModbus的TX/RX
    logging.getLogger('pymodbus').setLevel(logging.DEBUG)

    app = QApplication(sys.argv)
    
    # 加载全局工业风深色样式
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        
    qss_path = os.path.join(base_dir, "resources", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    # 实例化主窗口并显示
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
