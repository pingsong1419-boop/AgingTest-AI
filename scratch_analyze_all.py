import os
import re
import glob
from collections import Counter

log_dir = r"C:\Users\95403\Desktop\老化记录\新建文件夹 (2)\test_logs"
xtml_dir = r"C:\Users\95403\Desktop\老化记录\新建文件夹 (2)\logs"
out_path = r"c:\Users\95403\Desktop\AgingTest-AI\analysis_result_new.txt"

def clean_error_line(line):
    # 去除时间戳，例如 [20:32:13.492]
    line = re.sub(r"\[\d{2}:\d{2}:\d{2}\.\d{3}\]\s*", "", line)
    # 去除通道号和判定次数，例如 (当前为 1 次复测，上限 3 次)...
    line = re.sub(r"\(当前为\s*\d+\s*次复测.*", "", line)
    # 去除行首的 -> 或空白
    line = line.strip(" -#>")
    return line

def analyze_all():
    total_logs = 0
    total_xtmls = 0
    log_errors = []
    xtml_ng_items = []
    
    ch_failures = Counter()
    error_types = Counter()
    ng_test_items = Counter()
    
    # 细化“其他错误”的具体发生内容统计
    other_error_details = Counter()

    # 1. 分析 log 文件
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    total_logs = len(log_files)
    for p in log_files:
        basename = os.path.basename(p)
        ch_match = re.match(r"(CH\d+)_", basename)
        ch = ch_match.group(1) if ch_match else "Unknown"
        
        errors_in_file = []
        for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
            try:
                with open(p, 'r', encoding=encoding) as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    if "单体电压" in line:
                        continue
                    upper_line = line.upper()
                    upper_line_clean = upper_line.replace("AGING", "_____").replace("NGI", "___").replace("WARNING", "_______")
                    
                    if "FAIL" in upper_line_clean or "NG" in upper_line_clean or "TIMEOUT" in upper_line_clean or "超时" in line or "异常" in line:
                        cleaned_line = line.strip()
                        errors_in_file.append((i+1, cleaned_line))
                        
                        # 统计分类
                        if "响应超时" in line or "TIMEOUT" in upper_line or "超时" in line:
                            error_types["超时/响应超时"] += 1
                        elif "连接" in line or "握手" in line or "connect" in upper_line:
                            error_types["连接/握手失败"] += 1
                        elif "校验失败" in line or "校验" in line:
                            error_types["校验失败"] += 1
                        else:
                            error_types["其他错误"] += 1
                            # 提取核心错误文本以进行频率统计
                            msg = clean_error_line(cleaned_line)
                            other_error_details[msg] += 1
                break
            except UnicodeDecodeError:
                continue
                
        if errors_in_file:
            ch_failures[ch] += 1
            log_errors.append({
                "file": basename,
                "ch": ch,
                "count": len(errors_in_file),
                "samples": errors_in_file[:10]
            })

    # 2. 分析 xtml 文件
    xtml_files = glob.glob(os.path.join(xtml_dir, "*.xtml"))
    total_xtmls = len(xtml_files)
    for p in xtml_files:
        basename = os.path.basename(p)
        ng_in_file = []
        for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
            try:
                with open(p, 'r', encoding=encoding) as f:
                    content = f.read()
                item_matches = re.findall(r"<Item name='(.*?)'>(.*?)</Item>", content, re.DOTALL)
                for name, inner_xml in item_matches:
                    if "单体电压" in name:
                        continue
                    res_match = re.search(r"<Result>(.*?)</Result>", inner_xml)
                    if res_match and res_match.group(1).upper() == "NG":
                        meas_match = re.search(r"<Measured>(.*?)</Measured>", inner_xml)
                        limit_match = re.search(r"<Limit>(.*?)</Limit>", inner_xml)
                        meas = meas_match.group(1) if meas_match else "None"
                        limit = limit_match.group(1) if limit_match else "None"
                        
                        ng_in_file.append({
                            "name": name,
                            "measured": meas,
                            "limit": limit
                        })
                        ng_test_items[name] += 1
                break
            except UnicodeDecodeError:
                continue
        if ng_in_file:
            xtml_ng_items.append({
                "file": basename,
                "ng_list": ng_in_file
            })

    # 3. 输出报告
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("==================================================\n")
        out.write("             测试记录全面分析报告                 \n")
        out.write("==================================================\n\n")
        
        out.write(f"分析日志文件总数: {total_logs}\n")
        out.write(f"分析XTML文件总数: {total_xtmls}\n\n")
        
        out.write("1. 通道故障频次统计 (按 log 文件中非单体电压错误的发生次数):\n")
        for ch, cnt in ch_failures.most_common():
            out.write(f"   通道 {ch}: 发生故障日志数 {cnt} 个\n")
        out.write("\n")
        
        out.write("2. 故障原因特征分类统计 (基于 log 错误行关键词匹配):\n")
        for err_t, cnt in error_types.most_common():
            out.write(f"   {err_t}: 匹配到 {cnt} 次\n")
        out.write("\n")
        
        out.write("2.1. '其他错误' 细分内容频次统计 (排重并合并):\n")
        for detail, cnt in other_error_details.most_common(30):
            out.write(f"   频次: {cnt} | {detail}\n")
        out.write("\n")
        
        out.write("3. XTML中非单体电压测试项NG统计 (按出现NG的测试项名称频次):\n")
        for name, cnt in ng_test_items.most_common():
            out.write(f"   测试项 【{name}】: 出现 NG 共 {cnt} 次\n")
        out.write("\n")
        
        out.write("4. 故障样本详细分析 (每个有故障的通道抽取一个代表性文件展示):\n")
        ch_samples = {}
        for err_info in log_errors:
            ch = err_info["ch"]
            if ch not in ch_samples:
                ch_samples[ch] = err_info
                
        for ch, err_info in sorted(ch_samples.items(), key=lambda x: int(re.search(r"\d+", x[0]).group()) if re.search(r"\d+", x[0]) else 0):
            out.write(f"\n--- 通道 {ch} 样本文件: {err_info['file']} (共发现 {err_info['count']} 行错误) ---\n")
            for line_num, content in err_info["samples"]:
                out.write(f"    [行 {line_num}]: {content}\n")
                
        out.write("\n5. XTML 故障详情样本 (抽取前20个NG测试项记录):\n")
        for item in xtml_ng_items[:20]:
            out.write(f"   文件: {item['file']}\n")
            for ng in item["ng_list"]:
                out.write(f"     NG测试项: {ng['name']} | 测量值: {ng['measured']} | 判定范围: {ng['limit']}\n")

if __name__ == "__main__":
    analyze_all()
    print("Analysis finished successfully!")
