import os
import glob
import re

log_dir = r"C:\Users\95403\Desktop\老化记录\新建文件夹 (2)\test_logs"
out_path = r"c:\Users\95403\Desktop\AgingTest-AI\relay_exceptions.txt"

def check_relays():
    try:
        files = glob.glob(os.path.join(log_dir, "*.log"))
        
        total_logs = len(files)
        exceptions = []
        
        for p in files:
            basename = os.path.basename(p)
            for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
                try:
                    with open(p, 'r', encoding=encoding) as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines):
                        # 匹配含有 1,11,15 的通道闭合动作
                        if "1,11,15" in line and ("闭合" in line or "Aging Board" in line or "继电器" in line):
                            # 检查接下来 5 行是否有任何报错、异常、重试字样
                            check_range = lines[i:i+6]
                            is_err = False
                            err_lines = []
                            for sub_line in check_range:
                                sub_upper = sub_line.upper()
                                if "异常" in sub_line or "FAIL" in sub_upper or "警告" in sub_line or "失败" in sub_line or "WARNING" in sub_upper or "ERR" in sub_upper:
                                    is_err = True
                                    err_lines.append(sub_line.strip())
                            if is_err:
                                exceptions.append({
                                    "file": basename,
                                    "line_num": i+1,
                                    "context": [l.strip() for l in check_range],
                                    "reasons": err_lines
                                })
                    break
                except UnicodeDecodeError:
                    continue

        with open(out_path, "w", encoding="utf-8") as out:
            out.write("==================================================\n")
            out.write("     1,11,15 继电器闭合动作异常扫描报告           \n")
            out.write("==================================================\n\n")
            
            out.write(f"扫描日志总数: {total_logs}\n")
            out.write(f"发现异常次数: {len(exceptions)}\n\n")
            
            if exceptions:
                for idx, exc in enumerate(exceptions):
                    out.write(f"[{idx+1}] 文件: {exc['file']} (第 {exc['line_num']} 行附近)\n")
                    out.write("    上下文行:\n")
                    for l in exc['context']:
                        out.write(f"      {l}\n")
                    out.write(f"    检测到的错误标志:\n")
                    for r in exc['reasons']:
                        out.write(f"      -> {r}\n")
                    out.write("\n")
            else:
                out.write("未在所有日志中发现关于闭合通道 (1,11,15) 继电器的任何控制异常或回读报警。\n")
                
        print("Analysis finished successfully!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_relays()
