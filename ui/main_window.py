import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget, QStatusBar, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

from ui.tabs.overview_tab import OverviewTab
from ui.tabs.config_tab import ConfigTab
from ui.tabs.hardware_tab import HardwareTab
from ui.tabs.debug_tab import DebugTab
from ui.tabs.simulator_tab import SimulatorTab
from ui.tabs.hv_tab import HVSourceTab
from ui.tabs.afe_tab import AFEPowerTab
from ui.tabs.mainboard_power_tab import MainboardPowerTab
from ui.tabs.afe_power_tab_standalone import AFEPowerStandaloneTab
from ui.tabs.aging_board_tab_standalone import AgingBoardStandaloneTab
from ui.tabs.easy320_tab_standalone import Easy320StandaloneTab
from ui.tabs.ca550_tab_standalone import CA550StandaloneTab
from ui.tabs.rn_can_tab import RNCANTab
from ui.tabs.power_board_tab import PowerBoardTab
from ui.tabs.chamber_tab import ChamberTab
from ui.tabs.api_tab import ApiTab




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMS 老化测试上位机")
        
        # 动态加载窗体图标
        import os, sys
        from PySide6.QtGui import QIcon
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        
        icon_path = os.path.join(base_dir, "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.resize(1280, 800)
        
        # 初始化核心业务引擎
        from core.engine import TestEngine
        from data.db_manager import DBManager
        from devices.manager import DeviceManager
        
        self.db_manager = DBManager()
        self.device_manager = DeviceManager(self.db_manager)
        
        # 启动自检弹窗阻塞主进程
        from ui.dialogs.startup_dialog import StartupCheckDialog
        from PySide6.QtWidgets import QDialog
        import sys
        
        dialog = StartupCheckDialog(self.device_manager, self)
        if dialog.exec() != QDialog.Accepted:
            # 用户选择退出程序或强制关闭弹窗
            self.device_manager.disconnect_all()
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            sys.exit(0)
            
        self.engine = TestEngine(self.device_manager, self.db_manager)
        
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 顶部标题栏
        header_label = QLabel("BMS 老化测试上位机系统")
        header_label.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        layout.addWidget(header_label)

        # 核心导航 Tab
        self.tabs = QTabWidget()
        
        # 1. 多通道监控页
        self.tab_overview = OverviewTab(self.engine, self.db_manager)
        self.tabs.addTab(self.tab_overview, "多通道监控")

        # 2. 高低温老化箱监控页
        self.tab_chamber = ChamberTab(self.device_manager, self.db_manager)
        self.tabs.addTab(self.tab_chamber, "高低温老化箱")

        # 3. 测试用例/工步配置页
        self.tab_config = ConfigTab(self.db_manager)
        self.tabs.addTab(self.tab_config, "工步与配方配置")

        # 3. 硬件设备配置页 (硬件管理中心)
        self.tab_hardware = HardwareTab(self.db_manager)
        self.tab_hardware.set_device_manager(self.device_manager)
        self.tabs.addTab(self.tab_hardware, "硬件管理中心")

        # 3.5 API 监控与调试页
        self.tab_api = ApiTab(self.engine, self.db_manager)
        self.tabs.addTab(self.tab_api, "API 监控与调试")

        # 4. 单通道/硬件独立调试中心 (主容器)
        self.tab_debug_center = DebugTab(self.device_manager)
        self.tabs.addTab(self.tab_debug_center, "单通道/硬件独立调试")

        # --- 将各硬件调试页加入到调试中心 (Sub-Tabs) ---
        
        # 模拟器控制
        self.tab_simulator = SimulatorTab(self.device_manager)
        self.tab_debug_center.add_debug_tab(self.tab_simulator, "电池模拟器控制")

        # NGI 高压源
        self.tab_hv = HVSourceTab(self.device_manager)
        self.tab_debug_center.add_debug_tab(self.tab_hv, "NGI 高压源控制")

        # AFE 供电 (1#)
        self.tab_afe = AFEPowerTab(self.device_manager)
        self.tab_debug_center.add_debug_tab(self.tab_afe, "AFE供电电源")

        # 被测物电源 (DUT)
        self.tab_dut_power = MainboardPowerTab(self.device_manager)
        self.tab_debug_center.add_debug_tab(self.tab_dut_power, "被测物供电电源")

        # AFE 电源调试 (2# Standalone)
        self.tab_afe_standalone = AFEPowerStandaloneTab(self.device_manager.afe_pwr_2)
        self.tab_debug_center.add_debug_tab(self.tab_afe_standalone, "AFE电源调试")

        # 控制板电源调试
        self.tab_ctrl_pwr = PowerBoardTab(self.device_manager.ctrl_board_power)
        self.tab_debug_center.add_debug_tab(self.tab_ctrl_pwr, "控制板电源调试")

        # 老化板调试
        first_board = self.device_manager.boards.get(1)
        if first_board:
            self.tab_aging_standalone = AgingBoardStandaloneTab(first_board.relays)
            self.tab_debug_center.add_debug_tab(self.tab_aging_standalone, "老化板调试")
        
        # Easy320 调试
        self.tab_easy320_standalone = Easy320StandaloneTab(self.device_manager.easy320)
        self.tab_debug_center.add_debug_tab(self.tab_easy320_standalone, "Easy320调试")

        # CA550 调试
        self.tab_ca550_standalone = CA550StandaloneTab(self.device_manager.ca550)
        self.tab_debug_center.add_debug_tab(self.tab_ca550_standalone, "CA550调试")

        # RNCAN 调试
        self.tab_rn_can = RNCANTab(self.device_manager)
        self.tab_debug_center.add_debug_tab(self.tab_rn_can, "RNCAN调试")

        layout.addWidget(self.tabs)

        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.show_status("系统就绪")
        
        # 绑定 Tab 切换事件以实现数据跨页面联动
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # 软件刚启动时，手动同步一次预设配方
        self.on_tab_changed(0)

    def show_status(self, message: str, timeout: int = 5000):
        """在状态栏显示信息"""
        self.status_bar.showMessage(message, timeout)

    def closeEvent(self, event):
        """软件关闭时的清理逻辑"""
        print("正在关闭软件，清理资源...")
        if hasattr(self, 'engine'):
            print("正在停止所有测试引擎...")
            self.engine.stop_all()
            
        if hasattr(self, 'device_manager'):
            print("正在断开所有硬件设备连接...")
            self.device_manager.disconnect_all()

        if hasattr(self, 'db_manager'):
            print("正在关闭数据库连接...")
            self.db_manager.close()

        event.accept()

    def on_tab_changed(self, index):
        if index == 0:
            recipes = self.tab_config.get_all_recipes()
            self.tab_overview.update_recipes(recipes)
