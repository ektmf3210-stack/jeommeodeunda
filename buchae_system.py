# -*- coding: utf-8 -*-
"""
🪭 부채(재화) & 회원 시스템

결제 연동(토스/카카오페이)은 사업자등록 후 붙이면 됨.
지금은 그 전에 필요한 뼈대를 먼저 완성:
  · 회원별 부채 잔액 관리
  · 무료 파트 / 유료 파트(부채 차감) 구분
  · 부채 충전(지금은 '결제 성공' 가정 → 나중에 실제 PG 콜백으로 교체)
  · 리포트 열람 이력

저장소: 지금은 파일(JSON)로 간단히. 실서비스 땐 DB(PostgreSQL 등)로 교체.
결제만 나중에 끼우면 바로 완성되는 구조.
"""
import json, os, threading
from datetime import datetime

# DB 경로: 환경변수로 지정 가능, 없으면 임시폴더(쓰기 보장)
_DB_PATH = os.environ.get("BUCHAE_DB", os.path.join(os.environ.get("TMPDIR", "/tmp"), "buchae_db.json"))
_LOCK = threading.Lock()

# 부채 상품 (사주아이 '츄르' 포지션) — 1부채 = 500원
BUCHAE_PACKAGES = {
    "fan_1": {"name": "부채 1개", "buchae": 1, "won": 500},
    "fan_3": {"name": "부채 3개", "buchae": 3, "won": 1300, "best": True},
    "fan_5": {"name": "부채 5개", "buchae": 5, "won": 2300, "tag": "작명 딱!"},
    "fan_7": {"name": "부채 7개", "buchae": 7, "won": 2900},
}
# 분야별 부채 가격 (유료 리포트 열 때 차감)
FIELD_COST = {
    "wealth": 1, "career": 1, "love": 1, "life": 1, "overall": 1, "health": 1,
    "yearly": 1, "followup": 1, "naming": 5,   # 작명은 프리미엄 5부채(2,500원)
    "analysis": 2,   # 이름 분석(감정)은 2부채(1,000원)
}
FREE_DAILY = "today"       # 오늘의 운세는 무료
NEW_USER_FREE_BUCHAE = 1   # 신규 가입 시 부채 1개 증정(첫 리포트 무료 체험)


def _load():
    if not os.path.exists(_DB_PATH):
        return {"users": {}}
    with open(_DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(db):
    with open(_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def get_or_create_user(user_id):
    """user_id = 카카오/구글 로그인 식별자 (지금은 문자열이면 뭐든 OK)."""
    with _LOCK:
        db = _load()
        if user_id not in db["users"]:
            db["users"][user_id] = {
                "buchae": NEW_USER_FREE_BUCHAE,
                "joined": datetime.now().isoformat(timespec="seconds"),
                "history": [],
            }
            _save(db)
        return db["users"][user_id]


def get_balance(user_id):
    return get_or_create_user(user_id)["buchae"]


def grant_buchae(user_id, n):
    """개발/테스트용: 부채를 직접 지급."""
    get_or_create_user(user_id)
    with _LOCK:
        db = _load()
        db["users"][user_id]["buchae"] += int(n)
        _save(db)
        return db["users"][user_id]["buchae"]


def charge_buchae(user_id, package_key, paid=False):
    """
    부채 충전. 지금은 paid=True를 '결제 성공했다 치고' 처리.
    실서비스: 토스/카카오 결제 콜백에서 검증 후 paid=True로 호출.
    """
    if package_key not in BUCHAE_PACKAGES:
        return {"ok": False, "error": "없는 상품"}
    pkg = BUCHAE_PACKAGES[package_key]
    if not paid:
        # 여기서 실제로는 PG 결제창을 띄우고, 성공 콜백을 기다림
        return {"ok": False, "need_payment": True, "package": pkg,
                "note": "결제 연동 전 — 실제로는 여기서 토스/카카오 결제창"}
    get_or_create_user(user_id)   # 락 밖에서 먼저 보장 (재진입 데드락 방지)
    with _LOCK:
        db = _load()
        u = db["users"][user_id]
        u["buchae"] += pkg["buchae"]
        u["history"].append({"t": datetime.now().isoformat(timespec="seconds"),
                             "type": "charge", "buchae": pkg["buchae"], "won": pkg["won"]})
        _save(db)
        return {"ok": True, "balance": u["buchae"]}


def can_open(user_id, field):
    """이 분야 리포트를 열 수 있는지 (무료거나 부채 충분)."""
    if field == FREE_DAILY:
        return {"ok": True, "free": True, "cost": 0}
    cost = FIELD_COST.get(field, 1)
    bal = get_balance(user_id)
    if bal >= cost:
        return {"ok": True, "free": False, "cost": cost, "balance": bal}
    return {"ok": False, "cost": cost, "balance": bal, "need_charge": True}


def open_report(user_id, field):
    """유료 리포트 열람 → 부채 차감. 성공 시 True."""
    chk = can_open(user_id, field)
    if not chk["ok"]:
        return {"ok": False, "need_charge": True, "cost": chk["cost"], "balance": chk["balance"]}
    if chk.get("free"):
        return {"ok": True, "free": True, "balance": get_balance(user_id)}
    with _LOCK:
        db = _load()
        u = db["users"][user_id]
        u["buchae"] -= chk["cost"]
        u["history"].append({"t": datetime.now().isoformat(timespec="seconds"),
                             "type": "open", "field": field, "cost": chk["cost"]})
        _save(db)
        return {"ok": True, "free": False, "balance": u["buchae"]}


if __name__ == "__main__":
    uid = "test_user_123"
    print("신규 유저:", get_or_create_user(uid)["buchae"], "부채 (가입 증정)")
    print("재물 리포트 열기:", open_report(uid, "wealth"))   # 1 → 0
    print("또 열기(부채 부족):", open_report(uid, "career"))  # 부족
    print("오늘의운세(무료):", open_report(uid, "today"))
    print("3부채 충전(결제 성공 가정):", charge_buchae(uid, "fan_3", paid=True))
    print("이제 열기:", open_report(uid, "career"))
    print("잔액:", get_balance(uid))
    # 정리
    os.path.exists(_DB_PATH) and os.remove(_DB_PATH)
    print("(테스트 DB 삭제 완료)")
