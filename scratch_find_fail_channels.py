import os
import glob
import re

xtml_dir = r"C:\Users\95403\Desktop\老化记录\新建文件夹 (2)\logs"
out_path = r"c:\Users\95403\Desktop\AgingTest-AI\fail_channels.txt"

def find_100_percent_fails():
    try:
        files = glob.glob(os.path.join(xtml_dir, "*.xtml"))
        
        channel_total = {}
        channel_ng = {}
        
        for p in files:
            for encoding in ['utf-8', 'gbk', 'utf-16le', 'utf-16']:
                try:
                    with open(p, 'r', encoding=encoding) as f:
                        content = f.read()
                    
                    ch_match = re.search(r"<Channel>(.*?)</Channel>", content)
                    if not ch_match:
                        break
                    ch = ch_match.group(1)
                    
                    res_match = re.search(r"<TotalResult>(.*?)</TotalResult>", content)
                    total_res = res_match.group(1).upper() if res_match else "NONE"
                    
                    channel_total[ch] = channel_total.get(ch, 0) + 1
                    if total_res != "PASS":
                        channel_ng[ch] = channel_ng.get(ch, 0) + 1
                    break
                except UnicodeDecodeError:
                    continue

        with open(out_path, "w", encoding="utf-8") as out:
            out.write("==================================================\n")
            out.write("          老化测试最终结果 (TotalResult) 统计报告  \n")
            out.write("==================================================\n\n")
            
            out.write("【各通道最终测试结果NG率统计】（按通道号排序）:\n")
            sorted_channels = sorted(channel_total.keys(), key=lambda x: int(x) if x.isdigit() else 999)
            for ch in sorted_channels:
                total = channel_total[ch]
                ng = channel_ng.get(ch, 0)
                rate = (ng / total) * 100
                out.write(f"  通道 {ch} 号: 总测试 {total} 次 | 最终判定 NG {ng} 次 | 最终NG率 {rate:.1f}%\n")
                
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_100_percent_fails()
