from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, 
                               QComboBox, QMessageBox, QAbstractItemView, QMenu)
from PySide6.QtGui import QColor, QFont, QAction, QKeySequence, QShortcut
from PySide6.QtCore import Qt, Signal
from typing import List

class ConfigTab(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.clipboard_data = None  # 用于存储复制的节点数据
        self.current_recipe_name = None # 记录当前加载的配方名
        self._init_ui()
        self.refresh_recipe_list()
        self.set_editor_enabled(False) # 初始禁用编辑
        
    def _init_ui(self):
        layout = QHBoxLayout(self)
        
        # 左侧：用例配方列表
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("测试用例列表 (配方)"))
        self.recipe_tree = QTreeWidget()
        self.recipe_tree.setHeaderLabel("配方名称")
        self.recipe_tree.itemClicked.connect(self.on_recipe_selected)
        left_panel.addWidget(self.recipe_tree)
        
        self.btn_add_recipe = QPushButton("新建配方")
        self.btn_add_recipe.clicked.connect(self.add_new_recipe)
        left_panel.addWidget(self.btn_add_recipe)
        
        layout.addLayout(left_panel, 1)
        
        # 右侧：配方基础属性及工步编辑
        right_panel = QVBoxLayout()
        
        # 配方基础属性：主从拓扑配置
        prop_layout = QHBoxLayout()
        prop_layout.addWidget(QLabel("当前配方的【主从拓扑模式】:"))
        self.topology_combo = QComboBox()
        self.topology_combo.addItems(["1主0从", "1主1从", "1主2从", "1主3从"])
        self.topology_combo.setCurrentText("1主3从") # 默认选项
        prop_layout.addWidget(self.topology_combo)
        prop_layout.addStretch()
        right_panel.addLayout(prop_layout)
        
        # 使用容器包装右侧编辑区域以便整体控制启用状态
        self.edit_container = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_container)
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        
        self.edit_layout.addWidget(QLabel("测试项目与工步流 (树状结构):"))
        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderLabels(["名称/工步", "模式/范围", "目标值/下限", "截止时间/上限", "NG 策略"])
        self.step_tree.setColumnWidth(0, 250)
        
        # 启用拖拽排序
        self.step_tree.setDragEnabled(True)
        self.step_tree.setAcceptDrops(True)
        self.step_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.step_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 启用右键菜单
        self.step_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.step_tree.customContextMenuRequested.connect(self.on_context_menu)
        
        right_panel.addWidget(self.step_tree)
        
        btn_layout = QHBoxLayout()
        btn_add_item = QPushButton("添加测试项")
        btn_add_item.clicked.connect(self.add_test_item)
        btn_add_item.setStyleSheet("background-color: #17A2B8;")
        
        btn_add_step = QPushButton("添加子工步")
        btn_add_step.clicked.connect(self.add_step)
        
        btn_edit = QPushButton("编辑选中")
        btn_edit.clicked.connect(self.edit_node)
        btn_edit.setStyleSheet("background-color: #6F42C1; color: white;")
        
        btn_del = QPushButton("删除选中")
        btn_del.clicked.connect(self.delete_node)
        
        btn_save_recipe = QPushButton("保存配方")
        btn_save_recipe.clicked.connect(self.save_recipe)
        btn_save_recipe.setStyleSheet("background-color: #28A745; color: white;")
        
        btn_dry_run = QPushButton("仿真运行 (Dry Run)")
        btn_dry_run.clicked.connect(self.dry_run)
        btn_dry_run.setStyleSheet("background-color: #FF8C00; color: white;")
        
        btn_layout.addWidget(btn_add_item)
        btn_layout.addWidget(btn_add_step)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_save_recipe)
        btn_layout.addWidget(btn_dry_run)
        self.edit_layout.addLayout(btn_layout)
        
        right_panel.addWidget(self.edit_container)
        
        layout.addLayout(right_panel, 3)
        
        # 绑定双击编辑
        self.step_tree.itemDoubleClicked.connect(lambda item, col: self.edit_node())

        # 绑定快捷键
        QShortcut(QKeySequence("Ctrl+C"), self.step_tree, self.copy_node)
        QShortcut(QKeySequence("Ctrl+V"), self.step_tree, self.paste_node)
        QShortcut(QKeySequence("Delete"), self.step_tree, self.delete_node)

    def set_editor_enabled(self, enabled):
        """控制右侧编辑面板的启用状态"""
        self.edit_container.setEnabled(enabled)
        self.topology_combo.setEnabled(enabled)
        if not enabled:
            self.step_tree.clear()
            self.edit_container.setToolTip("请先在左侧选择或新建一个配方")
        else:
            self.edit_container.setToolTip("")

    def refresh_recipe_list(self):
        """从本地磁盘刷新配方列表"""
        self.recipe_tree.clear()
        recipes = self.db_manager.list_recipes()
        for name in recipes:
            self.recipe_tree.addTopLevelItem(QTreeWidgetItem([name]))

    def on_recipe_selected(self, item, column):
        """点击左侧配方时加载数据或切换折叠状态"""
        name = item.text(0)
        
        # 如果点击的是当前已选中的配方，则切换右侧树的展开/折叠状态
        if self.current_recipe_name == name:
            if self.step_tree.topLevelItemCount() > 0:
                # 以第一项的状态作为基准切换
                is_expanded = self.step_tree.topLevelItem(0).isExpanded()
                if is_expanded:
                    self.step_tree.collapseAll()
                else:
                    self.step_tree.expandAll()
            return

        data = self.db_manager.load_recipe_json(name)
        if data:
            self.current_recipe_name = name
            self.set_editor_enabled(True)
            self.load_recipe_to_tree(data)

    def load_recipe_to_tree(self, data):
        """将 JSON 数据还原到树状图中"""
        self.step_tree.clear()
        self.topology_combo.setCurrentText(data.get("topology", "1主3从"))
        
        for item_data in data.get("items", []):
            parent = QTreeWidgetItem([
                item_data['name'],
                item_data['mode'],
                item_data['min'],
                item_data['max'],
                item_data['strategy']
            ])
            parent.setForeground(0, QColor("#00E5FF"))
            font = QFont()
            font.setBold(True)
            parent.setFont(0, font)
            self.step_tree.addTopLevelItem(parent)
            
            for sub_data in item_data.get("sub_steps", []):
                child = QTreeWidgetItem([
                    f"  └─ {sub_data['name']}",
                    sub_data['action'],
                    sub_data['params'],
                    "参与判定" if sub_data.get("is_judgment") else "--",
                    sub_data.get("fail_strategy", "失败停止")
                ])
                # 恢复元数据
                child.setData(0, Qt.UserRole, sub_data.get("device"))
                child.setData(1, Qt.UserRole, sub_data.get("type"))
                child.setData(2, Qt.UserRole, sub_data.get("is_judgment"))
                
                if sub_data.get("is_judgment"):
                    child.setForeground(0, QColor("#FFD700")) # 亮金色
                
                parent.addChild(child)
        self.step_tree.expandAll()

    def on_context_menu(self, pos):
        item = self.step_tree.itemAt(pos)
        if not item: return
        
        menu = QMenu()
        copy_act = QAction("复制", self)
        copy_act.triggered.connect(self.copy_node)
        
        paste_act = QAction("粘贴", self)
        paste_act.setEnabled(self.clipboard_data is not None)
        paste_act.triggered.connect(self.paste_node)
        
        dup_act = QAction("克隆", self)
        dup_act.triggered.connect(self.duplicate_node)

        bulk_act = QAction("批量修改参数...", self)
        bulk_act.triggered.connect(self.bulk_edit_nodes)
        
        del_act = QAction("删除", self)
        del_act.triggered.connect(self.delete_node)
        
        menu.addAction(copy_act)
        menu.addAction(paste_act)
        menu.addSeparator()

        # 屏蔽/取消屏蔽操作 (保留并集成到右键菜单)
        is_skipped = item.text(0).strip().startswith("#") or "└─ #" in item.text(0)
        skip_action = QAction("取消屏蔽" if is_skipped else "屏蔽该项 (添加#)", self)
        skip_action.triggered.connect(lambda: self.toggle_skip(item))
        menu.addAction(skip_action)

        prefix_action = QAction("添加自定义前缀", self)
        prefix_action.triggered.connect(lambda: self.add_prefix(item))
        menu.addAction(prefix_action)

        menu.addSeparator()
        menu.addAction(dup_act)
        menu.addAction(bulk_act)
        menu.addSeparator()
        menu.addAction(del_act)
        menu.exec_(self.step_tree.viewport().mapToGlobal(pos))

    def toggle_skip(self, item):
        """切换屏蔽状态：在名称前添加或移除 #"""
        text = item.text(0)
        if "#" in text:
            # 移除所有 #
            item.setText(0, text.replace("#", ""))
            item.setForeground(0, QColor("#FFFFFF") if item.parent() else QColor("#00E5FF"))
        else:
            # 添加 #
            if "└─ " in text:
                parts = text.split("└─ ")
                item.setText(0, f"{parts[0]}└─ #{parts[1]}")
            else:
                item.setText(0, "#" + text)
            item.setForeground(0, QColor("#808080")) # 屏蔽后显示为灰色

    def add_prefix(self, item):
        """为工步名称添加自定义前缀"""
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "添加前缀", "请输入前缀内容:")
        if ok and text:
            old_text = item.text(0)
            if "└─ " in old_text:
                parts = old_text.split("└─ ")
                item.setText(0, f"{parts[0]}└─ {text}_{parts[1]}")
            else:
                item.setText(0, f"{text}_{old_text}")

    def _get_node_data(self, item):
        """序列化单个节点及其子节点"""
        is_parent = item.parent() is None
        if is_parent:
            data = {
                "type": "item",
                "name": item.text(0),
                "mode": item.text(1),
                "min": item.text(2),
                "max": item.text(3),
                "strategy": item.text(4),
                "sub_steps": []
            }
            for i in range(item.childCount()):
                data["sub_steps"].append(self._get_node_data(item.child(i)))
            return data
        else:
            return {
                "type": "step",
                "name": item.text(0).replace("  └─ ", ""),
                "action": item.text(1),
                "params": item.text(2),
                "device": item.data(0, Qt.UserRole),
                "stype": item.data(1, Qt.UserRole),
                "is_judgment": item.data(2, Qt.UserRole),
                "fail_strategy": item.text(4)
            }

    def copy_node(self):
        item = self.step_tree.currentItem()
        if item:
            self.clipboard_data = self._get_node_data(item)

    def paste_node(self):
        if not self.clipboard_data: return
        
        current = self.step_tree.currentItem()
        data = self.clipboard_data
        
        if data["type"] == "item":
            # 粘贴为顶层测试项
            new_item = QTreeWidgetItem([
                data['name'], data['mode'], data['min'], data['max'], data['strategy']
            ])
            new_item.setForeground(0, QColor("#00E5FF"))
            font = QFont()
            font.setBold(True)
            new_item.setFont(0, font)
            
            for sub in data.get("sub_steps", []):
                child = QTreeWidgetItem([
                    f"  └─ {sub['name']}", sub['action'], sub['params'],
                    "参与判定" if sub.get("is_judgment") else "--",
                    sub.get("fail_strategy", "失败停止")
                ])
                child.setData(0, Qt.UserRole, sub.get("device"))
                child.setData(1, Qt.UserRole, sub.get("stype"))
                child.setData(2, Qt.UserRole, sub.get("is_judgment"))
                if sub.get("is_judgment"): child.setForeground(0, QColor("#FFD700"))
                new_item.addChild(child)
            
            if current:
                idx = self.step_tree.indexOfTopLevelItem(current if not current.parent() else current.parent())
                self.step_tree.insertTopLevelItem(idx + 1, new_item)
            else:
                self.step_tree.addTopLevelItem(new_item)
                
        elif data["type"] == "step":
            # 粘贴为子工步
            parent = current if (current and not current.parent()) else (current.parent() if current else None)
            if not parent: return
            
            child = QTreeWidgetItem([
                f"  └─ {data['name']}", data['action'], data['params'],
                "参与判定" if data.get("is_judgment") else "--",
                data.get("fail_strategy", "失败停止")
            ])
            child.setData(0, Qt.UserRole, data.get("device"))
            child.setData(1, Qt.UserRole, data.get("stype"))
            child.setData(2, Qt.UserRole, data.get("is_judgment"))
            if data.get("is_judgment"): child.setForeground(0, QColor("#FFD700"))
            
            if current and current.parent():
                idx = parent.indexOfChild(current)
                parent.insertChild(idx + 1, child)
            else:
                parent.addChild(child)
            parent.setExpanded(True)

    def duplicate_node(self):
        self.copy_node()
        self.paste_node()

    def bulk_edit_nodes(self):
        # 1. 提取当前树中出现的所有设备名
        devices = set()
        for i in range(self.step_tree.topLevelItemCount()):
            item = self.step_tree.topLevelItem(i)
            for j in range(item.childCount()):
                d = item.child(j).data(0, Qt.UserRole)
                if d: devices.add(d)
        
        from ui.dialogs.bulk_edit_dialog import BulkEditDialog
        dialog = BulkEditDialog(sorted(list(devices)), self)
        if dialog.exec():
            cfg = dialog.get_config()
            count = 0
            
            # 2. 遍历树进行修改
            for i in range(self.step_tree.topLevelItemCount()):
                item = self.step_tree.topLevelItem(i)
                for j in range(item.childCount()):
                    sub = item.child(j)
                    dev = sub.data(0, Qt.UserRole) or ""
                    act = sub.text(1)
                    
                    # 匹配过滤条件
                    match_dev = (cfg["device_filter"] == "-- 全部设备 --") or (dev == cfg["device_filter"])
                    match_act = (not cfg["action_filter"]) or (cfg["action_filter"] in act)
                    
                    if match_dev and match_act:
                        if cfg["mode"] == 0: # 查找并替换
                            new_params = sub.text(2).replace(cfg["find_text"], cfg["replace_text"])
                            sub.setText(2, new_params)
                        elif cfg["mode"] == 1: # 统一设置
                            sub.setText(2, cfg["replace_text"])
                        elif cfg["mode"] == 2: # 修改策略
                            sub.setText(4, cfg["strategy"])
                        count += 1
            
            QMessageBox.information(self, "完成", f"批量修改完成，共影响 {count} 个工步。")

    def dry_run(self):
        """仿真运行：使用 Mock 设备管理器运行当前编辑的配方"""
        # 1. 序列化当前 UI 中的配方数据
        items = []
        for i in range(self.step_tree.topLevelItemCount()):
            node = self.step_tree.topLevelItem(i)
            item_data = {
                "name": node.text(0),
                "strategy": node.text(4),
                "min": node.text(2),
                "max": node.text(3),
                "sub_steps": []
            }
            for j in range(node.childCount()):
                sub = node.child(j)
                item_data["sub_steps"].append({
                    "name": sub.text(0).replace("  └─ ", ""),
                    "type": sub.data(1, Qt.UserRole),
                    "device": sub.data(0, Qt.UserRole),
                    "action": sub.text(1),
                    "params": sub.text(2),
                    "is_judgment": sub.data(2, Qt.UserRole),
                    "fail_strategy": sub.text(4)
                })
            items.append(item_data)
            
        if not items:
            QMessageBox.warning(self, "提醒", "配方为空，无法运行仿真。")
            return

        # 2. 初始化 Mock 硬件和临时引擎
        from devices.mock_manager import MockDeviceManager
        from core.engine import TestEngine
        from ui.dialogs.monitor_dialog import MonitorDialog
        
        mock_mgr = MockDeviceManager()
        # 注意：这里我们不传真实 db_manager，防止仿真数据污染数据库
        temp_engine = TestEngine(device_manager=mock_mgr, db_manager=None)
        
        # 3. 弹出监控窗口（使用通道 1 进行演示）
        dialog = MonitorDialog(channel_id=1, engine=temp_engine, parent=self)
        dialog.setWindowTitle("🧪 配方仿真运行 - 通道 1 (虚拟硬件)")
        
        # 启动测试
        temp_engine.start_channel_test(1, items)
        dialog.exec()
        
        # 结束后清理
        temp_engine.stop_all()

    def validate_recipe(self) -> List[str]:
        """逻辑校验：返回错误列表"""
        errors = []
        if self.step_tree.topLevelItemCount() == 0:
            errors.append("配方中没有任何测试项。")
            
        for i in range(self.step_tree.topLevelItemCount()):
            item = self.step_tree.topLevelItem(i)
            if item.childCount() == 0:
                errors.append(f"测试项【{item.text(0)}】下没有任何子工步。")
            
            for j in range(item.childCount()):
                sub = item.child(j)
                if "设置" in sub.text(1) and not sub.text(2):
                    errors.append(f"工步【{sub.text(0)}】参数为空。")
                    
        return errors

    def save_recipe(self):
        """将当前树状图序列化并保存为 JSON"""
        # 执行逻辑校验
        errors = self.validate_recipe()
        if errors:
            msg = "配方校验发现以下问题：\n\n" + "\n".join(errors[:5])
            if len(errors) > 5: msg += f"\n...等共 {len(errors)} 个问题"
            QMessageBox.warning(self, "校验未通过", msg)

        recipe_item = self.recipe_tree.currentItem()
        if not recipe_item:
            QMessageBox.warning(self, "提醒", "请先在左侧选择或新建一个配方。")
            return
            
        recipe_name = recipe_item.text(0)
        data = {
            "name": recipe_name,
            "topology": self.topology_combo.currentText(),
            "items": []
        }
        
        # 遍历树状图
        for i in range(self.step_tree.topLevelItemCount()):
            item_node = self.step_tree.topLevelItem(i)
            item_data = {
                "name": item_node.text(0),
                "mode": item_node.text(1),
                "min": item_node.text(2),
                "max": item_node.text(3),
                "strategy": item_node.text(4),
                "sub_steps": []
            }
            
            # 遍历子工步
            for j in range(item_node.childCount()):
                sub_node = item_node.child(j)
                sub_data = {
                    "name": sub_node.text(0).replace("  └─ ", ""),
                    "action": sub_node.text(1),
                    "params": sub_node.text(2),
                    "device": sub_node.data(0, Qt.UserRole), 
                    "type": sub_node.data(1, Qt.UserRole),
                    "is_judgment": sub_node.data(2, Qt.UserRole),
                    "fail_strategy": sub_node.text(4)
                }
                item_data["sub_steps"].append(sub_data)
                
            data["items"].append(item_data)
            
        if self.db_manager.save_recipe_json(recipe_name, data):
            QMessageBox.information(self, "成功", f"配方【{recipe_name}】已成功保存。")
            self.refresh_recipe_list()
        else:
            QMessageBox.critical(self, "错误", "配方保存失败，请检查日志。")

    def add_test_item(self):
        from ui.dialogs.test_item_dialog import TestItemDialog
        dialog = TestItemDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            item = QTreeWidgetItem([
                data['name'], 
                "范围判定", 
                str(data['min']), 
                str(data['max']), 
                data['strategy']
            ])
            item.setForeground(0, QColor("#00E5FF"))
            font = QFont()
            font.setBold(True)
            item.setFont(0, font)
            self.step_tree.addTopLevelItem(item)
            self.step_tree.setCurrentItem(item)

    def add_step(self):
        parent = self.step_tree.currentItem()
        if not parent:
            QMessageBox.warning(self, "提醒", "请先选择一个『测试项』作为父节点。")
            return
            
        if parent.parent():
            parent = parent.parent()

        from ui.dialogs.step_dialog import StepDialog
        dialog = StepDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            item = QTreeWidgetItem([
                f"  └─ {data['name']}", 
                data['action'], 
                data['params'], 
                "参与判定" if data['is_judgment'] else "--", 
                data['fail_strategy']
            ])
            # 存储元数据
            item.setData(0, Qt.UserRole, data['device'])
            item.setData(1, Qt.UserRole, data['type'])
            item.setData(2, Qt.UserRole, data['is_judgment'])
            
            if data['is_judgment']:
                item.setForeground(0, QColor("#FFD700"))
            
            parent.addChild(item)
            parent.setExpanded(True)

    def edit_node(self):
        item = self.step_tree.currentItem()
        if not item:
            return
            
        parent = item.parent()
        if not parent:
            # 这是一个『测试项』(Top Level)
            from ui.dialogs.test_item_dialog import TestItemDialog
            data = {
                'name': item.text(0),
                'min': item.text(2),
                'max': item.text(3),
                'strategy': item.text(4)
            }
            dialog = TestItemDialog(self, data=data)
            if dialog.exec():
                new_data = dialog.get_data()
                item.setText(0, new_data['name'])
                item.setText(2, str(new_data['min']))
                item.setText(3, str(new_data['max']))
                item.setText(4, new_data['strategy'])
        else:
            # 这是一个『子工步』(Child)
            from ui.dialogs.step_dialog import StepDialog
            # 从 UserRole 还原数据
            data = {
                'name': item.text(0).replace("  └─ ", ""),
                'action': item.text(1),
                'params': item.text(2),
                'device': item.data(0, Qt.UserRole) or "",
                'type': item.data(1, Qt.UserRole) or "",
                'is_judgment': item.data(2, Qt.UserRole) or False
            }
            dialog = StepDialog(self, step_data=data)
            if dialog.exec():
                new_data = dialog.get_data()
                item.setText(0, f"  └─ {new_data['name']}")
                item.setText(1, new_data['action'])
                item.setText(2, new_data['params'])
                item.setText(3, "参与判定" if new_data['is_judgment'] else "--")
                item.setText(4, new_data['fail_strategy'])
                
                # 更新元数据
                item.setData(0, Qt.UserRole, new_data['device'])
                item.setData(1, Qt.UserRole, new_data['type'])
                item.setData(2, Qt.UserRole, new_data['is_judgment'])
                
                if new_data['is_judgment']:
                    item.setForeground(0, QColor("#FFD700"))
                else:
                    item.setForeground(0, QColor("#FFFFFF"))

    def delete_node(self):
        item = self.step_tree.currentItem()
        if item:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.step_tree.indexOfTopLevelItem(item)
                self.step_tree.takeTopLevelItem(index)

    def add_new_recipe(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "新建测试配方", "请输入新配方名称:")
        if ok and text:
            self.step_tree.clear()
            item = QTreeWidgetItem([text])
            self.recipe_tree.addTopLevelItem(item)
            self.recipe_tree.setCurrentItem(item)
            self.current_recipe_name = text
            self.set_editor_enabled(True)
            # 顺便立即保存一个空的
            self.save_recipe()

    def get_all_recipes(self):
        recipes = []
        for i in range(self.recipe_tree.topLevelItemCount()):
            recipes.append(self.recipe_tree.topLevelItem(i).text(0))
        return recipes
