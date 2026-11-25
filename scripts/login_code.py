"""앱 로그인용 6자리 코드를 메일 없이 바로 받기 (테스트용).

Supabase 메일 템플릿 설정을 안 해도 됨.
1) 앱 로그인 화면에서 학교 메일 입력 -> '인증코드 받기'
2) VS Code 에서 이 파일 열고 ▷ 실행 -> 아래에 6자리 코드가 나옴
3) 앱에 그 코드 입력
메일 주소는 scripts/demo_owner.txt 첫 줄을 씀. 코드는 5분 안에 쓰기.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "match-server"))
os.chdir(os.path.join(ROOT, "match-server"))
try:
    from supabase import create_client
    from app import config
except ImportError:
    sys.exit("❌ VS Code 오른쪽 아래 파이썬을 'match-server (.venv)' 로 골라 주세요")

owner_file = os.path.join(ROOT, "scripts", "demo_owner.txt")
email = (open(owner_file).readline().strip() if os.path.exists(owner_file) else "") or \
        (sys.argv[1] if len(sys.argv) > 1 else "")
if not email:
    sys.exit("❌ scripts/demo_owner.txt 에 로그인할 학교 메일을 적어 주세요")

sb = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
res = sb.auth.admin.generate_link({"type": "magiclink", "email": email})
code = res.properties.email_otp
print(f"\n📧 {email}\n🔑 앱에 입력할 코드:  {code}\n(5분 안에 입력)\n")
