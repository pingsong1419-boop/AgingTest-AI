from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
                               QLabel, QScrollArea, QFrame)
from PySide6.QtCore import Qt
import re

class ChannelWidget(QFrame):
    def __init__(self, channel_id):
        super().__init__()
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        # 增加高度以容纳多行条码文本(包含货架、主机、最多3个从机)
        self.setMinimumSize(180, 190)
        self.setContentsMargins(6, 6, 6, 6)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        # 顶部：复选框和通道号
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_select = QCheckBox()
        self.chk_select.setFixedSize(20, 20)
        self.chk_select.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #00E5FF;
                border-radius: 3px;
                background-color: #1A1A2E;
            }
            QCheckBox::indicator:checked {
                background-color: #00FF00; /* 选中时变为鲜绿色 */
                border: 2px solid #FFFFFF;
            }
        """)
        top_layout.addWidget(self.chk_select)
        
        title = QLabel(f"CH-{channel_id:02d}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #31314C; border-radius: 3px; padding: 4px;")
        top_layout.addWidget(title)
        top_layout.addStretch()
        
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
        label_style = "font-size: 11px; color: #CCCCCC; background-color: #1F1F35; border: 1px solid #3E3E5C; border-radius: 2px; padding: 2px;"
        
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
        self.lbl_shelf.setText(f"货架: {shelf}")
        self.lbl_master.setText(f"主机: {master}")
        
        # 动态隐藏或显示从机
        for i, lbl in enumerate([self.lbl_s1, self.lbl_s2, self.lbl_s3]):
            if i < len(slaves_list):
                lbl.setText(f"从{i+1}: {slaves_list[i]}")
                lbl.show()
            else:
                lbl.hide() # 如果当前通道配置少于3个从机，直接隐藏多余的标签节省视觉空间


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
        
        self.btn_start = QPushButton("启动扫码/测试")
        self.btn_start.setStyleSheet("background-color: #28A745; border-color: #1e7e34;")
        self.btn_start.clicked.connect(self.open_scan_dialog)
        control_panel.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("强制停止测试")
        self.btn_stop.setStyleSheet("background-color: #DC3545; border-color: #bd2130;")
        control_panel.addWidget(self.btn_stop)
        
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
        
        main_layout.addLayout(control_panel)
        
        # 连接引擎信号
        if self.engine:
            self.engine.barrier_status_changed.connect(self.update_sync_status)
            self.engine.channel_sync_status_changed.connect(self.on_channel_sync_changed)
        
        # --- 下方：通道网格 ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(15)  # 增加卡片之间的横纵间距
        self.grid_layout.setContentsMargins(20, 20, 20, 20) # 增加周围的留白
        
        # 初始化 60 个通道的监控卡片
        self.channel_widgets = []
        columns = 8  # 每行减少为 8 个通道，避免横向挤压
        for i in range(60):
            ch_id = i + 1
            ch_widget = ChannelWidget(ch_id)
            
            # 禁用 CH-49 至 CH-60
            if ch_id > 48:
                ch_widget.setEnabled(False)
                ch_widget.set_status("已禁用", "#555555")
                ch_widget.setStyleSheet("background-color: #121212; border: 1px solid #222222;")
            
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
        
        # 模拟展示几个特殊状态
        self.channel_widgets[0].set_status("TESTING", "green")
        self.channel_widgets[1].set_status("NG", "red")
        self.channel_widgets[2].set_status("TESTING", "green")

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
        
        # 实例化扫码核心对话框
        dialog = ScanDialog(self, db_manager=self.db_manager, slaves_count=slaves_count)
        # 连接扫码完成的自定义信号到当前界面的刷新函数
        dialog.scan_completed.connect(self.on_scan_completed)
        dialog.exec()
        
    def on_scan_completed(self, target_channel, shelf, master, slaves):
        # 找到对应的通道 UI 并更新数据 (target_channel 是 1-60)
        idx = target_channel - 1
        if 0 <= idx < len(self.channel_widgets):
            ch_widget = self.channel_widgets[idx]
            ch_widget.set_barcodes(shelf, master, slaves)
            ch_widget.set_status("就绪(可测试)", "#00E5FF")

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
            # 缓存配方数据
            self.channel_recipes[ch_id] = recipe_data.get("items", [])
            # 记录该通道所属的同步组（即本次下发的所有通道）
            self.sync_groups[ch_id] = selected_cids
            
            # 更新 UI 状态
            self.channel_widgets[ch_id-1].set_status("已配方", "#AAAAAA")
        
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "下发成功", f"已成功将配方内容加载至 {count} 个通道，并建立了同步组。")

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
            
    def on_channel_sync_changed(self, channel_id, is_waiting):
        """处理单个通道的同步状态变化"""
        idx = channel_id - 1
        if 0 <= idx < len(self.channel_widgets):
            widget = self.channel_widgets[idx]
            if is_waiting:
                widget.set_status("WAIT_SYNC", "#FFD700") # 金黄色
            else:
                # 恢复为测试中状态
                widget.set_status("TESTING", "green")
            
    def update_recipes(self, recipe_list):
        """当别的界面新建了配方后，同步更新到本界面的下拉框里"""
        current = self.combo_recipe.currentText()
        self.combo_recipe.clear()
        self.combo_recipe.addItems(recipe_list)
        # 如果更新后原来的选项还在，则保持选中状态
        if current in recipe_list:
            self.combo_recipe.setCurrentText(current)
