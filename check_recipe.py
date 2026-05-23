import json
with open('recipes/DJ2513_Aging.json', encoding='utf-8') as f:
    data = json.load(f)
for item in data.get('items', []):
    for sub in item.get('sub_steps', []):
        if 'NTC' in sub.get('action', ''):
            print(f"Item: {item.get('name')} | min={item.get('min')} | max={item.get('max')}")
            break
