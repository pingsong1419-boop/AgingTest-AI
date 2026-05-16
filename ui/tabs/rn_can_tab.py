import time
import os
import csv
import threading
from datetime import datetime
from typing import List, Dict

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
                             QFileDialog, QCheckBox, QSpinBox, QProgressBar, QGridLayout)
from PySide6.QtCore import Qt, QTimer, Slot, QThread, Signal
from PySide6.QtGui import QColor, QFont

from devices.manager import DeviceManager

class ConfigWorker(QThread):
    finished = Signal(bool, str)
    def __init__(self, ip, modbus_port, channel, mode, nom_baud, data_baud):
        super().__init__()
        self.ip = ip
        self.port = modbus_port
        self.channel = channel # 0=CAN1, 1=CAN2
        self.mode = mode
        self.nom_baud = nom_baud
        self.data_baud = data_baud
        
    def run(self):
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(self.ip, port=self.port, timeout=2)
            if client.connect():
                # 基础偏移: CAN1=0x0120, CAN2=0x0160
                offset = 0x0120 if self.channel == 0 else 0x0160
                
                # 1. 启用通道
                client.write_register(offset + 0, 1)
                # 2. 设置模式
                client.write_register(offset + 1, self.mode)
                # 3. 设置波特率模式为标准预设 (0)
                client.write_register(offset + 2, 0)
                # 4. 设置仲裁段波特率
                client.write_register(offset + 3, self.nom_baud)
                # 5. 设置数据段波特率
                client.write_register(offset + 4, self.data_baud)
                
                # 6. 保存到 Flash (CMD=0x0004)
                client.write_register(0x0401, 0) # ARG=0
                client.write_register(0x0400, 0x0004) # CMD=Save
                
                client.close()
                self.finished.emit(True, "配置已成功下发并保存到 Flash")
            else:
                self.finished.emit(False, "无法连接到设备的 Modbus 端口 (502)")
        except Exception as e:
            self.finished.emit(False, f"配置异常: {e}")

class ConnectWorker(QThread):
    finished = Signal(bool)
    def __init__(self, driver, ip, port):
        super().__init__()
        self.driver = driver
        self.ip = ip
        self.port = port
    def run(self):
        res = self.driver.connect(self.ip, self.port)
        self.finished.emit(res)

class MessageWorker(QThread):
    def __init__(self, driver, channel, can_id, can_type, dlc, data, repeats, interval_ms):
        super().__init__()
        self.driver = driver
        self.channel, self.can_id, self.can_type, self.dlc, self.data = channel, can_id, can_type, dlc, data
        self.repeats = repeats
        self.interval = interval_ms / 1000.0
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        count = 0
        while self._running:
            if self.repeats > 0 and count >= self.repeats:
                break
            self.driver.send_can_message(self.channel, self.can_id, self.can_type, self.dlc, self.data)
            count += 1
            if self.repeats == 0 or count < self.repeats:
                time.sleep(self.interval)
            else:
                break

class ListSendWorker(QThread):
    finished = Signal()
    progress = Signal(int, int)
    
    def __init__(self, driver, message_list: List[Dict], global_cycles: int):
        super().__init__()
        self.driver = driver
        self.message_list = message_list
        self.global_cycles = global_cycles
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        cycle = 0
        while self._running:
            if self.global_cycles > 0 and cycle >= self.global_cycles:
                break
            for i, msg in enumerate(self.message_list):
                if not self._running: break
                self.progress.emit(i, len(self.message_list))
                for r in range(msg['repeats']):
                    if not self._running: break
                    self.driver.send_can_message(msg['channel'], msg['id'], msg['type'], msg['dlc'], msg['data'])
                    if r < msg['repeats'] - 1:
                        time.sleep(msg['interval'] / 1000.0)
                time.sleep(0.001) 
            cycle += 1
        self.finished.emit()

class RNCANTab(QWidget):
    def __init__(self, device_manager: DeviceManager):
        super().__init__()
        self.device_manager = device_manager
        # 默认使用 1 号板卡
        self.current_board = device_manager.boards.get(1)
        self.driver = self.current_board.can if self.current_board else None
        
        self.is_logging = False
        self.log_file = None
        self.log_writer = None
        self.log_format = "CSV"
        self.start_time = time.time()
        
        self.parallel_workers = []
        self.sequential_worker = None
        
        self.init_ui()
        
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_monitor)
        self.ui_timer.start(100) # 优化：降低刷新频率至 100ms

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- 1. 连接与参数配置 ---
        config_main_layout = QHBoxLayout()
        config_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1.1 通信连接
        conn_group = QGroupBox("1. 通信连接设置")
        conn_layout = QGridLayout(conn_group)
        conn_layout.setContentsMargins(5, 5, 5, 5)
        conn_layout.setSpacing(5)
        
        self.ip_edit = QLineEdit("192.168.1.10")
        self.port_edit = QLineEdit("5001")
        self.port_edit.setFixedWidth(50)
        self.modbus_port_edit = QLineEdit("502")
        self.modbus_port_edit.setFixedWidth(50)
        self.btn_connect = QPushButton("连接")
        self.btn_connect.setFixedWidth(80)
        self.btn_connect.setStyleSheet("background-color: #1A237E; color: white; font-weight: bold;")
        self.btn_connect.clicked.connect(self.connect_device)
        self.btn_disconnect = QPushButton("断开")
        self.btn_disconnect.setFixedWidth(80)
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self.disconnect_device)
        
        self.combo_target_ch = QComboBox()
        self.combo_target_ch.setFixedWidth(100)
        for i in range(1, 61): self.combo_target_ch.addItem(f"通道 {i}", i)
        self.combo_target_ch.currentIndexChanged.connect(self.on_target_board_changed)
        
        conn_layout.addWidget(QLabel("选择板卡:"), 0, 0)
        conn_layout.addWidget(self.combo_target_ch, 0, 1)
        conn_layout.addWidget(self.btn_connect, 0, 2)
        conn_layout.addWidget(self.btn_disconnect, 0, 3)
        
        conn_layout.addWidget(QLabel("IP:"), 1, 0)
        conn_layout.addWidget(self.ip_edit, 1, 1)
        conn_layout.addWidget(QLabel("端口:"), 1, 2)
        conn_layout.addWidget(self.port_edit, 1, 3)
        
        config_main_layout.addWidget(conn_group)
        
        # 1.2 硬件参数配置
        hw_group = QGroupBox("2. CAN 硬件参数配置")
        hw_layout = QGridLayout(hw_group)
        hw_layout.setContentsMargins(5, 5, 5, 5)
        hw_layout.setSpacing(5)
        
        self.combo_ch = QComboBox(); self.combo_ch.addItems(["CAN1", "CAN2"])
        self.combo_mode = QComboBox(); self.combo_mode.addItems(["Classic", "CAN FD", "CAN FD + BRS"])
        self.combo_nom_baud = QComboBox(); self.combo_nom_baud.addItems(["125k", "250k", "500k", "800k", "1M"])
        self.combo_nom_baud.setCurrentIndex(2) # 500k
        self.combo_data_baud = QComboBox(); self.combo_data_baud.addItems(["1M", "2M", "4M", "5M", "8M"])
        self.combo_data_baud.setCurrentIndex(1) # 2M
        
        self.btn_apply_hw = QPushButton("下发")
        self.btn_apply_hw.setFixedWidth(60)
        self.btn_apply_hw.setStyleSheet("background-color: #F57C00; color: white; font-weight: bold;")
        self.btn_apply_hw.clicked.connect(self.apply_hw_config)
        
        hw_layout.addWidget(QLabel("通道:"), 0, 0); hw_layout.addWidget(self.combo_ch, 0, 1)
        hw_layout.addWidget(QLabel("模式:"), 0, 2); hw_layout.addWidget(self.combo_mode, 0, 3)
        hw_layout.addWidget(QLabel("仲裁:"), 1, 0); hw_layout.addWidget(self.combo_nom_baud, 1, 1)
        hw_layout.addWidget(QLabel("数据:"), 1, 2); hw_layout.addWidget(self.combo_data_baud, 1, 3)
        hw_layout.addWidget(self.btn_apply_hw, 0, 4, 2, 1)
        
        config_main_layout.addWidget(hw_group)
        layout.addLayout(config_main_layout)

        # 2. 报文发送列表
        send_group = QGroupBox("3. 报文列表发送")
        send_layout = QVBoxLayout(send_group)
        send_layout.setContentsMargins(5, 5, 5, 5)
        
        ctrl_layout = QHBoxLayout()
        self.combo_send_mode = QComboBox()
        self.combo_send_mode.addItems(["顺序循环", "并行发送"])
        self.spin_global_cycles = QSpinBox()
        self.spin_global_cycles.setRange(0, 1000000); self.spin_global_cycles.setValue(1); self.spin_global_cycles.setSpecialValueText("无限")
        
        self.btn_add_row = QPushButton("+ 添加")
        self.btn_add_row.setFixedWidth(80) 
        self.btn_add_row.clicked.connect(self.add_send_row)
        
        self.btn_start_send = QPushButton("开始发送")
        self.btn_start_send.setFixedWidth(100)
        self.btn_start_send.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        self.btn_start_send.clicked.connect(self.start_sending)
        self.btn_stop_send = QPushButton("停止")
        self.btn_stop_send.setFixedWidth(60)
        self.btn_stop_send.setEnabled(False)
        self.btn_stop_send.clicked.connect(self.stop_sending)
        
        ctrl_layout.addWidget(QLabel("模式:"))
        ctrl_layout.addWidget(self.combo_send_mode)
        ctrl_layout.addWidget(QLabel("循环:"))
        ctrl_layout.addWidget(self.spin_global_cycles)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_add_row)
        ctrl_layout.addWidget(self.btn_start_send)
        ctrl_layout.addWidget(self.btn_stop_send)
        
        self.send_table = QTableWidget(0, 8)
        self.send_table.setHorizontalHeaderLabels(["通道", "ID", "类型", "DLC", "数据", "次数", "间隔", "操作"])
        self.send_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.send_table.setFixedHeight(110) 
        
        send_layout.addLayout(ctrl_layout)
        send_layout.addWidget(self.send_table)
        layout.addWidget(send_group)

        # 3. 报文监控与日志
        monitor_group = QGroupBox("4. 实时报文收发监控")
        monitor_layout = QVBoxLayout(monitor_group)
        
        log_ctrl_layout = QHBoxLayout()
        self.combo_log_fmt = QComboBox(); self.combo_log_fmt.addItems(["CSV", "ASC", "BLF (Wait)"])
        self.btn_toggle_log = QPushButton("开始记录保存")
        self.btn_toggle_log.clicked.connect(self.toggle_logging)
        self.lbl_log_status = QLabel("状态: 未记录")
        self.lbl_log_status.setStyleSheet("color: gray;")
        
        btn_clear_monitor = QPushButton("清空监控")
        btn_clear_monitor.clicked.connect(lambda: self.monitor_table.setRowCount(0))
        
        log_ctrl_layout.addWidget(QLabel("记录格式:"))
        log_ctrl_layout.addWidget(self.combo_log_fmt)
        log_ctrl_layout.addWidget(self.btn_toggle_log)
        log_ctrl_layout.addWidget(self.lbl_log_status)
        log_ctrl_layout.addStretch()
        log_ctrl_layout.addWidget(btn_clear_monitor)
        
        self.monitor_table = QTableWidget(0, 7)
        self.monitor_table.setHorizontalHeaderLabels(["方向", "通道", "ID", "类型", "DLC", "数据 Payload", "时间戳"])
        self.monitor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.monitor_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.monitor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.monitor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.monitor_table.setAlternatingRowColors(False) # 优化：禁用交替色，提高性能
        
        # 筛选工具栏
        filter_layout = QHBoxLayout()
        self.edit_filter_id = QLineEdit(); self.edit_filter_id.setPlaceholderText("ID (Hex)"); self.edit_filter_id.setFixedWidth(80)
        self.combo_filter_dir = QComboBox(); self.combo_filter_dir.addItems(["全部方向", "RX", "TX"])
        self.combo_filter_type = QComboBox(); self.combo_filter_type.addItems(["全部类型", "Classic", "FD", "FD+BRS"])
        self.edit_filter_data = QLineEdit(); self.edit_filter_data.setPlaceholderText("数据内容 (Hex 关键字)")
        
        filter_layout.addWidget(QLabel("筛选: "))
        filter_layout.addWidget(self.edit_filter_id)
        filter_layout.addWidget(self.combo_filter_dir)
        filter_layout.addWidget(self.combo_filter_type)
        filter_layout.addWidget(self.edit_filter_data)
        
        monitor_layout.addLayout(log_ctrl_layout)
        monitor_layout.addLayout(filter_layout)
        monitor_layout.addWidget(self.monitor_table)
        layout.addWidget(monitor_group)
        
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)
        layout.setStretch(2, 8)
        
        for _ in range(2): self.add_send_row()

    def add_send_row(self):
        row = self.send_table.rowCount()
        self.send_table.insertRow(row)
        ch_combo = QComboBox(); ch_combo.addItems(["CH1", "CH2", "CH3"])
        self.send_table.setCellWidget(row, 0, ch_combo)
        id_item = QTableWidgetItem("123"); id_item.setTextAlignment(Qt.AlignCenter)
        self.send_table.setItem(row, 1, id_item)
        type_combo = QComboBox(); type_combo.addItems(["Classic", "FD", "FD+BRS"])
        self.send_table.setCellWidget(row, 2, type_combo)
        dlc_spin = QSpinBox(); dlc_spin.setRange(0, 15); dlc_spin.setValue(8)
        self.send_table.setCellWidget(row, 3, dlc_spin)
        data_item = QTableWidgetItem("11 22 33 44 55 66 77 88")
        self.send_table.setItem(row, 4, data_item)
        repeats_spin = QSpinBox(); repeats_spin.setRange(1, 999999); repeats_spin.setValue(1)
        self.send_table.setCellWidget(row, 5, repeats_spin)
        interval_spin = QSpinBox(); interval_spin.setRange(1, 60000); interval_spin.setValue(100)
        self.send_table.setCellWidget(row, 6, interval_spin)
        btn_del = QPushButton("移除")
        btn_del.clicked.connect(lambda: self.send_table.removeRow(self.send_table.currentRow()))
        self.send_table.setCellWidget(row, 7, btn_del)

    def on_target_board_changed(self, index):
        ch_id = self.combo_target_ch.currentData()
        self.current_board = self.device_manager.boards.get(ch_id)
        if self.current_board:
            self.driver = self.current_board.can
            self.ip_edit.setText(self.current_board.ip)
            if self.driver.is_connected:
                self.btn_connect.setText("已连接"); self.btn_connect.setStyleSheet("background-color: #2E7D32; color: white;")
                self.btn_disconnect.setEnabled(True)
            else:
                self.btn_connect.setText("连接"); self.btn_connect.setStyleSheet("background-color: #1A237E; color: white;")
                self.btn_connect.setEnabled(True); self.btn_disconnect.setEnabled(False)

    def apply_hw_config(self):
        ip = self.ip_edit.text()
        try: modbus_port = int(self.modbus_port_edit.text())
        except: modbus_port = 502
        self.btn_apply_hw.setEnabled(False); self.btn_apply_hw.setText("正在下发...")
        self.config_worker = ConfigWorker(ip, modbus_port, self.combo_ch.currentIndex(), self.combo_mode.currentIndex(), self.combo_nom_baud.currentIndex(), self.combo_data_baud.currentIndex())
        self.config_worker.finished.connect(self.on_hw_config_finished); self.config_worker.start()

    def on_hw_config_finished(self, success, message):
        self.btn_apply_hw.setEnabled(True); self.btn_apply_hw.setText("应用并保存配置")
        if success: QMessageBox.information(self, "配置成功", message)
        else: QMessageBox.critical(self, "配置失败", message)

    def connect_device(self):
        ip = self.ip_edit.text()
        try: port = int(self.port_edit.text())
        except: port = 5001
        self.btn_connect.setEnabled(False); self.btn_connect.setText("正在连接...")
        self.conn_worker = ConnectWorker(self.driver, ip, port)
        self.conn_worker.finished.connect(self.on_connect_finished); self.conn_worker.start()

    def on_connect_finished(self, success):
        if success:
            self.btn_connect.setText("已连接"); self.btn_connect.setStyleSheet("background-color: #2E7D32; color: white;")
            self.btn_disconnect.setEnabled(True)
        else:
            self.btn_connect.setText("连接失败"); self.btn_connect.setStyleSheet("background-color: #C62828; color: white;")
            self.btn_connect.setEnabled(True)
            QMessageBox.critical(self, "连接错误", f"无法连接到 RNCAN 数据端口: {self.port_edit.text()}")

    def disconnect_device(self):
        self.driver.disconnect()
        self.btn_connect.setText("连接"); self.btn_connect.setStyleSheet("background-color: #1A237E; color: white;")
        self.btn_connect.setEnabled(True); self.btn_disconnect.setEnabled(False)

    def start_sending(self):
        if not self.driver or not self.driver.is_connected: return QMessageBox.warning(self, "未连接", "请先连接 RNCAN")
        msg_list = []
        try:
            for r in range(self.send_table.rowCount()):
                ch = self.send_table.cellWidget(r, 0).currentIndex()
                can_id = int(self.send_table.item(r, 1).text(), 16)
                can_type = self.send_table.cellWidget(r, 2).currentIndex()
                dlc = self.send_table.cellWidget(r, 3).value()
                data_hex = self.send_table.item(r, 4).text().replace(" ", "")
                data = bytes.fromhex(data_hex)
                repeats = self.send_table.cellWidget(r, 5).value()
                interval = self.send_table.cellWidget(r, 6).value()
                msg_list.append({'channel': ch, 'id': can_id, 'type': can_type, 'dlc': dlc, 'data': data, 'repeats': repeats, 'interval': interval})
        except Exception as e: return QMessageBox.critical(self, "数据错误", f"报文解析失败: {e}")
        if not msg_list: return
        self.btn_start_send.setEnabled(False); self.btn_stop_send.setEnabled(True)
        if self.combo_send_mode.currentIndex() == 0:
            self.sequential_worker = ListSendWorker(self.driver, msg_list, self.spin_global_cycles.value())
            self.sequential_worker.finished.connect(self.on_send_finished); self.sequential_worker.start()
        else:
            for m in msg_list:
                worker = MessageWorker(self.driver, m['channel'], m['id'], m['type'], m['dlc'], m['data'], m['repeats'], m['interval'])
                self.parallel_workers.append(worker); worker.start()

    def stop_sending(self):
        if self.sequential_worker: self.sequential_worker.stop()
        for w in self.parallel_workers: w.stop()
        self.parallel_workers.clear(); self.on_send_finished()

    def on_send_finished(self):
        self.btn_start_send.setEnabled(True); self.btn_stop_send.setEnabled(False)

    def toggle_logging(self):
        if not self.is_logging:
            fmt = self.combo_log_fmt.currentText().split(" ")[0]
            ext = fmt.lower(); file_name = f"CAN_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            path, _ = QFileDialog.getSaveFileName(self, "保存日志", file_name, f"{fmt} Files (*.{ext})")
            if not path: return
            try:
                self.log_format = fmt; self.log_file = open(path, 'w', newline='', encoding='utf-8')
                if fmt == "CSV":
                    self.log_writer = csv.writer(self.log_file)
                    self.log_writer.writerow(["Timestamp", "RelTime", "Dir", "CH", "ID", "Type", "DLC", "Data"])
                elif fmt == "ASC":
                    self.log_file.write(f"date {datetime.now().strftime('%a %b %d %I:%M:%S %p %Y')}\nbase hex  timestamps absolute\ninternal events logged\n")
                self.start_time = time.time(); self.is_logging = True
                self.btn_toggle_log.setText("停止记录"); self.lbl_log_status.setText(f"状态: 正在记录 ({fmt})"); self.lbl_log_status.setStyleSheet("color: green; font-weight: bold;")
            except Exception as e: QMessageBox.critical(self, "错误", f"无法创建日志文件: {e}")
        else:
            self.is_logging = False
            if self.log_file: self.log_file.close(); self.log_file = None
            self.btn_toggle_log.setText("开始记录保存"); self.lbl_log_status.setText("状态: 未记录"); self.lbl_log_status.setStyleSheet("color: gray;")

    def update_monitor(self):
        if not self.driver: return
        if self.driver.msg_queue.empty(): return

        # 1. 批量提取数据
        all_msgs = []
        while not self.driver.msg_queue.empty() and len(all_msgs) < 1000:
            msg = self.driver.msg_queue.get()
            all_msgs.append(msg)
            if self.is_logging: self._write_log(msg)
        if not all_msgs: return

        # 2. 筛选
        f_id = self.edit_filter_id.text().strip().lower()
        f_dir = self.combo_filter_dir.currentText()
        f_type = self.combo_filter_type.currentText()
        f_data = self.edit_filter_data.text().strip().lower().replace(" ", "")

        display_msgs = []
        for msg in all_msgs:
            if f_dir != "全部方向" and msg['direction'] != f_dir: continue
            if f_id:
                mid = f"{msg['can_id']:x}"
                if mid != f_id and f"0x{mid}" != f_id: continue
            if f_type != "全部类型":
                tstr = ["Classic", "FD", "FD+BRS"][msg['can_type']]
                if tstr != f_type: continue
            if f_data and f_data not in msg['data'].hex().lower(): continue
            display_msgs.append(msg)

        # 3. 限制 UI 刷新量 (仅显示最新的 50 条)
        if len(display_msgs) > 50: display_msgs = display_msgs[-50:]

        self.monitor_table.setUpdatesEnabled(False)
        for msg in display_msgs:
            row = self.monitor_table.rowCount()
            self.monitor_table.insertRow(row)
            item = QTableWidgetItem(msg['direction'])
            item.setForeground(QColor("blue") if msg['direction'] == 'TX' else QColor("green"))
            self.monitor_table.setItem(row, 0, item)
            self.monitor_table.setItem(row, 1, QTableWidgetItem(f"CH{msg['channel']+1}"))
            self.monitor_table.setItem(row, 2, QTableWidgetItem(f"0x{msg['can_id']:X}"))
            self.monitor_table.setItem(row, 3, QTableWidgetItem(["Classic", "FD", "FD+BRS"][msg['can_type']]))
            self.monitor_table.setItem(row, 4, QTableWidgetItem(str(msg['dlc'])))
            self.monitor_table.setItem(row, 5, QTableWidgetItem(msg['data'].hex(' ').upper()))
            ts = datetime.fromtimestamp(msg['timestamp_rel']).strftime('%H:%M:%S.%f')[:-3]
            self.monitor_table.setItem(row, 6, QTableWidgetItem(ts))

        # 4. 维护行数
        while self.monitor_table.rowCount() > 300:
            self.monitor_table.removeRow(0)

        self.monitor_table.scrollToBottom()
        self.monitor_table.setUpdatesEnabled(True)

    def _write_log(self, msg):
        rel_time = msg['timestamp_rel'] - self.start_time
        if self.log_format == "CSV":
            self.log_writer.writerow([datetime.fromtimestamp(msg['timestamp_rel']).isoformat(), f"{rel_time:.6f}", msg['direction'], msg['channel'], f"0x{msg['can_id']:X}", msg['can_type'], msg['dlc'], msg['data'].hex().upper()])
        elif self.log_format == "ASC":
            ext = "x" if msg['can_id'] > 0x7FF else ""
            self.log_file.write(f"  {rel_time:10.6f} {msg['channel']+1}  {msg['can_id']:X}{ext}             {msg['direction'].lower()} d {msg['dlc']} {msg['data'].hex(' ').upper()}\n")
