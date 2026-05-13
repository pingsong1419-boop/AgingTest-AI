import sys
import traceback

try:
    import main
    main.main()
except Exception as e:
    print("Caught an exception during app execution:")
    traceback.print_exc()
    sys.exit(1)
