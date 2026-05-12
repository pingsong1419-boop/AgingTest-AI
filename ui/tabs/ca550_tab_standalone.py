import sys
import time
import queue
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QPushButton, QLabel, QGroupBox, QDoubleSpinBox, 
                                QComboBox, QTextEdit, QFrame, QCheckBox, QScrollArea, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt, QTimer, QThread, Signal

# --- 顺序执行工作线程 ---

class CA550SerialWorker(QThread):
    """
    单线程串口工作者，确保所有指令按顺序下发，避免冲突。
    """
    response_received = Signal(str, str, object) # action, response, args
    
    def __init__(self, driver):
        super().__init__()
        self.driver = driver
        self.task_queue = queue.Queue()
        self.running = True
        
    def add_task(self, action, *args):
        self.task_queue.put((action, args))
        
    def run(self):
        while self.running:
            try:
                # 获取任务 (阻塞 0.1s 以便检查 running 状态)
                try:
                    action, args = self.task_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # 执行指令
                func = getattr(self.driver, action)
                res = func(*args)
                
                # 返回结果
                self.response_received.emit(action, str(res), args)
                self.task_queue.task_done()
                
                # 指令间强制停顿，给硬件喘息机会
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[Worker] 运行时异常: {e}")

    def stop(self):
        self.running = False
        self.wait()

class CA550StandaloneTab(QWidget):
    def __init__(self, driver):
        super().__init__()
        self.setWindowTitle("CA550 校准仪高级调试界面 (顺序队列版)")
        self.resize(1000, 800)
        
        self.ca550 = driver
        # 初始化单线程 Worker
        self.worker = CA550SerialWorker(self.ca550)
        self.worker.response_received.connect(self.on_response)
        self.worker.start()
        
        self._init_ui()
        
        # 定时更新回读信息
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.periodic_update)
        self.timer.start(2000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        content_layout = QGridLayout(content_widget)
        content_layout.setSpacing(15)

        # --- 1. 串口配置 ---
        group_comm = QGroupBox("串口通讯配置 (顺序执行)")
        comm_layout = QGridLayout()
        comm_layout.addWidget(QLabel("串口号:"), 0, 0)
        self.edit_port = QLineEdit(self.ca550.port)
        comm_layout.addWidget(self.edit_port, 0, 1)
        
        comm_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.edit_baud = QLineEdit(str(self.ca550.baudrate))
        comm_layout.addWidget(self.edit_baud, 1, 1)
        
        comm_layout.addWidget(QLabel("数据位:"), 0, 2)
        self.cb_bits = QComboBox()
        self.cb_bits.addItems(["7", "8"])
        self.cb_bits.setCurrentText("7")
        comm_layout.addWidget(self.cb_bits, 0, 3)
        
        comm_layout.addWidget(QLabel("校验位:"), 1, 2)
        self.cb_parity = QComboBox()
        self.cb_parity.addItems(["None", "Even", "Odd"])
        self.cb_parity.setCurrentText("None")
        comm_layout.addWidget(self.cb_parity, 1, 3)
        
        btn_connect = QPushButton("建立物理连接")
        btn_connect.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; height: 35px;")
        btn_connect.clicked.connect(self.connect_device)
        comm_layout.addWidget(btn_connect, 2, 0)
        
        btn_disconnect = QPushButton("断开物理连接")
        btn_disconnect.clicked.connect(self.disconnect_device)
        comm_layout.addWidget(btn_disconnect, 2, 1)
        
        self.lbl_comm = QLabel("状态: 未连接")
        self.lbl_comm.setStyleSheet("color: #ff4444; font-weight: bold;")
        comm_layout.addWidget(self.lbl_comm, 3, 0, 1, 2)
        
        group_comm.setLayout(comm_layout)
        content_layout.addWidget(group_comm, 0, 0)

        # --- 2. 设备状态与系统设置 ---
        group_info = QGroupBox("设备状态与高级配置")
        info_layout = QGridLayout()
        
        self.lbl_idn = QLabel("型号: --")
        self.lbl_sn = QLabel("序列号: --")
        self.lbl_battery = QLabel("电量: --")
        
        info_layout.addWidget(self.lbl_idn, 0, 0)
        info_layout.addWidget(self.lbl_sn, 0, 1)
        info_layout.addWidget(self.lbl_battery, 1, 0)
        
        btn_sync = QPushButton("全量同步设备信息")
        btn_sync.clicked.connect(self.sync_info)
        info_layout.addWidget(btn_sync, 2, 0, 1, 2)
        
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        info_layout.addWidget(line, 3, 0, 1, 2)
        
        # 系统开关
        self.chk_bl = QCheckBox("背光 (BL)"); self.chk_bl.clicked.connect(lambda: self.worker.add_task("set_backlight", 1 if self.chk_bl.isChecked() else 0))
        self.chk_vo = QCheckBox("24V电源 (VO)"); self.chk_vo.clicked.connect(lambda: self.worker.add_task("set_24v_power", 1 if self.chk_vo.isChecked() else 0))
        self.chk_io = QCheckBox("250Ω电阻 (IO)"); self.chk_io.clicked.connect(lambda: self.worker.add_task("set_250_resistor", 1 if self.chk_io.isChecked() else 0))
        self.chk_bu = QCheckBox("断偶检测 (BU)"); self.chk_bu.clicked.connect(lambda: self.worker.add_task("set_break_detection", 1 if self.chk_bu.isChecked() else 0))
        
        info_layout.addWidget(self.chk_bl, 4, 0)
        info_layout.addWidget(self.chk_vo, 4, 1)
        info_layout.addWidget(self.chk_io, 5, 0)
        info_layout.addWidget(self.chk_bu, 5, 1)
        
        btn_rc = QPushButton("仪器整机重置 (RC)")
        btn_rc.setStyleSheet("background-color: #661111; color: white; height: 30px;")
        btn_rc.clicked.connect(lambda: self.worker.add_task("full_reset"))
        info_layout.addWidget(btn_rc, 6, 0, 1, 2)
        
        group_info.setLayout(info_layout)
        content_layout.addWidget(group_info, 1, 0)

        # --- 3. 信号源输出 (Source) ---
        group_source = QGroupBox("源输出控制 (Source)")
        src_layout = QGridLayout()
        
        src_layout.addWidget(QLabel("功能:"), 0, 0)
        self.cb_sf = QComboBox()
        self.cb_sf.addItems(["0: DCV", "1: DCA", "2: OHM", "3: RTD", "4: TC", "5: FREQ"])
        src_layout.addWidget(self.cb_sf, 0, 1)
        btn_sf = QPushButton("设置")
        btn_sf.clicked.connect(lambda: self.worker.add_task("set_source_func", self.cb_sf.currentIndex()))
        src_layout.addWidget(btn_sf, 0, 2)
        
        src_layout.addWidget(QLabel("量程:"), 1, 0)
        self.cb_sr = QComboBox()
        self.cb_sr.addItems(["0: 100mV/20mA", "1: 1-5V/4-20mA", "2: 5V", "3: 30V"])
        src_layout.addWidget(self.cb_sr, 1, 1)
        btn_sr = QPushButton("设置")
        btn_sr.clicked.connect(lambda: self.worker.add_task("set_source_range", self.cb_sr.currentIndex()))
        src_layout.addWidget(btn_sr, 1, 2)
        
        src_layout.addWidget(QLabel("设定值:"), 2, 0)
        self.sp_sd = QDoubleSpinBox(); self.sp_sd.setRange(-1000, 30000); self.sp_sd.setDecimals(4)
        src_layout.addWidget(self.sp_sd, 2, 1)
        
        btn_set = QPushButton("下发设定值 (SD)")
        btn_set.setStyleSheet("background-color: #0055aa; color: white; font-weight: bold;")
        btn_set.clicked.connect(lambda: self.worker.add_task("set_source_data", self.sp_sd.value()))
        src_layout.addWidget(btn_set, 3, 0, 1, 3)
        
        self.btn_so = QPushButton("源输出: OFF")
        self.btn_so.setCheckable(True)
        self.btn_so.setFixedHeight(50)
        self.btn_so.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #333; color: white;")
        self.btn_so.clicked.connect(self.toggle_source_output)
        src_layout.addWidget(self.btn_so, 4, 0, 1, 3)
        
        group_source.setLayout(src_layout)
        content_layout.addWidget(group_source, 0, 1)

        # --- 4. 测量控制 (Measure) ---
        group_meas = QGroupBox("测量控制 (Measure)")
        meas_layout = QGridLayout()
        
        meas_layout.addWidget(QLabel("功能:"), 0, 0)
        self.cb_mf = QComboBox()
        self.cb_mf.addItems(["0: DCV", "1: DCA", "2: OHM", "3: RTD", "4: TC", "5: FREQ"])
        meas_layout.addWidget(self.cb_mf, 0, 1)
        btn_mf = QPushButton("设置")
        btn_mf.clicked.connect(lambda: self.worker.add_task("set_measure_func", self.cb_mf.currentIndex()))
        meas_layout.addWidget(btn_mf, 0, 2)
        
        meas_layout.addWidget(QLabel("接线:"), 1, 0)
        self.cb_wc = QComboBox()
        self.cb_wc.addItems(["0: 2线", "1: 3线", "2: 4线"])
        meas_layout.addWidget(self.cb_wc, 1, 1)
        btn_wc = QPushButton("设置")
        btn_wc.clicked.connect(lambda: self.worker.add_task("set_wiring", self.cb_wc.currentIndex()))
        meas_layout.addWidget(btn_wc, 1, 2)
        
        self.btn_mo = QPushButton("开始测量 (MO)")
        self.btn_mo.setCheckable(True)
        self.btn_mo.clicked.connect(self.toggle_measure_state)
        meas_layout.addWidget(self.btn_mo, 2, 0, 1, 3)
        
        self.lbl_od = QLabel("---")
        self.lbl_od.setStyleSheet("font-size: 36px; font-weight: bold; color: #00ff00; background-color: #000; padding: 10px; border: 1px solid #444;")
        self.lbl_od.setAlignment(Qt.AlignCenter)
        meas_layout.addWidget(self.lbl_od, 3, 0, 1, 3)
        
        group_meas.setLayout(meas_layout)
        content_layout.addWidget(group_meas, 1, 1)

        # --- 5. 日志 ---
        group_log = QGroupBox("串口通讯日志")
        log_layout = QVBoxLayout()
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1a1a1a; color: #aaa; font-family: 'Consolas'; font-size: 11px;")
        log_layout.addWidget(self.txt_log)
        btn_clear = QPushButton("清空日志")
        btn_clear.clicked.connect(self.txt_log.clear)
        log_layout.addWidget(btn_clear)
        group_log.setLayout(log_layout)
        content_layout.addWidget(group_log, 2, 0, 1, 2)

    def on_response(self, action, res, args):
        """处理 Worker 返回的结果"""
        timestamp = time.strftime('%H:%M:%S')
        self.txt_log.append(f"[{timestamp}] [RX] 指令 {action} 返回: {res}")
        
        # 限制日志行数
        if self.txt_log.document().blockCount() > 200:
            self.txt_log.clear()

        # 特殊处理连接结果
        if action == "connect":
            if res == "True":
                self.lbl_comm.setText("状态: 已连接 ✅")
                self.lbl_comm.setStyleSheet("color: #00ff00; font-weight: bold;")
                self.sync_info()
            else:
                self.lbl_comm.setText("状态: 连接失败 ❌")
                self.lbl_comm.setStyleSheet("color: #ff4444; font-weight: bold;")
        
        # 处理信息同步
        elif action == "get_idn": self.lbl_idn.setText(f"型号: {res}")
        elif action == "get_sn": self.lbl_sn.setText(f"序列号: {res}")
        elif action == "get_battery": self.lbl_battery.setText(f"电量: {res}")
        
        # 处理测量数据回读
        elif action == "read_measure_data":
            if res and "ERROR" not in res:
                self.lbl_od.setText(res)

    def connect_device(self):
        self.ca550.port = self.edit_port.text().strip()
        try:
            self.ca550.baudrate = int(self.edit_baud.text().strip())
            # 更新驱动参数
            import serial
            self.ca550.bytesize = serial.SEVENBITS if self.cb_bits.currentText() == "7" else serial.EIGHTBITS
            parity_map = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}
            self.ca550.parity = parity_map[self.cb_parity.currentText()]
        except:
            pass
        self.worker.add_task("connect")

    def disconnect_device(self):
        self.worker.add_task("disconnect")
        self.lbl_comm.setText("状态: 已断开")
        self.lbl_comm.setStyleSheet("color: gray; font-weight: bold;")

    def sync_info(self):
        self.worker.add_task("get_idn")
        self.worker.add_task("get_sn")
        self.worker.add_task("get_battery")

    def toggle_source_output(self, checked):
        self.worker.add_task("set_source_output", 1 if checked else 0)
        self.btn_so.setText("源输出: ON" if checked else "源输出: OFF")
        self.btn_so.setStyleSheet(f"font-size: 16px; font-weight: bold; background-color: {'#28a745' if checked else '#333'}; color: white;")

    def toggle_measure_state(self, checked):
        self.worker.add_task("set_measure_state", 1 if checked else 0)
        self.btn_mo.setText("停止测量" if checked else "开始测量")
        self.btn_mo.setStyleSheet(f"background-color: {'#007bff' if checked else ''}; color: {'white' if checked else ''};")

    def periodic_update(self):
        if self.ca550.is_connected and self.btn_mo.isChecked():
            # 只有当队列为空时才添加回读任务，防止任务堆积
            if self.worker.task_queue.empty():
                self.worker.add_task("read_measure_data")

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from devices.ca550_driver import CA550Controller
    driver = CA550Controller("COM5")
    window = CA550StandaloneTab(driver)
    window.show()
    sys.exit(app.exec())
