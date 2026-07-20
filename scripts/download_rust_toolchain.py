import urllib.request
import os
import zipfile

url = "https://mirrors.ustc.edu.cn/rust-static/dist/2026-07-10/rust-1.83.0-x86_64-pc-windows-msvc.zip"
output_path = r"D:\rust_toolchain.zip"

print(f"Downloading from: {url}")
print(f"Saving to: {output_path}")

try:
    urllib.request.urlretrieve(url, output_path)
    file_size = os.path.getsize(output_path)
    print(f"Download complete! Size: {file_size} bytes")
    
    extract_dir = r"C:\Users\tao.yang3\.rustup\toolchains\stable-x86_64-pc-windows-msvc"
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(output_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")
        
except Exception as e:
    print(f"Error: {e}")