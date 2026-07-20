import subprocess
import os

os.environ['RUSTUP_DIST_SERVER'] = 'https://mirrors.ustc.edu.cn/rust-static'
os.environ['RUSTUP_UPDATE_ROOT'] = 'https://mirrors.ustc.edu.cn/rust-static/rustup'

result = subprocess.run(
    [r"C:\Users\tao.yang3\.cargo\bin\rustup.exe", "default", "stable"],
    capture_output=True,
    text=True,
    timeout=300
)

print(f"Return code: {result.returncode}")
print(f"Stdout:\n{result.stdout}")
print(f"Stderr:\n{result.stderr}")