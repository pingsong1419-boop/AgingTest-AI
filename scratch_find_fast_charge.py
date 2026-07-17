import json
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

recipe_path = r"recipes/DJ2513_Aging.json"

def main():
    with open(recipe_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for i, item in enumerate(data.get("items", [])):
        name = item.get("name", "")
        if "快充" in name or "阻抗" in name:
            print(f"Index {i:3d} | Name: {name}")

if __name__ == "__main__":
    main()
