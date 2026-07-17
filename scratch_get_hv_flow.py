import json

file_path = r"c:\Users\95403\Desktop\AgingTest-AI\recipes\DJ2513_Aging.json"
out_path = r"c:\Users\95403\Desktop\AgingTest-AI\hv_flow_utf8.txt"

def get_hv_flow():
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        started = False
        
        with open(out_path, "w", encoding="utf-8") as out:
            for item in items:
                name = item.get("name", "")
                if name == "@高压源控制-100V":
                    started = True
                    
                if started:
                    out.write(f"=== 测试项: {name} (模式: {item.get('mode')}, 范围: {item.get('min')}~{item.get('max')} {item.get('unit')}) ===\n")
                    for i, sub in enumerate(item.get("sub_steps", [])):
                        out.write(f"  步骤 {i+1}: {sub.get('device')} -> {sub.get('action')} | 参数: {sub.get('params')} | [同步: {sub.get('sync_exec')}]\n")
                    out.write("\n")
                    
                if name == "@高压源控制-0V":
                    break
            print("Write done!")
    except Exception as e:
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(f"Error: {e}\n")

if __name__ == "__main__":
    get_hv_flow()
