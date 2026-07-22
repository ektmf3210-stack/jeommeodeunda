# -*- coding: utf-8 -*-
"""작명 엔진 (정통 수리성명학).
아기 사주 -> 부족오행 파악 -> 성씨 고정 하에 이름 2글자를 조합탐색:
  1) 사격(원형이정) 4개가 모두 길수
  2) 발음오행 상생(성-이름1-이름2)
  3) 자원오행이 부족오행을 보완
점수화해 상위 후보 반환 + 순한글 이름 추천.
계산은 전부 코드가 확정(할루시네이션 없음). 설명 문장만 LLM이 붙임.
"""
from datetime import datetime
from suri import four_gyeok
from hanja_db import SEONG, GIVEN, eum_ohaeng, normalize_seong, resolve_seong
from saju_engine import compute_saju

KR2HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}
HANJA2KR = {v: k for k, v in KR2HANJA.items()}
OH_ORDER = ["목", "화", "토", "금", "수"]

SANGSAENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
SANGGEUK = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 순한글 이름 후보 (뜻 포함) — 발음오행은 런타임 계산
SUNHANGEUL = [
    ("하람", "하늘이 내린 소중한 사람"), ("가온", "세상의 중심"),
    ("다온", "좋은 일이 다 오라"), ("라온", "즐거운"),
    ("아라", "바다처럼 넓게"), ("나래", "날개를 펴고 훨훨"),
    ("한결", "처음처럼 한결같이"), ("은결", "은은하고 곧은 결"),
    ("도담", "탈 없이 튼튼하게"), ("나린", "하늘이 내린"),
    ("소예", "밝고 예쁜"), ("시아", "새로 열리는"),
    ("여울", "잔잔히 흐르는 물결"), ("빛나", "빛나는 사람"),
    ("해든", "햇살이 드는"), ("슬기", "지혜로운"),
    ("미르", "용처럼 크게"), ("아름", "아름다운"),
    ("사랑", "사랑스러운"), ("바다", "바다처럼 깊고 넓게"),
    ("보라", "귀하게 보라"), ("초록", "싱그러운"),
    ("온유", "따뜻하고 부드러운"), ("예솔", "예쁘고 곧은 소나무"),
]


def _need_ohaeng(wx):
    """오행분포(dict 목화토금수) -> 부족오행 리스트(한자오행). 0개 우선, 없으면 최소."""
    zero = [o for o in OH_ORDER if wx.get(o, 0) == 0]
    if zero:
        picks = zero
    else:
        mn = min(wx.get(o, 0) for o in OH_ORDER)
        picks = [o for o in OH_ORDER if wx.get(o, 0) == mn]
    return [KR2HANJA[o] for o in picks]


def _flatten():
    """GIVEN -> [(음, 한자, 훈, 원획, 오행), ...]"""
    out = []
    for eum, lst in GIVEN.items():
        if len(eum) != 1:          # 단음절 음만
            continue
        for (hj, hun, hoek, oh) in lst:
            out.append((eum, hj, hun, hoek, oh))
    return out


def _eum_flow_score(s_oh, o1, o2):
    """발음오행 흐름 점수. 상극 있으면 None(제외)."""
    score = 0
    for a, b in [(s_oh, o1), (o1, o2)]:
        if not a or not b:
            continue
        if SANGGEUK.get(a) == b:      # 상극
            return None
        if SANGSAENG.get(a) == b:     # 상생
            score += 2
        elif a == b:                  # 상비(같은 오행)
            score += 1
        else:                         # 역생 등
            score += 0
    return score


def generate_names(seong_kr, dt_birth, gender, top=6, seong_hanja=None):
    raw = (seong_kr or "").strip()
    resolved = resolve_seong(raw, seong_hanja)
    if resolved is None:
        return {"error": f"'{raw[:2]}' 성씨를 아직 못 찾았어. 한글로 한 글자만 넣어줄래? (예: 김, 이, 박)"}
    seong_kr, s_hj, s_hoek = resolved
    s_oh = eum_ohaeng(seong_kr)                 # 성 발음오행(한자표기)
    s_oh_hj = KR2HANJA.get(HANJA2KR.get(s_oh, ""), s_oh) if s_oh in KR2HANJA.values() else s_oh
    s_oh = s_oh                                  # eum_ohaeng already returns 木火土金水

    saju = compute_saju(dt_birth, gender)
    wx = saju["오행분포"]
    need = set(_need_ohaeng(wx))                # 부족오행(한자)

    pool = _flatten()
    cands = []
    for (e1, h1, hun1, hk1, oh1) in pool:
        for (e2, h2, hun2, hk2, oh2) in pool:
            if e1 == e2:                         # 같은 음 반복 제외
                continue
            flow = _eum_flow_score(s_oh, oh1, oh2)
            if flow is None:                     # 발음 상극 제외
                continue
            fg = four_gyeok(s_hoek, [hk1, hk2])
            if not fg["_모두길"]:                # 사격 전부 길 필수
                continue
            bo = [o for o in (oh1, oh2) if o in need]
            score = flow * 2 + len(bo) * 4
            # 등급 가중 (최상/상)
            for k in ("원격", "형격", "이격", "정격"):
                g = fg[k]["등급"]
                score += 3 if g == "최상" else (2 if g == "상" else 1)
            cands.append({
                "이름": e1 + e2, "한자": h1 + h2, "훈": [hun1, hun2],
                "획수": [hk1, hk2], "자원오행": [oh1, oh2],
                "발음오행": [s_oh, oh1, oh2], "보완오행": bo,
                "사격": {k: {"수": fg[k]["수"], "등급": fg[k]["등급"], "격": fg[k]["격"]}
                        for k in ("원격", "형격", "이격", "정격")},
                "_score": score,
            })
    # 중복 이름(한글) 제거하며 상위 선별
    cands.sort(key=lambda c: c["_score"], reverse=True)
    seen, picked = set(), []
    for c in cands:
        if c["이름"] in seen:
            continue
        seen.add(c["이름"])
        picked.append(c)
        if len(picked) >= top:
            break

    # 순한글 후보 (발음 상극 없는 것)
    sun = []
    for (nm, meaning) in SUNHANGEUL:
        o1, o2 = eum_ohaeng(nm[0]), eum_ohaeng(nm[-1])
        if _eum_flow_score(s_oh, o1, o2) is None:
            continue
        sun.append({"이름": nm, "뜻": meaning, "발음오행": [s_oh, o1, o2]})
    sun = sun[:6]

    return {
        "성": {"한글": seong_kr, "한자": s_hj, "획수": s_hoek, "발음오행": s_oh},
        "사주": {"일간": saju["일간_kr"], "일간오행": saju["일간오행"],
                "오행분포": wx, "부족오행": [HANJA2KR[o] for o in need]},
        "한자후보": picked,
        "순한글후보": sun,
    }


if __name__ == "__main__":
    r = generate_names("김", datetime(2025, 3, 10, 9, 30), "M")
    if "error" in r:
        print(r["error"])
    else:
        print("성:", r["성"], "| 부족오행:", r["사주"]["부족오행"])
        for c in r["한자후보"]:
            sg = c["사격"]
            print(f"  {c['이름']}({c['한자']}) 획{c['획수']} 보완{c['보완오행']} "
                  f"원{sg['원격']['수']}{sg['원격']['등급']} 형{sg['형격']['수']}{sg['형격']['등급']} "
                  f"이{sg['이격']['수']}{sg['이격']['등급']} 정{sg['정격']['수']}{sg['정격']['등급']}")
        print("순한글:", [s["이름"] for s in r["순한글후보"]])
