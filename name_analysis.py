# -*- coding: utf-8 -*-
"""이름 분석(성명 감정): 기존 이름이 잘 지어졌는지 진단.
- 발음오행(음령오행) 흐름: 한글만으로 100% 정확
- 사주 궁합: 생일로 부족오행 계산 → 이름이 채워주는지
- 수리(사격): 한자를 주면 DB에서 획수 찾아 추가 분석
계산은 코드가 확정, 해설만 LLM.
"""
from datetime import datetime
from suri import four_gyeok, grade
from hanja_db import SEONG, GIVEN, SEONG_VARIANTS, eum_ohaeng
from saju_engine import compute_saju

KR2HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}
HANJA2KR = {v: k for k, v in KR2HANJA.items()}
OH_ORDER = ["목", "화", "토", "금", "수"]
SANGSAENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
SANGGEUK = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
OH_KR = {"木": "나무(木)", "火": "불(火)", "土": "흙(土)", "金": "쇠(金)", "水": "물(水)"}

# 한자 -> (원획, 자원오행 or None) 통합 조회표
HANJA_INFO = {}
for _kr, (_hj, _hk) in SEONG.items():
    HANJA_INFO.setdefault(_hj, (_hk, None))
for _kr, _lst in SEONG_VARIANTS.items():
    for _hj, _hk in _lst:
        HANJA_INFO.setdefault(_hj, (_hk, None))
for _eum, _lst in GIVEN.items():
    for _hj, _hun, _hk, _oh in _lst:
        HANJA_INFO[_hj] = (_hk, _oh)


def _need_ohaeng(wx):
    zero = [o for o in OH_ORDER if wx.get(o, 0) == 0]
    if zero:
        picks = zero
    else:
        mn = min(wx.get(o, 0) for o in OH_ORDER)
        picks = [o for o in OH_ORDER if wx.get(o, 0) == mn]
    return [KR2HANJA[o] for o in picks]


def analyze_name(fullname, dt_birth, gender, hanja=None):
    name = (fullname or "").strip().replace(" ", "")
    if not (2 <= len(name) <= 4):
        return {"error": "이름을 한글로 2~4글자 넣어줘 (예: 김다슬)"}
    seong, given = name[0], name[1:]

    # 1) 발음오행 흐름
    eums = [eum_ohaeng(c) for c in name]
    flow, good, bad = [], 0, 0
    for a, b in zip(eums, eums[1:]):
        if not a or not b:
            rel = "?"
        elif SANGGEUK.get(a) == b:
            rel = "상극"; bad += 1
        elif SANGSAENG.get(a) == b:
            rel = "상생"; good += 1
        elif a == b:
            rel = "상비"; good += 0.5
        else:
            rel = "역생"
        flow.append({"a": a, "b": b, "rel": rel})
    if bad == 0 and good >= len(flow) * 0.5:
        eum_grade = "좋음"
    elif bad == 0:
        eum_grade = "무난"
    elif bad == 1 and len(flow) >= 2:
        eum_grade = "아쉬움"
    else:
        eum_grade = "부딪힘"

    # 2) 사주 궁합
    saju = compute_saju(dt_birth, gender)
    wx = saju["오행분포"]
    need = _need_ohaeng(wx)
    name_oh = [e for e in eums if e]
    covered = [o for o in need if o in name_oh]
    saju_fit = ("좋음" if covered else "아쉬움")

    # 3) 수리(사격) — 한자 있으면
    suri = None
    if hanja:
        hj = hanja.strip().replace(" ", "")
        if len(hj) == len(name):
            hoeks, ohs, ok = [], [], True
            for c in hj:
                if c in HANJA_INFO:
                    hoeks.append(HANJA_INFO[c][0]); ohs.append(HANJA_INFO[c][1])
                else:
                    ok = False; break
            if ok and len(hoeks) >= 3:
                fg = four_gyeok(hoeks[0], hoeks[1:])
                suri = {"한자": hj, "획수": hoeks,
                        "사격": {k: {"수": fg[k]["수"], "등급": fg[k]["등급"], "격": fg[k]["격"]}
                                for k in ("원격", "형격", "이격", "정격")},
                        "모두길": fg["_모두길"], "길개수": fg["_길개수"]}
            elif not ok:
                suri = {"미지원": True}

    # 4) 장단점 정리
    pros, cons = [], []
    if eum_grade == "좋음":
        pros.append("이름 소리의 기운(발음오행)이 자연스럽게 상생으로 흐른다")
    elif eum_grade == "무난":
        pros.append("이름 소리의 기운이 서로 부딪히지 않고 무난하다")
    elif eum_grade == "아쉬움":
        cons.append("이름 소리 기운에 부딪히는(상극) 구간이 한 곳 있다")
    else:
        cons.append("이름 소리 기운이 여러 곳에서 상극으로 부딪힌다")
    if covered:
        pros.append(f"사주에 부족한 {'/'.join(HANJA2KR[o] for o in covered)} 기운을 이름 소리가 채워준다")
    else:
        cons.append(f"사주에 부족한 {'/'.join(HANJA2KR[o] for o in need)} 기운을 이름 소리가 직접 채워주진 않는다")
    if suri and suri.get("모두길"):
        pros.append("한자 획수 운(사격)이 초년·청년·장년·말년 모두 길하다")
    elif suri and "미지원" not in suri and not suri.get("모두길"):
        cons.append("한자 획수 운(사격)에 흉한 구간이 섞여 있다")

    return {
        "이름": name, "성": seong, "이름자": given,
        "발음오행": {"배열": eums, "흐름": flow, "등급": eum_grade},
        "사주": {"일간": saju["일간_kr"], "일간오행": saju["일간오행"],
                "오행분포": wx, "부족오행": [HANJA2KR[o] for o in need],
                "이름이채운오행": [HANJA2KR[o] for o in covered], "궁합": saju_fit},
        "수리": suri,
        "장점": pros, "단점": cons,
    }


if __name__ == "__main__":
    r = analyze_name("김다슬", datetime(1991, 3, 21, 19, 56), "F", hanja=None)
    print("이름:", r["이름"], "| 발음오행", r["발음오행"]["배열"], r["발음오행"]["등급"])
    print("부족오행:", r["사주"]["부족오행"], "| 이름이 채운:", r["사주"]["이름이채운오행"])
    print("장점:", r["장점"])
    print("단점:", r["단점"])
