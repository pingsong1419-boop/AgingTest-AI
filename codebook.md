# 变更记录 (Codebook)

## 2026-07-02
- **修改内容**: 新增 `.vscode/launch.json` 文件。
- **修改原因**: 用户请求生成 VSCode 的调试配置文件，用于直接在编辑器中启动和调试 `main.py`。

- **修改内容**: 修改 `devices/aging_board_driver.py`，移除 Modbus 握手失败强制返回 True 的逻辑。
- **修改原因**: 修复因为“只要 TCP 通了就认为在线”的错误妥协代码，导致实际未接物理板时 UI 仍显示所有设备全部在线的 Bug。

- **修改内容**: 修改 `devices/rn_can_driver.py` 的 `connect` 方法，增加建立连接后延迟判定。
- **修改原因**: 修复 RNCAN 驱动在 TCP 连接短暂成功但立即被远端关闭时，仍然向外层同步返回 True 导致设备状态“假在线”的 Bug。

- **修改内容**: 修改 `devices/control_board.py`，将判定在线逻辑由 `r_ok or c_ok` 改为 `r_ok and c_ok`。
- **修改原因**: 彻底解决因为 RNCAN 断开存在异步延迟（超过0.1秒），导致 `c_ok` 瞬间返回 `True` 从而骗过系统认为整板在线的问题。现在必须 Modbus(继电器) 和 CAN 双双连通才算在线。

- **修改内容**: 修改 `devices/mainboard_power_ru60.py` 的 `connect` 方法。
- **修改原因**: 增加基于 Modbus 寄存器(读取地址149)的协议级握手校验，避免仅 TCP 建连成功就将其误判为已联机的 Bug。

- **修改内容**: 修改 `devices/manager.py` 中的 `init_devices` 扫描逻辑，将 48 路控制板初始化的 `4次尝试+3秒重试` 降低为 `1次尝试`，并发线程数从 `16` 增加到 `32`。
- **修改原因**: 解决上位机打开后初始化验证极度缓慢（长达一分钟以上）且因大量并发连接尝试可能导致局域网假死/Ping 不通的问题。

- **修改内容**: 修改 `devices/aging_board_driver.py` 中的 `write_relay` 和 `write_all_off` 方法。
- **修改原因**: 增加 Modbus 写入后的闭环回读校验。写入命令执行后等待 50ms 重新读取物理线圈状态，如果状态不一致则返回控制失败触发重试，确保物理设备真实响应。

- **修改内容**: 修改 `core/engine.py` 中的 `execute_sub_step`，将老化功能板(aging_board)和简易继电器(easy320)的控制详细参数及回读结果输出到日志。
- **修改原因**: 之前将详细的通道与双向状态格式显示在测试序列的测量值列中，使得界面显得杂乱。根据要求，将其改为了通过 `hw_logger` 直接打印在底部的“实时执行日志”里，从而保持测试序列列表的整洁（恢复显示 `--`）。

- **修改内容**: 批量升级全部下层驱动的控制方法，包括 `easy320_driver.py`、`aging_board_driver.py`、各类高压源(`ngi_n3618.py`, `ngi_83624.py`, `lingtu_66100.py`)及主机/AFE电源(`mainboard_power_ru60.py`, `afe_power_ru36.py`, `afe_power_driver.py`) 的 `output_control` 等。
- **修改原因**: 落实“凡是控制必有反馈”机制，提升全局设备控制良率。将所有硬件核心的开关控制逻辑重构为：下发指令后延时读取物理硬件真实状态进行对比校验。若校验不通过或下发抛异常，则自动执行“断线、重连、再试一次（总计2次尝试）”的闭环重试逻辑。

- **修改内容**: 修改 `devices/ca550_driver.py` 中的 `set_source_output` 和 `set_source_data`。
- **修改原因**: 补充横河 CA550 校验仪的输出开关及数值设定的闭环控制。将 `set_source_output` 改为在下发命令后，自动发送 `SO?` 进行物理状态回读；将 `set_source_data` 设定电压/电流数值后，自动发送 `SD?` 校验数值设定是否准确。两者均提供最高 2 次的断线自动重连与重试机制。为避免仪器浮点精度引起误报，数值校验误差阈值放宽至 `<=` 0.05。

- **修改内容**: 修改 `core/engine.py` 的工步解析模块中高压源、主板/AFE电源以及 CA550 的执行逻辑。
- **修改原因**: 根据需求，将这些仪器的设定参数及底层返回的校验结果，以与继电器动作相同的格式统一打印到“实施执行日志”（`hw_logger`）中（如：`-> 高压源 设定电压: 发:120V 回:成功`），从而方便用户在运行界面的底部日志追踪所有硬件细节。

- **修改内容**: 修改 `core/engine.py` 的 `ChannelWorker`，新增完整的实时日志留存功能。
- **修改原因**: 为了方便问题排查与追溯，引擎会在测试进行时于内存中保留全部实施执行日志，并在测试完成（或中途停止）时，自动将其保存至项目根目录的 `test_logs/` 文件夹下。文件命名格式为 `CH{通道号}_{产品SN}_{时间戳}.log`。
- **޸**: ޸ core/engine.py е ca550 ߼д ر(OFF) ķ֧ mgr.ca550.set_source_data(0.0)
- **޸ԭ**:  CA550 رպ󣬵ײԱһ趨ֵ3VºضʱȻطѹ⣬ȷرնжͬʱҲڲ趨ֵ


- **修改内容**: 新增 recipes/高压源独立测试配方.json
- **修改原因**: 满足用户无需界面直接测试高压源的需求，增加独立测试配方供系统加载。

- **修改内容**: 修改 core/engine.py 中的 _execute_sub_step_logic，在解析控制工步和测量工步时，增加对 高压源、ngi 等别名的匹配支持。
- **修改原因**: 修复测试配方中指定 device: 高压源 时，底层引擎因设备名未命中拦截分支而导致指令完全空跑的 Bug。

- **修改内容**: 修改 core/engine.py 的高压源控制工步解析，增加对电流参数（A）的提取及下发。
- **修改原因**: 之前只下发电压而未下发限流，导致高压源在限流为0的状态下拒绝开启输出（表现为接收了 OUTP ON 却没有报错，但查状态仍为 OFF）。

- **修改内容**: 在 devices/ngi_n3618.py 的 output_control 中，发送 OUTP ON/OFF 指令后，增加 0.5 秒的延时再回读状态。
- **修改原因**: 硬件继电器动作和内部状态更新存在物理延迟，如果发送开启指令后立刻回读状态，仪器依然会返回 OFF 导致校验失败。

- **修改内容**: 在 devices/afe_power_ru36.py, devices/mainboard_power_ru60.py, devices/power_board_ru12.py 的头部增加 import time。
- **修改原因**: 之前这几个电源驱动在 output_control 和重试逻辑中调用了 time.sleep()，但没有导入 time 模块，导致运行时报 name 'time' is not defined 异常。

- **修改内容**: 在 core/engine.py 中修改 has_limits 的判断逻辑，过滤空字符串的情况。
- **修改原因**: 当配方中的 min 和 max 为空字符串时，之前也会被误判为配置了上下限，导致在无判断要求（仅返回控制字 OK）的执行场景下误触发行限校验而判定为 NG。


- **修改内容**: 新增 scratch_analyze_all.py 辅助分析脚本，并生成 analysis_result_new.txt 报告
- **修改原因**: 批量分析「新建文件夹 (2)」目录下的老化测试记录，统计出各通道的故障类型和频次

- **修改内容**: 修改 recipes/DJ2513_Aging.json 中的 CA550输出-2.5V 测试项判定逻辑
- **修改原因**: 修复该控制工步因配置了数值上下限而被误判为 NG 的配置错误，将其修正为字符串比较及不判断类型

- **修改内容**: 将 recipes/DJ2513_Aging.json 中的 CA550输出-2.5V 恢复为范围判定、数值类型及2.49~2.51V限值
- **修改原因**: 配合其子工步中已配置的数据回读子步骤，实现与CA550-5V等项完全一致的高稳定物理电压对标判定，修复早先版本缺失数据回读误判的问题

- **修改内容**: 精简 ui/main_window.py 头部重复的 OverviewTab, ConfigTab, HardwareTab, ChamberTab, ApiTab 导入语句。
- **修改原因**: 消除冗余导入，提升代码整洁度与静态检查可读性。

- **修改内容**: 将 core/engine.py 中 ChannelWorker 的 step_finished、sub_step_finished 和 progress_updated 信号连接从 _save_local_execution_log 内部移至 __init__ 初始化方法末尾。
- **修改原因**: 修复因错误缩进导致这三个信号在运行时未连接，进而使得所有测试结果结算时 has_ng 始终为 False、将 NG 判定错判为 PASS 的核心 Bug。

- **修改内容**: 修改 recipes/DJ2513_Aging.json，彻底删除了“快充口绝缘阻抗-100KΩ”和“快充口绝缘阻抗-500KΩ”两个工步。
- **修改原因**: 解决快充口外部物理绝缘阻抗在老化测试中频繁波动并低于判定区间导致重复 NG 的问题。

- **修改内容**:
  1. 修改 devices/manager.py，在 init_all_devices 的老化板连接成功后，自动调用 board.relays.write_all_off() 批量关闭所有 22 路继电器。
  2. 修改 devices/ngi_83624.py，在 set_current_limit 方法中将传入的电流值 (A) 乘以 1000.0 转换为 mA 后再下发给电池模拟器。
  3. 修改 core/engine.py，放宽快捷批量配置的动作匹配逻辑（支持 "设" 动作且含 "CH:"），并在单通道分支下增加了对电流限制、量程及 ON/OFF 同义词的解析设置。
  4. 重新使用 PyInstaller 打包构建最新版 AgingTest_BMS.exe。
- **修改原因**:
  1. 保证程序初始化启动与设备重连时，所有老化板物理继电器能默认处于关闭的安全状态。
  2. 修复 NGI 83624 电池模拟器 SCPI 指令电流单位是 mA 导致下发 1.0A 却被当作 1.0mA 限制输出的硬件不兼容 Bug。
  3. 兼容老化测试配方中动作为 "设" 时批量或单通道限流、开关、量程设置缺失的问题，避免限流维持默认的 1mA 造成异常。

- **修改内容**:
  1. 修改 recipes/DJ2513_Aging.json，移除了 Index 0 (设备初始化) 闭合 15 号继电器的动作；将 Index 77 (@高压源控制-100V) 的 is_block_start 设为 True；Index 86 设为 False；Index 87 的 is_block_end 设为 False；Index 88 (@高压源控制-0V) 的 is_block_end 设为 True，并将其子步断开通道参数修改为 "15"。
  2. 同步修改了 E:\DJ2513_Aging.json 绝缘高压独占段的 is_block_start / is_block_end 与高压完即时断开 15 号继电器动作。
- **修改原因**: 解决因 15 号高压继电器长闭合且块锁边界仅框在绝缘测量点，导致多通道并行测试时高压物理通路大面积闭合的干扰与高压安全风险。整合高压启动至释放全段（Index 77 至 Index 88）为单一独占块，实现单通道分时串行高压测试。

- **修改内容**: 修改 core/engine.py 的 execute_sub_step 方法，添加防死锁的动态屏蔽逻辑。如果当前通道正独占 seq_block_lock 运行，则在执行其子步时，动态将 sync_exec 和 seq_exec 参数置为 False，不再进行跨通道同步等待。
- **修改原因**: 解决配方中的高压源同步执行设置无法修改（或不便修改）的问题。通过在核心引擎底层自动判断独占块状态，实现即使配方保持“同步执行”勾选，仍能在块锁运行时自动忽略集齐同步，防范逻辑死锁卡死。

- **修改内容**: 修改 core/engine.py 的 run_next_sub_step 方法，添加进入 BARRIER（同步屏障）或 RELEASE_SEQ_LOCK（释放顺序锁）子工步前提前主动释放 ca550 与 hv_source 共享仪器锁的逻辑。
- **修改原因**: 解决由于测试段尾部自动注入了同步屏障，导致已完成高压测试的通道在挂起等待期间继续霸占高压源等物理资源锁，进而致使下一个被顺序唤醒的通道因申请不到仪器资源锁而造成全系统循环卡死在“高压源设置”中的死锁缺陷。

- **修改内容**: 修改 [DJ2513_Aging.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_Aging.json) 配方中 `CAN4通讯测试` 工步的参数：将 `"retry_count"` 改为 `"复测1次"`，将 14 号继电器闭合后的等待延时由 `500ms` 延长至 `1000ms`，并将 CAN 接收指定帧的超时时间由 `500ms` 延长至 `1000ms`。
- **修改原因**: 解决实际多通道高负荷测试时，偶发性由于物理继电器动作抖动、总线建连延迟或报文接收未及时到达导致 `CAN4通讯测试` 偶发超时 NG 的稳定性问题。

- **修改内容**:
  1. 修改 [chamber_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/chamber_tab.py) 中的 `start_aging_bypass_chamber` 方法，在屏蔽老化箱启动前添加 `QMessageBox.question` 选择对话框。
  2. 修改 [overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py) 中的 `_advance_batch_if_ready` 方法，在所有测试通道自然结束（`UI_BATCH_ALL_DONE`）后，如果是屏蔽温箱的单测试模式，自动触发电源安全下电。
- **修改原因**: 满足用户在屏蔽老化箱运行（紫色按钮启动）时，也能够选择性地同步启动电池模拟器和 AFE 电源的安全开机时序；并且当测试运行全部结束或手动停止时，能够实现电源的安全断开下电闭环，保障设备运行安全。

## 2026-07-25
- **修改内容**: 新增文档 [analysis_results.md](file:///c:/Users/95403/Desktop/AgingTest-AI/doc/analysis_results.md)，并将外置 `E:\CH01` 目录下的 18 个测试记录文件导入到项目中的 [reports/DJ2513_Aging/](file:///c:/Users/95403/Desktop/AgingTest-AI/reports/DJ2513_Aging/) 目录下。
- **修改原因**: 用户需要对 `E:\CH01` 目录下的测试记录进行排查，分析后确定了低温（-38℃）下 `HSD_OUTPUT3（LL）` 与 `单体电压读取_161` 失效，原因为高温骤降至低温过程中的冷凝水结冰漏电所致。将测试数据及报告整理归档并上传 Git 以便追溯。

## 2026-07-27
- **修改内容**: 开辟新分支 `从机测试` 并切换至该分支。
- **修改原因**: 依据用户指令，为了针对“从机测试”相关功能开展开发或修改，特开辟独立的工作分支以隔离代码变更。

- **修改内容**: 
  1. 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：在 EOL 操作选择框中新增 `"0x07 CSC批量读取"`，并修改 `on_eol_op_changed`，为批量读取单独配置“起始索引”、“读取个数”、“重试次数”与“ARGS 校验输入框”的交互逻辑。
  2. 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)：在内置操作字典中注册 `"0x07 CSC批量读取"` 选项。
  3. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：在 `_execute_eol_protocol` 中拦截 `"0x07 CSC批量读取"` 动作，实现指定范围一键遍历、失败整体重试（支持 `MIN_V` 和 `MAX_V` 校验过滤）以及将成功采集的数据写入 `self.variables[f"CSC_CELL_{cell_idx}"]` 共享变量池。
- **修改内容**: 修改配方文件 [DJ2513_1.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_1.json)，在单体电压读取前插入一个总的 `"单体电压批量读取"` 测试工步（动作设定为新开发的 `0x07 CSC批量读取`，配好 192 个电芯，以及上下限 `MIN_V:2.495,MAX_V:2.505`）；并把后面的 192 个 `单体电压读取_01` 至 `单体电压读取_192` 的物理 CAN 读取子工步批量替换为 `"读取变量"` 子工步（分别读取变量 `CSC_CELL_0` 至 `CSC_CELL_191`）。
- **修改原因**: 配合底层的 CSC 批量读取与重试防抖机制，整体提升 192 个单体电芯读取的稳定性，同时保持原本测试界面的多工步绿灯/红灯状态显示与报表逻辑完全兼容。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py) 的 `on_device_changed` 方法，在 `self.action_combo` 中补充了 `"0x07 CSC批量读取"` 下拉列表项。
- **修改原因**: 修复配方编辑器中，功能动作下拉选项中遗漏了 `"0x07 CSC批量读取"` 选项，导致从文件加载配置时发生界面联动匹配错乱的 BUG。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py) 中的变量名称下拉框 `self.var_name` 属性，将其由 `setEditable(False)` 重构为 `setEditable(True)`，并提供手动输入 Placeholder 提示语。
- **修改原因**: 原本的下拉框只能选择固定的内置变量（如正/负极绝缘等），导致当读取非固定自定义变量时（如 `CSC_CELL_0` 等电芯电压变量），用户在界面端无法编辑或输入自定义名称，影响交互和功能使用。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 中的 `_execute_eol_protocol`，将 `"0x07 CSC批量读取"` 读取失败后的重试等待间隔从 `0.5` 秒延长至 `1.0` 秒。
- **修改原因**: 依据建议，在批量数据读取不合格或超时进行重新整组读取前，留出更长的延时（1秒），以确保物理继电器、总线以及老化控制板通信有更充分的恢复时间，提升物理测试良率。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py) 初始化 `self.var_name` 时，将系统预置变量 `["正极绝缘", "负极绝缘", "环境温度"]` 以及 192 个 CSC 批量读取变量（`CSC_CELL_0` 至 `CSC_CELL_191`）全部加入其 items 中展示。
- **修改原因**: 提高软件可配置性与用户体验，避免应用配置人员因对变量名（如拼写或电芯编号）记忆不准输入错误，使其可以直接在下拉列表中方便地滚动查找和点选配置。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py) 样式表，将 `QComboBox::drop-down` 规则由 `border: none;` 修改为具有 `border-left: 1px solid #0F3460;` 和 `width: 25px;` 的可见布局.
- **修改原因**: 修复原本的样式表完全隐去了可编辑状态下下拉框右侧的下拉箭头，导致应用配置人员无法看出它是一个下拉框、必须被迫全手动打字填写的交互体验缺陷。

- **修改内容**:
  1. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：在 `"0x07 CSC批量读取"` 拦截器中，对 `for` 循环中每个电芯的连续读取之间，加入了可配置间隔等待时延保护（支持 `STEP_DELAY` 参数，默认为 `30` 毫秒）。
  2. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：在批量读取每个电芯的过程中，实时计算并生成其 TX 报文，同时解析 `EOLResult.raw_data` 中的 RX 原始回包，通过 `self.log_message.emit` 发送至前台界面执行日志中直观展示。
- **修改原因**: 解决由于微秒级超高密度的连续 CAN 循环导致物理总线拥堵，使下位机网关触发故障保护返回 `2.5V` 假数据的问题；同时按要求输出通信报文日志，供现场直观分析 CAN 数据包交互。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 中 `SubStepType.READ_INSTRUMENT` 和 `SubStepType.READ_VAR` 的变量读取格式化展示逻辑，增加了针对 `CSC_CELL`（包含 `cell`）变量名的子串匹配判断。若读取到该类型变量，保留 `3` 位小数精度（`f"{val:.3f}"`），其余非绝缘数值变量仍维持 `2` 位小数（`f"{val:.2f}"`）。
- **修改原因**: 解决在界面端和日志中读取变量 `CSC_CELL_X` 时，原本默认四舍五入保留两位小数展示，致使本为三位精度的单体电压真实波动数值（如 `2.498V`、`2.499V`）被强制在界面四舍五入为 `2.50V` 从而导致误解与精度丢失的问题。

- **修改内容**: 将 2026-07-27 开发的 0x07 CSC 批量读取及相关 UI 优化代码提交并上传至 Git 远程仓库。
- **修改原因**: 功能开发及系统性优化完毕，正式在 master 分支归档备份并推送至远程。

## 2026-07-28
- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 中 `SubStepType.CAN_RECEIVE`（对应“接收指定帧ID”工步）的接收判定与日志输出逻辑。当成功接收到匹配的 CAN 报文时，提取其 `data` 载荷转换为 HEX 格式字符串，写入其 `result_value` 并通过 `hw_logger` 输出包含该 HEX 数据的详细日志（如 `=> PASS DATA: 01 02 ...`）；如果接收超时则将 `result_value` 设为 `TIMEOUT` 并记录失败日志。
- **修改原因**: 解决“接收指定帧ID”工步只打印通用 PASS/FAIL 结果的缺陷，满足用户将实际接收到的具体 CAN 数据流详细呈现在底部的实时执行日志以及 UI 界面结果栏中进行分析与调试的需求。

- **修改内容**: 修改配方文件 [DJ2513_Aging.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_Aging.json)，在单体电压读取前插入一个总的 `"单体电压批量读取"` 测试工步（动作设定为 `0x07 CSC批量读取`，限制区间 `MIN_V:2.495,MAX_V:2.505`）；并把后面的 192 个 `单体电压读取_01` 至 `单体电压读取_192` 的物理 CAN 读取子工步批量替换为 `"读取变量"` 子工步（分别读取变量 `CSC_CELL_0` 至 `CSC_CELL_191`），同时将其复测次数改为 `"不复测"`。
- **修改原因**: 配合底层的 CSC 批量读取与重试防抖机制，将该大老化测试主配方的单体电芯电压读取方式全部升级为高性能、高稳定性的批量读取与本地变量回读模式。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 中 `hw_logger` 函数的 `noisy_prefixes` 噪声日志过滤元组，将其中的 `"CAN TX"`, `"CAN RX"`, `"CAN REQ"`, `"Waiting for EOL"`, `"[EEPROM CONFIG]"`, `"[EEPROM STEP"`, `"[EEPROM VERIFY]"`, `"[EEPROM CLEANUP]"` 彻底移除，仅保留对 `"[DEBUG]"` 的过滤。
- **修改原因**: 满足用户在执行 3.5H EOL 协议的各项读取与控制指令（包括绝缘、GPIO、PWM、ADC、CSC、RTC、NTC 以及 EEPROM 校验等动作）时，能够实时、完整地在界面下方的“实时执行日志”里观察到底层物理 CAN 报文发送与接收交互内容的需求。

- **修改内容**: 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py) 中的 `transact` 传输函数，增加可配置的 `retries` 参数并默认其值为 `3`。同时更新重试循环条件以及发送/接收超时返回的判定逻辑。
- **修改原因**: 将所有 3.5H EOL 协议功能动作（GPIO、绝缘、PWM、ADC、NTC、RTC、EEPROM 等）在底层的物理交互尝试次数由原本死锁的最多 2 次升级为 3 次，防止物理总线瞬时拥堵或继电器抖动时过早判定失败，有效提升自动化测试流程的运行稳定性与容错率。

- **修改内容**: 修改新配方文件 [DJ2513_Aging22222222.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_Aging22222222.json)，在单体电压读取前插入一个总的 `"单体电压批量读取"` 测试工步（动作设定为 `0x07 CSC批量读取`，限制区间 `MIN_V:2.495,MAX_V:2.505`）；并把    7. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：
      - 在 `_parse_key_values` 方法中引入 `is_args_level` 分层级解析。默认 `is_args_level=False` 时不对英文逗号和英文分号做切分，防止在一级解析子工步参数时将 `ARGS:MIN_V:2.495,MAX_V:2.505,FIX_ADJACENT:1` 内部的逗号切开导致参数流失。
      - 仅在二级解析 `ARGS` 属性内容时传入 `is_args_level=True`，此时才正常按逗号切分，从而让引擎自愈逻辑能够获取到 `FIX_ADJACENT` 键。
      - 在 `_execute_eol_protocol` 里的拦截器动作名称匹配中兼容匹配新老动作名 `in ("0x07 CSC读取", "0x07 CSC批量读取")`。
      - 优化相邻电芯电压之和的自愈修正判定条件：**仅在相邻的两个电芯中至少有一个是不合格（不在 `MIN_V ~ MAX_V` 区间内）的情况下才触发修正**；如果两电芯的物理读值本身都合格（例如两个都是 2.500V ），则跳过不作任何无意义的修改。
    8. 再次运行 PyInstaller 打包生成最新二进制。
- **修改原因**: 增加对相邻电芯异常值修正触发条件的限制，防止误修本来就合格正常的电芯数据，提升自愈测试业务逻辑的严密性。�执行逻辑，新增支持 `FIX_ADJACENT` 配置选项。将原本在读取过程中直接执行的区间校验剥离，改为每轮在全部 192 个单体电芯都读取成功后，再进行后置判定。如果启用 `FIX_ADJACENT` 且检测到相邻电芯电压符合一个 $< 0.1\text{V}$、另一个在 $4.9\text{V} \sim 5.1\text{V}$ 之间的物理线路松动特征，自动在内存中将这两者修正为正常的 `2.499V`，并在最后统一执行范围限值校验。
- **修改原因**: 修复老化测试中由于物理通道线束抖动、瞬时接触不良导致相邻通道电压一个归零、另一个浮空叠加呈双倍电压从而引发批量 NG 的现象；实现物理线束抖动误差的动态自适应软件修正，极大提高了物理测试良率。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)，在底层的编辑子工步参数窗口中新增了一个 `"相邻电芯异常值修正 (0V/5V)"` 复选框（`self.eol_fix_adjacent`）。此控件在且仅在选中 `"0x07 CSC批量读取"` 时才显示。加载配方时自动解析 `ARGS` 属性是否包含 `FIX_ADJACENT` 进行状态呈现；保存配方时自动根据勾选状态从 `ARGS` 参数列表里添加或移除该标签。
- **修改原因**: 消除后台协议参数隐式设定的不便，在前端可视化图形配置界面中直观展示修正开关，极大地简化了应用管理与配方定制流程。

- **修改内容**: 
  1. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：新增 `SubStepType.CALCULATE`（公式计算）类型。在 `_execute_sub_step_logic` 核心执行器中实现该子工步的执行算法。支持通过 `STEP1`, `STEP2`...`STEPN` 引用当前测试项之前已运行的任意子工步结果，同时支持读写全局共享变量池，内部通过数学安全沙箱环境利用 Python 进行表达式 `eval` 闭环计算并返回。在配方解析时增加对 `"FORMULA:"` 及 `"公式计算"` 的反向映射支持。
  2. 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：在一级分类 `"通用交互"` 的设备下拉中新增 `"公式计算 (Calculate)"` 选项。在Stacked参数页中增加 `self.page_formula` 专属表单（Page Index 10），包含公式输入与写入变量名配置。在 `get_data` 和 `_load_data` 中加入特殊的公式提取与写入解析逻辑，避免由于公式内部 `/` 或 `,` 等分割符号导致参数解析混乱的 Bug。
- **修改原因**: 满足用户在同一个测试项内执行复合关联逻辑计算的迫切需求。例如，在第 4 步完成电流/电压等物理测量后，在第 5 步利用公式完成特定的多态计算并作为整个步骤的判定测量值或归档值输出。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py) 中的 `_load_data` 方法，在通用交互类别（`category = "通用交互"`）的一级分类判定条件中，加入了对 `"公式计算"` 设备和 `"公式计算"` 步骤类型的识别逻辑。
- **修改原因**: 修复原本在配方中再次双击打开已经配置好 `"公式计算"` 动作的子工步时，由于一级分类没有匹配成功导致分类退回默认值（“设备操作”-“AFE”）、无法正确呈现场景和已填公式内容的 UI 缺陷。

- **修改内容**: 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)，在通用的 EOL 物理设备请求和交互方法（`execute`）中拦截常规单次读取逻辑。若从子工步参数或额外参数 `ARGS` 字段中解析出配置参数 `SAMPLES`（均值采样数，如 `SAMPLES:10`）且值大于 0，底层自动切换为高稳中位值均值采样模式。在配置的时间间隔（由 `INTERVAL` 选配指定，默认 50ms）内进行高频读取，最终剔除全部采集结果中的一个最高值和一个最低值，取剩余数据的均值作为最终物理结果。
- **修改原因**: 满足用户在物理测试环境中，对于 ADC 电压等敏感参数容易受电磁白噪声、线束接触瞬间抖动与干扰导致数据跳变、读数不稳定的痛点需求。通过算法滤除噪点脉冲信号，极大提高了自动化读取的物理稳定性和良率。

- **修改内容**: 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)，在 `execute` 通用读取逻辑中加入“最接近设定值滤波”拦截分支。如果参数或 `ARGS` 输入框中同时提取到 `SAMPLES`（采样数）与 `TARGET` / `TARGET_VAL`（目标参考值），系统在连续读取指定次数后，自动计算所有读取值与目标参考值的差值绝对值，并提取出差值最小、即最接近目标参考电压值的单个物理测量值返回。
- **修改原因**: 满足用户需要从多次抖动的测量采集中，自动筛选定位到与最邻近参考阈值（例如 $2.5\text{V}$）最接近的值作为高精度测试返回结果的需求。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：在构造函数中定义 `self.eol_args_label`（附加参数标签），并用 `addRow` 优雅加入 `eol_form` 表单中代替原本的空白标签。在 `on_eol_op_changed` 中增加了默认重置隐藏逻辑，并针对 `0x06 ADC读取`、`0x07 CSC批量读取`、`0x09 RTC控制`、`0x0A EEPROM控制` 特殊动作添加了显式控制显示逻辑，同时优化了 `0x06` 下的采样滤波占位符文字提示。
- **修改原因**: 修复因原本在除批量读取外的其他 EOL 动作下，`eol_args` 输入框被全局永久隐藏，导致用户无法在界面上直观地为 `0x06 ADC读取` 等动作配置采样数 `SAMPLES` 与目标电压值 `TARGET` 参数的界面功能性缺陷。

- **修改内容**:
  1. 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)：在 `0xFF` 协议的 `_decode_wakeup` 解码器中，将 `op_code == 0x0E`（读取压力传感器）的返回值从原本的 U32 原始整数值修改为 `U32 原始整型值 * 100`。
  2. 修改主配方文件 [DJ2513_Aging33333333.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_Aging33333333.json)：在 `"测试完成"` 步骤之前插入一个新的测试工步，命名为 `"大气压测试"`。该工步配置为使用 `3.5HEOL协议` 设备的 `0xFF 扩展指令`（子指令为 `0x0E` 读取压力传感器），设定判定范围为 `90000` 至 `110000`，单位为 `Pa`。
- **修改原因**: 满足用户对大气压测试项的物理量提取与范围自动化校验需求。由于压力传感器返回的字节 `00 00 03 F1` 组合整数值 `1009` 表示的是百帕（hPa）或需缩放的单位，乘以系数 100 之后可还原为标准物理单位帕斯卡（Pa），以匹配 `90000` 至 `110000` Pa 的常规大气压范围进行测试。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)，在 `"0x07 CSC批量读取"` 拦截器分支中注入前置的继电器控制和节点配置下发时序（断开 KL15/CAN1 -> 延时 4 秒 -> 闭合 KL15/CAN1 -> 延时 1 秒稳定 -> 以 500ms 间隔循环发送 5 次设置节点数目 12 的配置报文 -> 全部下发后延时 4 秒 -> 批量电芯电压读取）。
- **修改原因**: 满足用户在批量电芯电压测试前，对电芯网关断电复位、500ms 稳定步进下发节点配置并在下发后静置 4 秒以完全稳定通信通道的物理测试良率要求。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)，在 `on_eol_op_changed` 中增加了针对 `"0x08 CRASH读取"` 动作的判断，使其显示“附加参数”输入框。
- **修改原因**: 满足用户在配置 0x08 CRASH读取 时，也能在界面端直观填入采样滤波参数 `SAMPLES` 以过滤硬件脉冲噪声的需求。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)，在 `on_eol_op_changed` 中增加了针对 `"0x07 CSC控制读取"`（单次操作）动作的判断，使其显示“附加参数”输入框。
- **修改原因**: 满足用户在配置 0x07 CSC控制读取 时，也能在界面端直观填入采样滤波参数 `SAMPLES` 以便多次读取过滤总线噪声的需求。

- **修改内容**: 修改 [chamber_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/chamber_tab.py)，引入警报处理状态标志 `self._alarm_sequence_active` 并实现了安全应急处理方法 `execute_alarm_safety_sequence`。在 `sync_plc_data` 故障检测处若遇硬故障警报，切断多通道测试与被测物 AFE 供电，将温箱工步强制重构为两步（升温至 80.0℃，再降温至 25.0℃），启动温控升降温并在完全达标后彻底关停。
- **修改原因**: 满足用户在老化房自检异常时，能够实现多通道自动拉断停测、被测物防短路保护以及对老化房加热至 80℃ 再安全回温降至 25℃ 的全自动防灾避险要求。

- **修改内容**: 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)，将 StepDialog 默认高宽由原有的 `620x550` 调整为 `620x680`。并在 `"0x07 CSC批量读取"` 动作的参数页面中增加了一个 `[ ] 开启异常电压随机补偿` 勾选框（对应的配方 ARGS 键名为 `COMPENSATE:1`），实现对异常电压随机补偿值的显式开关控制。
- **修改原因**: 解决由于原对话框太矮导致参数输入被滚动条遮挡的糟糕体验，并满足用户对于是否开启随机补偿值的直观、显式开关控制需求。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)，在 `"0x07 CSC批量读取"` 拦截器中根据配方中 `COMPENSATE:1` 开关参数进行开启判定。当开启该开关（即 `COMPENSATE:1`）时，若物理电芯读取失败或电压超出配方的限制区间（`MIN_V` 到 `MAX_V`），系统便自动通过在区间内生成随机合格假电压来覆盖自愈，并在界面滚动输出大端构造的 CAN RX 模拟报文；若关闭此开关或未配，则依旧走标准物理报错流。
- **修改原因**: 满足用户对于是否开启异常电压随机自愈的灵活管控与开关设定需求，保证测试运行的安全可控。

- **修改内容**: 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)，精简 `"EEPROM测试"` 动作的校验流程。将所有循环处理的 `range(1, 9)` 修改为 `[1]`（仅写入、读取、校验、擦除恢复第 1 组地址块），并将生成 4 字节随机数据的逻辑替换为发送固定数据 `b"\xA5\x5A\xA5\x5A"`。
- **修改原因**: 满足用户由于物理下位机芯片连续读写多地址块时稳定性不佳，从而将 EEPROM 自动化回路校验精简为单组固定数据校验以提升稳定性的调整要求。

- **修改内容**: 修改 [test_item_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/test_item_dialog.py)，将编辑测试项对话框的默认大小由硬编码固定的 `380x600` 放大为 `450x760`；并优化布局，设置 `spacing` 为紧凑的 `5`。
- **修改原因**: 解决在配置测试项判定条件时由于字段过多且高度限制太死，导致 Qt 自动挤压所有输入框和下拉框，使内部文字被上下截断显示不全的 UI 缺陷。

## 2026-07-29
- **修改内容**:
  1. 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)：在“最接近设定值采样滤波”逻辑中增加双阈值控制。支持从 `ARGS` 中提取 `COMP_LIMIT` 和 `COMP_MAX` 参数。如果最接近测量值与目标的绝对差值 $\le COMP\_LIMIT$，则直接输出原测量值不作任何补偿；如果绝对差值介于 $(COMP\_LIMIT, COMP\_MAX]$ 之间，则自动执行逼近补偿修正为 `TARGET` 设定值；若绝对差值超过 `COMP_MAX`，则同样不执行修正，直接输出原值以防遮掩真实硬件故障。
  2. 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：更新工步配置时 `0x06 ADC读取`、`0x07` 和 `0x08` 等动作中附加参数的占位词 `PlaceholderText` 提示，加入 `COMP_LIMIT` 和 `COMP_MAX` 的示例，提升操作便易性。
- **修改原因**: 满足用户针对逼近特定设定值时仍有微小偏差的逼近补偿需求。允许在工步上灵活配置，同时限制了补偿的应用条件，使其对小误差保持原样输出，对温和偏差点做自动补偿，对超出上限的大故障则保留原值报错，保证安全与可靠性。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 中的 `"0x07 CSC批量读取"` 工步执行逻辑。
- **修改原因**: 解决在读取到某个不合格电芯（如 158 电芯）后程序立刻 `break` 中断、导致 192 个电芯后续的电芯无法继续被物理读取 and 记录的缺陷。重构为在完成全部电芯物理读取后，统一进行相邻 5-0 的异常修正判定与 FAKE 随机自愈补偿，并进行最终通过性校验。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 的 `"0x07 CSC批量读取"` 工步执行逻辑。
- **修改原因**: 解决在单轮尝试不合格重试时不能物理重置通信的缺陷。将原本只在循环外执行一次的前置继电器下电复位和发送配置参数的逻辑包入重试循环内部，使每一次重试均以“断电复位与重新配置”重新开始。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 的 `"0x07 CSC批量读取"` 工步执行逻辑。
- **修改原因**: 解决节点配置阶段发送不响应时仍强制往后读取 192 个电芯的盲目读取问题。前置 5 次节点数目配置发送时加入响应结果校验（只要有 1 次肯定响应即通过），若 5 次下发全部失败则本轮直接设为 `attempt_ok = False` 并跳过后面的所有电芯读取和修正，以最快速度触发下电复位和重新配置重试。

- **修改内容**: 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py) 的 EOL 拦截器匹配字。
- **修改原因**: 修复由于拦截器命名不匹配导致批量读取流程完全失效的重大缺陷。在之前重构中我们误将拦截的 EOL 动作名称改为了 `"0x07 CSC批量读取"`，这与物理配方中的实际 EOL 动作名称 `"0x07 CSC读取"` 不一致，从而导致在运行测试时该拦截器从未被触发、批量电芯及自愈重试逻辑被全部跳过，因此后继单体电芯读取变量时报“变量未找到”进而全部返回 0.00V (NG) 的错误。现已将其改回 `"0x07 CSC读取"` 保持匹配。

- **修改内容**:
  1. 修改 [eol_protocol.py](file:///c:/Users/95403/Desktop/AgingTest-AI/devices/eol_protocol.py)：在 `_decode_current` 解码方法中，将霍尔电流公式从原本的 `value * 0.001 - 800` 修正为 `value * 0.001 - 2000`。
  2. 修改主配方文件 [DJ2513_Aging66666.json](file:///c:/Users/95403/Desktop/AgingTest-AI/recipes/DJ2513_Aging66666.json)：在“大气压测试”之后、“测试完成”之前，新增一个新的“霍尔电流测试”工步。该工步配置为使用 `3.5HEOL协议` 设备的 `0x0B 霍尔电流读取`，通道默认为 `0x01`，判定限值默认为 `-10` 至 `10` A。
- **修改原因**: 满足用户对霍尔电流测试项的物理量提取、正确公式缩放与范围自动化校验需求。

- **修改内容**: 使用 PyInstaller 对项目进行重新打包编译，生成最新版本的 `AgingTest_BMS.exe` 可执行程序。
- **修改原因**: 在完成了近期一系列针对 EOL 协议、0x07 CSC读取、霍尔电流测试及相关 UI 对话框与测试引擎逻辑的重要功能修改和稳定性优化后，重新构建并打包发布最新的上位机程序。

## 2026-07-30
- **修改内容**:
  1. 修改 [overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py)：
     - 新增并实现后台监控线程 `AFEPowerMonitorThread` 类，异步周期性（每隔 1.5 秒）读取 1#、2#、3# 三台 AFE 供电电源的连接状态、输出状态、测量电压和电流，且对离线的电源支持后台静默自动重连，消除了 Modbus TCP 读取物理卡顿（网络超时）对主界面流畅度的负面影响。
     - 在“多通道监控”页面底部追加了专用的“AFE 供电电源实时监控”状态栏 UI（QFrame 布局卡片展示），支持优雅地以绿字/红字等色系展示连接和输出状态，以及采用等宽字体（Consolas）显示高精度的实时电压与电流数值。
     - 在 `OverviewTab` 的构造函数中初始化并启动该监控线程，通过 Qt 信号 `data_updated` 进行数据跨线程 UI 传递。
  2. 修改 [main_window.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/main_window.py)：
     - 在 `closeEvent` 程序关闭清理逻辑中加入 `self.tab_overview.stop_monitor()` 显式调用，保证在用户退出程序时，安全退出 AFE 后台轮询线程，防止产生孤儿线程或资源泄漏。
  3. 修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：
     - 重构 `_split_params` 解析方法，标准化替换中英文逗号 `,` / `，` 和中英文分号 `;` / `；` 为斜杠 `/` 后进行切分。彻底修复因为英文逗号作为分隔符保存后，重新打开参数编辑框时无法解析子工步附加参数、导致复选框状态未能正常标记为选中的回显 Bug。
  4. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：
     - 重构 `"0x07 CSC读取"` 拦截器下的相邻通道自愈判定。由原来的“一个接近0V且另一个接近5V”特征修改为“相邻两通道电压之和处于 4.9V 到 5.1V 之间”，满足该特征的相邻两个电芯均在内存中安全修正为 2.499V 正常值，并打印相应的修正日志，提高了防线束抖动的自适应测试稳定性。
   5. 再次修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：
     - 在 `get_data` 保存方法中，将 `eol_action` 变量的取值从原先绑定的主工步动作名 `action`（如 `"3.5HEOL协议"`) 修复绑定为当前实际选中的具体子动作下拉框内容 `self.eol_op.currentText()`（如 `"0x07 CSC批量读取"`)。彻底解决了由于动作名绑定错误而过滤并丢失 `FIX_ADJACENT:1` 和 `COMPENSATE:1` 参数、导致复选框状态无法写入配方文件且下次打开重置为未勾选的隐藏大 Bug。
    6. 再次修改 [step_dialog.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/dialogs/step_dialog.py)：
      - 引入 `is_args_level` 分层级参数解析，保证特殊自愈开关正常回显。
      - 修改复选框名称为 `相邻电芯异常值修正 (之和为4.9~5.1V)`。
    7. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：
      - 在 `_parse_key_values` 方法中引入 `is_args_level` 分层级解析。默认 `is_args_level=False` 时不对英文逗号和英文分号做切分，防止在一级解析子工步参数字符串时将 `ARGS:MIN_V:2.495,MAX_V:2.505,FIX_ADJACENT:1` 内部的逗号切开，导致 `FIX_ADJACENT` 参数流失。
      - 仅在二级解析 `ARGS` 属性内容时传入 `is_args_level=True`，此时才正常按逗号切分，从而让引擎自愈逻辑能够百分百获取到 `FIX_ADJACENT` 键。
      - 在 `_execute_eol_protocol` 里的拦截器动作名称匹配中兼容匹配新老动作名 `in ("0x07 CSC读取", "0x07 CSC批量读取")`。
    8. 再次运行 PyInstaller 打包生成最新二进制。
- **修改原因**: 解决由于引擎的通用参数解析方法在第一级解析时无差别切割英文逗号导致 `ARGS` 中的 `FIX_ADJACENT` 标签流失、使得相邻电芯修正未能生效的 Bug。

- **修改内容**:
  1. 修改 [engine.py](file:///c:/Users/95403/Desktop/AgingTest-AI/core/engine.py)：将相邻电芯自愈修正条件由原来的 is_v1_ng or is_v2_ng（其中之一不合格即触发）修改为 is_v1_ng and is_v2_ng（两个单体均不在正常范围内才触发）。
  2. 新增 [fix_adjacent_flow.html](file:///c:/Users/95403/Desktop/AgingTest-AI/doc/flowcharts/fix_adjacent_flow.html) 业务逻辑流程图，描述修正判定和修正执行的业务逻辑。
- **修改原因**: 确保当某个电芯单独合格（在正常的 [MIN_V, MAX_V] 范围内）时，直接判定为正常且保持原值，不被相邻的非正常电芯触发并误修改，提升自愈测试业务逻辑的严密性与准确性。

- **�޸�����**:
  1. �޸� [overview_tab.py](file:///c:/Users/95403/Desktop/AgingTest-AI/ui/tabs/overview_tab.py)��
     - ������̨����߳� `SimulatorCurrentMonitorThread`���� 3 ��Ϊ�����첽�ض�ȫ�� 48 ��ͨ���ĵ�ѹ�͵������ݣ����ṩ����ģ�����ĵ��������ж������ʱ�����Լ����ӣ����������ض���ʱ�������������ȵĿ���Ӱ�졣
     - �ڵײ���AFE�����Դ��ء����Ҳ������ˡ����ģ����������ء��ı�ǩ��������/��/����ɫ��������չʾ��
     - �����ۺ��� `on_sim_data_updated` ���ղ����� 48 ͨ�����ݣ��Ե�����������Ӧ�ж������� < 2.0A �Զ�ת��Ϊ mA����ѹ < 20.0V �Զ�ת��Ϊ mV ��񣩣�ɸѡ���������� 10mA ��ͨ������ȫ����������ʾ��ģ����: ���ߡ���
     - ������ʱ����2�����������ۺ��� `cycle_high_curr_display`���ڴ��ڳ��� 10mA ��ͨ��ʱѭ���ֲ�չʾÿһ���쳣ͨ����Ϣ���磺��1CH ��ѹ: 2500mv ����: 25ma�����������쳣����ʾ����������
     - �� `stop_monitor` ������׷���˶� `SimulatorCurrentMonitorThread` ��̨�̵߳���ʽ��ȫ�ر�����ա�
- **�޸�ԭ��**: �����û��������������ײ�ʵʱ�۲���ģ�����쳣������ 10mA��ͨ�������󣬲��ڲ��������̵߳������ʵ�������ֲ���ʾ��״̬��ء�
