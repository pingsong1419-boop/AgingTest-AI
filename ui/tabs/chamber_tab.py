import sys
import time
import logging

logger = logging.getLogger("ChamberApp")
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QPushButton, QGroupBox, QLineEdit, QScrollArea, 
                                QFrame, QMessageBox, QGridLayout, QTableWidget, 
                                QTableWidgetItem, QHeaderView, QComboBox, QProgressBar, 
                                QDoubleSpinBox, QCheckBox, QAbstractItemView, QSlider)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QFont

class ChamberTab(QWidget):
    """
    高低温老化箱 S7-200 Smart PLC 通讯与老化工步测试中心
    符合用户点位映射表，包含：高温箱温度、PT100(板换/冷却水)温度、老化工步编辑器、PLC 核心读写以及状态警报诊断面板。
    """
    def __init__(self, device_manager, db_manager=None):
        super().__init__()
        self.mgr = device_manager
        self.db_manager = db_manager
        
        # 工步执行引擎变量
        self.steps_data = [] # 存储当前编辑中的工步 [{name, temp, hours, status}]
        self.active_step_idx = -1
        self.step_elapsed_sec = 0.0 # 当前工步已过时间(小时表示)
        self.speed_factor = 1.0   # 默认实时倍速 1x
        self.sequence_running = False

        self._init_ui()
        
        # 定时器：每 1 秒查询一次 PLC 数据，驱动工步控制，刷新 UI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(1000)

        # 默认加载高温老化方案
        # self.load_preset_profile("高温老化方案")

        # 同步初始联机状态，防止启动已连上但 UI 显示离线
        if self.chamber and self.chamber.is_connected:
            self._finalize_connect(True)

    @property
    def chamber(self):
        return self.mgr.chamber if self.mgr else None

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # --- 1. 顶部 PLC 联机配置栏 ---
        group_comm = QGroupBox("S7-200 Smart PLC 通讯参数")
        group_comm.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3E3E5C;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: #00E5FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        comm_layout = QHBoxLayout()
        comm_layout.setContentsMargins(10, 15, 10, 10)
        
        comm_layout.addWidget(QLabel("PLC IP 地址:"))
        self.edit_ip = QLineEdit("192.168.2.1")
        self.edit_ip.setFixedWidth(120)
        self.edit_ip.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px; color: #FFFFFF;")
        comm_layout.addWidget(self.edit_ip)
        
        comm_layout.addWidget(QLabel("PLC 端口:"))
        self.edit_port = QLineEdit("102")
        self.edit_port.setFixedWidth(40)
        self.edit_port.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px; color: #FFFFFF;")
        comm_layout.addWidget(self.edit_port)
        
        comm_layout.addWidget(QLabel("  |  HMI IP:"))
        self.edit_hmi_ip = QLineEdit("192.168.2.5")
        self.edit_hmi_ip.setFixedWidth(120)
        self.edit_hmi_ip.setStyleSheet("background-color: #1A1A2E; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px; color: #8A8A9E;")
        self.edit_hmi_ip.setReadOnly(True)
        comm_layout.addWidget(self.edit_hmi_ip)
        
        self.btn_connect = QPushButton("连接 PLC")
        self.btn_connect.setFixedSize(85, 28)
        self.btn_connect.setStyleSheet("background-color: #007BFF; color: white; border-radius: 4px; font-weight: bold;")
        self.btn_connect.clicked.connect(self.connect_device)
        comm_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("断开")
        self.btn_disconnect.setFixedSize(65, 28)
        self.btn_disconnect.setStyleSheet("background-color: #4A4A6A; color: #CCCCCC; border-radius: 4px;")
        self.btn_disconnect.clicked.connect(self.disconnect_device)
        comm_layout.addWidget(self.btn_disconnect)
        
        comm_layout.addStretch()
        
        # 运行模式标签 (仿真模拟 / S7-200 Smart)
        self.lbl_mode = QLabel("通讯模式: 未连接")
        self.lbl_mode.setStyleSheet("""
            QLabel {
                background-color: #1A1A2E;
                color: #A0A0B0;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
        """)
        comm_layout.addWidget(self.lbl_mode)
        
        self.lbl_status = QLabel("PLC 状态: 离线")
        self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold; font-size: 13px; margin-right: 5px;")
        comm_layout.addWidget(self.lbl_status)
        
        group_comm.setLayout(comm_layout)
        main_layout.addWidget(group_comm)

        # --- 2. 中间：4 维大型多维数字化指示面板 (仪表盘卡片) ---
        grid_metrics = QGridLayout()
        grid_metrics.setSpacing(10)
        
        # 卡片 1: 高温箱实际温度仪表
        self.card_temp = QFrame()
        self.card_temp.setStyleSheet("background-color: #131326; border: 1px solid #2A2A40; border-radius: 10px;")
        ly_temp = QVBoxLayout(self.card_temp)
        lbl_t_title = QLabel("🔥 高温箱实时温度 (Actual Temp)")
        lbl_t_title.setStyleSheet("color: #A0A0B0; font-size: 12px; font-weight: bold; border: none;")
        self.lbl_temp_val = QLabel("25.0 °C")
        self.lbl_temp_val.setStyleSheet("color: #00E5FF; font-size: 34px; font-weight: bold; font-family: Consolas; border: none; padding: 2px 0;")
        self.lbl_temp_tgt = QLabel("设定温度: -- °C (制冷 VD750 / 制热 VD800)")
        self.lbl_temp_tgt.setStyleSheet("color: #6C757D; font-size: 11px; border: none;")
        ly_temp.addWidget(lbl_t_title)
        ly_temp.addWidget(self.lbl_temp_val)
        ly_temp.addWidget(self.lbl_temp_tgt)
        grid_metrics.addWidget(self.card_temp, 0, 0)
        
        # 卡片 2: PT100 实时温度仪表 (只需要显示一个温度 VD220)
        self.card_pt = QFrame()
        self.card_pt.setStyleSheet("background-color: #131326; border: 1px solid #2A2A40; border-radius: 10px;")
        ly_pt = QVBoxLayout(self.card_pt)
        lbl_pt_title = QLabel("🌡️ PT100 实时温度 (VD220)")
        lbl_pt_title.setStyleSheet("color: #A0A0B0; font-size: 12px; font-weight: bold; border: none;")
        self.lbl_pt1_val = QLabel("25.0 °C")
        self.lbl_pt1_val.setStyleSheet("color: #FF9F0A; font-size: 34px; font-weight: bold; font-family: Consolas; border: none; padding: 2px 0;")
        self.lbl_pt_lbl = QLabel("传感器位置: 板换1出口 PT100 探头")
        self.lbl_pt_lbl.setStyleSheet("color: #6C757D; font-size: 11px; border: none;")
        ly_pt.addWidget(lbl_pt_title)
        ly_pt.addWidget(self.lbl_pt1_val)
        ly_pt.addWidget(self.lbl_pt_lbl)
        grid_metrics.addWidget(self.card_pt, 0, 1)

        # 卡片 3: PLC 核心状态面板 (只读显示)
        self.card_plc = QFrame()
        self.card_plc.setStyleSheet("background-color: #131326; border: 1px solid #2A2A40; border-radius: 10px;")
        ly_plc = QVBoxLayout(self.card_plc)
        ly_plc.setSpacing(6)
        
        lbl_p_title = QLabel("💻 PLC 运行状态 (V0.5 / V0.6 / V699)")
        lbl_p_title.setStyleSheet("color: #A0A0B0; font-size: 12px; font-weight: bold; border: none;")
        ly_plc.addWidget(lbl_p_title)
        
        self.lbl_status_sys = QLabel("系统状态: --")
        self.lbl_status_sys.setAlignment(Qt.AlignCenter)
        self.lbl_status_sys.setStyleSheet("color: #777777; font-size: 11px; font-weight: bold; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 6px;")
        
        self.lbl_status_mode = QLabel("运行模式: --")
        self.lbl_status_mode.setAlignment(Qt.AlignCenter)
        self.lbl_status_mode.setStyleSheet("color: #777777; font-size: 11px; font-weight: bold; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 6px;")
        
        self.lbl_status_ctrl = QLabel("控制模式: --")
        self.lbl_status_ctrl.setAlignment(Qt.AlignCenter)
        self.lbl_status_ctrl.setStyleSheet("color: #777777; font-size: 11px; font-weight: bold; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 6px;")
        
        ly_plc.addWidget(self.lbl_status_sys)
        ly_plc.addWidget(self.lbl_status_mode)
        ly_plc.addWidget(self.lbl_status_ctrl)
        
        grid_metrics.addWidget(self.card_plc, 0, 2)

        # 卡片 4: 当前老化工步实时执行监控
        self.card_step = QFrame()
        self.card_step.setStyleSheet("background-color: #131326; border: 1px solid #2A2A40; border-radius: 10px;")
        ly_step = QVBoxLayout(self.card_step)
        lbl_s_title = QLabel("⏳ 老化测试阶段运行监控")
        lbl_s_title.setStyleSheet("color: #A0A0B0; font-size: 12px; font-weight: bold; border: none;")
        ly_step.addWidget(lbl_s_title)
        
        self.lbl_active_step = QLabel("当前阶段: 未启动老化测试工步")
        self.lbl_active_step.setStyleSheet("color: #00E5FF; font-size: 11px; font-weight: bold; border: none;")
        ly_step.addWidget(self.lbl_active_step)
        
        self.lbl_step_time = QLabel("工步耗时: -- / -- 分钟")
        self.lbl_step_time.setStyleSheet("color: #CCCCCC; font-size: 11px; border: none;")
        ly_step.addWidget(self.lbl_step_time)
        
        self.pbar_step = QProgressBar()
        self.pbar_step.setFixedHeight(12)
        self.pbar_step.setStyleSheet("""
            QProgressBar {
                background-color: #1E1E38;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                text-align: center;
                color: white;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #00FF00;
                border-radius: 3px;
            }
        """)
        ly_step.addWidget(self.pbar_step)
        
        grid_metrics.addWidget(self.card_step, 0, 3)
        
        main_layout.addLayout(grid_metrics)

        # --- 3. 下部：分栏 (左：老化测试工步配置表格，右：S7-200 Smart PLC 指示灯与状态警报) ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        # --- 3.1 左侧：老化测试工步编辑器及运行进度 ---
        group_steps = QGroupBox("高低温老化测试工步编辑器")
        group_steps.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3E3E5C;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: #00E5FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        steps_layout = QVBoxLayout(group_steps)
        steps_layout.setContentsMargins(8, 12, 8, 8)
        
        # 预设配方快速加载栏
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设方案:"))
        self.combo_presets = QComboBox()
        self.combo_presets.wheelEvent = lambda event: event.ignore()
        self.refresh_preset_list()
        preset_layout.addWidget(self.combo_presets)
        
        self.btn_load_p = QPushButton("加载")
        self.btn_load_p.setStyleSheet("background-color: #007BFF; color: white;")
        self.btn_load_p.clicked.connect(self.on_load_preset_clicked)
        preset_layout.addWidget(self.btn_load_p)

        self.btn_save_p = QPushButton("保存")
        self.btn_save_p.setStyleSheet("background-color: #28A745; color: white;")
        self.btn_save_p.clicked.connect(self.save_preset)
        preset_layout.addWidget(self.btn_save_p)

        self.btn_del_p = QPushButton("删除")
        self.btn_del_p.setStyleSheet("background-color: #DC3545; color: white;")
        self.btn_del_p.clicked.connect(self.delete_preset)
        preset_layout.addWidget(self.btn_del_p)
        

        
        # 联动多通道测试复选框
        self.chk_linkage = QCheckBox("联动多通道测试")
        self.chk_linkage.setChecked(True)
        self.chk_linkage.setStyleSheet("QCheckBox { color: #00E5FF; font-weight: bold; }")
        preset_layout.addWidget(self.chk_linkage)
        
        preset_layout.addStretch()
        steps_layout.addLayout(preset_layout)
        
        # 工步配置表格
        self.table_steps = QTableWidget(0, 7)
        self.table_steps.setHorizontalHeaderLabels(["工步序号", "老化测试工步", "目标温度 (℃)", "设定测试时间", "测试终止条件", "运行时间(m)", "执行状态"])
        self.table_steps.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_steps.setColumnWidth(0, 75)   # 工步序号
        self.table_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # 老化测试工步（自适应）
        self.table_steps.setColumnWidth(2, 110)   # 目标温度 (℃)
        self.table_steps.setColumnWidth(3, 140)  # 设定测试时间
        self.table_steps.setColumnWidth(4, 150)   # 测试终止条件
        self.table_steps.setColumnWidth(5, 100)   # 运行时间(m)
        self.table_steps.setColumnWidth(6, 90)   # 执行状态
        self.table_steps.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_steps.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_steps.setStyleSheet("""
            QTableWidget {
                background-color: #131326;
                gridline-color: #2A2A40;
                color: #FFFFFF;
                border: 1px solid #3E3E5C;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #1A1A2E;
                color: #00E5FF;
                padding: 5px;
                border: 1px solid #3E3E5C;
                font-weight: bold;
            }
        """)
        steps_layout.addWidget(self.table_steps)
        self.table_steps.cellChanged.connect(self.on_cell_changed)
        
        # 整体工步总进度条
        progress_total_layout = QHBoxLayout()
        progress_total_layout.addWidget(QLabel("总体测试总进度:"))
        self.pbar_total = QProgressBar()
        self.pbar_total.setFixedHeight(14)
        self.pbar_total.setStyleSheet("""
            QProgressBar {
                background-color: #1E1E38;
                border: 1px solid #3E3E5C;
                border-radius: 4px;
                text-align: center;
                color: white;
                font-weight: bold;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #007BFF;
                border-radius: 3px;
            }
        """)
        progress_total_layout.addWidget(self.pbar_total)
        
        # 新增：方案总运行时间显示 (增加最小宽度预留1000+分钟的显示空间)
        self.lbl_total_time = QLabel("方案运行总时间: 0.00 分钟")
        self.lbl_total_time.setMinimumWidth(180)
        self.lbl_total_time.setStyleSheet("color: #00E5FF; font-weight: bold; margin-left: 10px;")
        progress_total_layout.addWidget(self.lbl_total_time)
        
        steps_layout.addLayout(progress_total_layout)
        
        # 工步操作按钮栏
        actions_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ 新增工步")
        self.btn_add.setStyleSheet("background-color: #007BFF; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_add.clicked.connect(self.add_blank_step)
        actions_layout.addWidget(self.btn_add)
        
        self.btn_del = QPushButton("❌ 删除工步")
        self.btn_del.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_del.clicked.connect(self.delete_selected_step)
        actions_layout.addWidget(self.btn_del)
        
        self.btn_up = QPushButton("⬆ 上移")
        self.btn_up.setStyleSheet("background-color: #17A2B8; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_up.clicked.connect(self.move_step_up)
        actions_layout.addWidget(self.btn_up)
        
        self.btn_down = QPushButton("⬇ 下移")
        self.btn_down.setStyleSheet("background-color: #17A2B8; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_down.clicked.connect(self.move_step_down)
        actions_layout.addWidget(self.btn_down)
        
        actions_layout.addStretch()
        
        self.btn_bypass_run = QPushButton("🔕 屏蔽老化箱调试启动")
        self.btn_bypass_run.setStyleSheet("background-color: #6F42C1; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_bypass_run.clicked.connect(self.start_aging_bypass_chamber)
        actions_layout.addWidget(self.btn_bypass_run)
        
        self.btn_run_seq = QPushButton("▶ 启动老化测试工步")
        self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px;")
        self.btn_run_seq.clicked.connect(self.start_aging_sequence)
        actions_layout.addWidget(self.btn_run_seq)
        
        self.btn_stop_seq = QPushButton("⏹ 停止测试工步")
        self.btn_stop_seq.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px;")
        self.btn_stop_seq.clicked.connect(self.on_stop_clicked)
        actions_layout.addWidget(self.btn_stop_seq)
        
        steps_layout.addLayout(actions_layout)
        
        bottom_layout.addWidget(group_steps, 5)
        
        # --- 3.2 右侧：S7-200 Smart PLC I/O 控制指示灯与诊断故障中心 ---
        group_plc = QGroupBox("S7-200 Smart PLC 状态与诊断中心")
        group_plc.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3E3E5C;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: #FF007F;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        plc_layout = QVBoxLayout(group_plc)
        plc_layout.setContentsMargins(5, 12, 5, 5)
        
        # 手动参数下发栏
        man_set_layout = QHBoxLayout()
        man_set_layout.addWidget(QLabel("制冷设定 (VD750):"))
        self.dsp_cool = QDoubleSpinBox()
        self.dsp_cool.setRange(-50, 100)
        self.dsp_cool.setValue(25.0)
        self.dsp_cool.setDecimals(1)
        self.dsp_cool.setSingleStep(0.5)
        self.dsp_cool.setStyleSheet("background-color: #1A1A2E; color: white; border: 1px solid #3E3E5C; border-radius: 4px;")
        man_set_layout.addWidget(self.dsp_cool)
        
        man_set_layout.addWidget(QLabel("制热设定 (VD800):"))
        self.dsp_heat = QDoubleSpinBox()
        self.dsp_heat.setRange(0, 150)
        self.dsp_heat.setValue(25.0)
        self.dsp_heat.setDecimals(1)
        self.dsp_heat.setSingleStep(0.5)
        self.dsp_heat.setStyleSheet("background-color: #1A1A2E; color: white; border: 1px solid #3E3E5C; border-radius: 4px;")
        man_set_layout.addWidget(self.dsp_heat)
        
        btn_apply_tgt = QPushButton("下发设定")
        btn_apply_tgt.setStyleSheet("background-color: #17A2B8; color: white;")
        btn_apply_tgt.clicked.connect(self.apply_manual_targets)
        man_set_layout.addWidget(btn_apply_tgt)
        
        plc_layout.addLayout(man_set_layout)

        # 嵌套滚动区，容纳 30 个 PLC 点位指示灯
        scroll_plc = QScrollArea()
        scroll_plc.setWidgetResizable(True)
        scroll_plc.setStyleSheet("border: none; background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        self.ly_plc_io = QVBoxLayout(scroll_content)
        self.ly_plc_io.setContentsMargins(5, 5, 5, 5)
        self.ly_plc_io.setSpacing(12)
        
        # A: Q/I 区 I/O 指示
        self.group_io = QGroupBox("I/O 继电器状态 (Q1.5 / Q1.6 / Q0.x / I2.4)")
        self.group_io.setStyleSheet("QGroupBox { border: 1px solid #2A2A40; border-radius: 6px; color: #CCCCCC; font-weight: bold; margin-top: 5px; }")
        self.grid_io = QGridLayout(self.group_io)
        self.grid_io.setSpacing(8)
        self.io_lamps = {}
        
        io_points = [
            ("Q1.5", "门禁状态"), ("Q1.6", "灯状态"), 
            ("Q0.3", "高温机1"), ("Q0.4", "低温机1"), ("Q0.5", "冷风机1"),
            ("Q1.0", "高温机2"), ("Q1.1", "低温机2"), ("Q1.2", "冷风机2"),
            ("Q0.0", "加热器"), ("Q0.1", "热风机"), ("I2.4", "水流开关")
        ]
        for i, (point, desc) in enumerate(io_points):
            lamp = QLabel(f"⚪ {point}\n{desc}")
            lamp.setAlignment(Qt.AlignCenter)
            lamp.setStyleSheet("color: #777777; font-size: 10px; font-weight: bold; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 4px;")
            self.grid_io.addWidget(lamp, i // 4, i % 4)
            self.io_lamps[point] = lamp
        self.ly_plc_io.addWidget(self.group_io)
        
        # B: 诊断保护报警 V 寄存器
        self.group_alarm = QGroupBox("库区报警与安全自检状态 (V15 - V22 只读)")
        self.group_alarm.setStyleSheet("QGroupBox { border: 1px solid #2A2A40; border-radius: 6px; color: #FF4D4D; font-weight: bold; margin-top: 5px; }")
        self.grid_alarm = QGridLayout(self.group_alarm)
        self.grid_alarm.setSpacing(6)
        self.alarm_lamps = {}
        
        alarm_points = [
            ("V15.1", "高温机1接触器"), ("V15.2", "高温机1综合保护"), ("V15.3", "高温机1油压差"), ("V15.5", "高温机1高低压"),
            ("V16.1", "低温机1接触器"), ("V16.2", "低温机1综合保护"), ("V16.3", "低温机1油压差"), ("V16.5", "低温机1高低压"),
            ("V17.1", "高温机2接触器"), ("V17.2", "高温机2综合保护"), ("V17.3", "高温机2油压差"), ("V17.5", "高温机2高低压"),
            ("V18.1", "低温机2接触器"), ("V18.2", "低温机2综合保护"), ("V18.3", "低温机2油压差"), ("V18.5", "低温机2高低压"),
            ("V21.0", "急停按钮动作"), ("V21.1", "相序保护报警"), ("V22.7", "加热风机故障"), ("V22.4", "水流开关故障")
        ]
        for i, (point, desc) in enumerate(alarm_points):
            lamp = QLabel(f"⚪ {point}\n{desc}")
            lamp.setAlignment(Qt.AlignCenter)
            lamp.setStyleSheet("color: #777777; font-size: 9px; background-color: #1A121A; border: 1px solid #2D1B2D; border-radius: 4px; padding: 4px;")
            self.grid_alarm.addWidget(lamp, i // 4, i % 4)
            self.alarm_lamps[point] = lamp
        self.ly_plc_io.addWidget(self.group_alarm)
        
        # 调试操作：模拟故障触发开关，增强可玩度与极客感
        self.group_sim_fault = QGroupBox("仿真自诊断排故测试")
        self.group_sim_fault.setStyleSheet("QGroupBox { border: 1px solid #2A2A40; border-radius: 6px; color: #FFC107; font-weight: bold; }")
        sim_fault_layout = QHBoxLayout(self.group_sim_fault)
        self.chk_fault_estop = QCheckBox("急停拉起 V21.0")
        self.chk_fault_water = QCheckBox("断水故障 V22.4")
        self.chk_fault_estop.stateChanged.connect(self.toggle_sim_fault)
        self.chk_fault_water.stateChanged.connect(self.toggle_sim_fault)
        sim_fault_layout.addWidget(self.chk_fault_estop)
        sim_fault_layout.addWidget(self.chk_fault_water)
        self.ly_plc_io.addWidget(self.group_sim_fault)

        scroll_plc.setWidget(scroll_content)
        plc_layout.addWidget(scroll_plc)
        
        bottom_layout.addWidget(group_plc, 4)
        
        main_layout.addLayout(bottom_layout)
        
        # 自动触发一次 PLC 探测连接
        self.connect_device()
        
        # 定时器：监控是否有配方正在测试，如果有，则禁用启动按钮
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_buttons_state)
        self.status_timer.start(500)

    def _update_buttons_state(self):
        """如果引擎中有通道正在测试，则禁用启动老化工步等按钮"""
        is_testing = False
        overview = self.get_overview_tab()
        if overview and overview.engine and len(overview.engine.workers) > 0:
            is_testing = True
            
        if getattr(self, '_last_is_testing', None) == is_testing:
            return
        self._last_is_testing = is_testing
            
        self.btn_run_seq.setEnabled(not is_testing)
        self.btn_bypass_run.setEnabled(not is_testing)
        
        disabled_style = "background-color: #444444; color: #888888; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;"
        
        if is_testing:
            self.btn_run_seq.setStyleSheet(disabled_style)
            self.btn_bypass_run.setStyleSheet(disabled_style)
        else:
            self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px;")
            self.btn_bypass_run.setStyleSheet("background-color: #6F42C1; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")

    def get_overview_tab(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, "tab_overview"):
                return parent.tab_overview
            parent = parent.parent()
        return None

    def connect_device(self):
        ip = self.edit_ip.text().strip()
        try:
            port = int(self.edit_port.text().strip())
        except:
            port = 102
            
        if self.chamber:
            self.chamber.ip = ip
            self.chamber.port = port
            
            self.lbl_status.setText("PLC 状态: 正在探测...")
            self.lbl_status.setStyleSheet("color: #FFC107; font-weight: bold;")
            
            import threading
            def task():
                success = self.chamber.connect()
                QTimer.singleShot(0, lambda: self._finalize_connect(success))
                
            threading.Thread(target=task, daemon=True).start()

    def _finalize_connect(self, success):
        if success:
            is_sim = self.chamber.use_simulation
            self.lbl_status.setText("PLC 状态: 已联机")
            self.lbl_status.setStyleSheet("color: #28A745; font-weight: bold;")
            
            if is_sim:
                self.lbl_mode.setText("通讯模式: 高保真仿真 (S7)")
                self.lbl_mode.setStyleSheet("background-color: #533483; color: #FFD700; border: 1px solid #FFD700; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            else:
                self.lbl_mode.setText("通讯模式: 物理 S7-Smart TCP")
                self.lbl_mode.setStyleSheet("background-color: #1A1A2E; color: #00E5FF; border: 1px solid #00E5FF; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            
            self.sync_plc_data()
        else:
            self.lbl_status.setText("PLC 状态: 连接失败")
            self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold;")

    def disconnect_device(self):
        if self.chamber:
            self.chamber.disconnect()
            self.lbl_status.setText("PLC 状态: 已断开")
            self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.lbl_mode.setText("通讯模式: 未连接")
            self.lbl_mode.setStyleSheet("background-color: #1A1A2E; color: #A0A0B0; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px 10px; font-weight: bold;")

    def write_plc_bit(self, point: str, val: bool, sync: bool = True):
        """下发 PLC bit 控制位"""
        if self.chamber and self.chamber.is_connected:
            ok = self.chamber.write_bit(point, val)
            if sync:
                self.sync_plc_data()
            return ok
        return False



    def should_heat_step(self, step_name: str, target_temp: float) -> bool:
        """根据工步名称和目标温度判断制热/制冷模式。"""
        mode = self.temperature_step_mode(step_name)
        if mode == "cool":
            return False
        if mode == "heat":
            return True
            
        if step_name == "运行至室温工步":
            current_temp = self.chamber.data_store.get("VD720", 25.0) if getattr(self, "chamber", None) else 25.0
            return target_temp > current_temp
            
        return target_temp >= 25.0

    def temperature_step_mode(self, step_name: str):
        """返回温度目标工步类型：heat / cool / None。"""
        if "降温至目标温度" in step_name or ("降温" in step_name and "目标温度" in step_name):
            return "cool"
        if "升温至目标温度" in step_name or ("升温" in step_name and "目标温度" in step_name):
            return "heat"
        return None

    def apply_cooling_target(self, target_temp: float):
        """写入制冷目标温度。"""
        if not self.chamber:
            return False

        return self.chamber.write_real("VD750", target_temp)

    def apply_manual_targets(self):
        """手动设置 VD 设定温度并下发"""
        if not self.chamber or not self.chamber.is_connected:
            return
        cool_val = self.dsp_cool.value()
        heat_val = self.dsp_heat.value()
        
        self.apply_cooling_target(cool_val)
        self.chamber.write_real("VD800", heat_val)
        
        self.lbl_temp_tgt.setText(f"设定温度: 制冷 VD750={cool_val:.1f} °C / 制热 VD800={heat_val:.1f} °C")
        QMessageBox.information(self, "设定成功", f"设定温度寄存器写入成功：\n制冷 VD750 -> {cool_val} °C\n制热 VD800 -> {heat_val} °C")

    def toggle_sim_fault(self, state):
        """配合仿真逻辑：手动注入断水或急停故障以进行排故演示"""
        if self.chamber:
            self.chamber.data_store["V21.0"] = self.chk_fault_estop.isChecked()
            self.chamber.data_store["V22.4"] = self.chk_fault_water.isChecked()
            self.sync_plc_data()

    def change_speed_factor(self, idx):
        """调节仿真测试时间比例，支持超快速完成 12 小时老化以利于调试"""
        if idx == 0:
            self.speed_factor = 1.0     # 1x 实时
        elif idx == 1:
            self.speed_factor = 60.0    # 60x 加速 (1分钟=1小时)
        else:
            self.speed_factor = 3600.0  # 3600x 极速 (1秒=1小时)

    # --- 4. 老化测试工步配方库设计 ---
    def refresh_preset_list(self):
        self.combo_presets.clear()
        if self.db_manager and hasattr(self.db_manager, "list_chamber_presets"):
            recipes = self.db_manager.list_chamber_presets()
            if recipes:
                self.combo_presets.addItems(recipes)
            else:
                self.combo_presets.addItem("无可用预设")
        else:
            self.combo_presets.addItem("无可用预设")

    def on_load_preset_clicked(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "老化测试运行期间，禁止加载预设！")
            return
        preset_name = self.combo_presets.currentText()
        if preset_name and preset_name != "无可用预设":
            self.load_preset_profile(preset_name)

    def load_preset_profile(self, profile_name):
        self.stop_aging_sequence()
        self.steps_data.clear()
        
        if self.db_manager and hasattr(self.db_manager, "load_chamber_preset_json"):
            data = self.db_manager.load_chamber_preset_json(profile_name)
            if data and "steps" in data:
                for s in data["steps"]:
                    self.steps_data.append({
                        "name": s.get("name", "自定义工步"),
                        "temp": s.get("temp", 25.0),
                        "hours": s.get("hours", 1.0),
                        "end_cond": s.get("end_cond", "到达目标时间终止"),
                        "status": "等待中"
                    })
                self.refresh_steps_table()
                return

        # 兜底默认方案
        self.steps_data.append({"name": "维持温度", "temp": 25.0, "hours": 0.2, "end_cond": "到达目标时间终止", "status": "等待中"})
        self.refresh_steps_table()

    def save_preset(self):
        from PySide6.QtWidgets import QInputDialog
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "老化测试运行期间，禁止保存预设！")
            return
        if not self.steps_data:
            QMessageBox.warning(self, "警告", "当前没有工步数据可保存！")
            return
            
        # 同步界面上可能未生效的编辑内容
        self._sync_table_to_data()

        name, ok = QInputDialog.getText(self, "保存老化方案", "请输入新方案名称:")
        if ok and name:
            if self.db_manager and hasattr(self.db_manager, "load_chamber_preset_json"):
                existing_data = self.db_manager.load_chamber_preset_json(name)
                if existing_data is not None:
                    ret = QMessageBox.question(self, "确认覆盖", f"老化方案 '{name}' 已存在，是否覆盖？")
                    if ret != QMessageBox.Yes:
                        return

            if self.db_manager and hasattr(self.db_manager, "save_chamber_preset_json"):
                data = {"steps": self.steps_data}
                if self.db_manager.save_chamber_preset_json(name, data):
                    QMessageBox.information(self, "成功", f"老化方案 '{name}' 已保存！")
                    self.refresh_preset_list()
                    self.combo_presets.setCurrentText(name)
                else:
                    QMessageBox.critical(self, "错误", "保存失败，请检查文件权限！")

    def delete_preset(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "老化测试运行期间，禁止删除预设！")
            return
        name = self.combo_presets.currentText()
        if not name or name == "无可用预设": return
        
        ret = QMessageBox.question(self, "确认删除", f"确定要删除方案 '{name}' 吗？")
        if ret == QMessageBox.Yes:
            if self.db_manager and hasattr(self.db_manager, "delete_chamber_preset"):
                if self.db_manager.delete_chamber_preset(name):
                    QMessageBox.information(self, "成功", "方案已删除！")
                    self.refresh_preset_list()
                else:
                    QMessageBox.warning(self, "错误", "删除失败或文件不存在。")

    def _sync_table_to_data(self):
        """将表格中可能正在编辑的数据同步回 steps_data 内存中"""
        # 强制结束当前可能处于输入状态的单元格编辑并保存数据（解决直接点击启动按钮时编辑尚未提交的问题）
        self.table_steps.setCurrentCell(-1, -1)
        
        for row in range(self.table_steps.rowCount()):
            if row >= len(self.steps_data):
                continue
            combo = self.table_steps.cellWidget(row, 1)
            if combo:
                self.steps_data[row]["name"] = combo.currentText()
            try:
                temp_item = self.table_steps.item(row, 2)
                hours_item = self.table_steps.item(row, 3)
                
                if temp_item:
                    self.steps_data[row]["temp"] = float(temp_item.text())
                if hours_item:
                    hours_str = hours_item.text()
                    if "min" in hours_str: hours_str = hours_str.split("min")[0]
                    self.steps_data[row]["hours"] = float(hours_str)
                
                cond_item = self.table_steps.item(row, 4)
                if cond_item:
                    self.steps_data[row]["end_cond"] = cond_item.text()
                
                # 强力校正终止条件，确保数据层与业务规范100%绑定
                step_name = self.steps_data[row]["name"]
                if step_name in ["升温至目标温度", "降温至目标温度"]:
                    self.steps_data[row]["end_cond"] = "到达目标温度终止"
                elif step_name == "维持温度":
                    self.steps_data[row]["end_cond"] = "到达目标时间终止"
                elif step_name == "启动多通道测试":
                    self.steps_data[row]["end_cond"] = "测试结束终止"
                elif step_name in ["老化完成取料", "BMS带载工作", "高温老化", "温巡老化"]:
                    self.steps_data[row]["end_cond"] = "默认"
            except:
                pass
    def on_cell_changed(self, row, col):
        if col not in (2, 3):
            return
        if row >= len(self.steps_data):
            return
            
        item = self.table_steps.item(row, col)
        if not item:
            return
            
        self.table_steps.blockSignals(True)
        try:
            val_str = item.text().strip()
            if col == 2: # Temp
                if self.steps_data[row].get("name", "") in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
                    item.setText("--")
                    return
                val = float(val_str)
                if val < -45.0: val = -45.0
                if val > 90.0: val = 90.0
                self.steps_data[row]["temp"] = val
                # 重新格式化为 1 位小数
                item.setText(f"{self.steps_data[row]['temp']:.1f}")
            elif col == 3: # Hours (测试时间)
                if "min" in val_str:
                    val_str = val_str.split("min")[0].strip()
                self.steps_data[row]["hours"] = float(val_str)
                # 重新格式化为 3 位小数
                if self.steps_data[row]["status"] == "运行中...":
                    if self.steps_data[row]["hours"] > 0:
                        rem = max(0, self.steps_data[row]["hours"] - self.step_elapsed_sec)
                        total_m = int(rem)
                        s = int((rem - total_m) * 60)
                        h = total_m // 60
                        m = total_m % 60
                        item.setText(f"{self.steps_data[row]['hours']:.3f}min (剩 {h:02d}:{m:02d}:{s:02d})")
                    else:
                        item.setText("0.000")
                elif self.steps_data[row]["status"] == "已完成":
                    item.setText(f"{self.steps_data[row]['hours']:.3f}min (已完成)")
                else:
                    item.setText(f"{self.steps_data[row]['hours']:.3f}")
            
            # 如果修改的是当前正在运行的工步，且工步引擎处于启动状态，立即下发PLC
            if row == self.active_step_idx and self.sequence_running:
                self.apply_step_temperatures(self.active_step_idx)
        except Exception as e:
            # 异常时恢复原数值
            if col == 2:
                if self.steps_data[row].get("name", "") in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
                    item.setText("--")
                else:
                    item.setText(f"{self.steps_data[row]['temp']:.1f}")
            elif col == 3:
                item.setText(f"{self.steps_data[row]['hours']:.3f}")
        finally:
            self.table_steps.blockSignals(False)

    def refresh_steps_table(self):
        self.table_steps.blockSignals(True)
        self.table_steps.setRowCount(len(self.steps_data))
        for row, step in enumerate(self.steps_data):
            # 序号
            item_seq = QTableWidgetItem(f"{row + 1}")
            item_seq.setTextAlignment(Qt.AlignCenter)
            item_seq.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            
            # 设定温度
            if step.get("name", "") in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
                item_temp = QTableWidgetItem("--")
                item_temp.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            else:
                item_temp = QTableWidgetItem(f"{step.get('temp', 25.0):.1f}")
            item_temp.setTextAlignment(Qt.AlignCenter)
            
            # 测试时间/倒计时
            test_val = step.get('hours', 0.0)
            if step["status"] == "运行中...":
                if test_val > 0:
                    rem = max(0, test_val - self.step_elapsed_sec)
                    total_m = int(rem)
                    s = int((rem - total_m) * 60)
                    h = total_m // 60
                    m = total_m % 60
                    item_hours = QTableWidgetItem(f"{test_val:.3f}min (剩 {h:02d}:{m:02d}:{s:02d})")
                else:
                    item_hours = QTableWidgetItem("0.000")
            elif step["status"] == "已完成":
                item_hours = QTableWidgetItem(f"{test_val:.3f}min (已完成)")
            else:
                item_hours = QTableWidgetItem(f"{test_val:.3f}")
            item_hours.setTextAlignment(Qt.AlignCenter)
            
                        # 执行状态
            item_status = QTableWidgetItem(step["status"])
            item_status.setTextAlignment(Qt.AlignCenter)
            item_status.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            
            if step["status"] == "运行中...":
                item_status.setForeground(QColor("#39FF14"))
                item_status.setFont(QFont("Consolas", 9, QFont.Bold))
            elif step["status"] == "已完成":
                item_status.setForeground(QColor("#8A8A9E"))
            elif step["status"] == "超时未达标":
                item_status.setForeground(QColor("#FF3B30"))
                item_status.setFont(QFont("Consolas", 9, QFont.Bold))
            
            self.table_steps.setItem(row, 0, item_seq)
            
            # Issue 2: 工步下拉选择
            combo = QComboBox()
            combo.wheelEvent = lambda event: event.ignore()
            step_options = ["升温至目标温度", "降温至目标温度", "运行至室温工步", "维持温度", "启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]
            if step["name"] not in step_options:
                step_options.append(step["name"])
            combo.addItems(step_options)
            combo.setCurrentText(step["name"])
            combo.setStyleSheet("background-color: #1A1A2E; color: white; border: 1px solid #3E3E5C;")
            # 绑定下拉框数据到 underlying step list
            def _update_name(text, r=row):
                self.steps_data[r]["name"] = text
                # 自动分配固定终止条件
                if text in ["升温至目标温度", "降温至目标温度", "运行至室温工步"]:
                    self.steps_data[r]["end_cond"] = "到达目标温度终止"
                elif text == "维持温度":
                    self.steps_data[r]["end_cond"] = "到达目标时间终止"
                elif text == "启动多通道测试":
                    self.steps_data[r]["end_cond"] = "测试结束终止"
                elif text in ["老化完成取料", "BMS带载工作", "高温老化", "温巡老化"]:
                    self.steps_data[r]["end_cond"] = "默认"

                if text in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
                    item_t = self.table_steps.item(r, 2)
                    if item_t:
                        item_t.setText("--")
                        item_t.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    
                    if text in ["高温老化", "温巡老化"]:
                        self.steps_data[r]["hours"] = 3.0 / 60.0
                else:
                    item_t = self.table_steps.item(r, 2)
                    if item_t:
                        item_t.setText(f"{self.steps_data[r].get('temp', 25.0):.1f}")
                        item_t.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                
                # 延迟刷新表格以显示最新的终止条件绑定状态
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.refresh_steps_table)
            combo.currentTextChanged.connect(_update_name)
            self.table_steps.setCellWidget(row, 1, combo)
            
            # 根据工步名称自动固定/锁定终止条件
            step_name = step.get("name", "")
            fixed_cond = "默认"
            if step_name in ["升温至目标温度", "降温至目标温度", "运行至室温工步"]:
                fixed_cond = "到达目标温度终止"
            elif step_name == "维持温度":
                fixed_cond = "到达目标时间终止"
            elif step_name == "启动多通道测试":
                fixed_cond = "测试结束终止"
            elif step_name in ["老化完成取料", "BMS带载工作", "高温老化", "温巡老化"]:
                fixed_cond = "默认"
            else:
                fixed_cond = step.get("end_cond", "到达目标时间终止")
            step["end_cond"] = fixed_cond

            # 测试终止条件文本项 (只读)
            item_cond = QTableWidgetItem(fixed_cond)
            item_cond.setTextAlignment(Qt.AlignCenter)
            item_cond.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table_steps.setItem(row, 4, item_cond)
            
            # 新增: 工步运行时间
            elapsed = step.get('elapsed_mins', 0.0)
            if self.sequence_running and row == self.active_step_idx:
                elapsed = self.step_elapsed_sec
            item_elapsed = QTableWidgetItem(f"{elapsed:.2f}")
            item_elapsed.setTextAlignment(Qt.AlignCenter)
            item_elapsed.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table_steps.setItem(row, 5, item_elapsed)
            
            self.table_steps.setItem(row, 2, item_temp)
            self.table_steps.setItem(row, 3, item_hours)
            self.table_steps.setItem(row, 6, item_status)
        self.table_steps.blockSignals(False)

    def add_blank_step(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "当前老化测试正在运行，不允许新增工步！")
            return
            
        self._sync_table_to_data() # 在新增前先把用户对现有表格的修改同步回内存
        row = self.table_steps.rowCount()
        self.steps_data.append({
            "name": f"自定义工步 {row + 1}",
            "temp": 25.0,
            "hours": 0.0,
            "end_cond": "到达目标时间终止",
            "status": "等待中"
        })
        self.refresh_steps_table()


    def delete_selected_step(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "当前老化测试正在运行，不允许删除工步！")
            return
            
        # 先获取要删除的行索引，再进行数据同步（防止同步时清除当前选中状态）
        idx = self.table_steps.currentRow()
        if idx < 0:
            selected_items = self.table_steps.selectedItems()
            if selected_items:
                idx = selected_items[0].row()
                
        self._sync_table_to_data() # 在删除前先把用户对现有表格的修改同步回内存
                
        if 0 <= idx < len(self.steps_data):
            self.steps_data.pop(idx)
            self.refresh_steps_table()
        else:
            QMessageBox.warning(self, "提示", "请先在表格中点击选择您要删除的工步行！")

    def move_step_up(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "当前老化测试正在运行，不允许移动工步！")
            return
            
        idx = self.table_steps.currentRow()
        if idx < 0:
            selected_items = self.table_steps.selectedItems()
            if selected_items:
                idx = selected_items[0].row()
                
        if idx <= 0:
            return  # Already at top or none selected
            
        self._sync_table_to_data()
        
        # Swap
        self.steps_data[idx], self.steps_data[idx-1] = self.steps_data[idx-1], self.steps_data[idx]
        self.refresh_steps_table()
        # 强制选择整行，防止只移动单独的某一格焦点
        self.table_steps.selectRow(idx - 1)
        self.table_steps.setCurrentCell(idx - 1, 0)

    def move_step_down(self):
        if self.sequence_running:
            QMessageBox.warning(self, "警告", "当前老化测试正在运行，不允许移动工步！")
            return
            
        idx = self.table_steps.currentRow()
        if idx < 0:
            selected_items = self.table_steps.selectedItems()
            if selected_items:
                idx = selected_items[0].row()
                
        if idx < 0 or idx >= len(self.steps_data) - 1:
            return  # Already at bottom or none selected
            
        self._sync_table_to_data()
        
        # Swap
        self.steps_data[idx], self.steps_data[idx+1] = self.steps_data[idx+1], self.steps_data[idx]
        self.refresh_steps_table()
        # 强制选择整行，防止只移动单独的某一格焦点
        self.table_steps.selectRow(idx + 1)
        self.table_steps.setCurrentCell(idx + 1, 0)

    def start_aging_bypass_chamber(self):
        """屏蔽老化箱，强制放行多通道测试（直接跳过工步序列，仅触发多通道测试）"""
        if not self.chk_linkage.isChecked():
            QMessageBox.warning(self, "警告", "需勾选【联动多通道测试】才能启动电性能测试！")
            return
            
        overview_tab = self.get_overview_tab()
        if not overview_tab:
            return

        # 彻底屏蔽老化工步执行序列，仅保留标识
        self._is_bypass_chamber = True
        self.sequence_running = False
        
        # 联动触发大屏通道并行测试
        overview_tab.trigger_multi_channel_tests()
        
        # 解除所有 worker 挂起（如果是断点重连情况）
        if overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False
                    
        self.lbl_active_step.setText("当前阶段: 屏蔽模式，已直接启动多通道电性能测试")
        self.lbl_step_time.setText("工步耗时: -- / --")
        
        QMessageBox.information(self, "启动成功", "已跳过老化箱测试序列，直接启动多通道电性能测试！")

    def start_aging_sequence(self):
        """启动老化测试工步自动运行引擎"""
        import datetime
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [Chamber] 请求“启动老化测试工步”")

        self._is_bypass_chamber = False
        if not self.steps_data:
            QMessageBox.warning(self, "警告", "请先配置或加载老化测试工步！")
            return

        # 启动前必须先同步表格，否则刚编辑的工步类型/目标温度会被刷新覆盖。
        self._sync_table_to_data()
            
        # 真正开启 PLC 系统启动指令（如果是升降温，暂不启动，交由 tick 中的压缩机保护处理）
        first_step_name = self.steps_data[0].get("name", "") if self.steps_data else ""
        if first_step_name not in ["升温至目标温度", "降温至目标温度", "运行至室温工步"]:
            # 其它不带压的工步（如维持温度、老化测试等），不再强制启动系统，仅下发必要温度即可
            self.apply_step_temperatures(0)
            logger.info(f"[老化引擎] 首个工步为 '{first_step_name}'，不下发系统启动指令，仅下发温度配置。")
        else:
            self.write_plc_bit("V0.5", False, sync=False)
            self.write_plc_bit("V0.6", True, sync=False)
            logger.info(f"[老化引擎] 首个工步为 '{first_step_name}'，初始保持停机，准备进入压缩机保护。")
        
        self.active_step_idx = 0
        self.step_elapsed_sec = 0.0
        self.sequence_running = True
        
        # 将所有工步设为等待，并把第1步设为运行中
        for i, step in enumerate(self.steps_data):
            step["status"] = "运行中..." if i == 0 else "等待中"
            
        self.refresh_steps_table()
        self.btn_run_seq.setEnabled(False)
        self.btn_run_seq.setStyleSheet("background-color: #555555; color: #888888; border-radius: 4px;")
        self.btn_bypass_run.setEnabled(False)
        self.btn_bypass_run.setStyleSheet("background-color: #555555; color: #888888; border-radius: 4px;")
        
        # 禁用预设区与新增删除按钮
        self.btn_load_p.setEnabled(False)
        self.btn_load_p.setStyleSheet("background-color: #555555; color: #888888;")
        self.btn_save_p.setEnabled(False)
        self.btn_save_p.setStyleSheet("background-color: #555555; color: #888888;")
        self.btn_del_p.setEnabled(False)
        self.btn_del_p.setStyleSheet("background-color: #555555; color: #888888;")
        self.combo_presets.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.btn_add.setStyleSheet("background-color: #555555; color: #888888; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_del.setEnabled(False)
        self.btn_del.setStyleSheet("background-color: #555555; color: #888888; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")

        # 激活第一步的温度下发 (由上面的逻辑替代)
        # self.apply_step_temperatures(0)

    def on_stop_clicked(self):
        if not self.sequence_running:
            QMessageBox.information(self, "提示", "当前没有正在运行的老化工步。")
            return
            
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("停止测试工步")
        msg_box.setText("请选择您要执行的停止操作：\n\n【提示】如果您选择回温，系统将按照安全规范，先强制停机等待 1 分钟保护压缩机，再启动回温。")
        
        btn_stop = msg_box.addButton("立即切断停止", QMessageBox.DestructiveRole)
        btn_return = msg_box.addButton("回温至常温(25℃)后停止", QMessageBox.AcceptRole)
        btn_cancel = msg_box.addButton("取消操作", QMessageBox.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_stop:
            self.stop_aging_sequence()
        elif msg_box.clickedButton() == btn_return:
            self.execute_return_to_normal()

    def execute_return_to_normal(self):
        """执行回温至 25℃ 安全策略"""
        import datetime
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [Chamber] 收到“安全回温”指令")
        
        # 1. 停止一切可能运行的多通道测试，防止短路或过载
        overview_tab = self.get_overview_tab()
        if overview_tab and overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False
            if getattr(self, "chk_linkage", None) and self.chk_linkage.isChecked():
                for cid in list(overview_tab.engine.workers.keys()):
                    overview_tab.engine.stop_channel_test(cid)
                    idx = cid - 1
                    if 0 <= idx < len(overview_tab.channel_widgets):
                        overview_tab.channel_widgets[idx].set_status("测试中止", "#DC3545")
                        
        # 2. 判断当前温度，决定是制冷还是加热
        current_temp = self.chamber.data_store.get("VD720", 25.0) if getattr(self, "chamber", None) else 25.0
        step_name = "升温至目标温度" if current_temp < 25.0 else "降温至目标温度"
        
        # 3. 将工步序列强制截断为单一的回温工步
        self.steps_data = [{
            "step_id": "RETURN_25",
            "name": step_name,
            "temp": 25.0,
            "hours": 0.0,
            "end_cond": "到达目标温度终止",
            "status": "等待中"
        }]
        
        # 4. 初始化运行引擎，触发 1 分钟压缩机保护
        self.active_step_idx = 0
        self.step_elapsed_sec = 0.0
        self._current_step_init_idx = -1
        self.sequence_running = True
        
        # 初始化回温时，首步需要进行强制关机保护
        self.write_plc_bit("V0.5", False, sync=False)
        self.write_plc_bit("V0.6", True, sync=False)
        
        self.refresh_steps_table()
        self.lbl_active_step.setText("当前阶段: 安全回温保护中 (目标: 25℃)")

    def stop_aging_sequence(self):
        """停止工步测试"""
        import datetime
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [Chamber] 收到“停止工步测试”指令")

        if self.active_step_idx != -1 and self.active_step_idx < len(self.steps_data):
            self.steps_data[self.active_step_idx]["elapsed_mins"] = self.step_elapsed_sec

        self.sequence_running = False
        self.active_step_idx = -1
        self.step_elapsed_sec = 0.0
        
        # 关闭 PLC 系统启动
        self.write_plc_bit("V0.5", False, sync=False)
        self.write_plc_bit("V0.6", True, sync=False)
        self.sync_plc_data()
        
        # 联动复位：解除所有 worker 的挂起状态并停止通道测试
        overview_tab = self.get_overview_tab()
        if overview_tab and overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False
            # 停止多通道测试
            if getattr(self, "chk_linkage", None) and self.chk_linkage.isChecked():
                for cid in list(overview_tab.engine.workers.keys()):
                    overview_tab.engine.stop_channel_test(cid)
                    idx = cid - 1
                    if 0 <= idx < len(overview_tab.channel_widgets):
                        overview_tab.channel_widgets[idx].set_status("已停止", "#DC3545")
        
        # 复位状态
        for step in self.steps_data:
            step["status"] = "已停止"
            
        self.refresh_steps_table()
        self.btn_run_seq.setEnabled(True)
        self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_bypass_run.setEnabled(True)
        self.btn_bypass_run.setStyleSheet("background-color: #6F42C1; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        
        # 启用预设区与新增删除按钮
        self.btn_load_p.setEnabled(True)
        self.btn_load_p.setStyleSheet("background-color: #007BFF; color: white;")
        self.btn_save_p.setEnabled(True)
        self.btn_save_p.setStyleSheet("background-color: #28A745; color: white;")
        self.btn_del_p.setEnabled(True)
        self.btn_del_p.setStyleSheet("background-color: #DC3545; color: white;")
        self.combo_presets.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.btn_add.setStyleSheet("background-color: #007BFF; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_del.setEnabled(True)
        self.btn_del.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        
        self._is_bypass_chamber = False
        
        self.lbl_active_step.setText("当前阶段: 已停机终止")
        self.lbl_step_time.setText("工步耗时: -- / -- 分钟")
        self.pbar_step.setValue(0)
        self.pbar_total.setValue(0)

    def apply_step_temperatures(self, idx):
        """当工步发生转换，自动根据该工步的温度，写入 PLC 设定值"""
        if getattr(self, "_is_bypass_chamber", False): return # 屏蔽模式下不下发PLC
        if not (0 <= idx < len(self.steps_data)):
            return
            
        step = self.steps_data[idx]
        step_name = step.get("name", "")
        target_temp = step["temp"]
        
        if step_name in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
            # 这三个辅助工步以及提示工步不需要目标温度和启动老化箱
            return

        mode_heat = self.should_heat_step(step_name, target_temp)
        
        # 写入 PLC 寄存器
        mode_ok = self.write_plc_bit("V699.0", mode_heat, sync=False)
        if mode_heat:
            target_ok = self.chamber.write_real("VD800", target_temp) # 制热
        else:
            target_ok = self.apply_cooling_target(target_temp) # 制冷：VD750
            
        # 联动自动模式 V699.2 为 ON，让 PLC 根据我们写的目标值自己恒温
        auto_ok = self.write_plc_bit("V699.2", True, sync=False)
        self.sync_plc_data()
        if not (mode_ok and target_ok and auto_ok):
            self.lbl_status.setText("PLC 状态: 温度目标写入失败")
            self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold;")

    # --- 5. 定时数据刷新与工步运行引擎 Tick ---
    @Slot()
    def on_tick(self):
        """每秒执行的心跳刷新逻辑"""
        # 1. 抓取并同步 PLC 数据
        self.sync_plc_data()
        
        # 2. 如果工步测试引擎在运行，驱动工步计时
        if self.sequence_running and self.active_step_idx != -1:
            self.drive_aging_sequence_step()

    def sync_plc_data(self):
        """从底册读取数据并渲染 UI 的 41 个 S7 指示灯和数字"""
        if not self.chamber:
            return
            
        # 自动根据后台设备的实际连接状态更新 UI 连接标签
        if self.chamber.is_connected:
            self.lbl_status.setText("PLC 状态: 已联机")
            self.lbl_status.setStyleSheet("color: #28A745; font-weight: bold;")
            if self.chamber.use_simulation:
                self.lbl_mode.setText("通讯模式: 高保真仿真 (S7)")
                self.lbl_mode.setStyleSheet("background-color: #533483; color: #FFD700; border: 1px solid #FFD700; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            else:
                self.lbl_mode.setText("通讯模式: 物理 S7-Smart TCP")
                self.lbl_mode.setStyleSheet("background-color: #1A1A2E; color: #00E5FF; border: 1px solid #00E5FF; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
        else:
            self.lbl_status.setText("PLC 状态: 离线")
            self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.lbl_mode.setText("通讯模式: 未连接")
            self.lbl_mode.setStyleSheet("background-color: #1A1A2E; color: #A0A0B0; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            
            # 关闭了后台静默自动重连功能，避免后台抢占句柄或引发其他异常
            # if not getattr(self, "is_reconnecting", False):
            #     self.is_reconnecting = True
            #     import threading
            #     def reconnect_task():
            #         try:
            #             self.chamber.connect()
            #         finally:
            #             self.is_reconnecting = False
            #     threading.Thread(target=reconnect_task, daemon=True).start()
            return  # 离线状态下直接返回，不拉取数据

        data = self.chamber.get_all_data()
        
        # 实时同步 UI 的模拟故障选择到 data 和 chamber.data_store (物理与仿真均生效)
        if self.chk_fault_estop.isChecked():
            data["V21.0"] = True
            self.chamber.data_store["V21.0"] = True
        if self.chk_fault_water.isChecked():
            data["V22.4"] = True
            self.chamber.data_store["V22.4"] = True
        
        # 1. 刷新卡片数值 (PT100 只需要显示一个温度 VD220)
        self.lbl_temp_val.setText(f"{data['VD720']:.1f} °C")
        self.lbl_pt1_val.setText(f"{data['VD220']:.1f} °C")
        
        cool_target = data.get("VD750", 25.0)
        heat_target = data.get("VD800", 25.0)
        self.lbl_temp_tgt.setText(f"PLC 设定温度: 制冷 VD750={cool_target:.1f}°C / 制热 VD800={heat_target:.1f}°C")
        
        # 实时同步 PLC 设定温度到 spinbox (当没有焦点时)
        if not self.dsp_cool.hasFocus():
            self.dsp_cool.blockSignals(True)
            self.dsp_cool.setValue(cool_target)
            self.dsp_cool.blockSignals(False)
        if not self.dsp_heat.hasFocus():
            self.dsp_heat.blockSignals(True)
            self.dsp_heat.setValue(heat_target)
            self.dsp_heat.blockSignals(False)
        
        # 2. 刷新 PLC 状态显示指示牌
        is_running = data.get("V0.5", False) and not data.get("V0.6", False)
        if is_running:
            self.lbl_status_sys.setStyleSheet("color: #39FF14; font-size: 11px; font-weight: bold; background-color: #122812; border: 1px solid #1B3F1B; border-radius: 4px; padding: 6px;")
            self.lbl_status_sys.setText("▶ 系统运行状态: 启动中 (V0.5)")
        else:
            self.lbl_status_sys.setStyleSheet("color: #FF4D4D; font-size: 11px; font-weight: bold; background-color: #3E1010; border: 1px solid #6C1E1E; border-radius: 4px; padding: 6px;")
            self.lbl_status_sys.setText("⏹ 系统运行状态: 已停止 (V0.6)")

        mode_heat = data.get("V699.0", False)
        if mode_heat:
            self.lbl_status_mode.setStyleSheet("color: #FF9F0A; font-size: 11px; font-weight: bold; background-color: #2D1A00; border: 1px solid #4D2B00; border-radius: 4px; padding: 6px;")
            self.lbl_status_mode.setText("🔥 运行模式: 制热模式 (V699.0)")
        else:
            self.lbl_status_mode.setStyleSheet("color: #00E5FF; font-size: 11px; font-weight: bold; background-color: #002B3D; border: 1px solid #004D66; border-radius: 4px; padding: 6px;")
            self.lbl_status_mode.setText("❄️ 运行模式: 制冷模式 (V699.0)")

        ctrl_auto = data.get("V699.2", False)
        if ctrl_auto:
            self.lbl_status_ctrl.setStyleSheet("color: #39FF14; font-size: 11px; font-weight: bold; background-color: #122812; border: 1px solid #1B3F1B; border-radius: 4px; padding: 6px;")
            self.lbl_status_ctrl.setText("🤖 控制模式: 自动恒温 (V699.2)")
        else:
            self.lbl_status_ctrl.setStyleSheet("color: #AAAAAA; font-size: 11px; font-weight: bold; background-color: #222230; border: 1px solid #3E3E5C; border-radius: 4px; padding: 6px;")
            self.lbl_status_ctrl.setText("✍️ 控制模式: 手动控制 (V699.2)")

        # 3. 刷新 I/O 状态指示灯
        io_descs = {
            "Q1.5": "门禁状态", "Q1.6": "灯状态", 
            "Q0.3": "高温机1", "Q0.4": "低温机1", "Q0.5": "冷风机1",
            "Q1.0": "高温机2", "Q1.1": "低温机2", "Q1.2": "冷风机2",
            "Q0.0": "加热器", "Q0.1": "热风机", "I2.4": "水流开关"
        }
        for point, lamp in self.io_lamps.items():
            val = data.get(point, False)
            desc = io_descs.get(point, "")
            if val:
                # 绿色发光激活样式
                lamp.setStyleSheet("color: #39FF14; font-size: 10px; font-weight: bold; background-color: #122812; border: 1px solid #1B3F1B; border-radius: 4px; padding: 4px;")
                lamp.setText(f"🟢 {point}\n{desc}")
            else:
                # 灰色不激活状态
                lamp.setStyleSheet("color: #777777; font-size: 10px; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 4px;")
                lamp.setText(f"⚪ {point}\n{desc}")

        # 4. 刷新只读故障诊断警报 (V 报警寄存器)
        alarm_descs = {
            "V15.1": "高温机1接触器", "V15.2": "高温机1综合保护", "V15.3": "高温机1油压差", "V15.5": "高温机1高低压",
            "V16.1": "低温机1接触器", "V16.2": "低温机1综合保护", "V16.3": "低温机1油压差", "V16.5": "低温机1高低压",
            "V17.1": "高温机2接触器", "V17.2": "高温机2综合保护", "V17.3": "高温机2油压差", "V17.5": "高温机2高低压",
            "V18.1": "低温机2接触器", "V18.2": "低温机2综合保护", "V18.3": "低温机2油压差", "V18.5": "低温机2高低压",
            "V21.0": "急停按钮动作", "V21.1": "相序保护报警", "V22.7": "加热风机故障", "V22.4": "水流开关故障"
        }
        has_any_alarm = False
        for point, lamp in self.alarm_lamps.items():
            val = data.get(point, False)
            desc = alarm_descs.get(point, "")
            if val:
                has_any_alarm = True
                # 炫酷红色故障闪烁
                lamp.setStyleSheet("color: #FF4D4D; font-size: 9px; font-weight: bold; background-color: #3E1010; border: 1px solid #6C1E1E; border-radius: 4px; padding: 4px;")
                lamp.setText(f"🚨 {point}\n{desc}")
            else:
                # 正常无故障样式
                lamp.setStyleSheet("color: #777777; font-size: 9px; background-color: #1A121A; border: 1px solid #2D1B2D; border-radius: 4px; padding: 4px;")
                lamp.setText(f"⚪ {point}\n{desc}")
                
        # 如系统触发急停或重大报警，且未开启屏蔽模式，强制自动终止老化测试工步 (保障物理实验安全)
        if has_any_alarm and self.sequence_running and not getattr(self, "_is_bypass_chamber", False):
            self.stop_aging_sequence()
            QMessageBox.critical(self, "安全报警拦截", "PLC 底层自检监测到严重安全故障警报！老化测试工步已自动触发紧急安全中止！")

    def drive_aging_sequence_step(self):
        """老化测试工步计时执行逻辑机 (定时驱动器)"""
        # 如果已被挂起，直接停止倒计时和流转
        if getattr(self, "sequence_suspended", False):
            return
            
        # 从表格抓取实时修改后的温度和时间参数。必须同步所有行，避免刷新时覆盖尚未运行的工步编辑。
        self._sync_table_to_data()
            
        step = self.steps_data[self.active_step_idx]
        step_name = step.get("name", "")
        
        # --- 硬件控制一次性初始化动作 ---
        if getattr(self, "_current_step_init_idx", -1) != self.active_step_idx:
            self._current_step_init_idx = self.active_step_idx
            
            # 压缩机保护逻辑：进入升降温工步时，强制停机等待
            self._compressor_wait_sec = 0.0
            if step_name in ["运行至室温工步", "升温至目标温度", "降温至目标温度"] and not getattr(self, "_is_bypass_chamber", False):
                self._compressor_waiting = True
                self._wait_target_sec = 60.0
                
                # 先系统停止
                self.write_plc_bit("V0.5", False, sync=False)
                self.write_plc_bit("V0.6", True, sync=False)
                
                # 再切换制冷制热模式和设定温度
                mode_heat = self.should_heat_step(step_name, step["temp"])
                self.write_plc_bit("V699.0", mode_heat, sync=False)
                if mode_heat:
                    self.chamber.write_real("VD800", step["temp"])
                else:
                    self.apply_cooling_target(step["temp"])
                self.write_plc_bit("V699.2", True, sync=False)
                
                self.sync_plc_data()
                logger.info(f"[老化引擎] 进入工步 '{step_name}'，系统已停止，已设定模式与温度，等待 60 秒保护期。")
                
            else:
                self._compressor_waiting = False
            
            if step_name == "启动多通道测试":
                logger.info("[老化引擎] 进入 '启动多通道测试'，触发主界面的多通道测试")
                overview_tab = self.get_overview_tab()
                if overview_tab and getattr(self, "chk_linkage", None) and self.chk_linkage.isChecked():
                    overview_tab.trigger_multi_channel_tests()

            elif step_name in ["高温老化", "温巡老化"]:
                logger.info(f"[老化引擎] 进入 '{step_name}'，语音播报并等待 3 秒。")
                self.speak_text(f"{step_name}开始")
                # 设置当前工步测试时间为 3 秒
                self.steps_data[self.active_step_idx]["hours"] = 3.0 / 60.0
                step["hours"] = 3.0 / 60.0
                self.refresh_steps_table()

            elif step_name == "BMS带载工作":
                logger.info("[老化引擎] 进入 'BMS带载工作'，配置主机电源与老化板继电器")
                
                def _bms_task():
                    if getattr(self, "mgr", None) and getattr(self.mgr, "dut_power", None):
                        self.mgr.dut_power.set_voltage(12.0)
                        self.mgr.dut_power.set_current(200.0)
                        self.mgr.dut_power.output_control(True)
                    
                    # 按顺序控制勾选通道的老化功能板继电器的1，11继电器
                    overview_tab = self.get_overview_tab()
                    if overview_tab and getattr(self, "mgr", None) and hasattr(self.mgr, "boards"):
                        selected_cids = [i + 1 for i, ch in enumerate(overview_tab.channel_widgets) if ch.isEnabled() and ch.chk_select.isChecked()]
                        for cid in selected_cids:
                            if cid in self.mgr.boards:
                                board = self.mgr.boards[cid]
                                # 开启继电器连接并写入继电器 1 (索引为 0) 和继电器 11 (索引为 10)
                                if not board.relays.is_connected:
                                    board.relays.connect()
                                board.relays.write_relay(0, True)
                                board.relays.write_relay(10, True)
                
                import threading
                threading.Thread(target=_bms_task, daemon=True).start()
                            
                # 倒计时停止，执行状态变更
                step["hours"] = 0.0
                self.steps_data[self.active_step_idx]["hours"] = 0.0
                
            elif step_name == "老化完成取料":
                logger.info("[老化引擎] 进入 '老化完成取料'，关闭所有电源、高压源、模拟电池及老化板继电器")
                
                def _finish_task():
                    if getattr(self, "mgr", None):
                        # 1. 断开高压源 output
                        if getattr(self.mgr, "hv_source", None):
                            self.mgr.hv_source.output_control(False)
                            
                        # 2. 断开模拟电池输出 (广播关闭所有模拟器通道)
                        self.mgr.broadcast_output(False)
                        
                        # 3. 断开供电电源输出
                        if getattr(self.mgr, "dut_power", None):
                            self.mgr.dut_power.output_control(False)
                        if getattr(self.mgr, "afe_power_1", None):
                            self.mgr.afe_power_1.output_control(False)
                        if getattr(self.mgr, "afe_pwr_2", None):
                            self.mgr.afe_pwr_2.output_control(False)
                        if getattr(self.mgr, "afe_pwr_3", None):
                            self.mgr.afe_pwr_3.output_control(False)
                            
                        # 4. 关闭所有老化板继电器
                        if hasattr(self.mgr, "boards"):
                            for cid, board in self.mgr.boards.items():
                                if not board.relays.is_connected:
                                    board.relays.connect()
                                if board.relays.is_connected:
                                    board.relays.write_all_off()
                
                import threading
                threading.Thread(target=_finish_task, daemon=True).start()
                            
                # 倒计时停止，执行状态变更
                step["hours"] = 0.0
                self.steps_data[self.active_step_idx]["hours"] = 0.0

        # --- 压缩机保护拦截器 ---
        if getattr(self, "_compressor_waiting", False):
            self._compressor_wait_sec += 1.0
            wait_target = getattr(self, "_wait_target_sec", 60.0)
            if self._compressor_wait_sec < wait_target:
                remain_sec = int(wait_target - self._compressor_wait_sec)
                self.lbl_active_step.setText(f"当前阶段: {step_name} (停机保护等待: {remain_sec}s)")
                self.lbl_step_time.setText("系统已停止，等待保护期结束...")
                # 将倒计时状态写入表格中
                self.steps_data[self.active_step_idx]["status"] = f"停机等待({remain_sec}s)"
                self.refresh_steps_table()
                return # 拦截，直接跳过下方所有的：温度下发、终止判定以及工步时间的扣除
            else:
                self._compressor_waiting = False
                self.steps_data[self.active_step_idx]["status"] = "运行中..."
                self.write_plc_bit("V0.5", True, sync=False)
                self.write_plc_bit("V0.6", False, sync=False)
                self.sync_plc_data()
                logger.info(f"[老化引擎] 停机保护期 {wait_target} 秒结束，重新启动系统。")

        # --- 断点恢复追温拦截器 ---
        if getattr(self, "_is_recovering_temp", False):
            current_temp = self.chamber.data_store.get("VD720", 25.0) if getattr(self, "chamber", None) else 25.0
            target_temp = step.get("temp", 25.0)
            if abs(current_temp - target_temp) <= 2.0:
                logger.info(f"[老化引擎] 断点追温达标 (当前 {current_temp:.1f}℃ -> 目标 {target_temp:.1f}℃)，正式恢复倒计时与多通道测试。")
                self._is_recovering_temp = False
                self.steps_data[self.active_step_idx]["status"] = "运行中..."
                self.refresh_steps_table()
                
                # 唤醒多通道测试
                overview_tab = self.get_overview_tab()
                if overview_tab and overview_tab.engine:
                    with overview_tab.engine._lock:
                        for worker in overview_tab.engine.workers.values():
                            worker.is_suspended = False
            else:
                self.lbl_active_step.setText(f"当前阶段: 断点追温保护中 (当前 {current_temp:.1f}℃ -> 目标 {target_temp:.1f}℃)")
                # 将追温状态写入表格中
                self.steps_data[self.active_step_idx]["status"] = f"追温中({current_temp:.1f}℃)"
                self.refresh_steps_table()
                return # 拦截，直接跳过下方的时间累加与终止判定

        if not getattr(self, "_is_bypass_chamber", False):
            if step_name in ["启动多通道测试", "BMS带载工作", "老化完成取料", "高温老化", "温巡老化"]:
                # 绝对继承：忽略底层残余寄存器，直接向上追溯最近一次明确配置的工步温度
                setting_temp = 25.0
                for prev_idx in range(self.active_step_idx - 1, -1, -1):
                    if self.steps_data[prev_idx]["name"] in ["升温至目标温度", "降温至目标温度", "维持温度"]:
                        setting_temp = self.steps_data[prev_idx]["temp"]
                        break
                
                mode_heat = self.should_heat_step(step_name, setting_temp)
                self.chamber.write_bit("V699.0", mode_heat)
                if mode_heat:
                    self.chamber.write_real("VD800", setting_temp)
                else:
                    self.apply_cooling_target(setting_temp)
                self.chamber.write_bit("V699.2", True)
            else:
                if step_name not in ["运行至室温工步", "升温至目标温度", "降温至目标温度"]:
                    mode_heat = self.should_heat_step(step_name, step["temp"])
                    self.chamber.write_bit("V699.0", mode_heat)
                    if mode_heat:
                        self.chamber.write_real("VD800", step["temp"])
                    else:
                        self.apply_cooling_target(step["temp"])
                    self.chamber.write_bit("V699.2", True)

        test_hours = step.get("hours", 0.0)
        end_cond = step.get("end_cond", "默认")
        
        # 驱动工步计时：如果是物理 PLC 联机状态，强制 1.0 实时倍速运行（避免物理测试时间瞬间耗尽）；仿真模式下才支持时间加速
        effective_speed = 1.0 if (self.chamber and not self.chamber.use_simulation) else self.speed_factor
        mins_per_tick = (1.0 * effective_speed) / 60.0
        self.step_elapsed_sec += mins_per_tick
        
        # 当前工步进度百分比
        if test_hours > 0:
            pct = min(100, int((self.step_elapsed_sec / test_hours) * 100))
        else:
            pct = 100
        self.pbar_step.setValue(pct)
        
        # 刷新本行的倒计时显示
        self.refresh_steps_table()
        
        # 更新工步卡片显示
        self.lbl_active_step.setText(f"当前阶段: {step['name']} (Step {self.active_step_idx + 1}/{len(self.steps_data)})")
        if test_hours > 0:
            self.lbl_step_time.setText(f"工步耗时: {self.step_elapsed_sec:.3f} / {test_hours:.3f} 分钟 ({end_cond})")
        else:
            self.lbl_step_time.setText(f"工步耗时: {self.step_elapsed_sec:.3f} / 0.000 分钟 ({end_cond})")
            
        # --- 新增加大屏信息传输接口，将当前运行的老化测试全局系统工步信息传给大屏 ---
        self._api_report_ticks = getattr(self, "_api_report_ticks", 0) + 1
        if self._api_report_ticks % 5 == 0:
            overview_tab = self.get_overview_tab()
            if overview_tab and hasattr(overview_tab, "engine") and overview_tab.engine:
                overview_tab.engine.report_system_step_info(self.active_step_idx, step_name)
        
        # --- 联动多通道测试控制逻辑 ---
        if hasattr(self, "chk_linkage") and self.chk_linkage.isChecked():
            overview_tab = self.get_overview_tab()
            if overview_tab:
                step_name = step["name"]
                target_temp = step["temp"]
                
                # 判断当前工步属于高温、低温还是普通阶段
                status_text = "等待测试"
                status_color = "#A0A0B0"  # 默认灰色
                
                is_heating = "升温" in step_name
                is_cooling = "降温" in step_name
                is_testing = "测试" in step_name or "功能测试" in step_name
                
                suspend_all = True # 默认非测试阶段，挂起多通道测试
                
                if target_temp >= 80.0:
                    if is_testing:
                        status_text = "高温测试中"
                        status_color = "#28A745"  # 绿色
                        suspend_all = False
                    elif is_heating:
                        status_text = "高温升温中"
                        status_color = "#FF8C00"  # 橙色
                    else:
                        status_text = "高温维持中"
                        status_color = "#FFC107"  # 黄色
                elif target_temp <= 0.0:
                    if is_testing:
                        status_text = "低温测试中"
                        status_color = "#00FFCC"  # 蓝绿色
                        suspend_all = False
                    elif is_cooling:
                        status_text = "低温降温中"
                        status_color = "#00BFFF"  # 蓝色
                    else:
                        status_text = "低温维持中"
                        status_color = "#1E90FF"  # 深蓝色
                elif "常温" in step_name or "25℃" in step_name:
                    if is_testing:
                        status_text = "常温测试中"
                        status_color = "#39FF14"
                        suspend_all = False
                    else:
                        status_text = "常温维持中"
                        status_color = "#20C997"
                elif "上板" in step_name:
                    status_text = "等待扫码上板"
                    status_color = "#6C757D"
                elif "下板" in step_name:
                    status_text = "老化测试完成"
                    status_color = "#28A745"
                    
                if getattr(self, "_is_bypass_chamber", False):
                    suspend_all = False
                    status_text += " (屏蔽强制放行)"
                
                # 1. 动态设置引擎中各个活动 worker 的挂起状态已移除，允许多通道测试与老化箱并行独立执行
                # 2. 动态更新 UI 状态文本功能已交还给多通道自身，使其能实时显示测试项。
        
        # 总体总测试进度计算
        total_profile_hours = sum(s.get("hours", 0.0) for s in self.steps_data)
        if total_profile_hours > 0:
            completed_step_hours = sum(self.steps_data[i].get("hours", 0.0) for i in range(self.active_step_idx))
            current_effective_elapsed = min(test_hours, self.step_elapsed_sec) if test_hours > 0 else 0.0
            overall_hours = completed_step_hours + current_effective_elapsed
            overall_pct = min(100, int((overall_hours / total_profile_hours) * 100))
        else:
            overall_pct = 100
        self.pbar_total.setValue(overall_pct)
        
        # 统计方案已运行总时间
        actual_total_elapsed = sum(s.get("elapsed_mins", 0.0) for i, s in enumerate(self.steps_data) if i != self.active_step_idx)
        if self.sequence_running and self.active_step_idx != -1:
            actual_total_elapsed += self.step_elapsed_sec
        self.lbl_total_time.setText(f"方案运行总时间: {actual_total_elapsed:.2f} 分钟")
        
        # 判断当前工步是否结束
        step_completed = False
        completion_reason = "时间耗尽"
        step_name = step.get("name", "")
        
        # 预先判断多通道测试完成情况
        all_checked_finished = False
        has_selected_channels = False
        if hasattr(self, "chk_linkage") and self.chk_linkage.isChecked():
            overview_tab = self.get_overview_tab()
            if overview_tab and overview_tab.engine:
                selected_cids = [i + 1 for i, ch in enumerate(overview_tab.channel_widgets) if ch.isEnabled() and ch.chk_select.isChecked()]
                if selected_cids:
                    has_selected_channels = True
                    with overview_tab.engine._lock:
                        workers_keys = list(overview_tab.engine.workers.keys())
                        all_checked_finished = all(cid not in overview_tab.engine.workers for cid in selected_cids)
                    if int(self.step_elapsed_sec * 3600) % 5 == 0:
                        print(f"[Aging Debug] Step '{step_name}': test_hours={test_hours}, selected_cids={selected_cids}, workers={workers_keys}, all_checked_finished={all_checked_finished}")

        # 终止条件判断逻辑
        if end_cond == "测试结束终止":
            time_met = True
            if test_hours > 0:
                time_met = (self.step_elapsed_sec >= test_hours)
            
            test_met = True
            if has_selected_channels:
                test_met = all_checked_finished
                
            if time_met and test_met:
                step_completed = True
                completion_reason = "时间已达标且通道测试全部完成"
                logger.info(f"[老化引擎] 同时满足设定时间达标与勾选通道测试全部结束条件，自动结束工步 '{step_name}'。")
        elif end_cond == "到达目标温度终止":
            if getattr(self, "_is_bypass_chamber", False):
                step_completed = True
                completion_reason = "温度达标"
            else:
                current_temp = self.chamber.data_store.get("VD720", 25.0) if self.chamber else 25.0
                target_temp = step["temp"]
                
                is_heating_transition = False
                is_cooling_transition = False
                if "升温" in step_name:
                    is_heating_transition = True
                elif "降温" in step_name:
                    is_cooling_transition = True
                else:
                    if target_temp > current_temp:
                        is_heating_transition = True
                    else:
                        is_cooling_transition = True
                
                if is_heating_transition and current_temp >= target_temp:
                    step_completed = True
                    completion_reason = "温度达标"
                    logger.info(f"[老化引擎] 当前温度 {current_temp:.1f} °C 已达升温目标 {target_temp:.1f} °C，自动切换工步")
                elif is_cooling_transition and current_temp <= target_temp:
                    step_completed = True
                    completion_reason = "温度达标"
                    logger.info(f"[老化引擎] 当前温度 {current_temp:.1f} °C 已达降温目标 {target_temp:.1f} °C，自动切换工步")
                
                if not step_completed and test_hours > 0 and self.step_elapsed_sec >= test_hours:
                    self._handle_timeout_ng(step_name, test_hours, f"实际箱温未达设定温度 ({target_temp:.1f} ℃)，已超时")
                    return
        else: # "到达目标时间终止" 或 "默认"
            if test_hours > 0:
                if self.step_elapsed_sec >= test_hours:
                    step_completed = True
                    completion_reason = "时间耗尽"
            else:
                step_completed = True
                completion_reason = "即时完成"


        if step_completed:
            status_text = "已完成"
            self.steps_data[self.active_step_idx]["status"] = status_text
            self.steps_data[self.active_step_idx]["elapsed_mins"] = self.step_elapsed_sec
            self.active_step_idx += 1
            self.step_elapsed_sec = 0.0
            
            if self.active_step_idx < len(self.steps_data):
                # 转换至下一个工步
                self._sync_table_to_data()
                self.steps_data[self.active_step_idx]["status"] = "运行中..."
                self.apply_step_temperatures(self.active_step_idx)
                self.refresh_steps_table()
                self.speak_text(f"老化测试切换到第 {self.active_step_idx + 1} 步")
            else:
                # 所有工步全部执行完成
                self.sequence_running = False
                self.active_step_idx = -1
                self.write_plc_bit("V0.5", False) # 停止系统
                self.write_plc_bit("V0.6", True)
                
                # 保留特异性状态（如“已完成(超时)”或“超时未达标”），只将其他等待中或运行中的改为已完成
                for s in self.steps_data:
                    if not s["status"].startswith("已完成") and s["status"] != "超时未达标":
                        s["status"] = "已完成"
                self.refresh_steps_table()
                
                self.btn_run_seq.setEnabled(True)
                self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 4px;")
                
                # 恢复预设区功能
                self.btn_load_p.setEnabled(True)
                self.btn_load_p.setStyleSheet("background-color: #007BFF; color: white;")
                self.btn_save_p.setEnabled(True)
                self.btn_save_p.setStyleSheet("background-color: #28A745; color: white;")
                self.btn_del_p.setEnabled(True)
                self.btn_del_p.setStyleSheet("background-color: #DC3545; color: white;")
                self.combo_presets.setEnabled(True)
                
                # 启用新增和删除工步按钮
                self.btn_add.setEnabled(True)
                self.btn_add.setStyleSheet("background-color: #007BFF; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
                self.btn_del.setEnabled(True)
                self.btn_del.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
                
                self.lbl_active_step.setText("当前阶段: 老化测试全部完成！")
                self.lbl_step_time.setText("工步耗时: 全部结束")
                self.pbar_step.setValue(100)
                self.pbar_total.setValue(100)
                
                self.speak_text("恭喜，高低温老化测试工步全部执行完毕")
                QMessageBox.information(self, "测试结束", "高低温老化箱测试工步已全部成功执行完毕！")

    def _handle_timeout_ng(self, step_name, timeout_hours, reason):
        logger.warning(f"[老化引擎] 工步 {step_name} 超时/异常终止：{reason}")
        
        if self.active_step_idx != -1 and self.active_step_idx < len(self.steps_data):
            self.steps_data[self.active_step_idx]["elapsed_mins"] = self.step_elapsed_sec
            
        self.sequence_running = False
        self.write_plc_bit("V0.5", False, sync=False)
        self.write_plc_bit("V0.6", True, sync=False)
        self.sync_plc_data()
        
        overview_tab = self.get_overview_tab()
        if overview_tab and overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False
                    
        self.steps_data[self.active_step_idx]["status"] = "异常未达标"
        for idx in range(self.active_step_idx + 1, len(self.steps_data)):
            self.steps_data[idx]["status"] = "已停止"
            
        self.btn_run_seq.setEnabled(True)
        self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_bypass_run.setEnabled(True)
        self.btn_bypass_run.setStyleSheet("background-color: #6F42C1; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        
        # 恢复预设区功能
        self.btn_load_p.setEnabled(True)
        self.btn_load_p.setStyleSheet("background-color: #007BFF; color: white;")
        self.btn_save_p.setEnabled(True)
        self.btn_save_p.setStyleSheet("background-color: #28A745; color: white;")
        self.btn_del_p.setEnabled(True)
        self.btn_del_p.setStyleSheet("background-color: #DC3545; color: white;")
        self.combo_presets.setEnabled(True)
        
        self.btn_add.setEnabled(True)
        self.btn_add.setStyleSheet("background-color: #007BFF; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_del.setEnabled(True)
        self.btn_del.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        
        self._is_bypass_chamber = False
        self.lbl_active_step.setText("当前阶段: 老化测试异常终止")
        self.lbl_step_time.setText(f"工步耗时: 异常未达标")
        
        self.refresh_steps_table()
        
        self.speak_text(f"警告：老化测试第 {self.active_step_idx + 1} 步异常终止，原因：{reason}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "异常中止测试", f"工步 '{step_name}' 触发异常中止！\n原因：{reason}\n已为您自动停止系统测试。")

    def speak_text(self, text):
        import threading
        import subprocess
        def run():
            cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 4; $synth.Speak('{text}')"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    import os
    
    # 将当前独立文件夹加入路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data.db_manager import DBManager
    from devices.chamber_driver import ChamberController
    
    class StandaloneDeviceManager:
        def __init__(self):
            # 这里默认使用高保真通讯模拟器，如果在车间接真实设备，可将 use_sim 设为 False 并传入真实 IP
            self.chamber = ChamberController(ip="192.168.2.1", port=102)
            self.chamber.use_simulation = True # 默认开启仿真模式
            
    app = QApplication(sys.argv)
    
    # 在当前目录生成独立的测试数据库和配方文件夹
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standalone_data.db")
    db = DBManager(db_path)
    mgr = StandaloneDeviceManager()
    
    window = ChamberTab(mgr, db)
    window.resize(1100, 800)
    window.show()
    sys.exit(app.exec())
