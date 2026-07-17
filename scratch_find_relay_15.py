import json
import sys
import re

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

recipe_path = r"recipes/DJ2513_Aging.json"

def main():
    with open(recipe_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data.get("items", [])
    print(f"[*] 开始搜索 15 号继电器的所有动作...\n")
    
    found_count = 0
    for i, item in enumerate(items):
        step_name = item.get("name", "")
        sub_steps = item.get("sub_steps", [])
        
        for j, sub in enumerate(sub_steps):
            device = sub.get("device", "")
            action = sub.get("action", "")
            params = str(sub.get("params", ""))
            
            # Check if it is aging board relay control
            if "Aging Board" in device or "继电器" in device:
                # Parse channels out of params
                # params is usually a string of numbers like "1,11,15" or "15"
                channels = [c.strip() for c in params.replace("，", ",").split(",") if c.strip()]
                if "15" in channels:
                    found_count += 1
                    print(f"[{found_count:02d}] 关联测试项: Index {i:3d} |【{step_name}】")
                    print(f"     子步 {j+1}: {sub.get('name')}")
                    print(f"     设备: {device} | 动作: {action} | 参数: {params}\n")

    print(f"[*] 共发现 {found_count} 处涉及 15 号继电器的动作控制。")

if __name__ == "__main__":
    main()
