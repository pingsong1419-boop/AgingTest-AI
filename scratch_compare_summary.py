# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

file1 = r"E:\DJ2513_Aging.json"
file2 = r"E:\DJ2513_Aging1.json"

def main():
    try:
        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
            
        items1 = data1.get("items", [])
        items2 = data2.get("items", [])
        
        names1 = [it.get("name", "") for it in items1]
        names2 = [it.get("name", "") for it in items2]
        
        set1 = set(names1)
        set2 = set(names2)
        
        only_in_1 = [n for n in names1 if n not in set2]
        only_in_2 = [n for n in names2 if n not in set1]
        
        map1 = {it.get("name"): it for it in items1}
        map2 = {it.get("name"): it for it in items2}
        
        common_names = [n for n in names1 if n in set2]
        common_diffs = []
        
        for name in common_names:
            it1 = map1[name]
            it2 = map2[name]
            
            diffs = []
            for prop in ("min", "max", "strategy", "standard_type", "retry_count", "unit", "exec_mode", "drop_on_ng"):
                v1 = it1.get(prop)
                v2 = it2.get(prop)
                if v1 != v2:
                    diffs.append(f"属性 [{prop}] 不同: '{v1}' vs '{v2}'")
                    
            subs1 = it1.get("sub_steps", [])
            subs2 = it2.get("sub_steps", [])
            if len(subs1) != len(subs2):
                diffs.append(f"子工步数量不同: {len(subs1)} vs {len(subs2)}")
            else:
                for j in range(len(subs1)):
                    s1 = subs1[j]
                    s2 = subs2[j]
                    if s1.get("params") != s2.get("params"):
                        diffs.append(f"子工步 {j+1} 参数不同: '{s1.get('params')}' vs '{s2.get('params')}'")
                    if s1.get("action") != s2.get("action"):
                        diffs.append(f"子工步 {j+1} 动作不同: '{s1.get('action')}' vs '{s2.get('action')}'")
                        
            if diffs:
                common_diffs.append((name, diffs))
                
        with open("scratch_compare_output.txt", "w", encoding="utf-8") as out:
            out.write("================ 对比概要 ================\n")
            out.write(f"文件1 (DJ2513_Aging.json) 包含 {len(items1)} 个测试项\n")
            out.write(f"文件2 (DJ2513_Aging1.json) 包含 {len(items2)} 个测试项\n\n")
            
            out.write(f"仅在 文件1 中存在的测试项 ({len(only_in_1)} 个):\n")
            for n in only_in_1:
                out.write(f"    - {n}\n")
                
            out.write(f"\n仅在 文件2 中存在的测试项 ({len(only_in_2)} 个):\n")
            for n in only_in_2:
                out.write(f"    - {n}\n")
                
            out.write(f"\n所有有配置差异的测试项 ({len(common_diffs)} 个):\n")
            for name, diffs in common_diffs:
                out.write(f"    -【{name}】:\n")
                for d in diffs:
                    out.write(f"        * {d}\n")
                    
        print(f"[SUCCESS] Comparative details saved to scratch_compare_output.txt. Total common diffs: {len(common_diffs)}")
        
    except Exception as e:
        print(f"[ERROR] failed: {e}")

if __name__ == "__main__":
    main()
