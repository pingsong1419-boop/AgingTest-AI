import json

recipe_path = r"recipes/DJ2513_Aging.json"

def main():
    # Load recipe
    with open(recipe_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data.get("items", [])
    original_len = len(items)
    
    # Filter items
    new_items = []
    removed_names = []
    for item in items:
        name = item.get("name", "")
        if name in ("快充口绝缘阻抗-100KΩ", "快充口绝缘阻抗-500KΩ"):
            removed_names.append(name)
        else:
            new_items.append(item)
            
    data["items"] = new_items
    new_len = len(new_items)
    
    print(f"Original items count: {original_len}")
    print(f"Removed items: {removed_names}")
    print(f"New items count: {new_len}")
    
    # Write back
    with open(recipe_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print("[SUCCESS] Recipe updated successfully.")

if __name__ == "__main__":
    main()
