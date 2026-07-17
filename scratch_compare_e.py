# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

file1 = r"E:\DJ2513_Aging.json"
file2 = r"E:\DJ2513_Aging1.json"

def compare_sub_steps(subs1, subs2):
    diffs = []
    if len(subs1) != len(subs2):
        diffs.append(f"子工步数量不同: {len(subs1)} vs {len(subs2)}")
        
    for j in range(min(len(subs1), len(subs2))):
        s1 = subs1[j]
        s2 = subs2[j]
        
        name1, name2 = s1.get("name", ""), s2.get("name", "")
        if name1 != name2:
            diffs.append(f"子工步 {j+1} 名称不同: '{name1}' vs '{name2}'")
            
        act1, act2 = s1.get("action", ""), s2.get("action", "")
        if act1 != act2:
            diffs.append(f"子工步 {j+1} 动作不同: '{act1}' vs '{act2}'")
            
        param1, param2 = s1.get("params", ""), s2.get("params", "")
        if param1 != param2:
            diffs.append(f"子工步 {j+1} 参数不同: '{param1}' vs '{param2}'")
            
        dev1, dev2 = s1.get("device", ""), s2.get("device", "")
        if dev1 != dev2:
            diffs.append(f"子工步 {j+1} 设备不同: '{dev1}' vs '{dev2}'")
            
        type1, type2 = s1.get("type", ""), s2.get("type", "")
        if type1 != type2:
            diffs.append(f"子工步 {j+1} 类型不同: '{type1}' vs '{type2}'")
            
        judg1, judg2 = s1.get("is_judgment"), s2.get("is_judgment")
        if judg1 != judg2:
            diffs.append(f"子工步 {j+1} 判定属性不同: {judg1} vs {judg2}")
            
    return diffs

def main():
    try:
        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
            
        items1 = data1.get("items", [])
        items2 = data2.get("items", [])
        
        print(f"[*] 文件1 (DJ2513_Aging.json) 测试项总数: {len(items1)}")
        print(f"[*] 文件2 (DJ2513_Aging1.json) 测试项总数: {len(items2)}")
        
        # Compare by item name
        # We can construct maps or list compare
        diff_count = 0
        
        max_len = max(len(items1), len(items2))
        
        for i in range(max_len):
            if i >= len(items1):
                print(f"[+] 新增项在文件2 Index {i}:【{items2[i].get('name')}】")
                diff_count += 1
                continue
            if i >= len(items2):
                print(f"[-] 缺失项在文件2 Index {i}:【{items1[i].get('name')}】")
                diff_count += 1
                continue
                
            it1 = items1[i]
            it2 = items2[i]
            
            name1 = it1.get("name", "")
            name2 = it2.get("name", "")
            
            item_diffs = []
            if name1 != name2:
                item_diffs.append(f"测试项名称不同: '{name1}' vs '{name2}'")
            
            # Check properties
            for prop in ("min", "max", "strategy", "standard_type", "retry_count", "unit", "exec_mode", "drop_on_ng"):
                val1 = it1.get(prop)
                val2 = it2.get(prop)
                if val1 != val2:
                    item_diffs.append(f"属性 [{prop}] 不同: '{val1}' vs '{val2}'")
                    
            # Check sub-steps
            subs1 = it1.get("sub_steps", [])
            subs2 = it2.get("sub_steps", [])
            sub_diffs = compare_sub_steps(subs1, subs2)
            item_diffs.extend(sub_diffs)
            
            if item_diffs:
                diff_count += 1
                print(f"\n[!] 差异在 Index {i} | 文件1:【{name1}】 | 文件2:【{name2}】:")
                for d in item_diffs:
                    print(f"    - {d}")
                    
        print(f"\n[*] 对比结束。不同项总数: {diff_count}")
        
    except Exception as e:
        print(f"[ERROR] 对比失败: {e}")

if __name__ == "__main__":
    main()
