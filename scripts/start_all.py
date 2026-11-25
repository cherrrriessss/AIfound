"""VS Code 에서 이 파일을 열고 오른쪽 위 ▷(Run Python File) 한 번만 누르면:
  1) 두 서버 설치 (처음 한 번)
  2) 매칭 서버(8000) + 김준희 서버(8001) 켜기 (이미 켜져 있으면 그대로)
  3) 더미 데이터 넣기 (scripts/demo_owner.txt 에 메일이 있으면)
  4) Android Studio 로 앱 열기
서버는 이 창을 닫아도 계속 켜져 있음. 로그는 logs/ 폴더. 끄기: scripts/stop_all.py 실행.
표준 라이브러리만 써서 어떤 파이썬으로 실행해도 됨.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
os.makedirs(LOGS, exist_ok=True)


def sh(cmd):
    print(f"\n$ {cmd}")
    return subprocess.call(["bash", "-lc", f'cd "{ROOT}" && {cmd}'])


def health(port):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


def start(name, port):
    if health(port):
        print(f"✅ {name} 이미 켜져 있음 (포트 {port})")
        return
    log = open(os.path.join(LOGS, f"{name}.log"), "a")
    subprocess.Popen(["bash", "scripts/run.sh", "match" if port == 8000 else "server"], cwd=ROOT,
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        time.sleep(1)
        if health(port):
            print(f"✅ {name} 켜짐 (포트 {port})")
            return
    print(f"❌ {name} 가 안 켜졌어요. logs/{name}.log 마지막 부분:")
    print("".join(open(os.path.join(LOGS, f"{name}.log")).readlines()[-15:]))
    sys.exit(1)


print("=== 1) 설치 ===")
if sh("bash scripts/setup.sh") != 0:
    sys.exit("❌ 설치 실패: 위 오류를 확인하세요")

print("\n=== 2) 서버 켜기 ===")
start("match-server", 8000)
start("server", 8001)
m, s = health(8000), health(8001)
print("   매칭 서버:", {k: m.get(k) for k in ("supabase", "gemini")})
print("   김준희 서버:", {k: s.get(k) for k in ("mock", "ok") if k in s} or s)

print("\n=== 3) 더미 데이터 ===")
owner_file = os.path.join(ROOT, "scripts", "demo_owner.txt")
if os.path.exists(owner_file) and open(owner_file).read().strip():
    sh("bash scripts/seed.sh")
else:
    print("(건너뜀) scripts/demo_owner.txt 에 로그인할 학교 메일을 적으면 다음 실행 때 넣어요")

print("\n=== 4) Android Studio 열기 ===")
sh("open -a 'Android Studio' android || echo '❌ Android Studio 가 설치돼 있지 않아요'")
print("\n✅ 끝. Android Studio 에서 ▶(Run) 을 누르면 에뮬레이터에 앱이 떠요.")
