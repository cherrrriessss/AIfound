"""두 서버(8000, 8001) 끄기. VS Code 에서 열고 ▷ 누르면 됨."""
import subprocess

for port in (8000, 8001):
    pids = subprocess.run(["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                          capture_output=True, text=True).stdout.split()
    for pid in pids:
        subprocess.run(["kill", pid])
    print(f"포트 {port}: " + ("껐어요" if pids else "켜져 있지 않음"))
