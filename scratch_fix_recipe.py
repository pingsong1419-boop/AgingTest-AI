import json

file_path = r"c:\Users\95403\Desktop\AgingTest-AI\recipes\DJ2513_Aging.json"

def fix_recipe():
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        modified = False
        for item in data.get("items", []):
            if item.get("name") == "CA550输出-2.5V":
                print("Found target step CA550输出-2.5V. Modifying...")
                item["mode"] = "字符串比较"
                item["min"] = "--"
                item["max"] = "--"
                item["standard_type"] = "不判断"
                modified = True
                
        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("Recipe fixed successfully!")
        else:
            print("Target step not found in recipe.")
            
    except Exception as e:
        print(f"Error during modification: {e}")

if __name__ == "__main__":
    fix_recipe()
