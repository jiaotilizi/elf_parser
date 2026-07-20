import urllib.request
import os

url = "https://mirrors.ustc.edu.cn/rust-static/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe"
output_path = r"D:\rustup-init.exe"

print(f"Downloading from: {url}")
print(f"Saving to: {output_path}")

try:
    urllib.request.urlretrieve(url, output_path)
    file_size = os.path.getsize(output_path)
    print(f"Download complete! Size: {file_size} bytes")
except Exception as e:
    print(f"Error: {e}")