# -*- coding: utf-8 -*-
import json
import os

files = [
    r"c:\Users\95403\Desktop\AgingTest-AI\recipes\DJ2513_Aging.json",
    r"E:\DJ2513_Aging.json"
]

def modify_recipe(file_path):
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return False
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        
        modified_count = 0
        
        # 1. Index 0: 设备初始化 - clear relay 15 close
        if len(items) > 0 and items[0].get("name") == "设备初始化":
            for sub in items[0].get("sub_steps", []):
                if sub.get("device") == "老化功能板继电器 (Aging Board)" and "闭合勾选通道" in sub.get("action", ""):
                    if sub.get("params") == "15":
                        sub["params"] = ""
                        sub["name"] = sub["name"].replace("(15)", "()")
                        print(f"[{file_path}] Mod 1: Cleared relay 15 close in Index 0 (设备初始化)")
                        modified_count += 1
                        
        # 2. Index 77: @高压源控制-100V - set is_block_start to True
        if len(items) > 77 and "@高压源控制-100V" in items[77].get("name", ""):
            if not items[77].get("is_block_start", False):
                items[77]["is_block_start"] = True
                print(f"[{file_path}] Mod 2: Set is_block_start to True in Index 77 (@高压源控制-100V)")
                modified_count += 1
                
        # 3. Index 86: 绝缘采集测试-正极1MΩ - set is_block_start to False
        if len(items) > 86 and "绝缘采集测试-正极1MΩ" in items[86].get("name", ""):
            if items[86].get("is_block_start", False):
                items[86]["is_block_start"] = False
                print(f"[{file_path}] Mod 3: Set is_block_start to False in Index 86 (绝缘采集测试-正极1MΩ)")
                modified_count += 1
                
        # 4. Index 87: 绝缘采集测试-负极30KΩ or 绝缘采集测试-正极30KΩ - set is_block_end to False
        if len(items) > 87 and "绝缘采集测试" in items[87].get("name", ""):
            if items[87].get("is_block_end", False):
                items[87]["is_block_end"] = False
                print(f"[{file_path}] Mod 4: Set is_block_end to False in Index 87 (绝缘采集测试-负极30KΩ)")
                modified_count += 1
                
        # 5. Index 88: @高压源控制-0V - set is_block_end to True and disconnect relay 15
        if len(items) > 88 and "@高压源控制-0V" in items[88].get("name", ""):
            if not items[88].get("is_block_end", False):
                items[88]["is_block_end"] = True
                print(f"[{file_path}] Mod 5: Set is_block_end to True in Index 88 (@高压源控制-0V)")
                modified_count += 1
                
            for sub in items[88].get("sub_steps", []):
                if sub.get("device") == "老化功能板继电器 (Aging Board)" and "断开勾选通道" in sub.get("action", ""):
                    if sub.get("params") == "":
                        sub["params"] = "15"
                        sub["name"] = sub["name"].replace("()", "(15)")
                        print(f"[{file_path}] Mod 6: Set disconnect relay 15 in Index 88 (@高压源控制-0V)")
                        modified_count += 1
                        
        if modified_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[SUCCESS] Saved changes to {file_path}. Total mods: {modified_count}\n")
            return True
        else:
            print(f"[INFO] No changes needed for {file_path}\n")
            return True
            
    except Exception as e:
        print(f"[ERROR] Failed to modify {file_path}: {e}\n")
        return False

def main():
    for f in files:
        modify_recipe(f)

if __name__ == "__main__":
    main()
