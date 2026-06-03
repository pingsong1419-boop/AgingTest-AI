import re

with open('ui/tabs/chamber_tab.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Math change
text = text.replace('hours_per_tick = (1.0 * effective_speed) / 3600.0', 'mins_per_tick = (1.0 * effective_speed) / 60.0')
text = text.replace('self.step_elapsed_sec += hours_per_tick', 'self.step_elapsed_sec += mins_per_tick')

# 2. Text changes
text = text.replace('工步耗时: -- / -- 小时', '工步耗时: -- / -- 分钟')
text = text.replace('小时 (测试)', '分钟 (测试)')
text = text.replace('小时 (超时界限)', '分钟 (超时界限)')
text = text.replace('小时 (即时)', '分钟 (即时)')

# 3. Formatting changes for h:m:s
old_math = '''                        rem = max(0, self.steps_data[row]["hours"] - self.step_elapsed_sec)
                        h = int(rem)
                        m = int((rem - h) * 60)
                        s = int(((rem - h) * 60 - m) * 60)'''
new_math = '''                        rem = max(0, self.steps_data[row]["hours"] - self.step_elapsed_sec)
                        total_m = int(rem)
                        s = int((rem - total_m) * 60)
                        h = total_m // 60
                        m = total_m % 60'''
text = text.replace(old_math, new_math)

old_math_timeout = '''                        rem = max(0, self.steps_data[row]["timeout"] - self.step_elapsed_sec)
                        h = int(rem)
                        m = int((rem - h) * 60)
                        s = int(((rem - h) * 60 - m) * 60)'''
new_math_timeout = '''                        rem = max(0, self.steps_data[row]["timeout"] - self.step_elapsed_sec)
                        total_m = int(rem)
                        s = int((rem - total_m) * 60)
                        h = total_m // 60
                        m = total_m % 60'''
text = text.replace(old_math_timeout, new_math_timeout)

old_math_testval = '''                    rem = max(0, test_val - self.step_elapsed_sec)
                    h = int(rem)
                    m = int((rem - h) * 60)
                    s = int(((rem - h) * 60 - m) * 60)'''
new_math_testval = '''                    rem = max(0, test_val - self.step_elapsed_sec)
                    total_m = int(rem)
                    s = int((rem - total_m) * 60)
                    h = total_m // 60
                    m = total_m % 60'''
text = text.replace(old_math_testval, new_math_testval)

old_math_timeoutval = '''                    rem = max(0, timeout_val - self.step_elapsed_sec)
                    h = int(rem)
                    m = int((rem - h) * 60)
                    s = int(((rem - h) * 60 - m) * 60)'''
new_math_timeoutval = '''                    rem = max(0, timeout_val - self.step_elapsed_sec)
                    total_m = int(rem)
                    s = int((rem - total_m) * 60)
                    h = total_m // 60
                    m = total_m % 60'''
text = text.replace(old_math_timeoutval, new_math_timeoutval)

# Replace 'h' with 'min' in table format strings
text = text.replace('}h (剩', '}min (剩')
text = text.replace('}h (已完成)', '}min (已完成)')
text = text.replace('}h (超时)', '}min (超时)')

# Wait, there are some standalone 'h' appends, like item.setText(f"{val:.3f}") if not running. But they don't have 'h' appended.
# Actually, wait, the text parsing on cell changed:
text = text.replace('.split("h")', '.split("min")')
text = text.replace('if "h" in', 'if "min" in')

with open('ui/tabs/chamber_tab.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done replacements")
