# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

file_path = r"E:\DJ2513_Aging.json"

def main():
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        print(f"================ E:\\DJ2513_Aging.json 高压与绝缘相关序列 ================")
        
        # We find all items from Index 75 to Index 95 to show the context around the high voltage segment
        for i in range(max(0, len(items))):
            item = items[i]
            name = item.get("name", "")
            
            # If the item is related to high voltage or insulation
            if any(x in name for x in ["高压", "绝缘", "HV"]):
                print(f"\nIndex {i}: 【{name}】")
                print(f"  - 执行模式: {item.get('exec_mode')}")
                print(f"  - 块锁起点: {item.get('is_block_start')}")
                print(f"  - 块锁终点: {item.get('is_block_end')}")
                print(f"  - 子工步数量: {len(item.get('sub_steps', []))}")
                for j, sub in enumerate(item.get('sub_steps', [])):
                    print(f"    * 子步 {j+1}: {sub.get('name')} | 设备: {sub.get('device')} | 动作: {sub.get('action')} | 参数: '{sub.get('params')}'")
                    
        print("\n=========================================================================")
    except Exception as e:
        print(f"[ERROR] 读取失败: {e}")

if __name__ == "__main__":
    main()
