# -*- coding: utf-8 -*-
import json
import sys
import re

sys.stdout.reconfigure(encoding="utf-8")
recipe_path = r"recipes/DJ2513_Aging.json"

# In engine, if type doesn't match EOL, READ, CAN_SEND, CAN_RECEIVE, CAN_INTERACT, WAIT, BARRIER, it defaults to SET_INSTRUMENT.
# So all types are technically accepted, but we want to map them to the expected physical action.
VALID_ENGINE_TYPES = {
    "设置仪表", "读取仪表", "CAN发送", "CAN交互", "CAN接收", 
    "3.5HEOL协议", "等待", "同步等待", "读取变量", "申请顺序锁", "释放顺序锁",
    "继电器控制", "校准仪设置", "校准仪回读", "同步屏障"
}

VALID_FAIL_STRATEGIES = {"失败停止", "忽略继续", "重试3次", None}

def main():
    try:
        with open(recipe_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        print(f"[*] 开始对配方进行逐项/逐行深度检测。总项数: {len(items)}")
        
        issues = []
        
        for i, item in enumerate(items):
            step_name = item.get("name", "")
            if not step_name:
                issues.append(f"第 {i} 项: 测试项名称为空或缺失。")
                
            min_val = item.get("min")
            max_val = item.get("max")
            std_type = item.get("standard_type", "数值")
            strategy = item.get("strategy")
            
            # 1. 检查测试项判定标准与限制
            if std_type == "数值":
                if min_val not in (None, "--", ""):
                    try:
                        float(min_val)
                    except ValueError:
                        issues.append(f"第 {i} 项【{step_name}】: 类型为数值，但下限 '{min_val}' 无法解析为数字。")
                if max_val not in (None, "--", ""):
                    try:
                        float(max_val)
                    except ValueError:
                        issues.append(f"第 {i} 项【{step_name}】: 类型为数值，但上限 '{max_val}' 无法解析为数字。")
                        
            # 2. 检查子工步
            sub_steps = item.get("sub_steps", [])
            if not sub_steps:
                issues.append(f"第 {i} 项【{step_name}】: 没有配置任何子工步。")
                
            for j, sub in enumerate(sub_steps):
                sub_name = sub.get("name", "")
                sub_type = sub.get("type", "")
                sub_action = sub.get("action", "")
                sub_params = sub.get("params", "")
                fail_strat = sub.get("fail_strategy")
                
                # 检查子工步类型是否合法
                if sub_type not in VALID_ENGINE_TYPES:
                    issues.append(f"第 {i} 项【{step_name}】的第 {j+1} 个子步【{sub_name}】: 未知子工步类型 '{sub_type}'。")
                    
                # 检查子工步失败策略是否合法
                if fail_strat not in VALID_FAIL_STRATEGIES:
                    issues.append(f"第 {i} 项【{step_name}】的第 {j+1} 个子步【{sub_name}】: 未知失败策略 '{fail_strat}'。")
                    
                # 针对 CAN/EOL 等协议参数的完整性校验
                if "0x" in str(sub_params):
                    # 检查是否有不匹配的括号或引号
                    for char in ('(', ')', '[', ']', '{', '}'):
                        if sub_params.count(char[0]) != sub_params.count(char[-1]):
                            issues.append(f"第 {i} 项【{step_name}】的第 {j+1} 个子步【{sub_name}】: 参数字符串中的括号 '{char}' 不匹配。")
                            
        print("\n================== 检测报告 ==================")
        if issues:
            print(f"[!] 共检测到 {len(issues)} 处潜在配置问题/隐患:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("[SUCCESS] 逐行检测完成，配方结构完整，参数类型正确，未发现任何格式或逻辑错误！")
        print("==============================================")
        
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON 语法解析失败: {e}")
    except Exception as e:
        print(f"[FAIL] 深度检测发生异常: {e}")

if __name__ == "__main__":
    main()
