from pymodbus.client import ModbusTcpClient
from pymodbus.framer import FramerType

def scan():
    c = ModbusTcpClient("192.168.1.201", port=2000, framer=FramerType.SOCKET, timeout=1.0, retries=0)
    if not c.connect():
        print("Failed to connect to port 2000")
        return
    
    print("Scanning Modbus unit IDs 1 to 255 with SOCKET framer...")
    for uid in range(1, 256):
        try:
            res = c.read_input_registers(100, count=1, device_id=uid)
            if not res.isError():
                print(f"Success on unit_id={uid}")
                return
        except Exception as e:
            pass
            
    c.close()
    
    c2 = ModbusTcpClient("192.168.1.201", port=2000, framer=FramerType.RTU, timeout=1.0, retries=0)
    if not c2.connect():
        return
    print("Scanning Modbus unit IDs 1 to 255 with RTU framer...")
    for uid in range(1, 256):
        try:
            res = c2.read_input_registers(100, count=1, device_id=uid)
            if not res.isError():
                print(f"Success on unit_id={uid} (RTU Framer)")
                return
        except Exception:
            pass
            
    print("Scan complete. No response from any unit_id.")

if __name__ == "__main__":
    scan()
