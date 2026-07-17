import os
import re
import traceback

paths = [
    r"C:\Users\95403\Desktop\老化记录\CH26_SCUx03HP130030B12607140008_20260715_203231.log",
    r"C:\Users\95403\Desktop\老化记录\CH26_SCUx03HP130030B12607140008_20260715_204440.log",
    r"C:\Users\95403\Desktop\老化记录\test_26_20260715203231.xtml"
]

out_path = r"c:\Users\95403\Desktop\AgingTest-AI\analysis_result.txt"

def analyze_log(p):
    if not os.path.exists(p):
        return f"File Not Exist: {p}"
    
    errors = []
    for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
        try:
            with open(p, 'r', encoding=encoding) as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                # 排除单体电压
                if "单体电压" in line:
                    continue
                upper_line = line.upper()
                keywords = ["FAIL", "NG", "ERROR", "EXCEPTION", "异常", "未通过", "错误", "超时", "TIMEOUT"]
                if any(kw in upper_line or kw in line for kw in keywords):
                    errors.append((i+1, line.strip()))
            return errors
        except UnicodeDecodeError:
            continue
    return f"Failed to decode: {p}"

def analyze_xtml(p):
    if not os.path.exists(p):
        return f"File Not Exist: {p}"
    
    ng_items = []
    for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
        try:
            with open(p, 'r', encoding=encoding) as f:
                content = f.read()
            item_matches = re.findall(r"<Item name='(.*?)'>(.*?)</Item>", content, re.DOTALL)
            for name, inner_xml in item_matches:
                if "单体电压" in name:
                    continue
                res_match = re.search(r"<Result>(.*?)</Result>", inner_xml)
                meas_match = re.search(r"<Measured>(.*?)</Measured>", inner_xml)
                limit_match = re.search(r"<Limit>(.*?)</Limit>", inner_xml)
                
                res = res_match.group(1) if res_match else "None"
                meas = meas_match.group(1) if meas_match else "None"
                limit = limit_match.group(1) if limit_match else "None"
                
                if res.upper() == "NG":
                    ng_items.append({
                        "name": name,
                        "measured": meas,
                        "limit": limit,
                        "result": res
                    })
            return ng_items
        except UnicodeDecodeError:
            continue
    return f"Failed to decode: {p}"

try:
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("RECORD_CH26_故障分析报告\n\n")
        for p in paths:
            out.write(f"========================================\n")
            out.write(f"文件: {os.path.basename(p)}\n")
            out.write(f"========================================\n")
            
            if p.endswith('.xtml'):
                res = analyze_xtml(p)
                if isinstance(res, list):
                    if not res:
                        out.write("  未发现非单体电压的其它故障。\n")
                    else:
                        out.write(f"  发现如下非单体电压故障 ({len(res)}):\n")
                        for item in res:
                            out.write(f"    Item: {item['name']}\n")
                            out.write(f"      Measured: {item['measured']}\n")
                            out.write(f"      Limit: {item['limit']}\n")
                else:
                    out.write(f"  {res}\n")
            else:
                res = analyze_log(p)
                if isinstance(res, list):
                    if not res:
                        out.write("  未发现非单体电压的其它故障。\n")
                    else:
                        # 如果非单体电压的 NG 步骤很多，我们限制打印前 100 行
                        out.write(f"  发现如下非单体电压故障 ({len(res)}):\n")
                        for line_num, content in res[:100]:
                            out.write(f"    [行 {line_num}]: {content}\n")
                        if len(res) > 100:
                            out.write("    * ... 后面还有更多错误行被截断\n")
                else:
                    out.write(f"  {res}\n")
            out.write("\n")
            
except Exception as e:
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"ERROR: {e}\n")
        traceback.print_exc(file=out)
