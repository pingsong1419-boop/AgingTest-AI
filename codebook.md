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

## 2026-07-30: 解决 PySide 底层类型转换导致自检线程信号中断离线误报的BUG
- **修改文件**:
  - [ui/tabs/overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py)：将 `SimulatorCurrentMonitorThread` 类中的通信信号 `sim_data_updated = Signal(dict)` 修改为了 `Signal(object)`。
- **修改原因**: 解决在特定 PySide / Shiboken 底层封装机制下，跨线程传输包含复杂非字符串键和嵌套 tuple 数据的 dict 时，由于 `pythonToCpp` 类型强转缺陷抛出 Shiboken 转换报错，导致槽函数在主线程根本收不到自检刷新信号，状态栏常态误报离线的问题。

## 2026-07-30: 新增“DTU 诊断”工步及其 29 项故障变量自动映射与 UI 编辑配置支持功能
- **修改文件**:
  - [devices/eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)：在 `execute` 方法中新增 `DTU诊断` 特例逻辑。实现了连续两次发送 `10 13 00 00 00`，单次未成功接收肯定响应 `10 13 00 40` 时支持最多 **5 次自动重发** 并每次避让 `100ms` 的机制。最终返回拼接好的 8 字节原始故障数据。
  - [core/engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：拦截并解析 EOL 执行步骤中的 `DTU诊断` 工步。将返回的 8 字节故障数据对应的 29 项具体故障 bit 一一解析为 `0` 或 `1`，写入系统全局变量字典 `self.variables` 中，并提供判定结果返回。
  - [ui/dialogs/step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：在工步编辑对话框中，将 `DTU诊断` 正式编入 3.5HEOL 的“特殊执行”可选列表中。实现了参数布局的自适应切换、隐藏冗余输入控件以及工步加载逆向还原。
- **修改原因**: 满足老化配方测试中通过 CAN UDS 诊断指令高可靠获取被测物 BMS 内部所有具体故障，自动记录入系统变量方便后序逻辑自主判定分支，并在测试配方 UI 界面中直接支持该工步创建与编辑的要求。
## 2026-08-05: 取消 0x07 CSC 批量读取工步中的第一阶段前置时序
- **修改文件**:
  - [core/engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：移除了拦截 `0x07 CSC批量读取` / `0x07 CSC读取` 时的前置复位时序。
- **修改内容**:
  1. 移除了每次尝试读取前，对 `KL15` 和 `CAN1` 继电器的断开、延时（4.0s）、重新闭合并稳定（1.0s）的控制。
  2. 移除了 5 次尝试下发“设置节点数目为 12”的配置报文及等待配置响应的逻辑。
  3. 保留了重试读取的循环，每次尝试直接在已有供电和通信状态下直接触发 192 路单体电芯电压的物理遍历读取。
- **修改原因**: 满足用户优化调试效率的需求，避免每次读取测试时频繁操作继电器断电复位及重新下发节点配置以缩短测试耗时，直接重用上一工步保持的供电与建连状态。

## 2026-08-05: 修复相邻电芯电压修正（FIX_ADJACENT）不生效的逻辑缺陷
- **修改文件**:
  - [core/engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：将 `0x07 CSC批量读取` 工步下的相邻电芯异常判定逻辑的条件由 `and` 修改为 `or`。
- **修改内容**:
  1. 将相邻电芯对判定不合格的条件从 `if is_v1_ng and is_v2_ng:` 变更为 `if is_v1_ng or is_v2_ng:`。
  2. 使得只要相邻的两个电芯中至少有一个不合格，且它们的电压之和处于 `[4.9, 5.1]` 范围内，即可正常触发电压修正至 `2.499V`。
- **修改原因**: 修复原本限定两相邻通道必须同时不合格才修正的过严条件，使其能够正确识别和修正最常见的“单通道稍许漂移出界而另一通道合格”的触线故障，确保修正机制能够实际起效。

## 2026-08-05: 新增 0x10 NTC温度读取的双重偏差修正和自愈逻辑及 UI 参数编辑框显示支持
- **修改文件**:
  - [core/engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：重构了 `0x10` NTC 温度结果处理逻辑。
  - [ui/dialogs/step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：修改了 NTC 动作选择下的参数输入框可见性。
- **修改内容**:
  1. 在 `step_dialog.py` 中，当工步功能选择为 `0x10 NTC读取` 时，设置 `eol_args`（附加参数输入框）和标签为可见（`setVisible(True)`），并更新占位引导文本提示用户可输入类似 `TARGET:25,TOL1:0.5,TOL2:2.0`。
  2. 在 `engine.py` 的 EOL 结果后处理块中，增加了从 `ARGS` 参数中读取 `TARGET`、`TOL1`、`TOL2` 字段。
  3. 实现了双范围判定：当绝对温差 `<= TOL1` 时判定为第一范围（直接合格，显示实际测得值）；当温差在 `(TOL1, TOL2]` 之间时判定为第二范围（触发异常修复，将结果强制修正为 `TARGET` 以自愈通过）；当温差 `> TOL2` 时不予修正并显示实际读取值（判定不合格）。
- **修改原因**: 满足老化配方测试中对 NTC 读取精度控制及小幅漂移自愈修正的个性化工艺逻辑需求。


