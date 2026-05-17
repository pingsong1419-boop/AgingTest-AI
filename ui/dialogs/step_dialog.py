from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, 
                               QSpinBox, QStackedWidget, QWidget, QFormLayout, QFrame, 
                               QCheckBox, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt

class StepDialog(QDialog):
    def __init__(self, parent=None, step_data=None):
        super().__init__(parent)
        self.is_loading = False # 状态位：标记是否处于数据加载还原中
        self.setWindowTitle("编辑指令 (子工步)")
        self.resize(620, 550)
        self.setStyleSheet("""
            QDialog { background-color: #1A1A2E; color: #E0E0E0; }
            QLabel { font-size: 14px; color: #B0B0B0; }
            QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox { 
                background-color: #16213E; 
                border: 1px solid #0F3460; 
                border-radius: 4px; 
                padding: 8px;
                color: white;
                font-size: 14px;
            }
            QCheckBox { color: #E0E0E0; font-size: 14px; spacing: 10px; }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #4ECCA3;
                border-radius: 4px;
                background-color: #1A1A2E;
            }
            QCheckBox::indicator:checked {
                background-color: #4ECCA3;
                border: 2px solid #4ECCA3;
            }
            QCheckBox::indicator:unchecked:hover, QRadioButton::indicator:unchecked:hover {
                border: 2px solid #00E5FF;
            }
            QRadioButton { color: #E0E0E0; font-size: 14px; spacing: 10px; }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #4ECCA3;
                border-radius: 10px;
                background-color: #1A1A2E;
            }
            QRadioButton::indicator:checked {
                background-color: #4ECCA3;
                border: 6px solid #1A1A2E; /* Create a dot effect */
            }
            QComboBox::drop-down { border: none; }
            QPushButton#btn_ok { 
                background-color: #E94560; 
                color: white; 
                font-weight: bold; 
                border-radius: 6px; 
                padding: 12px;
                min-width: 140px;
            }
            QPushButton#btn_cancel { 
                background-color: #533483; 
                color: white; 
                border-radius: 6px; 
                padding: 12px;
                min-width: 100px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 1. 设备与大类选择 (分类整理)
        top_frame = QFrame(self)
        top_layout = QFormLayout(top_frame)
        top_layout.setLabelAlignment(Qt.AlignRight)
        top_layout.setSpacing(15)
        
        # 一级分类
        self.category_combo = QComboBox()
        self.category_combo.addItems(["设备操作", "报文交互", "三方协议", "通用交互"])
        top_layout.addRow("一级分类:", self.category_combo)
        
        # 二级分类 (仅在设备操作下有效)
        self.sub_category_combo = QComboBox()
        self.sub_category_combo.addItems(["AFE", "继电器", "高压源", "模拟电池", "校准源", "直流源"])
        top_layout.addRow("二级分类:", self.sub_category_combo)
        
        self.device_combo = QComboBox()
        top_layout.addRow("控制设备:", self.device_combo)
        
        self.action_combo = QComboBox()
        top_layout.addRow("功能动作:", self.action_combo)
        
        main_layout.addWidget(top_frame)
        
        # 分割线
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #0F3460;")
        main_layout.addWidget(line)
        
        # 2. 滚动区域 (包裹动态参数和策略区)
        self.main_scroll = QScrollArea(self)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.NoFrame)
        self.main_scroll.setStyleSheet("background-color: transparent;")
        
        self.main_scroll_content = QWidget() # 容器 Widget
        self.scroll_layout = QVBoxLayout(self.main_scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(15)
        
        # 动态参数配置区
        self.param_stack = QStackedWidget(self)
        self.scroll_layout.addWidget(self.param_stack)
        
        # --- 页面 0: 仪表设置参数 (可多选) ---
        self.page_instr = QWidget()
        instr_layout = QVBoxLayout(self.page_instr)
        instr_layout.setSpacing(15)
        
        # 电压设置行
        v_layout = QHBoxLayout()
        self.cb_volt = QCheckBox("设定电压:")
        self.cb_volt.setChecked(True)
        self.i_volt = QDoubleSpinBox()
        self.i_volt.setRange(0, 1000)
        self.i_volt.setSuffix(" V")
        self.i_volt.setDecimals(3)
        v_layout.addWidget(self.cb_volt)
        v_layout.addWidget(self.i_volt, 1)
        instr_layout.addLayout(v_layout)
        
        # 电流设置行
        c_layout = QHBoxLayout()
        self.cb_curr = QCheckBox("限制电流:")
        self.cb_curr.setChecked(True)
        self.i_curr = QDoubleSpinBox()
        self.i_curr.setRange(0, 500)
        self.i_curr.setSuffix(" A")
        self.i_curr.setDecimals(3)
        c_layout.addWidget(self.cb_curr)
        c_layout.addWidget(self.i_curr, 1)
        instr_layout.addLayout(c_layout)
        
        # 输出状态控制 (可选)
        self.cb_output = QCheckBox("同时控制输出状态")
        self.output_combo = QComboBox()
        self.output_combo.addItems(["保持现状", "开启输出", "关闭输出"])
        o_layout = QHBoxLayout()
        o_layout.addWidget(self.cb_output)
        o_layout.addWidget(self.output_combo, 1)
        instr_layout.addLayout(o_layout)
        
        instr_layout.addStretch()

        # --- 页面 1: CAN 参数 ---
        self.page_can = QWidget()
        c_form = QFormLayout(self.page_can)
        self.c_id = QLineEdit("0x7F0")
        self.c_data = QLineEdit("00 00 00 00 00 00 00 00")
        self.c_wait_id = QLineEdit("0x7F8")
        self.c_type = QComboBox()
        self.c_type.addItems(["Classic", "FD", "FD+BRS"])
        self.c_dlc = QSpinBox()
        self.c_dlc.setRange(0, 15)
        self.c_dlc.setValue(8)
        self.c_channel = QSpinBox()
        self.c_channel.setRange(0, 255)
        self.c_channel.setValue(0)
        self.c_timeout = QSpinBox()
        self.c_timeout.setRange(1, 600000)
        self.c_timeout.setValue(1000)
        self.c_timeout.setSuffix(" ms")
        c_form.addRow("帧 ID (HEX):", self.c_id)
        c_form.addRow("数据 (HEX):", self.c_data)
        c_form.addRow("等待响应 ID:", self.c_wait_id)
        c_form.addRow("CAN 类型:", self.c_type)
        c_form.addRow("DLC:", self.c_dlc)
        c_form.addRow("RNCAN通道:", self.c_channel)
        c_form.addRow("超时:", self.c_timeout)

        # --- 页面 2: 等待参数 ---
        self.page_wait = QWidget()
        w_form = QFormLayout(self.page_wait)
        self.w_time = QSpinBox()
        self.w_time.setRange(0, 86400000)
        self.w_time.setSuffix(" ms")
        self.w_time.setValue(1000)
        w_form.addRow("延时时间:", self.w_time)

        # --- 页面 3: 读取参数选择 (单选以确保判定唯一性) ---
        self.page_read = QWidget()
        read_layout = QVBoxLayout(self.page_read)
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self.read_group = QButtonGroup(self)
        
        self.rb_volt = QRadioButton("读取电压")
        self.rb_volt.setChecked(True)
        self.rb_curr = QRadioButton("读取电流")
        
        self.read_group.addButton(self.rb_volt)
        self.read_group.addButton(self.rb_curr)
        
        read_layout.addWidget(self.rb_volt)
        read_layout.addWidget(self.rb_curr)
        read_layout.addStretch()

        self.param_stack.addWidget(self.page_instr) # 0: 设置
        self.param_stack.addWidget(self.page_can)   # 1: CAN
        self.param_stack.addWidget(self.page_wait)  # 2: 等待
        self.param_stack.addWidget(self.page_read)  # 3: 读取

        # --- 页面 4: Easy320 参数 (勾选模式) ---
        self.page_easy320 = QWidget()
        e_layout = QVBoxLayout(self.page_easy320)
        
        scroll = QScrollArea()
        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        self.easy320_checks = []
        for i in range(32):
            cb = QCheckBox(f"CH-{i+1}")
            grid.addWidget(cb, i // 4, i % 4)
            self.easy320_checks.append(cb)
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        
        e_layout.addWidget(QLabel("选择操作通道 (多选):"))
        e_layout.addWidget(scroll)
        self.param_stack.addWidget(self.page_easy320) # 4

        # --- 页面 5: CA550 参数 (参数设置) ---
        self.page_ca550 = QWidget()
        ca_form = QFormLayout(self.page_ca550)
        
        self.ca_output_state = QComboBox()
        self.ca_output_state.addItems(["保持现状", "开启输出", "关闭输出"])
        
        self.ca_type = QComboBox()
        self.ca_type.addItems(["V (电压)", "mA (电流)", "TC_K", "TC_J", "TC_T", "TC_E", "TC_N", "TC_R", "TC_S", "TC_B", "mV", "OHM"])
        
        self.ca_range = QComboBox()
        self.ca_range.addItems(["Auto", "100mV", "1V", "10V", "30V", "20mA", "20mA_SINK"])
        
        self.ca_val = QDoubleSpinBox()
        self.ca_val.setRange(-1000, 2000)
        self.ca_val.setDecimals(3)
        self.ca_val.setValue(0.000)
        
        ca_form.addRow("输出状态:", self.ca_output_state)
        ca_form.addRow("输出类型:", self.ca_type)
        ca_form.addRow("输出量程:", self.ca_range)
        ca_form.addRow("输出设定值:", self.ca_val)
        
        self.param_stack.addWidget(self.page_ca550) # 5

        # --- 页面 6: 电池模拟器快捷批量配置 (LabVIEW 风格) ---
        self.page_sim_batch = QWidget()
        sim_batch_layout = QFormLayout(self.page_sim_batch)
        self.sim_batch_volt = QDoubleSpinBox()
        self.sim_batch_volt.setRange(0, 15); self.sim_batch_volt.setDecimals(3); self.sim_batch_volt.setValue(3.800)
        self.sim_batch_curr = QDoubleSpinBox()
        self.sim_batch_curr.setRange(0, 5000); self.sim_batch_curr.setDecimals(1); self.sim_batch_curr.setValue(1000.0)
        self.sim_batch_curr.setSuffix(" mA")
        self.sim_batch_output = QComboBox()
        self.sim_batch_output.addItems(["ON", "OFF"])
        self.sim_batch_range = QComboBox()
        self.sim_batch_range.addItems(["HIGH (大量程)", "LOW (小量程)"])
        self.sim_batch_channels = QLineEdit("ALL")
        
        sim_batch_layout.addRow("设定电压 (V):", self.sim_batch_volt)
        sim_batch_layout.addRow("设定电流 (mA):", self.sim_batch_curr)
        sim_batch_layout.addRow("输出状态:", self.sim_batch_output)
        sim_batch_layout.addRow("量程范围:", self.sim_batch_range)
        sim_batch_layout.addRow("作用通道:", self.sim_batch_channels)
        self.param_stack.addWidget(self.page_sim_batch) # 6

        # --- 页面 7: 智界 EOL 协议 ---
        self.page_eol = QWidget()
        eol_form = QFormLayout(self.page_eol)
        
        # 核心通讯参数 (置顶)
        self.eol_channel = QSpinBox()
        self.eol_channel.setRange(0, 255); self.eol_channel.setValue(0)
        self.eol_tx_id = QLineEdit("0x7F0")
        self.eol_rx_id = QLineEdit("0x7F8")
        
        # 新增：CAN 类型与 DLC
        self.eol_can_type = QComboBox()
        self.eol_can_type.addItems(["Classic", "FD", "FD+BRS"])
        self.eol_dlc = QSpinBox()
        self.eol_dlc.setRange(0, 15); self.eol_dlc.setValue(8)
        
        # 业务参数
        self.eol_param2_label = QLabel("读取模式:")
        self.eol_param2 = QComboBox()
        self.eol_param1_label = QLabel("ADC选择:")
        self.eol_param1 = QComboBox()
        
        self.eol_timeout = QSpinBox()
        self.eol_timeout.setRange(1, 600000); self.eol_timeout.setValue(1000); self.eol_timeout.setSuffix(" ms")

        # 隐藏参数 (仅用于后台逻辑，需填充选项以支持数据匹配)
        self.eol_op = QComboBox()
        self.eol_op.addItems([
            "0x03 绝缘控制读取", "0x03 绝缘控制写入",
            "0x04 GPIO控制读取", "0x04 GPIO控制写入",
            "0x05 PWM读取", "0x06 ADC读取",
            "0x07 CSC控制读取", "0x07 CSC控制写入",
            "0x08 CRASH读取", "0x09 RTC控制读取", "0x09 RTC控制写入",
            "0x10 NTC读取", "0x0A EEPROM控制读取", "0x0A EEPROM控制写入",
            "0x0B 霍尔电流读取", "0xFF 唤醒源读取"
        ])
        self.eol_op.setVisible(False)
        self.eol_args = QLineEdit("")
        self.eol_args.setVisible(False)

        # 添加到布局 (按用户指定顺序)
        eol_form.addRow("RNCAN通道:", self.eol_channel)
        eol_form.addRow("发送ID:", self.eol_tx_id)
        eol_form.addRow("接收ID:", self.eol_rx_id)
        eol_form.addRow("CAN 类型:", self.eol_can_type)
        eol_form.addRow("DLC:", self.eol_dlc)
        eol_form.addRow(self.eol_param2_label, self.eol_param2)
        eol_form.addRow(self.eol_param1_label, self.eol_param1)
        eol_form.addRow("超时时间:", self.eol_timeout)
        
        # 兼容旧代码的占位符
        eol_form.addRow("", self.eol_op) 
        eol_form.addRow("", self.eol_args)
        
        self.param_stack.addWidget(self.page_eol) # 7

        # --- 页面 8: 老化板继电器参数 (22路勾选模式) ---
        self.page_aging_relay = QWidget()
        ag_layout = QVBoxLayout(self.page_aging_relay)
        
        ag_scroll = QScrollArea()
        ag_scroll_content = QWidget()
        ag_grid = QGridLayout(ag_scroll_content)
        self.aging_relay_checks = []
        
        # 继电器名称列表 (来自 aging_board_driver.py)
        relay_names = [
            "KL15", "CC1_2K_12V", "ISO_NEG_SHORT", "CHAOJI_CC_1K", 
            "IN1_OUT1", "IN2_OUT2", "IN3_OUT3", "CAN_MATCH",
            "SIG1_SIG2_SHORT", "SIG3_SHORT", "CAN1", "CAN2",
            "CAN3", "CAN4", "HV", "ISOD_30K_1M",
            "ISOD_1M_30K", "LINK_PACK_SHORT", "FACH_PACK_SHORT",
            "DC_DC_100K", "DC_DC_500K", "HALL_POWER"
        ]
        
        for i, name in enumerate(relay_names):
            cb = QCheckBox(name)
            ag_grid.addWidget(cb, i // 3, i % 3)
            self.aging_relay_checks.append(cb)
            
        ag_scroll.setWidget(ag_scroll_content)
        ag_scroll.setWidgetResizable(True)
        ag_layout.addWidget(QLabel("选择老化板操作通道 (22路):"))
        ag_layout.addWidget(ag_scroll)
        self.param_stack.addWidget(self.page_aging_relay) # 8

        # 3. 策略与判定设置
        policy_frame = QFrame()
        policy_layout = QFormLayout(policy_frame)
        self.fail_strategy_combo = QComboBox()
        self.fail_strategy_combo.addItems(["失败停止", "忽略继续", "重试3次"])
        policy_layout.addRow("指令执行失败策略:", self.fail_strategy_combo)
        
        self.cb_judgment = QCheckBox("结果输出并参与最终判定")
        self.cb_judgment.setStyleSheet("color: #00E5FF; font-weight: bold;")
        policy_layout.addRow("", self.cb_judgment)
        
        self.cb_sync = QCheckBox("同步执行 (多通道集齐后执行一次)")
        self.cb_sync.setToolTip("开启后，所有勾选的测试通道将在此处等待集齐，然后由其中一个通道代表全体执行控制指令，避免共享设备重复操作。")
        self.cb_sync.setStyleSheet("color: #FFD700;") # 金色突出显示
        policy_layout.addRow("", self.cb_sync)
        
        self.scroll_layout.addWidget(policy_frame)
        
        self.main_scroll.setWidget(self.main_scroll_content)
        main_layout.addWidget(self.main_scroll)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确认指令")
        self.btn_ok.setObjectName("btn_ok")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        main_layout.addLayout(btn_layout)
        
        # 信号连接
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)
        self.sub_category_combo.currentIndexChanged.connect(self.on_sub_category_changed)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.action_combo.currentIndexChanged.connect(self.on_action_changed)
        self.eol_op.currentTextChanged.connect(self.on_eol_op_changed)
        
        # 初始状态：如果有传入数据则执行加载，否则执行默认初始化
        if step_data:
            self._load_data(step_data)
        else:
            self.on_category_changed(0)
            self.on_eol_op_changed()

    def _combo_value(self, combo):
        return combo.currentData() if combo.currentData() is not None else combo.currentText()

    def _set_combo_by_value(self, combo, value):
        text = str(value)
        index = combo.findData(text)
        if index < 0:
            index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_param_combo(self, combo, label, title, items):
        label.setText(title)
        label.setVisible(bool(items))
        combo.clear()
        combo.setVisible(bool(items))
        for text, value in items:
            combo.addItem(text, value)

    def _gpio_items(self):
        return [
            ("0x01 DIO_CHANNEL_HSD_O_00_EN", "0x01"), ("0x02 DIO_CHANNEL_HSD_O_01_EN", "0x02"),
            ("0x03 DIO_CHANNEL_HSD_O_02_EN", "0x03"), ("0x04 DIO_CHANNEL_HSD_O_03_EN", "0x04"),
            ("0x05 DIO_CHANNEL_HSD_O_04_EN", "0x05"), ("0x06 DIO_CHANNEL_HSD_O_05_EN", "0x06"),
            ("0x07 DIO_CHANNEL_HSD_O_06_EN", "0x07"), ("0x08 DIO_CHANNEL_HSD_O_07_EN", "0x08"),
            ("0x09 DIO_CHANNEL_LSD_O_00_EN", "0x09"), ("0x0A DIO_CHANNEL_LSD_O_01_EN", "0x0A"),
            ("0x0B DIO_CHANNEL_LSD_O_02_EN", "0x0B"), ("0x0C DIO_CHANNEL_LSD_O_03_EN", "0x0C"),
            ("0x0D DIO_CHANNEL_LSD_O_04_EN", "0x0D"), ("0x0E DIO_CHANNEL_LSD_O_05_EN", "0x0E"),
            ("0x10 CC1_2015+_S2", "0x10"), ("0x11 CC2_SW3", "0x11"),
            ("0x12 LINK", "0x12"), ("0x13 FAS", "0x13"), ("0x14 SC_EN1", "0x14")
        ]

    def _index_items(self, count, prefix=""):
        return [(f"{prefix}{i}", str(i)) for i in range(count)]

    def _adc_items(self):
        # ADC 选择列表，索引按 16 进制显示
        items = [
            ("0x00 KL30_IN1_V_A2D", "0"), ("0x01 WKD_EXT1_ADC", "1"), ("0x02 WKD_EXT2_ADC", "2"), 
            ("0x03 WKD_INT1_INT2_A2D", "3"), ("0x04 WKD_INT3_INT4_A2D", "4"), ("0x05 WKD_EXT3_ADC", "5"), 
            ("0x06 KL30_IN2_V_A2D", "6"), ("0x07 WKD_EXT6_ADC", "7"), ("0x08 HWREV_A2D", "8"), 
            ("0x09 HSD_O_00_USNS", "9"), ("0x0A HSD_O_01_USNS", "10"), ("0x0B HSD_O_02_USNS", "11"), 
            ("0x0C HSD_O_03_USNS", "12"), ("0x0D WKD_INT6_ADC", "13"), ("0x0E GB2015_CC2_PE", "14"), 
            ("0x0F HSD_O_06_USNS", "15"), ("0x10 HSD_O_07_USNS", "16"), ("0x11 HSD_I_CS1_4", "17"), 
            ("0x12 LSD_V_AD1", "18"), ("0x13 LSD_V_AD2", "19"), ("0x14 NTCF_MCU", "20"), 
            ("0x15 HSD_I_CS7_8", "21"), ("0x16 SIG1_A_ADC", "22"), ("0x17 HALL_IN1_ADC", "23"), 
            ("0x18 SIG3_A_ADC", "24"), ("0x19 LSD_V_AD3", "25"), ("0x1A SBC_VS1", "26"), 
            ("0x1B HSD_O_04_USNS", "27"), ("0x1C LSD_V_AD4", "28"), ("0x1D HSD_O_05_USNS", "29"), 
            ("0x1E NTCF_I_00", "30"), ("0x1F NTCF_I_01", "31"), ("0x20 INPUT2_USNS", "32"), 
            ("0x21 INPUT3_USNS", "33"), ("0x22 HALL_5V_ADC", "34"), ("0x23 WKD_INT7_ADC", "35"), 
            ("0x24 NTCF_I_02", "36"), ("0x25 NTCF_I_03", "37"), ("0x26 NTCF_I_04", "38"), 
            ("0x27 HSD_I_CS5_6", "39"), ("0x28 NTCF_I_05", "40"), ("0x29 CHRG_GB2015_CC1", "41"), 
            ("0x2A CHRG_GB_CC2", "42"), ("0x2B INPUT1_USNS", "43"), ("0x2C OUTPUT3_USNS", "44"), 
            ("0x2D WKD_EXT4_ADC", "45"), ("0x2E Pulse1_ADC", "46"), ("0x2F OUTPUT2_USNS", "47"), 
            ("0x30 OUTPUT1_USNS", "48")
        ]
        return items

    def on_eol_op_changed(self):
        # 注意：这里不能简单的 if self.is_loading: return
        # 因为 _load_data 显式调用它来生成 combo 项
        # 但我们通过判断 combo 是否已有项来决定是否跳过 clear
        op = self.eol_op.currentText()
        if not op: return
        self._set_param_combo(self.eol_param1, self.eol_param1_label, "参数1:", [])
        self._set_param_combo(self.eol_param2, self.eol_param2_label, "参数2:", [])
        self.eol_args.setPlaceholderText("可选，格式 KEY:VALUE / KEY2:VALUE2")

        if "0x04" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "GPIO通道:", self._gpio_items())
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "读取/写入:", [("读取电平", "READ"), ("写入高电平", "WRITE_HIGH"), ("写入低电平", "WRITE_LOW")])
        elif "0x06" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "ADC选择:", self._adc_items())
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "读取模式:", [("转换值", "VALUE"), ("原始值", "RAW")])
        elif "0x05" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "PWM通道:", self._index_items(16, "PWM "))
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "读取内容:", [("占空比", "DUTY"), ("频率", "FREQ")])
        elif "0x03" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "操作内容:", [("读取绝缘阻抗", "READ"), ("设置控制状态", "WRITE")])
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "控制值:", [("0 P/N均断开", "0"), ("1 P闭合N断开", "1"), ("2 P断开N闭合", "2")])
        elif "0x07" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "操作类别:", [("单体电压", "CELL_VOLT"), ("总压/采样", "HV_VOLT"), ("设置节点数", "NODE_COUNT"), ("均衡控制", "BALANCE")])
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "子索引/状态:", self._index_items(256, "Index "))
        elif "0x10" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "NTC索引:", self._index_items(64, "NTC "))
            self.eol_args.setPlaceholderText("无需额外参数")
        elif "0x08" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "读取内容:", [("占空比", "0x01"), ("频率", "0x02"), ("阻抗", "0x03"), ("脉宽", "0x04")])
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "通道索引:", [("sig1", "0"), ("sig3", "1")])
        elif "0x0A" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "操作:", [("读取数据", "READ"), ("写入数据", "WRITE"), ("设置地址", "SET_ADDR")])
            self.eol_args.setPlaceholderText("ADDRESS:0x00, DATA:00000000")
        elif "0x09" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "RTC功能:", [("读取时间", "READ"), ("设置时间", "SET_TIME"), ("设置唤醒", "SET_WAKEUP")])
            self.eol_args.setPlaceholderText("DATA:YYYYMMDDHHMMSS")
        elif "0xFF" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "读取项:", [("唤醒源", "0x06"), ("压力传感器", "0x0E"), ("高边负载电压", "0x11")])
        elif "0x0B" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "霍尔通道:", [("通道1", "0x01"), ("通道2", "0x03")])

    def _split_params(self, params_str):
        values = {}
        for part in str(params_str).replace("；", "/").replace("，", "/").split("/"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            key, value = part.split(":", 1)
            values[key.strip().upper()] = value.strip()
        return values

    def _load_data(self, data):
        """全量还原：分类、设备、动作、策略及参数 (终极加固版)"""
        self.is_loading = True
        try:
            device = data.get('device', '')
            action = data.get('action', '')
            params_str = str(data.get('params', ''))
            step_type = data.get('type', '')
            kv = self._split_params(params_str)
            
            # 1. 还原一级分类 (Category)
            category = "设备操作"
            if "CAN" in device or "报文" in device: category = "报文交互"
            # BUG-15修复: 统一用step_type和device字段判断，不再依赖kv字典的键名匹配
            elif "智界EOL" in device or "EOL" in step_type: category = "三方协议"
            elif "等待" in device or "固定延时" in action: category = "通用交互"
            
            self.category_combo.setCurrentText(category)
            self.on_category_changed()

            # 2. 还原二级分类 (Sub-Category) - 仅限设备操作
            if category == "设备操作":
                sub_cat = "AFE"
                if "AFE" in device: sub_cat = "AFE"
                elif "继电器" in device or "Aging Board" in device or "Easy320" in device: sub_cat = "继电器"
                elif "HV Source" in device or "高压" in device: sub_cat = "高压源"
                elif "Simulator" in device or "模拟" in device: sub_cat = "模拟电池"
                elif "CA550" in device or "校准" in device: sub_cat = "校准源"
                elif "Power" in device or "电源" in device: sub_cat = "直流源"
                
                self.sub_category_combo.setCurrentText(sub_cat)
                self.on_sub_category_changed()

            # 3. 还原控制设备 (Device)
            # 使用模糊匹配，防止因为后缀不同导致失败
            for i in range(self.device_combo.count()):
                if self.device_combo.itemText(i) == device or device in self.device_combo.itemText(i):
                    self.device_combo.setCurrentIndex(i)
                    break
            self.on_device_changed()

            # 4. 还原功能动作 (Action)
            idx = self.action_combo.findText(action)
            if idx >= 0: self.action_combo.setCurrentIndex(idx)
            self.on_action_changed()
            
            # 5. 还原执行指令策略
            self.cb_judgment.setChecked(data.get('is_judgment', False))
            self.cb_sync.setChecked(data.get('sync_exec', False))
            self.fail_strategy_combo.setCurrentText(data.get('fail_strategy', "失败停止"))

            # 6. 还原具体业务参数 (特征匹配法 + 异常隔离)
            import re
            
            # --- 电压/电流框 (通用) ---
            try:
                v_match = re.search(r'([\d.]+)V', params_str)
                if v_match:
                    val = float(v_match.group(1))
                    if hasattr(self, 'i_volt'): self.i_volt.setValue(val)
                    if hasattr(self, 'sim_batch_volt'): self.sim_batch_volt.setValue(val)
                
                a_match = re.search(r'([\d.]+)A', params_str)
                if a_match: 
                    if hasattr(self, 'i_curr'): self.i_curr.setValue(float(a_match.group(1)))
                
                ma_match = re.search(r'([\d.]+)mA', params_str)
                if ma_match:
                    val = float(ma_match.group(1))
                    if hasattr(self, 'sim_batch_curr'): self.sim_batch_curr.setValue(val)
                
                if "开启" in params_str or "ON" in params_str:
                    if hasattr(self, 'output_combo'): self.output_combo.setCurrentText("开启输出")
                    if hasattr(self, 'sim_batch_output'): self.sim_batch_output.setCurrentText("ON")
                elif "关闭" in params_str or "OFF" in params_str:
                    if hasattr(self, 'output_combo'): self.output_combo.setCurrentText("关闭输出")
                    if hasattr(self, 'sim_batch_output'): self.sim_batch_output.setCurrentText("OFF")
                    
                self.cb_volt.setChecked("V" in params_str)
                self.cb_curr.setChecked("A" in params_str)
                self.cb_output.setChecked("开启" in params_str or "关闭" in params_str or "ON" in params_str)
            except: pass

            # --- CAN 参数 (Page 1) ---
            try:
                if "ID" in kv: self.c_id.setText(kv["ID"])
                if "DATA" in kv: self.c_data.setText(kv["DATA"])
                if "WAIT_ID" in kv: self.c_wait_id.setText(kv["WAIT_ID"])
                if "TIMEOUT" in kv: self.c_timeout.setValue(int(float(kv["TIMEOUT"])))
                if "TYPE" in kv: self.c_type.setCurrentIndex(int(kv["TYPE"]))
                if "DLC" in kv: self.c_dlc.setValue(int(kv["DLC"]))
                if "CH" in kv: self.c_channel.setValue(int(kv["CH"]))
            except: pass

            # --- CA550 (Page 5) ---
            try:
                if "CA550" in device:
                    val_match = re.search(r'Val:([\d.-]+)', params_str)
                    if val_match: self.ca_val.setValue(float(val_match.group(1)))
                    if "RANGE" in kv: self.ca_range.setCurrentText(kv["RANGE"])
                    if "OUTPUT" in kv: self.ca_output_state.setCurrentText(kv["OUTPUT"])
                    # 精准匹配输出类型
                    for i in range(self.ca_type.count()):
                        t_text = self.ca_type.itemText(i).split(" ")[0]
                        if f"Type:{t_text}" in params_str or (t_text in params_str and "Type:" not in params_str):
                            self.ca_type.setCurrentIndex(i); break
            except: pass

            # --- 延时参数 (Page 2) ---
            try:
                ms_match = re.search(r'(\d+)ms', params_str)
                if ms_match: self.w_time.setValue(int(ms_match.group(1)))
            except: pass

            # --- 继电器控制 (Page 4/8) ---
            try:
                if "继电器" in step_type or "Easy320" in device or "Aging Board" in device:
                    channels = params_str.split(",")
                    for c in channels:
                        try:
                            clean_c = re.sub(r'[^\d]', '', c) # 只保留数字
                            if clean_c:
                                c_idx = int(clean_c) - 1
                                if 0 <= c_idx < 32:
                                    if "Easy320" in device: self.easy320_checks[c_idx].setChecked(True)
                                    if "Aging Board" in device and c_idx < 22: self.aging_relay_checks[c_idx].setChecked(True)
                        except: pass
            except: pass

            # --- 智界 EOL 协议 (Page 7) ---
            try:
                if "EOL" in step_type or "EOL" in kv:
                    self.eol_op.setCurrentText(kv.get("EOL", action))
                    self.on_eol_op_changed()
                    if "TIMEOUT" in kv: self.eol_timeout.setValue(int(float(kv["TIMEOUT"])))
                    if "CH" in kv: self.eol_channel.setValue(int(float(kv["CH"])))
                    if "TX_ID" in kv: self.eol_tx_id.setText(kv["TX_ID"])
                    if "RX_ID" in kv: self.eol_rx_id.setText(kv["RX_ID"])
                    
                    mappings = [("0x06", ["ADC", "MODE"]), ("0x03", ["STATE"]), ("0x04", ["INDEX", "LEVEL"]), 
                                ("0x05", ["PWM"]), ("0x10", ["NTC"]), ("0x0B", ["HALL"])]
                    for code, keys in mappings:
                        if code in str(kv.get("EOL", "")):
                            for k in keys:
                                if k in kv:
                                    combo = self.eol_param1 if k in ["ADC", "STATE", "INDEX", "PWM", "NTC", "HALL"] else self.eol_param2
                                    self._set_combo_by_value(combo, kv[k])
            except: pass
        
        except Exception as e:
            print(f"Error in _load_data: {e}")
        finally:
            self.is_loading = False
            self.update()

    def on_category_changed(self, index=0):
        category = self.category_combo.currentText()
        self.sub_category_combo.setVisible(category == "设备操作")
        
        self.sub_category_combo.clear()
        self.device_combo.clear()
        
        if category == "设备操作":
            self.sub_category_combo.addItems(["AFE", "直流源", "高压源", "模拟电池", "继电器", "校准源"])
        elif category == "报文交互":
            self.device_combo.addItems(["CAN 交互"])
        elif category == "三方协议":
            self.device_combo.addItems(["智界EOL协议"])
        elif category == "通用交互":
            self.device_combo.addItems(["等待 (Wait)"])
        
        if not self.is_loading:
            if category == "设备操作":
                self.on_sub_category_changed()
            else:
                self.on_device_changed()

    def on_sub_category_changed(self, index=0):
        if self.category_combo.currentText() != "设备操作": return
        
        sub_cat = self.sub_category_combo.currentText()
        self.device_combo.clear()
        
        if sub_cat == "AFE":
            self.device_combo.addItems(["1# AFE 电源 (AFE 1)", "2# AFE 电源 (AFE 2)", "3# AFE 电源 (AFE 3)"])
        elif sub_cat == "继电器":
            self.device_combo.addItems(["Easy320 继电器 (Easy320)", "老化功能板继电器 (Aging Board)"])
        elif sub_cat == "高压源":
            self.device_combo.addItems(["NGI 高压源 (HV Source)"])
        elif sub_cat == "模拟电池":
            self.device_combo.addItems(["1# 电池模拟器 (Simulator 1)", "2# 电池模拟器 (Simulator 2)", "3# 电池模拟器 (Simulator 3)"])
        elif sub_cat == "校准源":
            self.device_combo.addItems(["CA550 校准仪 (CA550)"])
        elif sub_cat == "直流源":
            self.device_combo.addItems(["控制板供电电源 (Control Power)", "主机板电源 (Main Power)"])
        
        if not self.is_loading:
            self.on_device_changed()

    def on_device_changed(self, index=0):
        self.action_combo.clear()
        device_text = self.device_combo.currentText()
        if not device_text: return
        
        if "智界EOL" in device_text:
            self.action_combo.addItems([
                "0x03 绝缘控制读取", "0x04 GPIO控制读取", "0x05 PWM读取", "0x06 ADC读取",
                "0x07 CSC控制读取", "0x08 CRASH读取", "0x09 RTC控制读取", "0x10 NTC读取",
                "0x0A EEPROM控制读取", "0x0B 霍尔电流读取", "0xFF 唤醒源读取"
            ])
        elif "CAN" in device_text:
            self.action_combo.addItems(["发送指令", "交互/问答", "读取数据"])
        elif "等待" in device_text:
            self.action_combo.addItems(["固定延时"])
        elif "Easy320" in device_text:
            self.action_combo.addItems(["闭合勾选通道", "断开勾选通道", "全部断开"])
        elif "老化" in device_text:
            self.action_combo.addItems(["闭合勾选通道", "断开勾选通道", "全部断开"])
        elif "CA550" in device_text:
            self.action_combo.addItems(["参数设置", "数据回读"])
        else: # 电源类
            if "Simulator" in device_text:
                self.action_combo.addItems(["快捷批量配置", "回读数据"])
            elif any(x in device_text for x in ["HV Source", "Control Power", "Main Power", "控制板", "主机板", "高压源"]):
                self.action_combo.addItems(["设置参数", "回读数据"])
            else:
                self.action_combo.addItems(["设置参数", "回读数据", "全部通道开启", "全部通道关闭"])
        
        if not self.is_loading:
            self.on_action_changed()

    def on_action_changed(self):
        device = self.device_combo.currentText()
        action = self.action_combo.currentText()
        
        if "智界EOL" in device:
            self.param_stack.setCurrentIndex(7)
            # 同步 action 到内部 eol_op 逻辑，并保持其隐藏
            self.eol_op.setCurrentText(action)
            self.on_eol_op_changed()
            self.eol_op.setVisible(False)
        elif "CAN" in device:
            self.param_stack.setCurrentIndex(1)
        elif "等待" in device:
            self.param_stack.setCurrentIndex(2)
        elif "同步屏障" in device:
            self.param_stack.setCurrentIndex(-1)
        elif "老化" in device:
            self.param_stack.setCurrentIndex(8)
        elif "继电器" in device or "Easy320" in device:
            self.param_stack.setCurrentIndex(4)
        elif "CA550" in device:
            if "参数设置" in action:
                self.param_stack.setCurrentIndex(5)
            elif "回读" in action:
                self.param_stack.setCurrentIndex(3)
            else:
                self.param_stack.setCurrentIndex(-1)
        elif "设置参数" in action or "快捷批量配置" in action:
            if "Simulator" in device:
                self.param_stack.setCurrentIndex(6)
            else:
                self.param_stack.setCurrentIndex(0)
                # 动态调整范围
                if "AFE" in device:
                    self.i_volt.setRange(0, 100)
                    # 2# 和 3# AFE 电源电流限制为 12A，1# 为 36A
                    if "2#" in device or "3#" in device:
                        self.i_curr.setRange(0, 12)
                    else:
                        self.i_curr.setRange(0, 36)
                    self.i_curr.setSuffix(" A")
                elif "control power" in device.lower() or "控制板" in device:
                    self.i_volt.setRange(0, 30)
                    self.i_curr.setRange(0, 40)
                    self.i_curr.setSuffix(" A")
                elif "主机板" in device or "Main Power" in device:
                    self.i_volt.setRange(0, 30)
                    self.i_curr.setRange(0, 200)
                    self.i_curr.setSuffix(" A")
                elif "控制板" in device or "Control Power" in device:
                    self.i_volt.setRange(0, 30)
                    self.i_curr.setRange(0, 40)
                    self.i_curr.setSuffix(" A")
                elif "Simulator" in device: # 虽然现在模拟器用Page 6，但以防万一Page 0也被选中
                    self.i_volt.setRange(0, 15)
                    self.i_curr.setRange(0, 5)
                    self.i_curr.setSuffix(" A")
                else: # NGI 或其它
                    self.i_volt.setRange(0, 1000)
                    self.i_curr.setRange(0, 500)
                    self.i_curr.setSuffix(" A")
        elif "回读" in action or "读取数据" in action:
            self.param_stack.setCurrentIndex(3)
        else: # 全局操作等
            self.param_stack.setCurrentIndex(-1) # 隐藏参数区

    def get_data(self):
        device = self.device_combo.currentText()
        action = self.action_combo.currentText()
        idx = self.param_stack.currentIndex()
        
        params = []
        step_type = "设置仪表"
        
        if "同步屏障" in device:
            step_type = "同步屏障"
            params.append("Barrier")
        elif idx == 0: # 设置页面
            if self.cb_volt.isChecked(): params.append(f"{self.i_volt.value()}V")
            if self.cb_curr.isChecked(): params.append(f"{self.i_curr.value()}A")
            if self.cb_output.isChecked(): params.append(self.output_combo.currentText())
        elif idx == 3: # 读取页面
            step_type = "读取仪表"
            if self.rb_volt.isChecked(): params.append("读取电压")
            if self.rb_curr.isChecked(): params.append("读取电流")
        elif idx == 4: # Easy320 / Relay
            step_type = "继电器控制"
            selected = [str(i+1) for i, cb in enumerate(self.easy320_checks) if cb.isChecked()]
            params.append(",".join(selected))
        elif idx == 8: # Aging Board Relay
            step_type = "继电器控制"
            selected = [str(i+1) for i, cb in enumerate(self.aging_relay_checks) if cb.isChecked()]
            params.append(",".join(selected))
        elif idx == 1: # CAN
            step_type = "CAN发送" if "发送" in action else "CAN交互"
            params.append(f"ID:{self.c_id.text().strip()}")
            params.append(f"DATA:{self.c_data.text().strip()}")
            if "发送" not in action:
                params.append(f"WAIT_ID:{self.c_wait_id.text().strip()}")
                params.append(f"TIMEOUT:{self.c_timeout.value()}")
            params.append(f"TYPE:{self.c_type.currentIndex()}")
            params.append(f"DLC:{self.c_dlc.value()}")
            params.append(f"CH:{self.c_channel.value()}")
        elif idx == 7: # 智界 EOL 协议
            step_type = "智界EOL协议"
            eol_action = action
            params.append(f"EOL:{eol_action}")
            
            # --- 核心业务参数匹配 (硬编码映射，解决 Label 匹配不可靠问题) ---
            if "0x06" in eol_action:
                params.append(f"ADC:{self._combo_value(self.eol_param1)}")
                params.append(f"MODE:{self._combo_value(self.eol_param2)}")
            elif "0x03" in eol_action:
                params.append(f"STATE:{self._combo_value(self.eol_param1)}")
            elif "0x04" in eol_action:
                params.append(f"INDEX:{self._combo_value(self.eol_param1)}")
                params.append(f"LEVEL:{self._combo_value(self.eol_param2)}")
            elif "0x05" in eol_action:
                params.append(f"PWM:{self._combo_value(self.eol_param1)}")
            elif "0x10" in eol_action:
                params.append(f"NTC:{self._combo_value(self.eol_param1)}")
            elif "0x0B" in eol_action:
                params.append(f"HALL:{self._combo_value(self.eol_param1)}")
            
            # 通用参数
            params.append(f"TIMEOUT:{self.eol_timeout.value()}")
            params.append(f"CH:{self.eol_channel.value()}")
            params.append(f"TYPE:{self.eol_can_type.currentIndex()}")
            params.append(f"DLC:{self.eol_dlc.value()}")
            params.append(f"TX_ID:{self.eol_tx_id.text().strip()}")
            params.append(f"RX_ID:{self.eol_rx_id.text().strip()}")
        elif idx == 2: # 等待
            step_type = "等待"
            params.append(f"{self.w_time.value()}ms")
        elif idx == 5: # CA550
            step_type = "校准仪设置"
            params.append(f"Type:{self.ca_type.currentText().split(' ')[0]}")
            params.append(f"Val:{self.ca_val.value()}")
            params.append(f"Range:{self.ca_range.currentText()}")
            params.append(f"Output:{self.ca_output_state.currentText()}")
        elif idx == 6: # 模拟器批量页面
            params.append(f"{self.sim_batch_volt.value()}V")
            params.append(f"{self.sim_batch_curr.value()}mA")
            params.append(f"{self.sim_batch_output.currentText()}")
            params.append(f"Range:{self.sim_batch_range.currentText().split(' ')[0]}")
            params.append(f"CH:{self.sim_batch_channels.text()}")
        elif "全部" in action:
            if "开启" in action: params.append("开启")
            elif "关闭" in action: params.append("关闭")
            else: params.append("--")

        params_str = " / ".join(params) if params else "--"
        
        return {
            'device': device,
            'action': action,
            'params': params_str,
            'type': step_type,
            'is_judgment': self.cb_judgment.isChecked(),
            'sync_exec': self.cb_sync.isChecked(),
            'fail_strategy': self.fail_strategy_combo.currentText(),
            'name': f"{device}-{action} ({params_str})" + (" [同步]" if self.cb_sync.isChecked() else "")
        }
