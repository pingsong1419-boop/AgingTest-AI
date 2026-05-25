import json

raw = json.load(open('recipes/DJ2513_Aging.json', encoding='utf-8'))
data = raw['items']

print("="*60)
print("DJ2513_Aging 测试序列 - 同步分析报告")
print("="*60)

# 打印前3个关键测试项的详细子工步
for idx in [0, 1]:
    item = data[idx]
    name = item.get('name', '')
    exec_mode = item.get('exec_mode', 'par')
    subs = item.get('sub_steps', [])
    print(f"\n[测试项 {idx}] {name} | exec_mode={exec_mode}")
    for j, s in enumerate(subs):
        t = s.get('type', '')
        dev = s.get('device', '')
        act = s.get('action', '')
        se = s.get('sync_exec', False)
        print(f"  sub[{j}] sync={se} | type={t} | device={dev} | action={act}")

print("\n\n" + "="*60)
print("所有含 sync_exec=True 的测试项:")
print("="*60)
for i, item in enumerate(data):
    name = item.get('name', '')
    exec_mode = item.get('exec_mode', 'par')
    subs = item.get('sub_steps', [])
    sync_subs = [s for s in subs if s.get('sync_exec', False)]
    if sync_subs or exec_mode not in ('par', '并行执行'):
        print(f"\n[{i}] {name} | exec_mode={exec_mode}")
        for s in sync_subs:
            print(f"  -> type={s.get('type','')} device={s.get('device','')} action={s.get('action','')}")
