# -*- coding: utf-8 -*-
import json
import os

files = [
    r"c:\Users\95403\Desktop\AgingTest-AI\recipes\DJ2513_Aging.json",
    r"E:\DJ2513_Aging.json"
]

def remove_sync_exec_in_block(file_path):
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return False
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        
        modified_count = 0
        
        # Modify steps from Index 77 to Index 88
        for idx in range(77, min(89, len(items))):
            item = items[idx]
            for sub in item.get("sub_steps", []):
                if sub.get("sync_exec", False):
                    sub["sync_exec"] = False
                    # Remove [同步] suffix from sub-step name if present
                    if " [同步]" in sub.get("name", ""):
                        sub["name"] = sub["name"].replace(" [同步]", "")
                    elif "[同步]" in sub.get("name", ""):
                        sub["name"] = sub["name"].replace("[同步]", "")
                    print(f"[{file_path}] Mod: Set sync_exec=False for Index {idx} ({item.get('name')}) sub-step: {sub.get('name')}")
                    modified_count += 1
                    
        if modified_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[SUCCESS] Saved changes to {file_path}. Total mods: {modified_count}\n")
            return True
        else:
            print(f"[INFO] No sync_exec changes needed for {file_path}\n")
            return True
            
    except Exception as e:
        print(f"[ERROR] Failed to modify {file_path}: {e}\n")
        return False

def main():
    for f in files:
        remove_sync_exec_in_block(f)

if __name__ == "__main__":
    main()
