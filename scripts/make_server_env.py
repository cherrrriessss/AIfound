"""match-server/.env 의 키를 server/.env 로 복사 (MOCK=false). 키 값은 출력하지 않음."""
import os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = {}
for l in open(os.path.join(root, "match-server/.env")):
    if "=" in l and not l.lstrip().startswith("#"):
        k, v = l.strip().split("=", 1)
        src[k.strip()] = v.strip()
keys = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "INTERNAL_KEY"]
out = []
for l in open(os.path.join(root, "server/.env.example")):
    k = l.split("=", 1)[0].strip()
    if k == "MOCK":
        l = "MOCK=false\n"
    elif k in keys and src.get(k):
        l = f"{k}={src[k]}\n"
    out.append(l)
open(os.path.join(root, "server/.env"), "w").writelines(out)
print("server/.env 만들었어요 (MOCK=false, 키", sum(1 for k in keys if src.get(k)), "개 복사)")
