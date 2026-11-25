"""FCM 푸시 알림 전송 (Firebase Admin SDK)."""
import firebase_admin
from firebase_admin import credentials, messaging

from . import config

_app = None


def _firebase():
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app(credentials.Certificate(config.FIREBASE_CREDENTIALS))
    return _app


def send_match_push(token: str, title: str, body: str, data: dict) -> bool:
    """data는 앱이 알림을 눌렀을 때 어떤 화면을 열지 정하는 값(문자열만 가능)."""
    _firebase()
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
        return False
