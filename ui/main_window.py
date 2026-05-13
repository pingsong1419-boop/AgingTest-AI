import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget, QStatusBar
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



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMS 老化测试上位机")
        self.resize(1280, 800)
        
        # 初始化核心业务引擎
        from core.engine import TestEngine
        from data.db_manager import DBManager
        from devices.manager import DeviceManager
        
        self.db_manager = DBManager()
        self.device_manager = DeviceManager()
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

        # 2. 测试用例/工步配置页
        self.tab_config = ConfigTab(self.db_manager)
        self.tabs.addTab(self.tab_config, "工步与配方配置")

        # 3. 硬件设备配置页
        self.tab_hardware = HardwareTab(self.db_manager)
        self.tabs.addTab(self.tab_hardware, "设备通讯与全局配置")

        # 4. 单通道调试页
        self.tab_debug = DebugTab()
        self.tabs.addTab(self.tab_debug, "单通道/硬件独立调试")

        # 5. 模拟器控制页
        self.tab_simulator = SimulatorTab(self.device_manager)
        self.tabs.addTab(self.tab_simulator, "电池模拟器控制")

        # 6. NGI 高压源控制页
        self.tab_hv = HVSourceTab(self.device_manager)
        self.tabs.addTab(self.tab_hv, "NGI 高压源控制")

        # 7. 1#AFE 供电电源页
        self.tab_afe = AFEPowerTab(self.device_manager)
        self.tabs.addTab(self.tab_afe, "1#AFE供电电源")

        # 8. 主机板供电电源页
        self.tab_main_power = MainboardPowerTab(self.device_manager)
        self.tabs.addTab(self.tab_main_power, "主机板供电电源")

        # --- 扩展调试页 (B 方案: 四个独立 Tab) ---
        self.tab_afe_standalone = AFEPowerStandaloneTab(self.device_manager.afe_pwr_standalone)
        self.tabs.addTab(self.tab_afe_standalone, "AFE电源调试")

        self.tab_power_board = PowerBoardTab(self.device_manager.power_board_ru12)
        self.tabs.addTab(self.tab_power_board, "功能测试板电源")

        self.tab_aging_standalone = AgingBoardStandaloneTab(self.device_manager.aging_board)
        self.tabs.addTab(self.tab_aging_standalone, "老化板调试")

        self.tab_easy320_standalone = Easy320StandaloneTab(self.device_manager.easy320)
        self.tabs.addTab(self.tab_easy320_standalone, "Easy320调试")

        self.tab_ca550_standalone = CA550StandaloneTab(self.device_manager.ca550)
        self.tabs.addTab(self.tab_ca550_standalone, "CA550调试")

        self.tab_rn_can = RNCANTab(self.device_manager)
        self.tabs.addTab(self.tab_rn_can, "RNCAN调试")

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
