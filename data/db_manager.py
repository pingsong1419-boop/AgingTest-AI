import sqlite3
import os
import datetime
import threading
import queue
from typing import List, Dict, Any, Optional

class DBManager:
    """
    数据存储管理类
    支持 SQLite 数据库持久化存储和 XTML/XML 格式的本地文本备份。
    采用单线程异步写入机制，确保 60 通道高频采样时不阻塞主线程。
    """
    def __init__(self, db_path: str = "bms_test_data.db"):
        self.db_path = db_path
        self._init_db()
        
        # 异步写入队列与后台线程
        self.queue = queue.Queue()
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._db_worker, daemon=True)
        self.worker_thread.start()

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 测试主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_main (
                test_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                shelf_code TEXT,
                master_code TEXT,
                slave_codes TEXT,
                recipe_name TEXT,
                start_time DATETIME,
                end_time DATETIME,
                result TEXT
            )
        ''')
        
        # 测试数据详细记录表 (采样数据)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                step_name TEXT,
                voltage REAL,
                current REAL,
                temp TEXT,
                timestamp DATETIME,
                FOREIGN KEY (test_id) REFERENCES test_main(test_id)
            )
        ''')

        # 测试项判定结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_items_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                item_name TEXT,
                lower_limit REAL,
                upper_limit REAL,
                measured_value REAL,
                result TEXT,
                duration REAL,
                timestamp DATETIME,
                FOREIGN KEY (test_id) REFERENCES test_main(test_id)
            )
        ''')
        
        # 兼容性迁移：检查是否包含 duration 列和 unit 列，若无则 Alter Table 增加
        try:
            cursor.execute("PRAGMA table_info(test_items_results)")
            columns = [col[1] for col in cursor.fetchall()]
            if "duration" not in columns:
                cursor.execute("ALTER TABLE test_items_results ADD COLUMN duration REAL DEFAULT 0.0")
            if "unit" not in columns:
                cursor.execute("ALTER TABLE test_items_results ADD COLUMN unit TEXT DEFAULT 'NULL'")
        except Exception as migration_err:
            print(f"[-] 数据库迁移报错 (兼容列迁移): {migration_err}")
        
        conn.commit()
        conn.close()

    def _db_worker(self):
        """后台数据库写入线程"""
        # 在同一个线程内保持一个长连接，提高性能并避免多线程冲突
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        while self.is_running or not self.queue.empty():
            try:
                # 批量处理以提高效率 (最多等待 100ms)
                try:
                    task = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                sql, params, callback_event, result_container = task
                
                if sql is None:
                    # BUG-09修复: 收到None哨兵信号，立即退出
                    break
                try:
                    cursor.execute(sql, params)
                    if "INSERT" in sql.upper():
                        res = cursor.lastrowid
                    else:
                        res = True
                    
                    if result_container is not None:
                        result_container['value'] = res
                    
                    conn.commit()
                except Exception as e:
                    print(f"[-] 数据库执行异常: {e}, SQL: {sql}")
                    if result_container is not None:
                        result_container['error'] = e
                finally:
                    if callback_event:
                        callback_event.set()
                    self.queue.task_done()
                    
            except Exception as e:
                print(f"[-] 数据库后台线程严重错误: {e}")
        
        conn.close()

    def close(self):
        """BUG-09修复: 先投入哨兵信号唤醒工作线程，再 join，防止大量队列时卡住"""
        self.is_running = False
        self.queue.put((None, None, None, None))  # 哨兵信号
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)

    def _execute_async(self, sql: str, params: tuple = (), wait: bool = False) -> Any:
        """内部通用异步执行方法"""
        event = threading.Event() if wait else None
        container = {'value': None, 'error': None} if wait else None
        
        self.queue.put((sql, params, event, container))
        
        if wait:
            if not event.wait(timeout=5.0):
                raise TimeoutError("数据库操作超时")
            if container['error']:
                raise container['error']
            return container['value']
        return None

    def start_new_test(self, channel_id: int, shelf: str, master: str, slaves: List[str], recipe: str) -> int:
        """记录测试开始并返回测试 ID (同步等待结果)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = '''
            INSERT INTO test_main (channel_id, shelf_code, master_code, slave_codes, recipe_name, start_time, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        params = (channel_id, shelf, master, ",".join(slaves), recipe, now, "RUNNING")
        return self._execute_async(sql, params, wait=True)

    def log_detail(self, test_id: int, step_name: str, voltage: float, current: float, temp: str):
        """记录实时采样数据 (异步不等待)"""
        now = datetime.datetime.now().strftime("%H:%M:%S")
        sql = '''
            INSERT INTO test_details (test_id, step_name, voltage, current, temp, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        params = (test_id, step_name, voltage, current, temp, now)
        self._execute_async(sql, params, wait=False)

    def log_item_result(self, test_id: int, name: str, low: float, high: float, val: float, res: str, duration: float = 0.0, unit: str = "NULL"):
        """记录某个测试项目的最终判定结果 (异步不等待)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = '''
            INSERT INTO test_items_results (test_id, item_name, lower_limit, upper_limit, measured_value, result, duration, unit, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (test_id, name, low, high, val, res, duration, unit, now)
        self._execute_async(sql, params, wait=False)

    def finish_test(self, test_id: int, result: str):
        """记录测试结束 (同步等待以确保后续文件导出正确)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = 'UPDATE test_main SET end_time = ?, result = ? WHERE test_id = ?'
        params = (now, result, test_id)
        self._execute_async(sql, params, wait=True)
        
        # 测试结束后生成本地备份文件
        self.export_to_xtml(test_id)
        
        # 自动生成用户要求的报表报告 CSV / HTML
        self.generate_report(test_id)

    def generate_report(self, test_id: int):
        """生成详细测试报表 CSV 和 premium HTML 报告"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM test_main WHERE test_id = ?", (test_id,))
        main_info = cursor.fetchone()
        if not main_info:
            conn.close()
            return
            
        master_code = main_info[3] or "未知主机"
        slave_codes_str = main_info[4] or ""
        recipe_name = main_info[5] or "默认配方"
        start_time_str = main_info[6] or "未知开始时间"
        end_time_str = main_info[7] or "未知结束时间"
        overall_result = main_info[8] or "RUNNING"
        
        cursor.execute("SELECT item_name, lower_limit, upper_limit, measured_value, result, duration, timestamp, unit FROM test_items_results WHERE test_id = ?", (test_id,))
        items = cursor.fetchall()
        conn.close()
        
        # 解析从机条码列表
        slaves_list = [s.strip() for s in slave_codes_str.split(",") if s.strip()]
        
        # 1. 确定报表根路径
        sys_cfg = self.load_sys_config()
        report_root = sys_cfg.get("report_root_path", os.path.abspath("reports"))
        
        # 2. 所在文件夹按日期和通道号分类
        try:
            test_date = start_time_str.split(" ")[0]
            if len(test_date) != 10 or test_date[4] != '-' or test_date[7] != '-':
                raise ValueError
        except Exception:
            test_date = datetime.date.today().strftime("%Y-%m-%d")
            
        channel_id = main_info[1]
        channel_folder_name = f"CH{channel_id:02d}"
        target_folder = os.path.join(report_root, test_date, channel_folder_name)
        os.makedirs(target_folder, exist_ok=True)
        
        # 3. 报表命名：通道号 + 主机条码 + 测试开始时间 + 结束时间
        def sanitize_filename(name):
            return "".join(c for c in name if c.isalnum() or c in ('-', '_', ' ')).strip()
            
        safe_master = sanitize_filename(master_code)
        safe_start = sanitize_filename(start_time_str.replace(":", "-").replace(" ", "_"))
        safe_end = sanitize_filename(end_time_str.replace(":", "-").replace(" ", "_"))
        filename_base = f"CH{channel_id:02d}_{safe_master}_{safe_start}_to_{safe_end}"
        
        csv_path = os.path.join(target_folder, f"{filename_base}.csv")
        html_path = os.path.join(target_folder, f"{filename_base}.html")
        
        # 4. 写入 CSV
        import csv
        try:
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["BMS老化测试详细判定报表"])
                writer.writerow([])
                writer.writerow(["基本信息"])
                writer.writerow(["通道号", main_info[1]])
                writer.writerow(["货架号", main_info[2]])
                writer.writerow(["主机条码", master_code])
                # 体现每个从机条码与对应关系
                for idx, sv in enumerate(slaves_list):
                    writer.writerow([f"从机{idx+1}条码", sv])
                writer.writerow(["测试配方", recipe_name])
                writer.writerow(["测试开始时间", start_time_str])
                writer.writerow(["测试结束时间", end_time_str])
                writer.writerow(["测试总判定", overall_result])
                writer.writerow([])
                writer.writerow(["详细判定数据"])
                writer.writerow(["测试项名称", "单位", "下限", "上限", "测量值", "判定结果", "执行时间(秒)", "记录时间"])
                
                for item in items:
                    unit_str = item[7] if len(item) > 7 and item[7] is not None else "NULL"
                    writer.writerow([
                        item[0],
                        unit_str,
                        item[1] if item[1] is not None else "--",
                        item[2] if item[2] is not None else "--",
                        item[3] if item[3] is not None else "--",
                        item[4],
                        f"{item[5]:.2f}" if item[5] is not None else "0.00",
                        item[6]
                    ])
            print(f"[+] 成功生成 CSV 报表: {csv_path}")
        except Exception as e:
            print(f"[-] 生成 CSV 报表失败: {e}")
            
        # 5. 写入 HTML
        try:
            # 动态生成从机基本信息的 HTML 栅格项
            slaves_html_items = ""
            for idx, sv in enumerate(slaves_list):
                slaves_html_items += f'            <div class="info-item"><span class="info-label">从机{idx+1}条码:</span>{sv}</div>\n'
                
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>BMS 测试报告 - {master_code}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f6f9;
            color: #333;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        }}
        h1 {{
            color: #1a1a2e;
            border-bottom: 2px solid #4ecca3;
            padding-bottom: 10px;
            font-size: 28px;
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: bold;
            color: #0f3460;
            margin-top: 25px;
            margin-bottom: 15px;
            border-left: 4px solid #4ecca3;
            padding-left: 10px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .info-item {{
            font-size: 14px;
        }}
        .info-label {{
            font-weight: bold;
            color: #666;
            margin-right: 10px;
        }}
        .result-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        }}
        .result-pass {{ background-color: #d4edda; color: #155724; }}
        .result-ng {{ background-color: #f8d7da; color: #721c24; }}
        .result-running {{ background-color: #fff3cd; color: #856404; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
            font-size: 14px;
        }}
        th {{
            background-color: #0f3460;
            color: #fff;
            font-weight: 600;
        }}
        tr:hover {{ background-color: #f8f9fa; }}
        .text-center {{ text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>BMS 老化测试详细判定报告</h1>
        
        <div class="section-title">基本信息</div>
        <div class="info-grid">
            <div class="info-item"><span class="info-label">通道号:</span>CH-{main_info[1]:02d}</div>
            <div class="info-item"><span class="info-label">货架号:</span>{main_info[2]}</div>
            <div class="info-item"><span class="info-label">主机条码:</span>{master_code}</div>
{slaves_html_items}            <div class="info-item"><span class="info-label">测试配方:</span>{recipe_name}</div>
            <div class="info-item"><span class="info-label">测试总判定:</span>
                <span class="result-badge {'result-pass' if overall_result == 'PASS' else 'result-ng' if overall_result in ('NG', 'FAIL') else 'result-running'}">{overall_result}</span>
            </div>
            <div class="info-item"><span class="info-label">测试开始时间:</span>{start_time_str}</div>
            <div class="info-item"><span class="info-label">测试结束时间:</span>{end_time_str}</div>
        </div>
        
        <div class="section-title">详细判定数据</div>
        <table>
            <thead>
                <tr>
                    <th>测试项名称</th>
                    <th class="text-center">单位</th>
                    <th class="text-center">下限</th>
                    <th class="text-center">上限</th>
                    <th class="text-center">测量值</th>
                    <th class="text-center">判定结果</th>
                    <th class="text-center">执行用时(秒)</th>
                    <th>记录时间</th>
                </tr>
            </thead>
            <tbody>""")
                
                for item in items:
                    res_class = "result-pass" if item[4] == "PASS" else "result-ng"
                    unit_str = item[7] if len(item) > 7 and item[7] is not None else "NULL"
                    f.write(f"""
                <tr>
                    <td>{item[0]}</td>
                    <td class="text-center">{unit_str}</td>
                    <td class="text-center">{item[1] if item[1] is not None else "--"}</td>
                    <td class="text-center">{item[2] if item[2] is not None else "--"}</td>
                    <td class="text-center">{item[3] if item[3] is not None else "--"}</td>
                    <td class="text-center"><span class="result-badge {res_class}">{item[4]}</span></td>
                    <td class="text-center">{f"{item[5]:.2f}" if item[5] is not None else "0.00"}</td>
                    <td>{item[6]}</td>
                </tr>""")
                    
                f.write("""
            </tbody>
        </table>
    </div>
</body>
</html>""")
            print(f"[+] 成功生成 HTML 报表: {html_path}")
        except Exception as e:
            print(f"[-] 生成 HTML 报表失败: {e}")

    def export_to_xtml(self, test_id: int):
        """导出单个测试记录为 XTML (直接读取，需确保主库已同步)"""
        file_path = f"logs/test_{test_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xtml"
        os.makedirs("logs", exist_ok=True)
        
        # 导出读取时需要单独连接
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM test_main WHERE test_id = ?", (test_id,))
        main_info = cursor.fetchone()
        
        cursor.execute("SELECT * FROM test_items_results WHERE test_id = ?", (test_id,))
        items = cursor.fetchall()
        
        conn.close()

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"<TestReport id='{test_id}'>\n")
            if main_info:
                f.write(f"  <BasicInfo>\n")
                f.write(f"    <Channel>{main_info[1]}</Channel>\n")
                f.write(f"    <Recipe>{main_info[5]}</Recipe>\n")
                f.write(f"    <StartTime>{main_info[6]}</StartTime>\n")
                f.write(f"    <EndTime>{main_info[7]}</EndTime>\n")
                f.write(f"    <TotalResult>{main_info[8]}</TotalResult>\n")
                f.write(f"  </BasicInfo>\n")
            
            f.write("  <ItemsResults>\n")
            for item in items:
                f.write(f"    <Item name='{item[2]}'>\n")
                f.write(f"      <Limit>{item[3]} ~ {item[4]}</Limit>\n")
                f.write(f"      <Measured>{item[5]}</Measured>\n")
                f.write(f"      <Result>{item[6]}</Result>\n")
                f.write(f"    </Item>\n")
            f.write("  </ItemsResults>\n")
            f.write("</TestReport>")
            
        print(f"[OK] 测试数据(含判定项)已导出备份: {file_path}")

    # --- 配方 (Recipe) JSON 存储逻辑 ---
    
    def get_recipe_dir(self):
        recipe_dir = os.path.join(os.path.dirname(self.db_path), "recipes")
        os.makedirs(recipe_dir, exist_ok=True)
        return recipe_dir

    def save_recipe_json(self, name: str, data: Dict[str, Any]) -> bool:
        try:
            import json
            file_path = os.path.join(self.get_recipe_dir(), f"{name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except: return False

    def load_recipe_json(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            import json
            file_path = os.path.join(self.get_recipe_dir(), f"{name}.json")
            if not os.path.exists(file_path): return None
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None

    def list_recipes(self) -> List[str]:
        try:
            recipe_dir = self.get_recipe_dir()
            files = [f for f in os.listdir(recipe_dir) if f.endswith(".json")]
            return [os.path.splitext(f)[0] for f in files]
        except: return []

    def delete_recipe(self, name: str) -> bool:
        try:
            file_path = os.path.join(self.get_recipe_dir(), f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except: return False

    # --- 老化箱工步配方 (Chamber Preset) JSON 存储逻辑 (与测试配方隔离) ---
    def get_chamber_preset_dir(self):
        preset_dir = os.path.join(os.path.dirname(self.db_path), "chamber_presets")
        os.makedirs(preset_dir, exist_ok=True)
        return preset_dir

    def save_chamber_preset_json(self, name: str, data: Dict[str, Any]) -> bool:
        try:
            import json
            file_path = os.path.join(self.get_chamber_preset_dir(), f"{name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except: return False

    def load_chamber_preset_json(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            import json
            file_path = os.path.join(self.get_chamber_preset_dir(), f"{name}.json")
            if not os.path.exists(file_path): return None
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None

    def list_chamber_presets(self) -> List[str]:
        try:
            preset_dir = self.get_chamber_preset_dir()
            files = [f for f in os.listdir(preset_dir) if f.endswith(".json")]
            return [os.path.splitext(f)[0] for f in files]
        except: return []

    def delete_chamber_preset(self, name: str) -> bool:
        try:
            file_path = os.path.join(self.get_chamber_preset_dir(), f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except: return False

    # --- 系统与硬件配置存储逻辑 ---
    
    def get_config_dir(self):
        config_dir = os.path.join(os.path.dirname(self.db_path), "config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def save_sys_config(self, data: Dict[str, Any]) -> bool:
        try:
            import json
            file_path = os.path.join(self.get_config_dir(), "sys_config.json")
            existing = {}
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except:
                    pass
            existing.update(data)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=4, ensure_ascii=False)
            return True
        except: return False

    def load_sys_config(self) -> Dict[str, Any]:
        try:
            import json
            file_path = os.path.join(self.get_config_dir(), "sys_config.json")
            if not os.path.exists(file_path): return {}
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}

    def save_channel_config(self, data: List[Dict[str, Any]]) -> bool:
        """保存通道与货架映射、通道板 IP 等配置"""
        try:
            import json
            file_path = os.path.join(self.get_config_dir(), "channel_config.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except: return False

    def load_channel_config(self) -> List[Dict[str, Any]]:
        try:
            import json
            file_path = os.path.join(self.get_config_dir(), "channel_config.json")
            if not os.path.exists(file_path): return []
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
