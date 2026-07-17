import json

file_path = r"c:\Users\95403\Desktop\AgingTest-AI\recipes\DJ2513_Aging.json"

def restore_recipe():
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        modified = False
        for item in data.get("items", []):
            if item.get("name") == "CA550输出-2.5V":
                print("Restoring CA550输出-2.5V to range evaluation...")
                item["mode"] = "范围判定"
                item["min"] = "2.49"
                item["max"] = "2.51"
                item["standard_type"] = "数值"
                modified = True
                
        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("Recipe restored successfully!")
        else:
            print("Target step not found in recipe.")
            
    except Exception as e:
        print(f"Error during restoration: {e}")

if __name__ == "__main__":
    restore_recipe()
