# -*- coding: utf-8 -*-
"""작명 엔진 (정통 수리성명학).
아기 사주 -> 부족오행 파악 -> 성씨 고정 하에 이름 2글자를 조합탐색:
  1) 사격(원형이정) 4개가 모두 길수
  2) 발음오행 상생(성-이름1-이름2)
  3) 자원오행이 부족오행을 보완
점수화해 상위 후보 반환 + 순한글 이름 추천.
계산은 전부 코드가 확정(할루시네이션 없음). 설명 문장만 LLM이 붙임.
"""
import random
from datetime import datetime
from suri import four_gyeok, four_gyeok_single
from hanja_db import (SEONG, GIVEN, eum_ohaeng, normalize_seong, resolve_seong,
                      gender_ok, ending_ok, ENDING_ONLY, PRETTY, TRENDY)
from saju_engine import compute_saju

KR2HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}
HANJA2KR = {v: k for k, v in KR2HANJA.items()}
OH_ORDER = ["목", "화", "토", "금", "수"]

SANGSAENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
SANGGEUK = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 이상하게 들리는 이름(비속어·성적표현·욕설·부정어) 차단
BAD_NAMES = {
    # 성적·비속어 (절대 금지)
    "보지", "자지", "성기", "정액", "자위", "몽정", "발정", "변태", "섹스",
    "음란", "음경", "고환", "질염", "포경", "애무", "야동", "포르",
    # 욕설·비하
    "미친", "병신", "등신", "빙신", "지랄", "염병", "바보", "멍청", "얼간",
    "쪼다", "찌질", "저능", "백치", "미개", "발광", "광기", "잡놈", "쌍놈",
    "개년", "걸레", "창녀", "화냥", "호구", "찐따", "루저",
    # 부정·불길
    "한심", "무심", "변심", "의심", "야심", "욕심", "고심", "환심", "흑심",
    "죽음", "자살", "살인", "폭행", "폭력", "강간", "마약", "재앙", "저주",
    "불행", "불운", "파산", "몰락", "패망", "자멸", "치질", "설사", "오물",
    "무능", "무식", "허무", "우울", "고통", "실망", "재수", "악마", "지옥",
    "시체", "하수", "오줌", "방구", "코딱",
}

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


def _rel(a, b):
    """발음오행 두 글자 관계 점수 (상극은 양방향으로 감점)."""
    if not a or not b:
        return 0
    if SANGGEUK.get(a) == b or SANGGEUK.get(b) == a:   # 상극(서로 극) — 약하게 감점
        return -2
    if SANGSAENG.get(a) == b:                          # 상생(정방향)
        return 2
    if SANGSAENG.get(b) == a:                          # 역생(약한 생)
        return 1
    if a == b:                                         # 상비(같은 오행)
        return 1
    return 0


def _flow(oh_list):
    """성-이름1-이름2 발음오행 흐름 -> (총점, 상극있음)."""
    total, geuk = 0, False
    for a, b in zip(oh_list, oh_list[1:]):
        s = _rel(a, b)
        total += s
        if s < 0:
            geuk = True
    return total, geuk


def _find_entries(text):
    """고정할 글자(한글 음 또는 한자) -> 매칭되는 [(음,한자,훈,획,오행), ...]"""
    t = (text or "").strip()
    if not t:
        return []
    c = t[0]
    out = []
    for eum, lst in GIVEN.items():
        if len(eum) != 1:
            continue
        for (hj, hun, hk, oh) in lst:
            if c == eum or c == hj:      # 한글 음이거나 한자 일치
                out.append((eum, hj, hun, hk, oh))
    return out


def _grade_bonus(fg, keys):
    s = 0
    for k in keys:
        gr = fg[k]["등급"]
        s += 3 if gr == "최상" else (2 if gr == "상" else 1)
    return s


def generate_names(seong_kr, dt_birth, gender, top=6, seong_hanja=None,
                   fixed=None, fixed_pos=None, single=False):
    raw = (seong_kr or "").strip()
    resolved = resolve_seong(raw, seong_hanja)
    if resolved is None:
        return {"error": f"'{raw[:2]}' 성씨를 아직 못 찾았어. 한글로 한 글자만 넣어줄래? (예: 김, 이, 박)"}
    seong_kr, s_hj, s_hoek = resolved
    s_oh = eum_ohaeng(seong_kr)

    saju = compute_saju(dt_birth, gender)
    wx = saju["오행분포"]
    need = set(_need_ohaeng(wx))

    want = "F" if gender in ("F", "여", "여아") else "M"
    # 성별 어울리고 + '예쁜 음절'인 것만 자동 생성에 사용 (벽자 걸러냄)
    pool = [p for p in _flatten() if gender_ok(p[0], want) and p[0] in PRETTY]

    fixed_entries = _find_entries(fixed) if fixed else []
    if fixed and not fixed_entries:
        return {"error": f"'{fixed}'는 아직 이름 한자 DB에 없어. 다른 글자로 해줄래?"}

    cands = []
    # 끝 글자(외자면 그 글자, 두자면 뒷글자)는 여아 어미 규칙 적용
    end_pool = [p for p in pool if ending_ok(p[0], want)]
    first_pool = [p for p in pool if p[0] not in ENDING_ONLY]   # 첫 글자엔 '끝전용' 제외

    if single:
        # ── 외자(홑이름): 이름 한 글자 (끝전용 음절 제외) ──
        src = fixed_entries if fixed_entries else [p for p in end_pool if p[0] not in ENDING_ONLY]
        for (e1, h1, hun1, hk1, oh1) in src:
            fg = four_gyeok_single(s_hoek, hk1)
            if not fg["_모두길"]:
                continue
            eo1 = eum_ohaeng(e1)
            flow, geuk = _flow([s_oh, eo1])
            bo = [o for o in (oh1,) if o in need]
            score = flow + len(bo) * 5 + _grade_bonus(fg, ("원격", "정격")) + (9 if e1 in TRENDY else 0)
            cands.append({
                "이름": e1, "한자": h1, "훈": [hun1], "획수": [hk1],
                "자원오행": [oh1], "발음오행": [s_oh, eo1], "보완오행": bo, "_geuk": geuk,
                "사격": {k: {"수": fg[k]["수"], "등급": fg[k]["등급"], "격": fg[k]["격"]}
                        for k in ("원격", "정격")},
                "_score": score,
            })
    else:
        # ── 두 글자: fixed_pos(1/2)에 고정, 나머지 자유 ──
        pos1 = fixed_entries if (fixed and fixed_pos == 1) else first_pool
        pos2 = fixed_entries if (fixed and fixed_pos == 2) else end_pool
        for (e1, h1, hun1, hk1, oh1) in pos1:
            eo1 = eum_ohaeng(e1)
            for (e2, h2, hun2, hk2, oh2) in pos2:
                if e1 == e2:            # 겹소리(민민 등) 제외
                    continue
                fg = four_gyeok(s_hoek, [hk1, hk2])
                if not fg["_모두길"]:
                    continue
                eo2 = eum_ohaeng(e2)
                flow, geuk = _flow([s_oh, eo1, eo2])
                bo = [o for o in (oh1, oh2) if o in need]
                score = (flow + len(bo) * 5 + _grade_bonus(fg, ("원격", "형격", "이격", "정격"))
                         + sum(9 for _e in (e1, e2) if _e in TRENDY))
                cands.append({
                    "이름": e1 + e2, "한자": h1 + h2, "훈": [hun1, hun2],
                    "획수": [hk1, hk2], "자원오행": [oh1, oh2],
                    "발음오행": [s_oh, eo1, eo2], "보완오행": bo, "_geuk": geuk,
                    "사격": {k: {"수": fg[k]["수"], "등급": fg[k]["등급"], "격": fg[k]["격"]}
                            for k in ("원격", "형격", "이격", "정격")},
                    "_score": score,
                })
    # 미러 이름(영우/우영) 및 중복 제거, 점수순
    cands.sort(key=lambda c: c["_score"], reverse=True)
    seen_name, seen_char, uniq = set(), set(), []
    for c in cands:
        ck = frozenset(c["한자"])
        if c["이름"] in seen_name or ck in seen_char:   # 같은 한글이름/미러 제거
            continue
        seen_name.add(c["이름"])
        seen_char.add(ck)
        uniq.append(c)
    # 상위 풀에서 랜덤 추출 + 같은 첫/끝 글자 도배 방지 → 다양하게, 재구매 시 매번 다름
    top_pool = uniq[:max(top * 8, 48)]
    random.shuffle(top_pool)
    seen_first, seen_last, picked = {}, {}, []
    for c in top_pool:
        if c["이름"] in BAD_NAMES:                 # 이상한 단어 이름 제외
            continue
        f, l = c["이름"][0], c["이름"][-1]
        if seen_first.get(f, 0) >= 1 or seen_last.get(l, 0) >= 2:
            continue
        seen_first[f] = 1
        seen_last[l] = seen_last.get(l, 0) + 1
        picked.append(c)
        if len(picked) >= top:
            break
    if len(picked) < top:                 # 모자라면 남은 것으로 채움
        for c in top_pool:
            if c not in picked and c["이름"] not in BAD_NAMES:
                picked.append(c)
            if len(picked) >= top:
                break
    picked.sort(key=lambda c: c["_score"], reverse=True)

    # 순한글 후보 (발음 상극 없는 것), 매번 섞어서 다양하게
    sun = []
    for (nm, meaning) in SUNHANGEUL:
        o1, o2 = eum_ohaeng(nm[0]), eum_ohaeng(nm[-1])
        _f, geuk = _flow([s_oh, o1, o2])
        if geuk:
            continue
        sun.append({"이름": nm, "뜻": meaning, "발음오행": [s_oh, o1, o2]})
    random.shuffle(sun)
    sun = sun[:5]

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
