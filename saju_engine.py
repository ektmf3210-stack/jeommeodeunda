# -*- coding: utf-8 -*-
"""
사주(四柱) 엔진 — 팔자·십성·대운·세운 계산

기문 엔진(qimen_engine)과 짝을 이루는 모듈.
계산 백엔드는 검증된 lunar-python(6tail) 사용.
역할 분담:
  · 사주 = 인생의 큰 판·시기 (대운 10년 단위, 세운 1년 단위)
  · 기문 = 그 시기 안에서 언제·어디서·무엇을 (시진 단위 실행)

한자 십성/오행을 한글로 매핑해 사용성↑.
"""
from datetime import datetime
from lunar_python import Solar

# ── 한자→한글 매핑 ──
GAN_KR = {"甲":"갑","乙":"을","丙":"병","丁":"정","戊":"무","己":"기","庚":"경","辛":"신","壬":"임","癸":"계"}
ZHI_KR = {"子":"자","丑":"축","寅":"인","卯":"묘","辰":"진","巳":"사","午":"오","未":"미","申":"신","酉":"유","戌":"술","亥":"해"}
WUXING = {"甲":"목","乙":"목","丙":"화","丁":"화","戊":"토","己":"토","庚":"금","辛":"금","壬":"수","癸":"수"}
ZHI_WUXING = {"子":"수","丑":"토","寅":"목","卯":"목","辰":"토","巳":"화","午":"화","未":"토","申":"금","酉":"금","戌":"토","亥":"수"}

# 십성 한자→한글 + 의미
SHISHEN_KR = {
    "比肩":"비견","劫财":"겁재","食神":"식신","伤官":"상관","偏财":"편재",
    "正财":"정재","七杀":"편관","正官":"정관","偏印":"편인","正印":"정인",
}
SHISHEN_MEANING = {
    "비견":"자립·경쟁·동료. 주체성과 추진력, 독립심.",
    "겁재":"경쟁·확장·모험. 강한 승부욕, 재물 변동 큼.",
    "식신":"표현·여유·재능. 먹복·창작·즐기는 기운.",
    "상관":"재능·표현·반항. 톡톡 튀는 능력, 규칙 벗어남.",
    "편재":"유동적 재물·사업·기회. 큰 돈이 오가는 사업가 기질.",
    "정재":"안정적 재물·성실·저축. 꾸준히 모으는 근면함.",
    "편관":"도전·권력·압박. 강한 추진력, 위기돌파(七杀).",
    "정관":"명예·직장·규범. 안정된 지위·관운·책임감.",
    "편인":"직관·전문성·비주류. 독특한 재능, 눈치·통찰.",
    "정인":"학문·문서·귀인. 배움·보호·명예로운 후원.",
}

def hanja_to_kr(gz):
    return GAN_KR.get(gz[0], gz[0]) + ZHI_KR.get(gz[1], gz[1])


def compute_saju(dt_local, gender):
    """
    dt_local: datetime, gender: 'M'(남)/'F'(여)
    반환: 팔자·십성·대운·현재 대운/세운
    """
    l = Solar.fromYmdHms(dt_local.year, dt_local.month, dt_local.day,
                         dt_local.hour, dt_local.minute, 0).getLunar()
    ec = l.getEightChar()
    ilgan = ec.getDayGan()

    pillars = {
        "년주": ec.getYear(), "월주": ec.getMonth(),
        "일주": ec.getDay(), "시주": ec.getTime(),
    }
    # 십성 (천간 기준)
    shishen = {
        "년간": SHISHEN_KR.get(ec.getYearShiShenGan(), ec.getYearShiShenGan()),
        "월간": SHISHEN_KR.get(ec.getMonthShiShenGan(), ec.getMonthShiShenGan()),
        "시간": SHISHEN_KR.get(ec.getTimeShiShenGan(), ec.getTimeShiShenGan()),
    }
    # 오행 분포 집계
    wx_count = {"목":0,"화":0,"토":0,"금":0,"수":0}
    for gz in pillars.values():
        wx_count[WUXING[gz[0]]] += 1
        wx_count[ZHI_WUXING[gz[1]]] += 1

    # 대운
    gender_code = 1 if gender == "M" else 0
    yun = ec.getYun(gender_code)
    daewoon = []
    for d in yun.getDaYun():
        gz = d.getGanZhi()
        if not gz:
            continue
        daewoon.append({
            "시작나이": d.getStartAge(), "끝나이": d.getEndAge(),
            "시작연도": d.getStartYear(), "끝연도": d.getEndYear(),
            "간지": gz, "간지_kr": hanja_to_kr(gz),
            "천간십성": SHISHEN_KR.get(_shishen_of(ilgan, gz[0]), ""),
        })

    # 현재 대운 + 세운
    this_year = datetime.now().year
    cur = next((d for d in daewoon if d["시작연도"] <= this_year <= d["끝연도"]), None)
    saeun = []
    if cur:
        for d in yun.getDaYun():
            if d.getGanZhi() == cur["간지"] and d.getStartYear() == cur["시작연도"]:
                for ln in d.getLiuNian():
                    gz = ln.getGanZhi()
                    saeun.append({
                        "연도": ln.getYear(), "나이": ln.getAge(),
                        "간지": gz, "간지_kr": hanja_to_kr(gz),
                        "천간십성": SHISHEN_KR.get(_shishen_of(ilgan, gz[0]), ""),
                    })
                break

    return {
        "일간": ilgan, "일간_kr": GAN_KR[ilgan], "일간오행": WUXING[ilgan],
        "성별": "남" if gender == "M" else "여",
        "팔자": {k: f"{v}({hanja_to_kr(v)})" for k, v in pillars.items()},
        "십성": shishen,
        "오행분포": wx_count,
        "대운순행": yun.isForward(),
        "대운": daewoon,
        "현재대운": cur,
        "세운": saeun,
    }


# 십성 산출 (일간 기준 대상 천간의 관계)
_GAN_ORDER = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
_YIN_YANG = {g:(i % 2 == 0) for i, g in enumerate(_GAN_ORDER)}  # True=양
_WX_ORDER = {"甲":"목","乙":"목","丙":"화","丁":"화","戊":"토","己":"토","庚":"금","辛":"금","壬":"수","癸":"수"}
_SHENG = {"목":"화","화":"토","토":"금","금":"수","수":"목"}
_KE = {"목":"토","토":"수","수":"화","화":"금","금":"목"}

def _shishen_of(ilgan, target):
    """일간 대비 target 천간의 십성(한자) 반환."""
    iw, tw = _WX_ORDER[ilgan], _WX_ORDER[target]
    same_yy = (_YIN_YANG[ilgan] == _YIN_YANG[target])
    if iw == tw:
        return "比肩" if same_yy else "劫财"
    if _SHENG[iw] == tw:      # 일간이 생함 → 식상
        return "食神" if same_yy else "伤官"
    if _KE[iw] == tw:         # 일간이 극함 → 재성
        return "偏财" if same_yy else "正财"
    if _KE[tw] == iw:         # target이 일간을 극함 → 관성
        return "七杀" if same_yy else "正官"
    if _SHENG[tw] == iw:      # target이 일간을 생함 → 인성
        return "偏印" if same_yy else "正印"
    return ""


if __name__ == "__main__":
    import sys
    # 사용: python3 saju_engine.py 1991-03-21 19:56 F
    if len(sys.argv) >= 4:
        d = datetime.strptime(f"{sys.argv[1]} {sys.argv[2]}", "%Y-%m-%d %H:%M")
        gender = sys.argv[3].upper()
    else:
        d, gender = datetime(1991,3,21,19,56), "F"

    s = compute_saju(d, gender)
    print("="*58)
    print(f"사주 — {d.strftime('%Y-%m-%d %H:%M')} ({s['성별']})")
    print("="*58)
    print("팔자:", " ".join(s["팔자"].values()))
    print(f"일간(본인): {s['일간']}({s['일간_kr']}, {s['일간오행']})")
    print("십성:", s["십성"])
    wx = s["오행분포"]
    print("오행분포:", " ".join(f"{k}{v}" for k,v in wx.items()),
          f"| 강한오행: {max(wx,key=wx.get)}, 약한오행: {min(wx,key=wx.get)}")
    print(f"대운 순행: {s['대운순행']}")
    print("\n대운(10년 단위):")
    for d_ in s["대운"]:
        star = " ★현재" if d_ is s["현재대운"] else ""
        print(f"  {d_['시작나이']:>2}~{d_['끝나이']:>2}세 ({d_['시작연도']}~{d_['끝연도']}) "
              f"{d_['간지']}({d_['간지_kr']}) {d_['천간십성']}{star}")
    if s["현재대운"]:
        c = s["현재대운"]
        print(f"\n현재 대운: {c['간지']}({c['간지_kr']}) {c['천간십성']} — {c['시작연도']}~{c['끝연도']}")
        print("세운(연 단위):")
        for y in s["세운"][:8]:
            print(f"  {y['연도']}년({y['나이']}세) {y['간지']}({y['간지_kr']}) {y['천간십성']}")
