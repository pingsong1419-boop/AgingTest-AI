from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QComboBox, QMessageBox)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

class ConfigTab(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._init_ui()
        self.refresh_recipe_list()
        
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
        
        right_panel.addWidget(QLabel("测试项目与工步流 (树状结构):"))
        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderLabels(["名称/工步", "模式/范围", "目标值/下限", "截止时间/上限", "NG 策略"])
        self.step_tree.setColumnWidth(0, 200)
        from PySide6.QtWidgets import QAbstractItemView
        self.step_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.step_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.step_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.step_tree.customContextMenuRequested.connect(self.show_context_menu)
        
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
        
        btn_layout.addWidget(btn_add_item)
        btn_layout.addWidget(btn_add_step)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_save_recipe)
        right_panel.addLayout(btn_layout)
        
        layout.addLayout(right_panel, 3)

        # 绑定双击编辑
        self.step_tree.itemDoubleClicked.connect(lambda item, col: self.edit_node())
        
        # 重写 dropEvent 以支持拖拽复制 (Ctrl 键)
        self.step_tree.dropEvent = self._step_tree_drop_event

    def _step_tree_drop_event(self, event):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QAbstractItemView
        
        # 获取当前选中的所有项
        selected_items = self.step_tree.selectedItems()
        if not selected_items:
            QTreeWidget.dropEvent(self.step_tree, event)
            return

        # 检查是否按下了 Ctrl 键或事件动作是 CopyAction
        is_copy = (event.keyboardModifiers() & Qt.ControlModifier) or (event.dropAction() == Qt.CopyAction)
        
        if is_copy:
            # 找到落点
            target_item = self.step_tree.itemAt(event.pos())
            
            for item in selected_items:
                # 递归克隆项目
                def clone_item(old_item):
                    # 注意：不要使用 QTreeWidgetItem(old_item) 构造函数，它会自动建立父子关系导致递归死循环
                    new_item = QTreeWidgetItem()
                    # 复制文本
                    for col in range(old_item.columnCount()):
                        new_item.setText(col, old_item.text(col))
                        
                    # 复制 Data (元数据 - 关键：设备ID和参数都在这里)
                    for i in range(50): # 遍历可能的 Role
                        val = old_item.data(0, Qt.UserRole + i)
                        if val is not None:
                            new_item.setData(0, Qt.UserRole + i, val)
                    
                    # 递归克隆子节点
                    for i in range(old_item.childCount()):
                        new_item.addChild(clone_item(old_item.child(i)))
                    return new_item

                cloned = clone_item(item)
                
                if item.parent(): # 如果是子工步
                    # 尝试放到落点测试项下，如果没有落点则放到原父节点下
                    if target_item:
                        parent = target_item if not target_item.parent() else target_item.parent()
                        parent.addChild(cloned)
                        parent.setExpanded(True)
                    else:
                        item.parent().addChild(cloned)
                else: # 如果是测试项
                    self.step_tree.addTopLevelItem(cloned)
            
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            # 默认移动逻辑
            QTreeWidget.dropEvent(self.step_tree, event)

    def refresh_recipe_list(self):
        """从本地磁盘刷新配方列表"""
        self.recipe_tree.clear()
        self.step_tree.clear() # 初始清空右侧
        recipes = self.db_manager.list_recipes()
        for name in recipes:
            self.recipe_tree.addTopLevelItem(QTreeWidgetItem([name]))
        
        # 初始状态下禁用编辑按钮或显示提示
        self.step_tree.setEnabled(False)

    def on_recipe_selected(self, item, column):
        """点击左侧配方时加载数据"""
        self.step_tree.setEnabled(True)
        name = item.text(0)
        data = self.db_manager.load_recipe_json(name)
        if data:
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

    def save_recipe(self):
        """将当前树状图序列化并保存为 JSON"""
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

    def show_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        item = self.step_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        # 屏蔽/取消屏蔽操作
        is_skipped = item.text(0).startswith("#")
        skip_action = QAction("取消屏蔽" if is_skipped else "屏蔽测试项 (添加#)", self)
        skip_action.triggered.connect(lambda: self.toggle_skip(item))
        menu.addAction(skip_action)
        
        # 自定义前缀操作
        prefix_action = QAction("添加自定义前缀", self)
        prefix_action.triggered.connect(lambda: self.add_prefix(item))
        menu.addAction(prefix_action)
        
        # 也可以放个删除在这里
        menu.addSeparator()
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.delete_node)
        menu.addAction(delete_action)
        
        menu.exec_(self.step_tree.viewport().mapToGlobal(position))

    def toggle_skip(self, item):
        text = item.text(0)
        if text.startswith("#"):
            item.setText(0, text[1:]) # 去掉第一个字符
        else:
            # 如果是子工步，需要保留缩进，比如 "  └─ name" 变成 "  └─ #name"
            if "└─ " in text:
                parts = text.split("└─ ")
                item.setText(0, f"{parts[0]}└─ #{parts[1]}")
            else:
                item.setText(0, "#" + text)

    def add_prefix(self, item):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "添加前缀", "请输入前缀内容:")
        if ok and text:
            old_text = item.text(0)
            if "└─ " in old_text:
                parts = old_text.split("└─ ")
                item.setText(0, f"{parts[0]}└─ {text}_{parts[1]}")
            else:
                item.setText(0, f"{text}_{old_text}")

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
            # 顺便立即保存一个空的
            self.save_recipe()

    def get_all_recipes(self):
        recipes = []
        for i in range(self.recipe_tree.topLevelItemCount()):
            recipes.append(self.recipe_tree.topLevelItem(i).text(0))
        return recipes
