# AI Coding Change Log

## 2026-07-30: PSA 报表主从机本地拆分与自锁汇总功能开发
- **修改文件**:
  - [data/db_manager.py](file:///c:/Users/95403/Desktop/AgingTest-AI/data/db_manager.py)：在 `generate_report` 方法尾部新增了主从机报表拆分与 PSA 合成归档逻辑。
- **修改内容**:
  1. **主从机数据拆分**：通过调用 `self.load_recipe_json` 获取当前配方的工步映射字典，将当前通道的 items 详细判定结果分类为 `主机`、`从机1`、`从机2`、`从机3` 四组。
  2. **汇总归档路径**：在报表根路径下自动创建 `reports/PSA/{被测物}/` 子目录并按 SN 进行归档。无对应条码或无数据的板卡将不予生成报表。
  3. **数据纵向追加与时间继承**：若文件已存在，则自动提取历史数据并与本次数据合并追加，更新结束时间并继承首次测试开始时间。
  4. **判定状态自愈与自锁改名**：如果之前是 PASS 且本轮为 PASS，保存为 `{SN}_PASS.csv`；若历史中已出现 FAIL 或本次出现 FAIL，则移除旧的 `_PASS.csv` 并生成保存为 `{SN}_FAIL.csv`，使总判定持续自锁为 `FAIL` 状态。
- **修改原因**: 满足现场流水线老化循环测试中将一个通道内的各单体被测物按其 SN 标识独立输出、并跨轮次持续合并追加数据的 PSA 报表规范需求。

## 2026-07-30: 解决电池模拟器误判离线的并发冲突优化
- **修改文件**:
  - [devices/ngi_83624.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/ngi_83624.py)：在 `measure_voltage` 和 `measure_current` 中引入了通信失败计数器 `self._fail_count`。只有高频读取连续失败达 5 次以上才判定 `is_connected = False` 并切断，成功则自动清零，增加通信防抖。
  - [ui/tabs/overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py)：删除了自检线程在读取异常时越权直接将 `sim.is_connected` 设为 `False` 的代码（统一由驱动自行维护）。在自检线程单次遍历 48 通道内，引入了每个通道 `msleep(15)` 的主动避让延时。
- **修改原因**: 解决由于后台自检线程无间歇高频并发读取 48 路仪器寄存器，导致与测试主线程产生激烈的互斥锁竞争与 TCP 通信延迟超时，进而触发越权断线重连并误判为“离线”的并发死锁问题。

## 2026-07-30: 解决由于设备管理器重新配置实例化导致自检线程持有老引用误报离线的BUG
- **修改文件**:
  - [ui/tabs/overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py)：重构了自检线程 `SimulatorCurrentMonitorThread` 和 AFE 监控线程 `AFEPowerMonitorThread`。将其初始化接收的 `device_manager` 改为 `engine`。在 `run()` 的死循环中，每次迭代都通过 `getattr(self.engine, 'device_manager', None)` 动态地获取当前的设备实例。
- **修改原因**: 解决在软件运行或硬件重新初始化（如点击初始化设备）后，主测试线程生成并使用了新的 `DeviceManager`，而后台 UI 状态监控线程依然持有老旧的 `DeviceManager` 的失效对象引用，进而由于读取不到数据导致状态常态化误判定为“离线”的问题。

