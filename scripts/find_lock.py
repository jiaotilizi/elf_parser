import psutil

target_file = r"C:\rust_install2\rustup-init.exe"

for proc in psutil.process_iter(['name', 'open_files']):
    try:
        for file_info in proc.open_files():
            if target_file.lower() in file_info.path.lower():
                print(f"Process {proc.name()} (PID: {proc.pid}) is locking: {file_info.path}")
                proc.kill()
                print(f"Killed process {proc.name()} (PID: {proc.pid})")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass