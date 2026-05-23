import codecs
import re
import os

path = 'd:/精华老化FCT/AgingTest-AI/ui/tabs/overview_tab.py'
with open(path, 'rb') as f:
    data = f.read().decode('utf-8', errors='replace')

pattern = r'# 顶部：.*?top_layout\.addWidget\(self\.chk_select\)'
replacement = '''# 顶部：复选框和标题
        top_layout = QHBoxLayout()
        
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        checkmark_path = os.path.join(current_dir, "checkmark.png").replace("\\\\", "/")

        self.chk_select = QCheckBox()
        self.chk_select.setFixedSize(25, 25)
        self.chk_select.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #00E5FF;
                border-radius: 3px;
                background-color: #1A1A2E;
            }}
            QCheckBox::indicator:checked {{
                background-color: #1A1A2E;
                border: 2px solid #00FF00;
                image: url({checkmark_path});
            }}
        """)
        top_layout.addWidget(self.chk_select)'''

new_data = re.sub(pattern, replacement, data, flags=re.DOTALL)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_data)

print('Fixed file.')
