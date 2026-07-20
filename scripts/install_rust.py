import subprocess
import time
import os

installer_path = r"C:\rust_install2\rustup-init.exe"

print(f"Trying to run: {installer_path}")
print(f"File exists: {os.path.exists(installer_path)}")

try:
    result = subprocess.run([installer_path, "-y"], capture_output=True, text=True, timeout=180)
    print(f"Return code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
except Exception as e:
    print(f"Error: {e}")