from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, 
                               QSpinBox, QStackedWidget, QWidget, QFormLayout, QFrame, QCheckBox)
from PySide6.QtCore import Qt

class StepDialog(QDialog):
    def __init__(self, parent=None, step_data=None):
        super().__init__(parent)
        self.setWindowTitle("编辑指令 (子工步)")
        self.resize(620, 720)
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
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        # 1. 设备与大类选择
        top_frame = QFrame()
        top_layout = QFormLayout(top_frame)
        top_layout.setLabelAlignment(Qt.AlignRight)
        top_layout.setSpacing(15)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems([
            "电池模拟器 (Simulator)", 
            "NGI 高压源 (HV Source)", 
            "1# AFE 电源 (AFE 1)", 
            "2# AFE 电源 (AFE 2)", 
            "3# AFE 电源 (AFE 3)", 
            "主机板电源 (Main Power)",
            "CA550 校准仪 (CA550)",
            "Easy320 继电器 (Easy320)",
            "老化功能板继电器 (Aging Board)",
            "功能测试板电源 (Power Board)",
            "CAN 交互",
            "智界EOL协议",
            "等待 (Wait)",
            "同步屏障 (Synchronization Barrier)"
        ])
        top_layout.addRow("控制设备:", self.device_combo)
        
        self.action_combo = QComboBox()
        top_layout.addRow("功能动作:", self.action_combo)
        
        main_layout.addWidget(top_frame)
        
        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #0F3460;")
        main_layout.addWidget(line)
        
        # 2. 动态参数配置区
        self.param_stack = QStackedWidget()
        
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

        # --- 页面 4: 继电器参数 ---
        self.page_relay = QWidget()
        r_form = QFormLayout(self.page_relay)
        self.r_channel = QSpinBox()
        self.r_channel.setRange(1, 256)
        r_form.addRow("目标通道 (CH):", self.r_channel)
        self.param_stack.addWidget(self.page_relay)

        # --- 页面 5: CA550 参数 ---
        self.page_ca550 = QWidget()
        ca_form = QFormLayout(self.page_ca550)
        self.ca_type = QComboBox()
        self.ca_type.addItems(["TC_K (K型热电偶)", "TC_J (J型热电偶)", "TC_T", "TC_E", "TC_N", "TC_R", "TC_S", "TC_B", "V", "mV", "mA", "OHM"])
        self.ca_val = QDoubleSpinBox()
        self.ca_val.setRange(-1000, 2000)
        self.ca_val.setDecimals(3)
        ca_form.addRow("输出类型:", self.ca_type)
        ca_form.addRow("输出设定值:", self.ca_val)
        self.param_stack.addWidget(self.page_ca550)

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
        self.eol_op = QComboBox()
        self.eol_op.setEditable(False)
        self.eol_op.addItems([
            "0x03_read_insulation", "0x03_insulation_control",
            "0x04_read_gpio", "0x04_write_gpio",
            "0x05_read_pwm_duty", "0x05_read_pwm_freq",
            "0x06_read_adc_value", "0x06_read_adc_raw",
            "0x07_set_csc_node_count", "0x07_read_csc_hv", "0x07_csc_balance_control",
            "0x07_read_cell_voltage", "0x07_read_stack_voltage", "0x07_read_fast_charge_impedance",
            "0x08_read_crash_pwm_duty", "0x08_read_crash_pwm_freq",
            "0x08_read_crash_impedance", "0x08_read_crash_pulse_width",
            "0x09_read_rtc_time", "0x09_set_rtc_wakeup", "0x09_set_rtc_time",
            "0x10_read_cell_temp", "0x10_read_pcb_temp", "0x10_read_host_temp", "0x10_read_host_pcb_temp",
            "0x0a_set_eeprom_address", "0x0a_read_eeprom_data", "0x0a_write_eeprom_data",
            "0x0b_read_hall_current", "0x0b_read_hall_current_2",
            "0xff_read_wakeup_source", "0xff_read_pressure_sensor", "0xff_read_hsd_load_voltage"
        ])
        self.eol_param1_label = QLabel("参数1:")
        self.eol_param1 = QComboBox()
        self.eol_param2_label = QLabel("参数2:")
        self.eol_param2 = QComboBox()
        self.eol_args = QLineEdit("")
        self.eol_channel = QSpinBox()
        self.eol_channel.setRange(0, 255)
        self.eol_channel.setValue(0)
        self.eol_timeout = QSpinBox()
        self.eol_timeout.setRange(1, 600000)
        self.eol_timeout.setValue(1000)
        self.eol_timeout.setSuffix(" ms")
        eol_form.addRow("EOL操作:", self.eol_op)
        eol_form.addRow(self.eol_param1_label, self.eol_param1)
        eol_form.addRow(self.eol_param2_label, self.eol_param2)
        eol_form.addRow("扩展参数:", self.eol_args)
        eol_form.addRow("RNCAN通道:", self.eol_channel)
        eol_form.addRow("超时:", self.eol_timeout)
        self.param_stack.addWidget(self.page_eol) # 7

        main_layout.addWidget(self.param_stack)
        
        main_layout.addStretch()
        
        # 3. 策略与判定设置
        policy_frame = QFrame()
        policy_layout = QFormLayout(policy_frame)
        self.fail_strategy_combo = QComboBox()
        self.fail_strategy_combo.addItems(["失败停止", "忽略继续", "重试3次"])
        policy_layout.addRow("指令执行失败策略:", self.fail_strategy_combo)
        
        self.cb_judgment = QCheckBox("结果输出并参与最终判定")
        self.cb_judgment.setStyleSheet("color: #00E5FF; font-weight: bold;")
        policy_layout.addRow("", self.cb_judgment)
        main_layout.addWidget(policy_frame)
        
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
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.action_combo.currentIndexChanged.connect(self.on_action_changed)
        self.eol_op.currentTextChanged.connect(self.on_eol_op_changed)
        
        # 初始状态
        if step_data:
            self._load_data(step_data)
        else:
            self.on_device_changed(0)
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

    def on_eol_op_changed(self):
        op = self.eol_op.currentText()
        self._set_param_combo(self.eol_param1, self.eol_param1_label, "参数1:", [])
        self._set_param_combo(self.eol_param2, self.eol_param2_label, "参数2:", [])
        self.eol_args.setPlaceholderText("可选，格式 KEY:VALUE / KEY2:VALUE2")

        if "gpio" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "GPIO:", self._gpio_items())
            if "write" in op:
                self._set_param_combo(self.eol_param2, self.eol_param2_label, "LEVEL:", [("0 低电平", "0"), ("1 高电平", "1")])
        elif "adc" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "INDEX:", self._index_items(49, "ADC "))
        elif "pwm" in op and "crash" not in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "PWM:", self._index_items(16, "PWM "))
        elif "insulation_control" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "STATE:", [("0 P/N均断开", "0"), ("1 P闭合N断开", "1"), ("2 P断开N闭合", "2")])
        elif "node_count" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "COUNT:", self._index_items(12, "节点 "))
        elif "balance_control" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "CELL:", self._index_items(256, "Cell "))
            self._set_param_combo(self.eol_param2, self.eol_param2_label, "STATE:", [("0 关闭", "0"), ("1 开启", "1")])
        elif "cell_voltage" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "CELL:", self._index_items(256, "Cell "))
        elif "temp" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "INDEX:", self._index_items(64, "NTC "))
        elif "crash_impedance" in op:
            self._set_param_combo(self.eol_param1, self.eol_param1_label, "INDEX:", [("0 sig1", "0"), ("1 sig3", "1")])
        elif "eeprom_address" in op:
            self.eol_args.setPlaceholderText("ADDRESS:0x00000000")
        elif "eeprom_data" in op or "rtc" in op:
            self.eol_args.setPlaceholderText("DATA:00000000")

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
        """将已有数据填充到界面"""
        # 暂时阻塞信号，避免初始化过程中的交叉触发
        self.device_combo.blockSignals(True)
        self.action_combo.blockSignals(True)

        device = data.get('device', '')
        action = data.get('action', '')
        params_str = data.get('params', '')
        step_type = data.get('type', '')
        kv = self._split_params(params_str)
        is_eol_step = "EOL" in step_type.upper() or "智界EOL" in step_type or "EOL" in kv
        if is_eol_step:
            device = "智界EOL协议"
            action = "执行EOL操作"

        # 1. 设置设备
        index = self.device_combo.findText(device)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)
        
        # 无论是否找到设备，都强制执行一次联动刷新以填充 action_combo
        self.on_device_changed(self.device_combo.currentIndex())
            
        # 2. 设置动作 (增加模糊匹配以兼容旧版数据)
        index = self.action_combo.findText(action)
        if index < 0:
            # 尝试模糊匹配，例如 "设置电压/电流" 匹配 "设置参数"
            for i in range(self.action_combo.count()):
                txt = self.action_combo.itemText(i)
                if action[:2] in txt or txt[:2] in action: # 匹配前两个字，如 "设置"
                    index = i
                    break
        
        if index >= 0:
            self.action_combo.setCurrentIndex(index)
        
        # 刷新参数堆栈界面
        self.on_action_changed()
        
        self.device_combo.blockSignals(False)
        self.action_combo.blockSignals(False)

        # 2. 判定勾选与策略
        is_judgment = data.get('is_judgment')
        self.cb_judgment.setChecked(bool(is_judgment))
        
        fail_strategy = data.get('fail_strategy', '失败停止')
        self.fail_strategy_combo.setCurrentText(fail_strategy)

        # 3. 解析参数字符串并尝试还原

        # --- 模拟器批量参数还原 ---
        if "mA" in params_str:
            import re
            ma_match = re.search(r"([\d.]+)mA", params_str)
            if ma_match: self.sim_batch_curr.setValue(float(ma_match.group(1)))
            
            v_match = re.search(r"([\d.]+)V", params_str)
            if v_match: self.sim_batch_volt.setValue(float(v_match.group(1)))
            
            if "ON" in params_str: self.sim_batch_output.setCurrentText("ON")
            elif "OFF" in params_str: self.sim_batch_output.setCurrentText("OFF")
            
            if "Range:HIGH" in params_str: self.sim_batch_range.setCurrentIndex(0)
            elif "Range:LOW" in params_str: self.sim_batch_range.setCurrentIndex(1)
            
            if "CH:" in params_str:
                self.sim_batch_channels.setText(params_str.split("CH:")[-1])

        # --- 通用参数还原 ---
        if "V" in params_str:
            import re
            v_match = re.search(r'([\d.]+)V', params_str)
            if v_match:
                self.cb_volt.setChecked(True)
                self.i_volt.setValue(float(v_match.group(1)))
        
        if "A" in params_str:
            import re
            a_match = re.search(r'([\d.]+)A', params_str)
            if a_match:
                self.cb_curr.setChecked(True)
                self.i_curr.setValue(float(a_match.group(1)))

        if "开启" in params_str:
            self.cb_output.setChecked(True)
            self.output_combo.setCurrentText("开启输出")
        elif "关闭" in params_str:
            self.cb_output.setChecked(True)
            self.output_combo.setCurrentText("关闭输出")

        if "ms" in params_str:
            import re
            ms_match = re.search(r'(\d+)ms', params_str)
            if ms_match:
                self.w_time.setValue(int(ms_match.group(1)))

        if "EOL" in kv:
            self.eol_op.setCurrentText(kv.get("EOL", ""))
            self.on_eol_op_changed()
            self.eol_timeout.setValue(int(float(kv.get("TIMEOUT", "1000"))))
            self.eol_channel.setValue(int(float(kv.get("CH", "0"))))
            used_keys = {"EOL", "TIMEOUT", "CH"}
            if self.eol_param1.isVisible():
                key = self.eol_param1_label.text().replace(":", "").strip().upper()
                if key in kv:
                    self._set_combo_by_value(self.eol_param1, kv[key])
                    used_keys.add(key)
            if self.eol_param2.isVisible():
                key = self.eol_param2_label.text().replace(":", "").strip().upper()
                if key in kv:
                    self._set_combo_by_value(self.eol_param2, kv[key])
                    used_keys.add(key)
            eol_args = []
            for key, value in kv.items():
                if key not in used_keys:
                    eol_args.append(f"{key}:{value}")
            self.eol_args.setText(" / ".join(eol_args))
            self.param_stack.setCurrentIndex(7)
        else:
            if "ID" in kv: self.c_id.setText(kv["ID"])
            if "DATA" in kv: self.c_data.setText(kv["DATA"])
            if "WAIT_ID" in kv: self.c_wait_id.setText(kv["WAIT_ID"])
            if "TYPE" in kv: self.c_type.setCurrentIndex(max(0, min(2, int(kv["TYPE"]))))
            if "DLC" in kv: self.c_dlc.setValue(int(kv["DLC"]))
            if "CH" in kv: self.c_channel.setValue(int(kv["CH"]))
            if "TIMEOUT" in kv: self.c_timeout.setValue(int(float(kv["TIMEOUT"])))

        if "读取电压" in params_str:
            self.rb_volt.setChecked(True)
        elif "读取电流" in params_str:
            self.rb_curr.setChecked(True)

        if "CH:" in params_str:
            import re
            ch_match = re.search(r'CH:(\d+)', params_str)
            if ch_match:
                self.r_channel.setValue(int(ch_match.group(1)))
                
        if "Type:" in params_str:
            import re
            type_match = re.search(r'Type:([^\s/]+)', params_str)
            if type_match:
                type_str = type_match.group(1)
                for i in range(self.ca_type.count()):
                    if self.ca_type.itemText(i).startswith(type_str):
                        self.ca_type.setCurrentIndex(i)
                        break
        if "Val:" in params_str:
            import re
            val_match = re.search(r'Val:([\d.-]+)', params_str)
            if val_match:
                self.ca_val.setValue(float(val_match.group(1)))

    def on_device_changed(self, index):
        self.action_combo.clear()
        device_text = self.device_combo.currentText()
        
        if "智界EOL" in device_text:
            self.action_combo.addItems(["执行EOL操作"])
        elif "CAN" in device_text:
            self.action_combo.addItems(["发送指令", "交互/问答", "读取数据"])
        elif "等待" in device_text:
            self.action_combo.addItems(["固定延时"])
        elif "同步屏障" in device_text:
            self.action_combo.addItems(["等待全通道同步"])
        elif "继电器" in device_text:
            self.action_combo.addItems(["闭合指定通道", "断开指定通道", "全部断开"])
        elif "CA550" in device_text:
            self.action_combo.addItems(["设置输出参数", "开启输出", "关闭输出"])
        else: # 电源类: 模拟器, NGI, AFE, Main, Power Board
            if "Simulator" in device_text:
                self.action_combo.addItems(["快捷批量配置", "回读数据"])
            elif "AFE" in device_text:
                self.action_combo.addItems(["设置参数", "回读数据"])
            else:
                self.action_combo.addItems(["设置参数", "回读数据", "全部通道开启", "全部通道关闭"])
        
        self.on_action_changed()

    def on_action_changed(self):
        device = self.device_combo.currentText()
        action = self.action_combo.currentText()
        
        if "智界EOL" in device:
            self.param_stack.setCurrentIndex(7)
        elif "CAN" in device:
            self.param_stack.setCurrentIndex(1)
        elif "等待" in device:
            self.param_stack.setCurrentIndex(2)
        elif "同步屏障" in device:
            self.param_stack.setCurrentIndex(-1)
        elif "继电器" in device:
            if "指定通道" in action:
                self.param_stack.setCurrentIndex(4)
            else:
                self.param_stack.setCurrentIndex(-1)
        elif "CA550" in device:
            if "设置输出" in action:
                self.param_stack.setCurrentIndex(5)
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
            params.append(f"EOL:{self.eol_op.currentText().strip()}")
            if self.eol_param1.isVisible():
                key = self.eol_param1_label.text().replace(":", "").strip().upper()
                params.append(f"{key}:{self._combo_value(self.eol_param1)}")
            if self.eol_param2.isVisible():
                key = self.eol_param2_label.text().replace(":", "").strip().upper()
                params.append(f"{key}:{self._combo_value(self.eol_param2)}")
            for part in self.eol_args.text().split("/"):
                part = part.strip()
                if part:
                    params.append(part)
            params.append(f"TIMEOUT:{self.eol_timeout.value()}")
            params.append(f"CH:{self.eol_channel.value()}")
        elif idx == 2: # 等待
            step_type = "等待"
            params.append(f"{self.w_time.value()}ms")
        elif idx == 4: # 继电器
            step_type = "继电器控制"
            params.append(f"CH:{self.r_channel.value()}")
        elif idx == 5: # CA550
            step_type = "校准仪设置"
            params.append(f"Type:{self.ca_type.currentText().split(' ')[0]}")
            params.append(f"Val:{self.ca_val.value()}")
        elif idx == 6: # 模拟器批量页面
            params.append(f"{self.sim_batch_volt.value()}V")
            params.append(f"{self.sim_batch_curr.value()}mA")
            params.append(f"{self.sim_batch_output.currentText()}")
            params.append(f"Range:{self.sim_batch_range.currentText().split(' ')[0]}")
            params.append(f"CH:{self.sim_batch_channels.text()}")
        elif "全部" in action:
            params.append("--")

        params_str = " / ".join(params) if params else "--"
        
        return {
            'device': device,
            'action': action,
            'params': params_str,
            'type': step_type,
            'is_judgment': self.cb_judgment.isChecked(),
            'fail_strategy': self.fail_strategy_combo.currentText(),
            'name': f"{device}-{action} ({params_str})"
        }
