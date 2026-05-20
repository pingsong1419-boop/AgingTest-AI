import sys
import time
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
        self.chamber = device_manager.chamber
        
        # 工步执行引擎变量
        self.steps_data = [] # 存储当前编辑中的工步 [{name, temp, hours, status}]
        self.active_step_idx = -1
        self.step_elapsed_sec = 0.0 # 当前工步已过时间(小时表示)
        self.speed_factor = 3600.0   # 默认加速比 3600x (1秒仿真1小时，极易测试)
        self.sequence_running = False

        self._init_ui()
        
        # 定时器：每 1 秒查询一次 PLC 数据，驱动工步控制，刷新 UI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(1000)

        # 默认加载高温老化方案
        self.load_preset_profile("高温老化方案")

        # 同步初始联机状态，防止启动已连上但 UI 显示离线
        if self.chamber and self.chamber.is_connected:
            self._finalize_connect(True)

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
        self.lbl_temp_tgt = QLabel("设定温度: -- °C (制冷 VD700 / 制热 VD800)")
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

        # 卡片 3: PLC 核心操作面板 (V 寄存器读写)
        self.card_plc = QFrame()
        self.card_plc.setStyleSheet("background-color: #131326; border: 1px solid #2A2A40; border-radius: 10px;")
        ly_plc = QVBoxLayout(self.card_plc)
        lbl_p_title = QLabel("💻 PLC 核心控制台 (V0.5 / V0.6 / V699)")
        lbl_p_title.setStyleSheet("color: #A0A0B0; font-size: 12px; font-weight: bold; border: none;")
        ly_plc.addWidget(lbl_p_title)
        
        lay_p_btns = QGridLayout()
        self.btn_sys_start = QPushButton("系统启动 V0.5")
        self.btn_sys_start.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 11px;")
        self.btn_sys_start.clicked.connect(lambda: self.write_plc_bit("V0.5", True))
        
        self.btn_sys_stop = QPushButton("系统停止 V0.6")
        self.btn_sys_stop.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; font-size: 11px;")
        self.btn_sys_stop.clicked.connect(lambda: self.write_plc_bit("V0.6", True))
        
        self.btn_mode_switch = QPushButton("冷热模式 V699.0")
        self.btn_mode_switch.setCheckable(True)
        self.btn_mode_switch.setStyleSheet("background-color: #17A2B8; color: white; font-weight: bold; font-size: 11px;")
        self.btn_mode_switch.clicked.connect(self.toggle_mode_switch)
        
        self.btn_auto_switch = QPushButton("手自模式 V699.2")
        self.btn_auto_switch.setCheckable(True)
        self.btn_auto_switch.setStyleSheet("background-color: #6C757D; color: white; font-weight: bold; font-size: 11px;")
        self.btn_auto_switch.clicked.connect(self.toggle_auto_switch)
        
        lay_p_btns.addWidget(self.btn_sys_start, 0, 0)
        lay_p_btns.addWidget(self.btn_sys_stop, 0, 1)
        lay_p_btns.addWidget(self.btn_mode_switch, 1, 0)
        lay_p_btns.addWidget(self.btn_auto_switch, 1, 1)
        ly_plc.addLayout(lay_p_btns)
        
        # 实时启停显示
        self.lbl_plc_state = QLabel("PLC 模式: 停止中 | 模式: --")
        self.lbl_plc_state.setStyleSheet("color: #E2E2E2; font-size: 11px; font-weight: bold; border: none;")
        ly_plc.addWidget(self.lbl_plc_state)
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
        
        self.lbl_step_time = QLabel("工步耗时: -- / -- 小时")
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
        self.combo_presets.addItems(["高温老化方案", "温巡老化方案", "自定义老化方案"])
        preset_layout.addWidget(self.combo_presets)
        
        btn_load_p = QPushButton("加载预设")
        btn_load_p.setStyleSheet("background-color: #007BFF; color: white;")
        btn_load_p.clicked.connect(self.on_load_preset_clicked)
        preset_layout.addWidget(btn_load_p)
        
        # 加速比滑块
        preset_layout.addWidget(QLabel("  时间加速比:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["实时 (1x)", "加速 (60x) - 1分表1小时", "极速 (3600x) - 1秒表1小时"])
        self.combo_speed.setCurrentIndex(2) # 默认极速方便测试
        self.combo_speed.currentIndexChanged.connect(self.change_speed_factor)
        preset_layout.addWidget(self.combo_speed)
        
        # 联动多通道测试复选框
        self.chk_linkage = QCheckBox("联动多通道测试")
        self.chk_linkage.setChecked(True)
        self.chk_linkage.setStyleSheet("QCheckBox { color: #00E5FF; font-weight: bold; }")
        preset_layout.addWidget(self.chk_linkage)
        
        preset_layout.addStretch()
        steps_layout.addLayout(preset_layout)
        
        # 工步配置表格
        self.table_steps = QTableWidget(0, 4)
        self.table_steps.setHorizontalHeaderLabels(["工步序号", "老化测试工步", "时间 (h)", "执行状态"])
        self.table_steps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
        steps_layout.addLayout(progress_total_layout)
        
        # 工步操作按钮栏
        actions_layout = QHBoxLayout()
        
        btn_add = QPushButton("➕ 新增工步")
        btn_add.clicked.connect(self.add_blank_step)
        actions_layout.addWidget(btn_add)
        
        btn_del = QPushButton("❌ 删除工步")
        btn_del.clicked.connect(self.delete_selected_step)
        actions_layout.addWidget(btn_del)
        
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
        self.btn_stop_seq.clicked.connect(self.stop_aging_sequence)
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
        man_set_layout.addWidget(QLabel("制冷设定 (VD700):"))
        self.dsp_cool = QDoubleSpinBox()
        self.dsp_cool.setRange(-50, 100)
        self.dsp_cool.setValue(25.0)
        self.dsp_cool.setSingleStep(0.5)
        self.dsp_cool.setStyleSheet("background-color: #1A1A2E; color: white; border: 1px solid #3E3E5C; border-radius: 4px;")
        man_set_layout.addWidget(self.dsp_cool)
        
        man_set_layout.addWidget(QLabel("制热设定 (VD800):"))
        self.dsp_heat = QDoubleSpinBox()
        self.dsp_heat.setRange(0, 150)
        self.dsp_heat.setValue(25.0)
        self.dsp_heat.setSingleStep(0.5)
        self.dsp_heat.setStyleSheet("background-color: #1A1A2E; color: white; border: 1px solid #3E3E5C; border-radius: 4px;")
        man_set_layout.addWidget(self.dsp_heat)
        
        btn_apply_tgt = QPushButton("下发 VD")
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

    def write_plc_bit(self, point: str, val: bool):
        """下发 PLC bit 控制位"""
        if self.chamber and self.chamber.is_connected:
            self.chamber.write_bit(point, val)
            self.sync_plc_data()

    def toggle_mode_switch(self):
        """切换制冷/制热模式 V699.0"""
        checked = self.btn_mode_switch.isChecked()
        self.write_plc_bit("V699.0", checked)

    def toggle_auto_switch(self):
        """切换手动/自动模式 V699.2"""
        checked = self.btn_auto_switch.isChecked()
        self.write_plc_bit("V699.2", checked)

    def apply_manual_targets(self):
        """手动设置 VD 设定温度并下发"""
        if not self.chamber or not self.chamber.is_connected:
            return
        cool_val = self.dsp_cool.value()
        heat_val = self.dsp_heat.value()
        
        self.chamber.write_real("VD700", cool_val)
        self.chamber.write_real("VD800", heat_val)
        
        self.lbl_temp_tgt.setText(f"设定温度: 制冷 {cool_val:.1f} °C / 制热 {heat_val:.1f} °C")
        QMessageBox.information(self, "设定成功", f"设定温度寄存器写入成功：\n制冷 VD700 -> {cool_val} °C\n制热 VD800 -> {heat_val} °C")

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
    def on_load_preset_clicked(self):
        preset_name = self.combo_presets.currentText()
        self.load_preset_profile(preset_name)

    def load_preset_profile(self, profile_name):
        """
        根据用户上传的第 3 张图片《老化测试工步》表完全定制预设路径
        """
        self.stop_aging_sequence()
        self.steps_data.clear()
        
        if profile_name == "高温老化方案":
            # 严格依据图片 高温老化 配方
            presets = [
                ("上板+扫码", 25.0, 1.0),
                ("常温25℃-高温85℃", 85.0, 0.5),
                ("维持85℃ (功能测试1)", 85.0, 0.5),
                ("维持85℃ (老化测试1)", 85.0, 0.5),
                ("维持85℃ (功能测试2)", 85.0, 3.0),
                ("维持85℃ (老化测试2)", 85.0, 0.5),
                ("维持85℃ (功能测试3)", 85.0, 2.5),
                ("维持85℃ (老化测试3)", 85.0, 0.5),
                ("维持85℃ (高温结束)", 85.0, 0.5)
            ]
        elif profile_name == "温巡老化方案":
            # 严格依据图片 温巡老化 配方
            presets = [
                ("维持85℃ (功能测试)", 85.0, 0.5),
                ("维持85℃ (测试时间)", 85.0, 0.5),
                ("高温85℃-低温-40℃", -40.0, 1.0),
                ("维持-40℃ (功能测试)", -40.0, 0.5),
                ("维持-40℃ (测试时间)", -40.0, 0.5),
                ("低温-40℃-高温85℃", 85.0, 1.0),
                ("维持85℃ (功能测试)", 85.0, 0.5),
                ("维持85℃ (测试时间)", 85.0, 0.5),
                ("高温85℃-低温-40℃", -40.0, 1.0),
                ("维持-40℃ (功能测试)", -40.0, 0.5),
                ("维持-40℃ (测试时间)", -40.0, 0.5),
                ("低温-40℃-高温25℃", 25.0, 0.5),
                ("下板+收板", 25.0, 0.5)
            ]
        else: # 自定义方案
            presets = [
                ("常温保持", 25.0, 0.2),
                ("极速升温", 60.0, 0.1),
                ("恒温保持", 60.0, 0.2),
                ("极速降温", -10.0, 0.1),
                ("恒冷保持", -10.0, 0.2)
            ]
            
        for name, temp, hours in presets:
            self.steps_data.append({
                "name": name,
                "temp": temp,
                "hours": hours,
                "status": "等待中"
            })
            
        self.refresh_steps_table()

    def refresh_steps_table(self):
        self.table_steps.setRowCount(len(self.steps_data))
        for row, step in enumerate(self.steps_data):
            # 序号
            item_seq = QTableWidgetItem(f"{row + 1}")
            item_seq.setTextAlignment(Qt.AlignCenter)
            item_seq.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            
            # 工步名称
            item_name = QTableWidgetItem(step["name"])
            
            # 设定温度
            item_temp = QTableWidgetItem(f"{step['temp']:.1f}")
            item_temp.setTextAlignment(Qt.AlignCenter)
            
            # 恒温时间
            item_hours = QTableWidgetItem(f"{step['hours']:.2f}")
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
            
            self.table_steps.setItem(row, 0, item_seq)
            self.table_steps.setItem(row, 1, item_name)
            self.table_steps.setItem(row, 2, item_hours)
            self.table_steps.setItem(row, 3, item_status)

    def add_blank_step(self):
        row = self.table_steps.rowCount()
        self.steps_data.append({
            "name": f"自定义工步 {row + 1}",
            "temp": 25.0,
            "hours": 1.0,
            "status": "等待中"
        })
        self.refresh_steps_table()

    def delete_selected_step(self):
        idx = self.table_steps.currentRow()
        if 0 <= idx < len(self.steps_data):
            self.steps_data.pop(idx)
            self.refresh_steps_table()

    def start_aging_bypass_chamber(self):
        """屏蔽老化箱，强制放行多通道测试（直接唤醒所有由于挂起导致暂停的通道，不下发PLC指令）"""
        if not self.steps_data:
            QMessageBox.warning(self, "警告", "请先配置或加载老化测试工步！")
            return
            
        self._is_bypass_chamber = True
        self.active_step_idx = 0
        self.step_elapsed_sec = 0.0
        self.sequence_running = True
        
        for i, step in enumerate(self.steps_data):
            step["status"] = "运行中(屏蔽状态)" if i == 0 else "等待中"
            
        self.refresh_steps_table()
        self.btn_run_seq.setEnabled(False)
        self.btn_run_seq.setStyleSheet("background-color: #555555; color: #888888; border-radius: 4px;")
        self.btn_bypass_run.setEnabled(False)
        self.btn_bypass_run.setStyleSheet("background-color: #555555; color: #888888; border-radius: 4px;")
        
        # 联动复位：解除所有 worker 的挂起状态
        overview_tab = self.get_overview_tab()
        if overview_tab and overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False

    def start_aging_sequence(self):
        """启动老化测试工步自动运行引擎"""
        self._is_bypass_chamber = False
        if not self.steps_data:
            QMessageBox.warning(self, "警告", "请先配置或加载老化测试工步！")
            return
            
        # 真正开启 PLC 系统启动指令
        self.write_plc_bit("V0.5", True)
        self.write_plc_bit("V0.6", False)
        
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
        
        # 激活第一步的温度下发
        self.apply_step_temperatures(0)

    def stop_aging_sequence(self):
        """停止工步测试"""
        self.sequence_running = False
        self.active_step_idx = -1
        self.step_elapsed_sec = 0.0
        
        # 关闭 PLC 系统启动
        self.write_plc_bit("V0.5", False)
        self.write_plc_bit("V0.6", True)
        
        # 联动复位：解除所有 worker 的挂起状态
        overview_tab = self.get_overview_tab()
        if overview_tab and overview_tab.engine:
            with overview_tab.engine._lock:
                for worker in overview_tab.engine.workers.values():
                    worker.is_suspended = False
        
        # 复位状态
        for step in self.steps_data:
            step["status"] = "已停止"
            
        self.refresh_steps_table()
        self.btn_run_seq.setEnabled(True)
        self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self.btn_bypass_run.setEnabled(True)
        self.btn_bypass_run.setStyleSheet("background-color: #6F42C1; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 4px;")
        self._is_bypass_chamber = False
        
        self.lbl_active_step.setText("当前阶段: 已停机终止")
        self.lbl_step_time.setText("工步耗时: -- / -- 小时")
        self.pbar_step.setValue(0)
        self.pbar_total.setValue(0)

    def apply_step_temperatures(self, idx):
        """当工步发生转换，自动根据该工步的温度，写入 PLC 设定值"""
        if getattr(self, "_is_bypass_chamber", False): return # 屏蔽模式下不下发PLC
        if not (0 <= idx < len(self.steps_data)):
            return
            
        step = self.steps_data[idx]
        target_temp = step["temp"]
        
        # 根据工步温度判断启动制冷模式或制热模式
        # V699.0 : False=制冷, True=制热 (通常设定温度 >= 25℃ 设为制热，低于 25℃ 设为制冷)
        mode_heat = target_temp >= 25.0
        
        # 写入 PLC 寄存器
        self.write_plc_bit("V699.0", mode_heat)
        if mode_heat:
            self.chamber.write_real("VD800", target_temp) # 制热
        else:
            self.chamber.write_real("VD700", target_temp) # 制冷
            
        # 设置模式按钮样式
        self.btn_mode_switch.setChecked(mode_heat)
        self.btn_mode_switch.setText("制热模式 V699.0" if mode_heat else "制冷模式 V699.0")
        
        # 联动自动模式 V699.2 为 ON，让 PLC 根据我们写的目标值自己恒温
        self.write_plc_bit("V699.2", True)
        self.btn_auto_switch.setChecked(True)

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
            self.lbl_status.setText("PLC 状态: 离线 (正在自动重连...)")
            self.lbl_status.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.lbl_mode.setText("通讯模式: 未连接")
            self.lbl_mode.setStyleSheet("background-color: #1A1A2E; color: #A0A0B0; border: 1px solid #3E3E5C; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            
            # 后台静默自动重连
            if not getattr(self, "is_reconnecting", False):
                self.is_reconnecting = True
                import threading
                def reconnect_task():
                    try:
                        self.chamber.connect()
                    finally:
                        self.is_reconnecting = False
                threading.Thread(target=reconnect_task, daemon=True).start()
            return  # 离线状态下直接返回，不拉取数据

        data = self.chamber.get_all_data()
        
        # 1. 刷新卡片数值 (PT100 只需要显示一个温度 VD220)
        self.lbl_temp_val.setText(f"{data['VD720']:.1f} °C")
        self.lbl_pt1_val.setText(f"{data['VD220']:.1f} °C")
        
        self.lbl_temp_tgt.setText(f"PLC 设定温度: 制冷 VD700={data['VD700']:.1f}°C / 制热 VD800={data['VD800']:.1f}°C")
        
        # 2. 刷新 PLC 控制模式标签
        sys_state = "启动 (V0.5)" if (data["V0.5"] and not data["V0.6"]) else "停止 (V0.6)"
        mode_state = "制热 V699.0" if data["V699.0"] else "制冷 V699.0"
        ctrl_mode = "自动" if data["V699.2"] else "手动"
        self.lbl_plc_state.setText(f"系统: {sys_state} | 模式: {mode_state} | 控制: {ctrl_mode}")
        
        # 刷新按键自身按下状态 (由 PLC 寄存器回读同步，保证状态百分百一致)
        self.btn_mode_switch.setChecked(data["V699.0"])
        self.btn_mode_switch.setText("制热模式 V699.0" if data["V699.0"] else "制冷模式 V699.0")
        
        self.btn_auto_switch.setChecked(data["V699.2"])
        self.btn_auto_switch.setText("自动模式 V699.2" if data["V699.2"] else "手动模式 V699.2")

        # 3. 刷新 I/O 状态指示灯
        for point, lamp in self.io_lamps.items():
            val = data.get(point, False)
            if val:
                # 绿色发光激活样式
                lamp.setStyleSheet("color: #39FF14; font-size: 10px; font-weight: bold; background-color: #122812; border: 1px solid #1B3F1B; border-radius: 4px; padding: 4px;")
                lamp.setText(f"🟢 {point}\n{lamp.text().split(point)[1].strip()}")
            else:
                # 灰色不激活状态
                lamp.setStyleSheet("color: #777777; font-size: 10px; background-color: #16162C; border: 1px solid #25253A; border-radius: 4px; padding: 4px;")
                lamp.setText(f"⚪ {point}\n{lamp.text().split(point)[1].strip()}")

        # 4. 刷新只读故障诊断警报 (V 报警寄存器)
        has_any_alarm = False
        for point, lamp in self.alarm_lamps.items():
            val = data.get(point, False)
            if val:
                has_any_alarm = True
                # 炫酷红色故障闪烁
                lamp.setStyleSheet("color: #FF4D4D; font-size: 9px; font-weight: bold; background-color: #3E1010; border: 1px solid #6C1E1E; border-radius: 4px; padding: 4px;")
                lamp.setText(f"🚨 {point}\n{lamp.text().split(point)[1].strip()}")
            else:
                # 正常无故障样式
                lamp.setStyleSheet("color: #777777; font-size: 9px; background-color: #1A121A; border: 1px solid #2D1B2D; border-radius: 4px; padding: 4px;")
                lamp.setText(f"⚪ {point}\n{lamp.text().split(point)[1].strip()}")
                
        # 如系统触发急停或重大报警，强制自动终止老化测试工步 (保障物理实验安全)
        if has_any_alarm and self.sequence_running:
            self.stop_aging_sequence()
            QMessageBox.critical(self, "安全报警拦截", "PLC 底层自检监测到严重安全故障警报！老化测试工步已自动触发紧急安全中止！")

    def drive_aging_sequence_step(self):
        """老化测试工步计时执行逻辑机 (定时驱动器)"""
        # 从表格抓取实时修改后的温度和时间参数
        try:
            # 允许测试人员在表格上实时编辑修改 (灵活性极高)
            item_name = self.table_steps.item(self.active_step_idx, 1).text()
            item_temp = float(self.table_steps.item(self.active_step_idx, 2).text())
            item_hours = float(self.table_steps.item(self.active_step_idx, 3).text())
            
            # 更新缓存
            self.steps_data[self.active_step_idx]["name"] = item_name
            self.steps_data[self.active_step_idx]["temp"] = item_temp
            self.steps_data[self.active_step_idx]["hours"] = item_hours
        except Exception as e:
            # 如果解析出错，使用预存的数据
            pass
            
        step = self.steps_data[self.active_step_idx]
        total_hours = step["hours"]
        
        # 驱动工步计时：小时累加 = (1秒 * 加速比) / 3600.0 (小时/秒)
        hours_per_tick = (1.0 * self.speed_factor) / 3600.0
        self.step_elapsed_sec += hours_per_tick
        
        # 当前工步进度百分比
        pct = min(100, int((self.step_elapsed_sec / total_hours) * 100))
        self.pbar_step.setValue(pct)
        
        # 更新工步卡片显示
        self.lbl_active_step.setText(f"当前阶段: {step['name']} (Step {self.active_step_idx + 1}/{len(self.steps_data)})")
        self.lbl_step_time.setText(f"工步耗时: {self.step_elapsed_sec:.3f} / {total_hours:.2f} 小时")
        
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
                
                # 1. 动态设置引擎中各个活动 worker 的挂起状态
                if overview_tab.engine:
                    with overview_tab.engine._lock:
                        for cid, worker in overview_tab.engine.workers.items():
                            worker.is_suspended = suspend_all
                            
                # 2. 动态更新 OverviewTab 通道卡片在 UI 的状态文本
                for i, widget in enumerate(overview_tab.channel_widgets):
                    # 如果该通道被勾选，更新其显示
                    if widget.chk_select.isChecked():
                        cid = i + 1
                        # 如果 worker 存在且在运行
                        is_worker_running = cid in overview_tab.engine.workers if overview_tab.engine else False
                        if is_worker_running:
                            widget.set_status(status_text, status_color)
        
        # 总体总测试进度计算
        completed_step_hours = sum(self.steps_data[i]["hours"] for i in range(self.active_step_idx))
        total_profile_hours = sum(s["hours"] for s in self.steps_data)
        overall_hours = completed_step_hours + min(total_hours, self.step_elapsed_sec)
        overall_pct = min(100, int((overall_hours / total_profile_hours) * 100))
        self.pbar_total.setValue(overall_pct)
        
        # 判断当前工步是否计时结束
        if self.step_elapsed_sec >= total_hours:
            # 当前工步设为已完成
            self.steps_data[self.active_step_idx]["status"] = "已完成"
            self.active_step_idx += 1
            self.step_elapsed_sec = 0.0
            
            if self.active_step_idx < len(self.steps_data):
                # 转换至下一个工步
                self.steps_data[self.active_step_idx]["status"] = "运行中..."
                self.apply_step_temperatures(self.active_step_idx)
                self.refresh_steps_table()
                
                # 播放语音提醒 (由 overview_tab 中引用的 speak_text 拓展)
                self.speak_text(f"老化测试切换到第 {self.active_step_idx + 1} 步")
            else:
                # 所有工步全部执行完成
                self.sequence_running = False
                self.active_step_idx = -1
                self.write_plc_bit("V0.5", False) # 停止系统
                self.write_plc_bit("V0.6", True)
                
                for s in self.steps_data:
                    s["status"] = "已完成"
                self.refresh_steps_table()
                
                self.btn_run_seq.setEnabled(True)
                self.btn_run_seq.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 4px;")
                
                self.lbl_active_step.setText("当前阶段: 老化测试全部完成！")
                self.lbl_step_time.setText("工步耗时: 全部结束")
                self.pbar_step.setValue(100)
                self.pbar_total.setValue(100)
                
                self.speak_text("恭喜，高低温老化测试工步全部执行完毕")
                QMessageBox.information(self, "测试结束", "高低温老化箱测试工步已全部成功执行完毕！")

    def speak_text(self, text):
        import threading
        import subprocess
        def run():
            cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 4; $synth.Speak('{text}')"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True)
        threading.Thread(target=run, daemon=True).start()
