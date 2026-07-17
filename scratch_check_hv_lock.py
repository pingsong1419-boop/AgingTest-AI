import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

def main():
    content = open("core/engine.py", "r", encoding="utf-8").readlines()
    for i, line in enumerate(content):
        if "hv_source" in line or "lock" in line.lower() or "resource" in line.lower():
            print(f"Line {i+1:4d}: {line.strip()}")

if __name__ == "__main__":
    main()
