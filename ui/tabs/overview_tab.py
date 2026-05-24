from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QPushButton, QComboBox, QCheckBox,

                               QLabel, QScrollArea, QFrame)

from PySide6.QtCore import Qt, Slot

import re



class ChannelWidget(QFrame):

    def __init__(self, channel_id):

        super().__init__()

        # 初始化条码缓存属性

        self.shelf_barcode = ""

        self.master_barcode = ""

        self.slave_barcodes = []



        self.setFrameStyle(QFrame.Box | QFrame.Raised)

        # 增加高度以容纳多行条码文本(包含货架、主机、最多3个从机)

        self.setFixedSize(255, 200) # 固定大小，避免测试中状态文字长短变化导致卡片伸缩抖动

        self.setContentsMargins(8, 8, 8, 8)

        self.setStyleSheet("""

            QFrame {

                background-color: #1A1A2E; 

                border: 1px solid #3E3E5C; 

                border-radius: 12px; 

            }

            QFrame:hover {

                border: 1px solid #00E5FF; /* 悬停时边框高亮 */

            }

        """)

        

        layout = QVBoxLayout(self)

        layout.setSpacing(4)

        

        # 顶部：复选框和标题
        top_layout = QHBoxLayout()
        
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        checkmark_path = os.path.join(current_dir, "checkmark.png").replace("\\", "/")

        self.chk_select = QCheckBox()
        self.chk_select.setFixedSize(25, 25)
        self.chk_select.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #00E5FF;
                border-radius: 3px;
                background-color: #1A1A2E;
            }}
            QCheckBox::indicator:checked {{
                background-color: #1A1A2E;
                border: 2px solid #00FF00;
                image: url('{checkmark_path}');
            }}
        """)
        top_layout.addWidget(self.chk_select)

        

        top_layout.addStretch()

        

        title = QLabel(f"CH-{channel_id:02d}")

        title.setAlignment(Qt.AlignCenter)

        title.setStyleSheet("color: #FF9F0A; font-weight: bold; font-size: 14px; background-color: #31314C; border-radius: 6px; padding: 4px 10px; border: none;")

        top_layout.addWidget(title)

        

        top_layout.addStretch()

        

        # 右侧占位以实现标题绝对居中
        right_spacer = QWidget()
        right_spacer.setFixedSize(25, 25)
        right_spacer.setStyleSheet("background: transparent; border: none;")
        top_layout.addWidget(right_spacer)

        

        layout.addLayout(top_layout)

        

        # 中间：状态 (未扫码, 测试中, NG等)

        self.status_label = QLabel("等待扫码")

        self.status_label.setAlignment(Qt.AlignCenter)

        self.status_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #A0A0B0; padding: 2px;")

        layout.addWidget(self.status_label)

        

        # 底部：扫码信息区域

        self.lbl_shelf = QLabel("货架: --")

        self.lbl_master = QLabel("主机: --")

        self.lbl_s1 = QLabel("从1: --")

        self.lbl_s2 = QLabel("从2: --")

        self.lbl_s3 = QLabel("从3: --")

        

        # 为了和深色主题匹配，给每个信息框加底色和边框

        label_style = "font-size: 11px; color: #CCCCCC; background-color: #1F1F35; border: 1px solid #3E3E5C; border-radius: 4px; padding: 2px;"

        

        self.barcode_labels = [self.lbl_shelf, self.lbl_master, self.lbl_s1, self.lbl_s2, self.lbl_s3]

        for lbl in self.barcode_labels:

            lbl.setStyleSheet(label_style)

            layout.addWidget(lbl)

            

        layout.addStretch() # 将所有标签往上顶，保证布局紧凑对齐



    def set_status(self, status_text, color):

        self.status_label.setText(status_text)

        self.status_label.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {color}; padding: 2px;")

        

    def set_barcodes(self, shelf, master, slaves_list):

        """后续业务用于更新界面的接口，slaves_list 是一个包含从机条码的列表"""

        self.shelf_barcode = shelf

        self.master_barcode = master

        self.slave_barcodes = slaves_list



        self.lbl_shelf.setText(f"货架: {shelf}")

        self.lbl_master.setText(f"主机: {master}")

        

        # 动态隐藏或显示从机

        for i, lbl in enumerate([self.lbl_s1, self.lbl_s2, self.lbl_s3]):

            if i < len(slaves_list):

                lbl.setText(f"从{i+1}: {slaves_list[i]}")

                lbl.show()

            else:

                lbl.hide() # 如果当前通道配置少于3个从机，直接隐藏多余的标签节省视觉空间



    def reset_widget(self):

        """恢复通道卡片至默认等待扫码状态"""

        self.set_status("等待扫码", "#A0A0B0")

        self.lbl_shelf.setText("货架: --")

        self.lbl_master.setText("主机: --")

        self.lbl_s1.setText("从1: --")

        self.lbl_s1.show()

        self.lbl_s2.setText("从2: --")

        self.lbl_s2.show()

        self.lbl_s3.setText("从3: --")

        self.lbl_s3.show()

        self.chk_select.setChecked(False)



        # 清空条码缓存

        self.shelf_barcode = ""

        self.master_barcode = ""

        self.slave_barcodes = []





class OverviewTab(QWidget):

    def __init__(self, engine=None, db_manager=None):

        super().__init__()

        self.engine = engine

        self.db_manager = db_manager

        self._init_ui()

        

    def _init_ui(self):

        main_layout = QVBoxLayout(self)

        

        # --- 新增：顶部操作控制台 ---

        control_panel = QHBoxLayout()

        

        self.btn_select_all = QPushButton("全选/取消全选")

        self.btn_select_all.clicked.connect(self.toggle_select_all)

        control_panel.addWidget(self.btn_select_all)

        

        control_panel.addWidget(QLabel("  |  选择测试配方:"))

        self.combo_recipe = QComboBox()

        # 移除静态绑定的项，后续由 MainWindow 从配方页同步

        control_panel.addWidget(self.combo_recipe)

        

        self.btn_apply = QPushButton("下发配方至勾选通道")

        self.btn_apply.setStyleSheet("background-color: #007BFF; border-color: #0056b3;")

        self.btn_apply.clicked.connect(self.apply_recipe_to_selected)

        control_panel.addWidget(self.btn_apply)

        

        self.btn_start = QPushButton("启动扫码")

        self.btn_start.setStyleSheet("background-color: #17A2B8; border-color: #117A8B;")

        self.btn_start.clicked.connect(self.open_scan_dialog)

        control_panel.addWidget(self.btn_start)

        

        self.btn_run_test = QPushButton("开始测试")

        self.btn_run_test.setStyleSheet("background-color: #28A745; border-color: #1e7e34;")

        self.btn_run_test.clicked.connect(self.start_selected_tests)

        control_panel.addWidget(self.btn_run_test)

        

        self.btn_stop = QPushButton("强制停止测试")

        self.btn_stop.setStyleSheet("background-color: #DC3545; border-color: #bd2130;")

        self.btn_stop.clicked.connect(self.stop_selected_tests)

        control_panel.addWidget(self.btn_stop)

        

        self.btn_report_path = QPushButton("📁 报表路径")

        self.btn_report_path.setStyleSheet("background-color: #6C757D; border-color: #545b62;")

        self.btn_report_path.clicked.connect(self.select_report_path)

        control_panel.addWidget(self.btn_report_path)

        

        control_panel.addStretch()

        

        # 新增：全局同步状态指示

        self.lbl_sync_status = QLabel("同步状态: 空闲")

        self.lbl_sync_status.setStyleSheet("""

            QLabel {

                background-color: #1A1A2E;

                color: #808080;

                border: 1px solid #4ECCA3;

                border-radius: 4px;

                padding: 5px 15px;

                font-weight: bold;

            }

        """)

        control_panel.addWidget(self.lbl_sync_status)

        

        # 新增：顺序排队状态指示
        self.lbl_seq_status = QLabel("顺序排队: 空闲")
        self.lbl_seq_status.setStyleSheet("""
            QLabel {
                background-color: #1A1A2E;
                color: #808080;
                border: 1px solid #4ECCA3;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }
        """)
        control_panel.addWidget(self.lbl_seq_status)

        main_layout.addLayout(control_panel)

        

        # 定时器：轮询测试引擎状态以更新按钮可用性

        from PySide6.QtCore import QTimer

        self.status_timer = QTimer(self)

        self.status_timer.timeout.connect(self._update_buttons_state)

        self.status_timer.start(500)

        

        # 连接引擎信号

        if self.engine:

            self.engine.barrier_status_changed.connect(self.update_sync_status)

            self.engine.seq_status_changed.connect(self.update_seq_status)

            self.engine.channel_sync_status_changed.connect(self.on_channel_sync_changed)

            self.engine.channel_step_started.connect(self.on_channel_step_started)

            self.engine.channel_test_finished.connect(self.on_channel_test_finished)

        

        # --- 下方：通道网格 ---

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        

        container = QWidget()

        self.grid_layout = QGridLayout(container)

        self.grid_layout.setHorizontalSpacing(2)  # 进一步缩小卡片左右间距

        self.grid_layout.setVerticalSpacing(6)    # 保持适当的上下间距

        self.grid_layout.setContentsMargins(5, 5, 5, 5) # 缩小边缘留白

        

        # BUG-13修复: 从配置动态读取活跃通道数，不再硬编码

        active_channels = 48  # 默认值

        if self.db_manager:

            cfg = self.db_manager.load_sys_config()

            active_channels = int(cfg.get("active_channels", 48))



        # 初始化 60 个通道的监控卡片

        self.channel_widgets = []

        columns = 5  # 每行改为 5 个通道

        for i in range(60):

            ch_id = i + 1

            ch_widget = ChannelWidget(ch_id)



            # 超出配置通道数的工位禁用

            if ch_id > active_channels:

                ch_widget.setEnabled(False)

                ch_widget.set_status("已禁用", "#555555")

                ch_widget.setStyleSheet("background-color: #121212; border: 1px solid #222222; border-radius: 12px;")

            

            # 开启右键菜单策略

            ch_widget.setContextMenuPolicy(Qt.CustomContextMenu)

            ch_widget.customContextMenuRequested.connect(lambda pos, cid=ch_id: self.show_context_menu(pos, cid))

            

            row = i // columns

            col = i % columns

            self.grid_layout.addWidget(ch_widget, row, col)

            self.channel_widgets.append(ch_widget)

            

        scroll.setWidget(container)

        main_layout.addWidget(scroll)



    def show_context_menu(self, pos, channel_id):

        """显示通道右键菜单"""

        from PySide6.QtWidgets import QMenu

        from PySide6.QtGui import QAction

        

        menu = QMenu(self)

        view_action = QAction("查看测试详情/实时日志", self)

        view_action.triggered.connect(lambda: self.show_channel_details(channel_id))

        menu.addAction(view_action)

        

        # 也可以加其他快捷操作

        menu.addSeparator()

        stop_action = QAction("停止当前通道", self)

        stop_action.triggered.connect(lambda: self.stop_single_channel_test(channel_id))

        menu.addAction(stop_action)

        

        menu.exec(self.channel_widgets[channel_id-1].mapToGlobal(pos))



    def show_channel_details(self, channel_id):

        """弹出详细监控对话框 (防止重复打开)"""

        if not hasattr(self, 'monitor_dialogs'):

            self.monitor_dialogs = {}

            

        # 检查是否已经存在该通道的窗口，且窗口未被销毁

        existing_dialog = self.monitor_dialogs.get(channel_id)

        if existing_dialog:

            try:

                # 尝试检查窗口是否可见（如果已被用户关闭，调用会抛异常或返回不可见）

                if existing_dialog.isVisible():

                    existing_dialog.activateWindow() # 激活窗口

                    existing_dialog.raise_()         # 置于顶层

                    return

            except:

                # 窗口可能已被销毁，清除引用准备重建

                del self.monitor_dialogs[channel_id]



        from ui.dialogs.monitor_dialog import MonitorDialog

        dialog = MonitorDialog(self, channel_id=channel_id, engine=self.engine)

        dialog.show()

        self.monitor_dialogs[channel_id] = dialog



    def open_scan_dialog(self):

        from ui.dialogs.scan_dialog import ScanDialog

        recipe_name = self.combo_recipe.currentText()

        if not recipe_name:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "未选择配方", "请先选择一个测试配方，以便确定主从拓扑结构。")

            return

            

        # 从数据库/文件加载配方以获取拓扑

        recipe_data = self.db_manager.load_recipe_json(recipe_name)

        slaves_count = 0

        if recipe_data:

            topology = recipe_data.get("topology", "1主3从")

            # 提取数字，例如 "1主3从" -> 3

            match = re.search(r"(\d)从", topology)

            if match:

                slaves_count = int(match.group(1))

        

        # 收集主界面勾选的测试通道

        checked_channels = [i + 1 for i, w in enumerate(self.channel_widgets) if w.chk_select.isChecked()]

        if not checked_channels:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "未选择通道", "请先在主界面勾选需要扫码入站的测试通道！")

            return

            

        # 识别已扫码完成的勾选通道

        already_completed = []

        for cid in checked_channels:

            w = self.channel_widgets[cid - 1]

            has_shelf = bool(w.shelf_barcode)

            has_master = bool(w.master_barcode)

            slaves_scanned = [s for s in w.slave_barcodes if s]

            has_all_slaves = len(slaves_scanned) >= slaves_count

            if has_shelf and has_master and has_all_slaves:

                already_completed.append(cid)

            

        # 实例化扫码核心对话框

        dialog = ScanDialog(self, db_manager=self.db_manager, slaves_count=slaves_count, checked_channels=checked_channels, already_completed=already_completed)

        # 连接扫码完成的自定义信号到当前界面的刷新函数

        dialog.scan_completed.connect(self.on_scan_completed)

        dialog.exec()

        

    @Slot(int, str, str, object)

    def on_scan_completed(self, target_channel, shelf, master, slaves):

        print(f"[DEBUG] on_scan_completed signal received in OverviewTab!")

        print(f"[DEBUG] Target Channel: {target_channel}, Shelf: {shelf}, Master: {master}, Slaves: {slaves}")

        # 找到对应的通道 UI 并更新数据 (target_channel 是 1-60)
        idx = target_channel - 1
        if 0 <= idx < len(self.channel_widgets):
            ch_widget = self.channel_widgets[idx]
            ch_widget.set_barcodes(shelf, master, slaves)
            ch_widget.set_status("就绪(可测试)", "#00E5FF")
            print(f"[DEBUG] Channel {target_channel} barcodes and status updated successfully.")
            self.speak_text(f"通道 {target_channel} 扫码完成")

        else:

            print(f"[DEBUG] Target Channel index {idx} out of range (0-59)!")



    def speak_text(self, text):

        import threading

        import subprocess

        def run():

            cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 4; $synth.Speak('{text}')"

            subprocess.run(["powershell", "-Command", cmd], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

        threading.Thread(target=run, daemon=True).start()



    def start_selected_tests(self):

        """开始测试勾选的通道，开始前做严格校验（配方下发和扫码完整性）"""

        # 1. 查找勾选的活跃通道

        selected_cids = [i + 1 for i, ch in enumerate(self.channel_widgets) if ch.isEnabled() and ch.chk_select.isChecked()]

        if not selected_cids:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "启动测试失败", "请先勾选需要启动测试的通道！")

            return



        # 2. 判断是否选择了配方

        recipe_name = self.combo_recipe.currentText()

        if not recipe_name:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "启动测试失败", "请选择测试配方并下发！")

            return



        # 3. 加载配方拓扑结构以获取预期的从机数量

        recipe_data = self.db_manager.load_recipe_json(recipe_name)

        expected_slaves = 0

        if recipe_data:

            topology = recipe_data.get("topology", "1主3从")

            import re

            match = re.search(r"(\d)从", topology)

            if match:

                expected_slaves = int(match.group(1))



        # 4. 判断各勾选通道的配方下发和扫码完整性

        no_recipe_channels = []

        incomplete_channels = []



        for cid in selected_cids:

            ch_widget = self.channel_widgets[cid - 1]

            

            # 校验是否下发了配方

            if not hasattr(self, 'channel_recipes') or cid not in self.channel_recipes:

                no_recipe_channels.append(cid)

                continue

                

            # 校验货架、主机、以及所有预期的从机是否都扫码成功

            has_shelf = bool(ch_widget.shelf_barcode)

            has_master = bool(ch_widget.master_barcode)

            slaves_scanned = [s for s in ch_widget.slave_barcodes if s]

            has_all_slaves = len(slaves_scanned) >= expected_slaves

            

            if not (has_shelf and has_master and has_all_slaves):

                incomplete_channels.append(cid)



        # 5. 如果有通道未下发配方，不允许启动

        if no_recipe_channels:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(

                self, 

                "启动测试被拦截", 

                f"通道 {', '.join(map(str, no_recipe_channels))} 尚未下发配方！\n\n请勾选对应通道并点击“下发配方至勾选通道”后再试。"

            )

            return



        # 6. 如果有通道扫码不完整，不允许启动

        if incomplete_channels:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(

                self, 

                "启动测试被拦截 (扫码未完成)", 

                f"以下勾选的通道条码扫码不完整，不允许启动测试：\n通道 {', '.join(map(str, incomplete_channels))}\n\n请点击“启动扫码”补全所有条码后再试！"

            )

            return



        # 7. 通过全部校验，准备进入老化箱界面

        if not self.engine:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "错误", "测试引擎未初始化！")

            return



        # 不再弹窗选择，直接跳转到“高低温老化箱”通讯控制界面，等待用户加载配方并点击“启动老化测试工步”

        parent_widget = self.parentWidget()

        while parent_widget:

            from PySide6.QtWidgets import QTabWidget

            if isinstance(parent_widget, QTabWidget):

                for idx in range(parent_widget.count()):

                    if parent_widget.tabText(idx) == "高低温老化箱":

                        parent_widget.setCurrentIndex(idx)

                        break

                break

            parent_widget = parent_widget.parentWidget()



    def trigger_multi_channel_tests(self):

        """由老化箱界面调用：立即触发已勾选且配方完整的通道进行测试"""

        selected_cids = [i + 1 for i, ch in enumerate(self.channel_widgets) if ch.isEnabled() and ch.chk_select.isChecked()]

        if not selected_cids:

            return

            

        recipe_name = self.combo_recipe.currentText()

        

        # 使用异步启动机制，防止多通道连续写库导致的主界面卡死

        from PySide6.QtCore import QTimer

        

        if self.engine:

            self.engine.begin_batch_start()

        

        def _start_next_channel(cids):

            if not cids:

                if self.engine:

                    self.engine.end_batch_start()

                return

            

            cid = cids.pop(0)

            # 如果某通道没有准备好配方，则跳过

            if cid in getattr(self, 'channel_recipes', {}):

                recipe_items = self.channel_recipes[cid]

                ch_widget = self.channel_widgets[cid - 1]

                shelf = ch_widget.shelf_barcode

                master = ch_widget.master_barcode

                slaves = [s for s in ch_widget.slave_barcodes if s]

                

                test_id = -1

                if self.db_manager:

                    test_id = self.db_manager.start_new_test(cid, shelf, master, slaves, recipe_name)

                    

                self.engine.start_channel_test(cid, recipe_items, test_id=test_id, sync_group=selected_cids, master_barcode=master, slaves=slaves)

                self.channel_widgets[cid - 1].set_status("测试中", "#28A745")

                

            # 延迟 10ms 启动下一个，让出主线程事件循环以刷新 UI

            QTimer.singleShot(10, lambda: _start_next_channel(cids))

            

        _start_next_channel(selected_cids.copy())



    def get_chamber_tab(self):

        parent = self.parent()

        while parent:

            if hasattr(parent, "tab_chamber"):

                return parent.tab_chamber

            parent = parent.parent()

        return None



    @Slot(int, str)

    def on_channel_step_started(self, cid, step_name):

        idx = cid - 1

        if 0 <= idx < len(self.channel_widgets):

            self.channel_widgets[idx].set_status(f"测试中({step_name})", "#28A745")



    @Slot(int, bool)

    def on_channel_test_finished(self, cid, success):

        idx = cid - 1

        if 0 <= idx < len(self.channel_widgets):

            status = "完成(PASS)" if success else "完成(NG)"

            color = "#28A745" if success else "#DC3545"

            self.channel_widgets[idx].set_status(status, color)



    def stop_selected_tests(self):

        """强制停止选中的测试通道"""

        selected_cids = [i + 1 for i, ch in enumerate(self.channel_widgets) if ch.isEnabled() and ch.chk_select.isChecked()]

        

        from PySide6.QtWidgets import QMessageBox

        if not selected_cids:

            if self.engine and self.engine.workers:

                reply = QMessageBox.question(

                    self, 

                    "停止所有测试", 

                    "当前未勾选任何通道，是否要强制停止**所有**正在运行的通道测试？",

                    QMessageBox.Yes | QMessageBox.No,

                    QMessageBox.No

                )

                if reply == QMessageBox.Yes:

                    selected_cids = list(self.engine.workers.keys())

                else:

                    return

            else:

                QMessageBox.warning(self, "停止测试失败", "请先勾选需要停止测试的通道！")

                return

            

        if self.engine:

            for cid in selected_cids:

                self.engine.stop_channel_test(cid)

                ch_widget = self.channel_widgets[cid - 1]

                ch_widget.set_status("已停止", "#DC3545")

                

        # 联动停止老化箱工步

        chamber_tab = self.get_chamber_tab()

        if chamber_tab and getattr(chamber_tab, 'sequence_running', False):

            chamber_tab.stop_aging_sequence()

                

        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "停止成功", f"已成功停止 {len(selected_cids)} 个通道的电池老化测试并复位老化箱！")



    def stop_single_channel_test(self, channel_id):

        """停止单个物理通道测试"""

        if self.engine:

            self.engine.stop_channel_test(channel_id)

            self.channel_widgets[channel_id - 1].set_status("已停止", "#DC3545")



    def apply_recipe_to_selected(self):

        """将选中的配方内容加载到缓存，并更新 UI"""

        recipe_name = self.combo_recipe.currentText()

        if not recipe_name:

            return

            

        # 真正从数据库读取配方详情

        recipe_data = self.db_manager.load_recipe_json(recipe_name)

        if not recipe_data:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "错误", f"无法加载配方【{recipe_name}】的数据。")

            return



        if not hasattr(self, 'channel_recipes'):

            self.channel_recipes = {}

        if not hasattr(self, 'sync_groups'):

            self.sync_groups = {}



        selected_cids = [i + 1 for i, ch in enumerate(self.channel_widgets) if ch.chk_select.isChecked()]

        count = len(selected_cids)

        for ch_id in selected_cids:

            # 过滤并深度拷贝没禁用的测试项及其子工步（禁用的项不用加载进来）

            raw_items = recipe_data.get("items", [])

            filtered_items = []

            for item in raw_items:

                if item.get("name", "").strip().startswith("#"):

                    continue

                new_item = item.copy()

                if "sub_steps" in new_item:

                    new_item["sub_steps"] = [

                        sub.copy() for sub in new_item["sub_steps"]

                        if not sub.get("name", "").strip().startswith("#")

                    ]

                filtered_items.append(new_item)

                

            # 缓存配方数据

            self.channel_recipes[ch_id] = filtered_items

            # 记录该通道所属的同步组（即本次下发的所有通道）

            self.sync_groups[ch_id] = selected_cids

            

            # 更新 UI 状态

            self.channel_widgets[ch_id-1].set_status("已配方", "#AAAAAA")



        # 未勾选的通道恢复至默认等待扫码状态，通道停止测试

        for i, ch in enumerate(self.channel_widgets):

            ch_id = i + 1

            if ch.isEnabled() and ch_id not in selected_cids:

                # 恢复 UI 状态为等待扫码

                ch.reset_widget()

                # 停止物理通道测试

                if self.engine:

                    self.engine.stop_channel_test(ch_id)

                # 清除可能缓存的配方及同步组

                if ch_id in self.channel_recipes:

                    del self.channel_recipes[ch_id]

                if ch_id in self.sync_groups:

                    del self.sync_groups[ch_id]

        

        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "下发成功", f"已成功将配方内容加载至 {count} 个通道，并建立了同步组。\n未勾选的通道已重置并停止测试。")



    def get_sync_group_for_channel(self, channel_id):

        """获取通道所属的同步组列表"""

        return getattr(self, 'sync_groups', {}).get(channel_id, [])



    def get_recipe_for_channel(self, channel_id):

        """供监控窗口查询已分配但尚未启动的配方"""

        if hasattr(self, 'channel_recipes'):

            return self.channel_recipes.get(channel_id, [])

        return []



    def toggle_select_all(self):

        # 统计当前活跃通道的选中状态

        active_widgets = [ch for ch in self.channel_widgets if ch.isEnabled()]

        if not active_widgets:

            return

            

        all_checked = all(ch.chk_select.isChecked() for ch in active_widgets)

        target_state = not all_checked  # 如果全选了就取消，否则全选

        

        # print(f"[DEBUG] Toggle Select All: target={target_state}")

        for ch in active_widgets:

            ch.chk_select.setChecked(target_state)



    def clear_all_selections(self):

        """清空所有通道的勾选状态"""

        for ch in self.channel_widgets:

            ch.chk_select.setChecked(False)



    def update_sync_status(self, waiting, total):

        """更新全局同步指示器"""

        if waiting > 0:

            self.lbl_sync_status.setText(f"同步中: {waiting}/{total} 就绪")

            self.lbl_sync_status.setStyleSheet("""

                QLabel {

                    background-color: #533483;

                    color: #FFD700;

                    border: 1px solid #FFD700;

                    border-radius: 4px;

                    padding: 5px 15px;

                    font-weight: bold;

                }

            """)

        else:

            self.lbl_sync_status.setText("同步状态: 已对齐/空闲")

            self.lbl_sync_status.setStyleSheet("""

                QLabel {

                    background-color: #1A1A2E;

                    color: #4ECCA3;

                    border: 1px solid #4ECCA3;

                    border-radius: 4px;

                    padding: 5px 15px;

                    font-weight: bold;

                }

            """)

    def update_seq_status(self, executing_cid, queue_len):
        """更新顺序排队状态指示器"""
        if executing_cid != -1:
            self.lbl_seq_status.setText(f"顺序排队: CH{executing_cid} 执行, {queue_len} 人排队")
            self.lbl_seq_status.setStyleSheet("""
                QLabel {
                    background-color: #6a0572;
                    color: #FF8C00;
                    border: 1px solid #FF8C00;
                    border-radius: 4px;
                    padding: 5px 15px;
                    font-weight: bold;
                }
            """)
        else:
            self.lbl_seq_status.setText("顺序排队: 空闲")
            self.lbl_seq_status.setStyleSheet("""
                QLabel {
                    background-color: #1A1A2E;
                    color: #4ECCA3;
                    border: 1px solid #4ECCA3;
                    border-radius: 4px;
                    padding: 5px 15px;
                    font-weight: bold;
                }
            """)
            
    def on_channel_sync_changed(self, channel_id, is_waiting):

        """处理单个通道的同步状态变化"""

        idx = channel_id - 1

        if 0 <= idx < len(self.channel_widgets):

            widget = self.channel_widgets[idx]

            if is_waiting:

                widget.set_status("等待同步", "#FFD700") # 金黄色

            else:

                # 恢复为测试中状态

                if self.engine and channel_id in self.engine.workers:

                    widget.set_status("测试中", "#28A745")



    def _update_buttons_state(self):

        """如果引擎中有通道正在测试，则禁用部分操作按钮"""

        is_testing = False

        if self.engine and len(self.engine.workers) > 0:

            is_testing = True

            

        if getattr(self, '_last_is_testing', None) == is_testing:

            return

        self._last_is_testing = is_testing

            

        self.btn_apply.setEnabled(not is_testing)

        self.btn_start.setEnabled(not is_testing)

        self.btn_run_test.setEnabled(not is_testing)

        

        # 灰色样式以便更明显地看出被禁用

        disabled_style = "background-color: #444444; color: #888888; border-color: #333333;"

        

        if is_testing:

            self.btn_apply.setStyleSheet(disabled_style)

            self.btn_start.setStyleSheet(disabled_style)

            self.btn_run_test.setStyleSheet(disabled_style)

        else:

            self.btn_apply.setStyleSheet("background-color: #007BFF; border-color: #0056b3;")

            self.btn_start.setStyleSheet("background-color: #17A2B8; border-color: #117A8B;")

            self.btn_run_test.setStyleSheet("background-color: #28A745; border-color: #1e7e34;")



            

    def update_recipes(self, recipe_list):

        """当别的界面新建了配方后，同步更新到本界面的下拉框里"""

        current = self.combo_recipe.currentText()

        self.combo_recipe.clear()

        self.combo_recipe.addItems(recipe_list)

        # 如果更新后原来的选项还在，则保持选中状态

        if current in recipe_list:

            self.combo_recipe.setCurrentText(current)



    def select_report_path(self):

        """选择报表保存根目录"""

        from PySide6.QtWidgets import QFileDialog

        import os

        sys_cfg = {}

        if self.db_manager:

            sys_cfg = self.db_manager.load_sys_config() or {}

        

        current_path = sys_cfg.get("report_root_path", os.path.abspath("reports"))

        

        dir_path = QFileDialog.getExistingDirectory(self, "选择报表保存根目录", current_path)

        if dir_path:

            sys_cfg["report_root_path"] = dir_path

            if self.db_manager:

                self.db_manager.save_sys_config(sys_cfg)

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "设置成功", f"报表保存根目录已成功设置为：\n{dir_path}")

