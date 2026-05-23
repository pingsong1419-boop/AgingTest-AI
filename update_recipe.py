import json

file_path = 'recipes/DJ2513_Aging.json'
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

changed = False

for item in data.get('items', []):
    is_ntc_item = False
    
    # check sub_steps
    for sub in item.get('sub_steps', []):
        if sub.get('action') == '0x10 NTC读取':
            is_ntc_item = True
            params = sub.get('params', '')
            if 'DIFF_AMBIENT:1' in params:
                sub['params'] = params.replace('DIFF_AMBIENT:1', 'DIFF_AMBIENT:0')
                changed = True
            
            # Update name as well
            name = sub.get('name', '')
            if 'DIFF_AMBIENT:1' in name:
                sub['name'] = name.replace('DIFF_AMBIENT:1', 'DIFF_AMBIENT:0')
                changed = True

    if is_ntc_item:
        if item.get('min') == '-2':
            item['min'] = '-45'
            changed = True
        if item.get('max') == '8':
            item['max'] = '90'
            changed = True

if changed:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("Recipe updated.")
else:
    print("No changes needed or found.")
