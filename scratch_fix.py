import sys, re
content = open('devices/manager.py', encoding='utf-8').read()

# Remove the first disconnect_all
first_pattern = re.compile(r'    def disconnect_all\(self\):\n.*?print\(\"\[DeviceManager\] 所有硬件设备通讯句柄已安全释放\"\)\n', re.DOTALL)
content = first_pattern.sub('', content, count=1)

# Now replace the remaining disconnect_all
second_pattern = re.compile(r'    def disconnect_all\(self\):\n.*?(?=\n\n|\Z)', re.DOTALL)
new_disconnect_all = '''    def disconnect_all(self):
        """断开所有设备的连接并释放资源 (新增系统安全退出逻辑)"""
        if getattr(self, "chamber", None):
            self.chamber.close()
        if getattr(self, "afe_system", None):
            self.afe_system.close()
            
        for cid, board in self.boards.items():
            try: board.relays.close()
            except: pass
            
        # 释放所有电源设备
        power_devices = [
            getattr(self, "hv_source", None),
            getattr(self, "dut_power", None),
            getattr(self, "ctrl_board_power", None),
            getattr(self, "afe_power_1", None),
            getattr(self, "afe_pwr_2", None),
            getattr(self, "afe_pwr_3", None)
        ]
        for pwr in power_devices:
            if pwr:
                try: pwr.close()
                except: pass

        # 释放其他设备
        if getattr(self, "easy320", None):
            try: self.easy320.close()
            except: pass
        if getattr(self, "ca550", None):
            try: self.ca550.close()
            except: pass
            
        # 释放所有电池模拟器
        for sim in getattr(self, "simulators", []):
            try: sim.close()
            except: pass
            
        print("[DeviceManager] 所有硬件设备通讯句柄已安全释放")'''

content = second_pattern.sub(new_disconnect_all, content)
with open('devices/manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed manager.py')
