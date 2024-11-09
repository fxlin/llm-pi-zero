# test if we can open /dev/mem for reading

try:
    with open("/dev/mem", "rb") as f:
        print("Successfully opened /dev/mem for reading.")
except Exception as e:
    print(f"Failed to open /dev/mem: {e}")

