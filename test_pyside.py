import sys
from PySide6.QtWidgets import QApplication, QLabel
try:
    app = QApplication(sys.argv)
    label = QLabel("Hello World")
    label.show()
    print("Window shown successfully")
    # Don't run app.exec() to exit immediately after success in this test
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
