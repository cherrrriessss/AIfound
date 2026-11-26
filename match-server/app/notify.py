"""FCM 푸시 알림 전송 (Firebase Admin SDK)."""
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from . import config

_app = None
_warned = False


def available() -> bool:
    """서비스 계정 키 파일이 있어야 푸시를 보낼 수 있다. 없으면 알림함(27)에만 저장."""
    global _warned
    ok = os.path.exists(config.FIREBASE_CREDENTIALS)
    if not ok and not _warned:
        print(f"[notify] {config.FIREBASE_CREDENTIALS} 이 없어 푸시는 건너뜀 (알림함에는 저장됨)")
        _warned = True
    return ok


def _firebase():
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app(credentials.Certificate(config.FIREBASE_CREDENTIALS))
    return _app


def send_match_push(token: str, title: str, body: str, data: dict) -> Optional[bool]:
    """data는 앱이 알림을 눌렀을 때 어떤 화면을 열지 정하는 값(문자열만 가능).
    True 보냄 / False 토큰이 만료됨(지워도 됨) / None 못 보냈지만 토큰은 그대로 둠."""
    if not available():
        return None
    try:
        _firebase()
    except Exception as e:
        print("[notify] Firebase 초기화 실패:", e)
        return None
    msg = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
        android=messaging.AndroidConfig(priority="high"),
    )
    try:
        messaging.send(msg)
        return True
    except messaging.UnregisteredError:
        print("[notify] 만료된 토큰:", token[:12])
        return False
    except Exception as e:
        print("[notify] 전송 실패:", e)
        return None
