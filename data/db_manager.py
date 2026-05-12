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
                timestamp DATETIME,
                FOREIGN KEY (test_id) REFERENCES test_main(test_id)
            )
        ''')
        
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
        """停止后台线程并关闭数据库"""
        self.is_running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join()

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

    def log_item_result(self, test_id: int, name: str, low: float, high: float, val: float, res: str):
        """记录某个测试项目的最终判定结果 (异步不等待)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = '''
            INSERT INTO test_items_results (test_id, item_name, lower_limit, upper_limit, measured_value, result, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        params = (test_id, name, low, high, val, res, now)
        self._execute_async(sql, params, wait=False)

    def finish_test(self, test_id: int, result: str):
        """记录测试结束 (同步等待以确保后续文件导出正确)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = 'UPDATE test_main SET end_time = ?, result = ? WHERE test_id = ?'
        params = (now, result, test_id)
        self._execute_async(sql, params, wait=True)
        
        # 测试结束后生成本地备份文件
        self.export_to_xtml(test_id)

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
            
        print(f"✅ 测试数据(含判定项)已导出备份: {file_path}")

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

    # --- 系统与硬件配置存储逻辑 ---
    
    def get_config_dir(self):
        config_dir = os.path.join(os.path.dirname(self.db_path), "config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def save_sys_config(self, data: Dict[str, Any]) -> bool:
        try:
            import json
            file_path = os.path.join(self.get_config_dir(), "sys_config.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
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
