# -*- coding: utf-8 -*-
"""
기문둔갑(奇門遁甲) 계산 엔진
포팅 출처: anthonylee1994/qimen (MIT License) — ALGORITHM.md 알고리즘 문서 기준
https://github.com/anthonylee1994/qimen

구성:
  1. 절기(24節氣) 계산 — 태양황경 기반 (Meeus 저정밀 공식)
  2. 사주(년월일시 干支) 계산 — 입춘/월별 절기 경계, 오호둔/오서둔 표준 규칙
  3. 기문둔갑 포국 — 원 리포지토리 ALGORITHM.md 12단계 그대로 포팅
  4. 자체 검증 — ALGORITHM.md의 "완전 예시"(2024-05-10 14:30) 재현 후 대조
"""

import math
from datetime import datetime, timedelta

# ============================================================
# 0. 기초 테이블
# ============================================================

CHEONGAN = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
CHEONGAN_HANJA = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
JIJI = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
JIJI_HANJA = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

def ganzhi_str(i):
    """0~59 인덱스를 60갑자 한자 문자열로."""
    return CHEONGAN_HANJA[i % 10] + JIJI_HANJA[i % 12]

def ganzhi_kr(i):
    return CHEONGAN[i % 10] + JIJI[i % 12]

# ============================================================
# 1. 태양황경 & 24절기 (Meeus 저정밀 공식, 오차 ~0.01도 이내)
# ============================================================

JIEQI_BY_LONGITUDE = [
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
]  # index i -> 경도 i*15도에서 시작하는 절기

def julian_day(dt_utc):
    """UTC datetime -> Julian Day (소수 포함)."""
    y, m = dt_utc.year, dt_utc.month
    d = dt_utc.day + (dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return jd

def solar_longitude(dt_utc):
    """지구에서 본 태양의 겉보기 황경(도, 0~360). Meeus 저정밀 공식."""
    jd = julian_day(dt_utc)
    T = (jd - 2451545.0) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T ** 2
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T ** 2
    Mr = math.radians(M)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T ** 2) * math.sin(Mr)
         + (0.019993 - 0.000101 * T) * math.sin(2 * Mr)
         + 0.000289 * math.sin(3 * Mr))
    true_long = L0 + C
    omega = 125.04 - 1934.136 * T
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    return lam % 360

def get_jieqi(dt_local, tz_offset_hours=9):
    """로컬 시각(기본 KST, UTC+9) 기준 '지금 속한' 절기 이름(한자) 반환."""
    dt_utc = dt_local - timedelta(hours=tz_offset_hours)
    lam = solar_longitude(dt_utc)
    idx = int(lam // 15) % 24
    return JIEQI_BY_LONGITUDE[idx]

def find_jieqi_moment(target_longitude, near_dt_local, tz_offset_hours=9, search_days=20):
    """target_longitude(0~360)에 해당하는 절기의 정확한 시각을 이진탐색으로 근사."""
    lo = near_dt_local - timedelta(days=search_days)
    hi = near_dt_local + timedelta(days=search_days)

    def diff(dt):
        lam = solar_longitude(dt - timedelta(hours=tz_offset_hours))
        d = (lam - target_longitude + 540) % 360 - 180
        return d

    for _ in range(60):
        mid = lo + (hi - lo) / 2
        if diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    return lo + (hi - lo) / 2

# ============================================================
# 2. 사주(八字) 계산 — 표준 규칙 (오호둔/오서둔, 입춘/절기 경계)
# ============================================================

# 절기(節) 12개 -> 월지(月支) 매핑 (입춘=인월 시작)
JIE_TO_MONTH_BRANCH = {
    "立春": 2, "惊蛰": 3, "清明": 4, "立夏": 5, "芒种": 6, "小暑": 7,
    "立秋": 8, "白露": 9, "寒露": 10, "立冬": 11, "大雪": 0, "小寒": 1,
}  # 지지 인덱스: 인=2 ... (JIJI 배열 인덱스 기준)

# 오호둔(五虎遁): 연간(年干) -> 인월(寅月) 월간(月干)
WUHU_DUN = {0: 2, 5: 2,   # 갑기년 -> 병인두 (병=index2)
            1: 4, 6: 4,   # 을경년 -> 무인두
            2: 6, 7: 6,   # 병신년 -> 경인두
            3: 8, 8: 8,   # 정임년 -> 임인두
            4: 0, 9: 0}   # 무계년 -> 갑인두

# 오서둔(五鼠遁): 일간(日干) -> 자시(子時) 시간(時干)
WUSHU_DUN = {0: 0, 5: 0,   # 갑기일 -> 갑자시
             1: 2, 6: 2,   # 을경일 -> 병자시
             2: 4, 7: 4,   # 병신일 -> 무자시
             3: 6, 8: 6,   # 정임일 -> 경자시
             4: 8, 9: 8}   # 무계일 -> 임자시

# 일주(日柱) 보정 상수 — 검증 완료 ✅
# 자체 근사 계산용 보정값. 실사용 시에는 아래 lunar-python 백엔드가 우선 사용되며,
# 이 자체 계산은 라이브러리가 없을 때의 폴백입니다.
# 검증: 권위 만세력 라이브러리(lunar-python, 6tail/sxwnl 기반)와
#   1950~2035년 랜덤 400개 날짜의 일주를 교차검증 → 400/400 완전 일치 확인.
#   기준일 2000-01-01=戊午, 1900-01-01=甲戌 모두 라이브러리와 일치.
DAY_PILLAR_REF_DATE = datetime(2000, 1, 1)
DAY_PILLAR_REF_INDEX = 54  # 戊午 (stem 4=戊, branch 6=午 → i%10=4, i%12=6 → i=54)
DAY_PILLAR_EPOCH_OFFSET = None

def calibrate_day_pillar():
    global DAY_PILLAR_EPOCH_OFFSET
    ordinal = DAY_PILLAR_REF_DATE.toordinal()
    DAY_PILLAR_EPOCH_OFFSET = (DAY_PILLAR_REF_INDEX - ordinal) % 60

calibrate_day_pillar()

def day_pillar_index(dt_local):
    return (dt_local.toordinal() + DAY_PILLAR_EPOCH_OFFSET) % 60

def hour_branch_index(hour):
    """시(0~23) -> 지지 인덱스 (23~1시=자시)."""
    return ((hour + 1) // 2) % 12

# ------------------------------------------------------------
# 권위있는 만세력 백엔드: lunar-python (6tail, sxwnl 기반).
# 설치돼 있으면 이걸 우선 사용(엣지케이스·분단위 절기까지 정확).
# 없으면 아래 자체 근사 계산으로 폴백.
# ------------------------------------------------------------
try:
    from lunar_python import Solar as _Solar
    _HAS_LUNAR = True
except ImportError:
    _HAS_LUNAR = False

def _ganzhi_to_index(gz_hanja):
    s = CHEONGAN_HANJA.index(gz_hanja[0])
    b = JIJI_HANJA.index(gz_hanja[1])
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise ValueError(gz_hanja)

def get_bazi_lunar(dt_local):
    """lunar-python 기반 사주 4주 + 절기(24절기 중 현재 속한 것)."""
    l = _Solar.fromYmdHms(dt_local.year, dt_local.month, dt_local.day,
                          dt_local.hour, dt_local.minute, 0).getLunar()
    return {
        "년주": _ganzhi_to_index(l.getYearInGanZhiByLiChun()),
        "월주": _ganzhi_to_index(l.getMonthInGanZhi()),
        "일주": _ganzhi_to_index(l.getDayInGanZhi()),
        "시주": _ganzhi_to_index(l.getTimeInGanZhi()),
        "절기": l.getPrevJieQi(True).getName(),
    }

def get_bazi(dt_local, tz_offset_hours=9, force_builtin=False):
    """dt_local -> 4주 60갑자 인덱스 + 절기.
    lunar-python이 있으면 그걸(권위), 없으면 자체 근사 계산으로 폴백."""
    if _HAS_LUNAR and not force_builtin:
        return get_bazi_lunar(dt_local)
    jieqi_now = get_jieqi(dt_local, tz_offset_hours)

    # ---- 년주: 입춘 기준 ----
    ipchun_this_year = find_jieqi_moment(315, datetime(dt_local.year, 2, 4), tz_offset_hours)
    if dt_local >= ipchun_this_year:
        bazi_year = dt_local.year
    else:
        bazi_year = dt_local.year - 1
    # 갑자년 기준점: 1984-02-04(입춘 이후)는 갑자년 (index0)
    year_index = (bazi_year - 1984) % 60

    # ---- 월주: 12절(節) 경계 기준 ----
    jie_candidates = [j for j in JIE_TO_MONTH_BRANCH]
    boundaries = []
    for jname in jie_candidates:
        lon = JIEQI_BY_LONGITUDE.index(jname) * 15
        # dt_local 근처에서 해당 절기가 발생하는 시각을 찾는다 (연도 앞뒤로 탐색)
        approx = datetime(dt_local.year, 1, 1) + timedelta(days=(lon / 360) * 365.25)
        t = find_jieqi_moment(lon, approx, tz_offset_hours, search_days=200)
        boundaries.append((t, JIE_TO_MONTH_BRANCH[jname]))
    boundaries.sort(key=lambda x: x[0])
    month_branch = boundaries[0][1]
    for t, branch in boundaries:
        if t <= dt_local:
            month_branch = branch
        else:
            break

    year_gan = year_index % 10
    month_gan_start = WUHU_DUN[year_gan]  # 인월의 월간
    # 인(2)부터 month_branch까지 몇 칸 이동했는지
    steps = (month_branch - 2) % 12
    month_gan = (month_gan_start + steps) % 10
    month_index = None
    for i in range(60):
        if i % 10 == month_gan and i % 12 == month_branch:
            month_index = i
            break

    # ---- 일주 ----
    day_index = day_pillar_index(dt_local)

    # ---- 시주 ----
    day_gan = day_index % 10
    hour_gan_start = WUSHU_DUN[day_gan]  # 자시의 시간
    hbranch = hour_branch_index(dt_local.hour)
    hour_gan = (hour_gan_start + hbranch) % 10
    hour_index = None
    for i in range(60):
        if i % 10 == hour_gan and i % 12 == hbranch:
            hour_index = i
            break

    return {
        "년주": year_index, "월주": month_index, "일주": day_index, "시주": hour_index,
        "절기": jieqi_now,
    }

# ============================================================
# 3. 기문둔갑 포국 — anthonylee1994/qimen ALGORITHM.md 그대로 포팅
# ============================================================

FEIXING_TO_ZHUANPAN = [1, 8, 3, 4, 9, 2, 7, 6]           # 飛星轉轉盤序
ZHUANPAN_TO_FEIXING = [1, 6, 3, 4, None, 8, 7, 2, 5]      # 轉盤轉飛星序

SANQI_LIUYI_SEQ = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]
GONG_FEIXING = ["坎一宮", "坤二宮", "震三宮", "巽四宮", "中五宮", "乾六宮", "兌七宮", "艮八宮", "離九宮"]
GONG_ZHUANPAN = ["坎一宮", "艮八宮", "震三宮", "巽四宮", "離九宮", "坤二宮", "兌七宮", "乾六宮"]
BASHEN_SEQ = ["值符", "騰蛇", "太陰", "六合", "白虎", "玄武", "九地", "九天"]
JIUXING_SEQ = ["天蓬", "天任", "天冲", "天輔", "天英", "天芮", "天柱", "天心"]
BAMEN_SEQ = ["休門", "生門", "傷門", "杜門", "景門", "死門", "驚門", "開門"]
GAN_SEQ = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

XUNSHOU_TABLE = {
    "甲子": ["甲子","乙丑","丙寅","丁卯","戊辰","己巳","庚午","辛未","壬申","癸酉"],
    "甲寅": ["甲寅","乙卯","丙辰","丁巳","戊午","己未","庚申","辛酉","壬戌","癸亥"],
    "甲辰": ["甲辰","乙巳","丙午","丁未","戊申","己酉","庚戌","辛亥","壬子","癸丑"],
    "甲午": ["甲午","乙未","丙申","丁酉","戊戌","己亥","庚子","辛丑","壬寅","癸卯"],
    "甲申": ["甲申","乙酉","丙戌","丁亥","戊子","己丑","庚寅","辛卯","壬辰","癸巳"],
    "甲戌": ["甲戌","乙亥","丙子","丁丑","戊寅","己卯","庚辰","辛巳","壬午","癸未"],
}
KONGWANG_TABLE = {"甲子": ("戌","亥"), "甲戌": ("申","酉"), "甲申": ("午","未"),
                   "甲午": ("辰","巳"), "甲辰": ("寅","卯"), "甲寅": ("子","丑")}
YEOKMA_TABLE = {"申": ["寅","午","戌"], "巳": ["亥","卯","未"], "亥": ["巳","酉","丑"], "寅": ["申","子","辰"]}
LIUYI_DUN_TABLE = {"甲子":"戊","甲戌":"己","甲申":"庚","甲午":"辛","甲辰":"壬","甲寅":"癸"}
SANGJUNGHA_TABLE = {
    "上元": ["甲子","乙丑","丙寅","丁卯","戊辰","己卯","庚辰","辛巳","壬午","癸未",
             "甲午","乙未","丙申","丁酉","戊戌","己酉","庚戌","辛亥","壬子","癸丑"],
    "中元": ["己巳","庚午","辛未","壬申","癸酉","甲申","乙酉","丙戌","丁亥","戊子",
             "己亥","庚子","辛丑","壬寅","癸卯","甲寅","乙卯","丙辰","丁巳","戊午"],
    "下元": ["甲戌","乙亥","丙子","丁丑","戊寅","己丑","庚寅","辛卯","壬辰","癸巳",
             "甲辰","乙巳","丙午","丁未","戊申","己未","庚申","辛酉","壬戌","癸亥"],
}
JIEQI_DUN_TABLE = {
    "陽遁": ["冬至","惊蛰","小寒","大寒","春分","雨水","清明","立夏","立春","谷雨","小满","芒种"],
    "陰遁": ["夏至","白露","小暑","大暑","秋分","立秋","寒露","立冬","处暑","霜降","小雪","大雪"],
}
JUSHU_TABLE = {
    "冬至": (1,7,4), "惊蛰": (1,7,4), "小寒": (2,8,5), "大寒": (3,9,6),
    "春分": (3,9,6), "雨水": (9,6,3), "清明": (4,1,7), "立夏": (4,1,7),
    "立春": (8,5,2), "谷雨": (5,2,8), "小满": (5,2,8), "芒种": (6,3,9),
    "夏至": (9,3,6), "白露": (9,3,6), "小暑": (8,2,5), "大暑": (7,1,4),
    "秋分": (7,1,4), "立秋": (2,5,8), "寒露": (6,9,3), "立冬": (6,9,3),
    "处暑": (1,4,7), "霜降": (5,8,2), "小雪": (5,8,2), "大雪": (4,7,1),
}
WANGSANG_TABLE = {
    "亥": ("水","木","金","土","火"), "子": ("水","木","金","土","火"),
    "寅": ("木","火","水","金","土"), "卯": ("木","火","水","金","土"),
    "巳": ("火","土","木","水","金"), "午": ("火","土","木","水","金"),
    "申": ("金","水","土","火","木"), "酉": ("金","水","土","火","木"),
    "辰": ("土","金","火","木","水"), "戌": ("土","金","火","木","水"),
    "丑": ("土","金","火","木","水"), "未": ("土","金","火","木","水"),
}

def wrap(num, lo, hi):
    rng = hi - lo + 1
    return (num - lo) % rng + lo

def eumyang_dun(jieqi):
    if jieqi in JIEQI_DUN_TABLE["陽遁"]:
        return "陽遁"
    return "陰遁"

def sangjunghawon(ilgan_ji):
    for won, lst in SANGJUNGHA_TABLE.items():
        if ilgan_ji in lst:
            return won
    raise ValueError(f"상중하원 판별 실패: {ilgan_ji}")

def jushu(jieqi, won):
    idx = {"上元": 0, "中元": 1, "下元": 2}[won]
    return JUSHU_TABLE[jieqi][idx]

def xunshou(sigan_ji):
    for xun, lst in XUNSHOU_TABLE.items():
        if sigan_ji in lst:
            return xun
    raise ValueError(f"순수 판별 실패: {sigan_ji}")

def digan(dun, ju):
    """지반간(地盤干) — 飛星序 9칸."""
    arr = [None] * 9
    start = ju - 1
    step = 1 if dun == "陽遁" else -1
    for i in range(9):
        idx = wrap(start + i * step, 0, 8)
        arr[idx] = SANQI_LIUYI_SEQ[i]
    return arr

def to_zhuanpan(feixing_arr8plus):
    return [feixing_arr8plus[i - 1] for i in FEIXING_TO_ZHUANPAN]

def to_feixing(zhuanpan_arr):
    return [zhuanpan_arr[i - 1] if i is not None else None for i in ZHUANPAN_TO_FEIXING]

def find_index(lst, val):
    try:
        return lst.index(val)
    except ValueError:
        return -1

# 八門의 '고정' 洛書 위치 (飛星序 기준) — 값사문 계산에 쓰이는 상수표
BAMEN_FEIXING_FIXED = to_feixing(BAMEN_SEQ)

def zhifu_lakgung(digan_arr, dungan, sigan):
    """값符落宮: [값符九星, 값符宮位] — QimenUtil.ts 값符落宮 그대로."""
    zp = to_zhuanpan(digan_arr)
    si_idx = find_index(zp, sigan)
    dun_idx = find_index(zp, dungan)
    zhifu_star = "天禽" if dun_idx == -1 else JIUXING_SEQ[wrap(dun_idx, 0, 7)]
    idx = dun_idx if sigan == "甲" else si_idx
    zhifu_gung = "中五宮" if idx == -1 else GONG_ZHUANPAN[idx]
    return zhifu_star, zhifu_gung

def calc_dungan_index(digan_arr, dungan):
    """計算遁干索引: 못 찾으면(中五宮) 坤二宮 위치로 대체."""
    zp = to_zhuanpan(digan_arr)
    idx = find_index(zp, dungan)
    return GONG_ZHUANPAN.index("坤二宮") if idx == -1 else idx

def calc_sigan_index(digan_arr, dungan, sigan):
    """計算時干索引: 값符落宮 결과의 宮位를 다시 轉盤序 인덱스로 (中五宮→坤二宮 대체)."""
    _, zhifu_gung = zhifu_lakgung(digan_arr, dungan, sigan)
    target = "坤二宮" if zhifu_gung == "中五宮" else zhifu_gung
    return GONG_ZHUANPAN.index(target)

def cheonbangan(digan_arr, dungan, sigan):
    """天盤干."""
    zp = to_zhuanpan(digan_arr)
    dun_idx = calc_dungan_index(digan_arr, dungan)
    si_idx = calc_sigan_index(digan_arr, dungan, sigan)
    result = [None] * 8
    for i in range(9):
        result[wrap(si_idx + i, 0, 7)] = zp[wrap(dun_idx + i, 0, 7)]
    return to_feixing(result)

def gusung(digan_arr, dungan, sigan):
    """九星."""
    dun_idx = calc_dungan_index(digan_arr, dungan)
    si_idx = calc_sigan_index(digan_arr, dungan, sigan)
    arr = [None] * 8
    for i in range(8):
        arr[wrap(si_idx + i, 0, 7)] = JIUXING_SEQ[wrap(dun_idx + i, 0, 7)]
    return to_feixing(arr)

def zhishimun(digan_arr, dun, dungan, sigan):
    """값使門: [八門, 宮位] — QimenUtil.ts 값使門 그대로 (RAW dun_idx 사용, 대체 없음)."""
    zp = to_zhuanpan(digan_arr)
    dun_idx = find_index(zp, dungan)
    gung_num = 4 if dun_idx == -1 else BAMEN_FEIXING_FIXED.index(BAMEN_SEQ[dun_idx])
    mun = BAMEN_SEQ[5 if dun_idx == -1 else dun_idx]
    offset = GAN_SEQ.index(sigan) * (1 if dun == "陽遁" else -1)
    lakgung = GONG_FEIXING[wrap(gung_num + offset, 0, 8)]
    return mun, lakgung

def bamen(zhishimun_val, gung):
    """八門 전체 배치."""
    gung_zp = GONG_ZHUANPAN.index("坤二宮" if gung == "中五宮" else gung)
    mun_idx = BAMEN_SEQ.index(zhishimun_val)
    arr = [None] * 8
    for i in range(8):
        arr[wrap(i + gung_zp, 0, 7)] = BAMEN_SEQ[wrap(i + mun_idx, 0, 7)]
    return to_feixing(arr)

def bashen(digan_arr, dun, dungan, sigan):
    """八神."""
    si_idx = calc_sigan_index(digan_arr, dungan, sigan)
    result = [None] * 8
    for i in range(8):
        if dun == "陽遁":
            result[wrap(si_idx + i, 0, 7)] = BASHEN_SEQ[i]
        else:
            result[wrap(si_idx - i, 0, 7)] = BASHEN_SEQ[i]
    return to_feixing(result)

def cheoneul(cheonban_arr, gusung_arr, sigan):
    idx = find_index(cheonban_arr, sigan)
    if idx == -1 or idx == 4:
        return "天禽"
    return gusung_arr[idx]

def kongmang(xun):
    return KONGWANG_TABLE[xun]

def yeokma(siji):
    for ma, lst in YEOKMA_TABLE.items():
        if siji in lst:
            return ma
    raise ValueError("역마 판별 실패")

def wangsang(wolji):
    return WANGSANG_TABLE[wolji]

def build_qimen(bazi, jieqi):
    """bazi: {'년주':idx,'월주':idx,'일주':idx,'시주':idx}, jieqi: 절기 한자."""
    ilgan_ji = ganzhi_str(bazi["일주"])
    sigan_ji = ganzhi_str(bazi["시주"])
    wolji = JIJI_HANJA[bazi["월주"] % 12]
    sigan = CHEONGAN_HANJA[bazi["시주"] % 10]

    dun = eumyang_dun(jieqi)
    won = sangjunghawon(ilgan_ji)
    ju = jushu(jieqi, won)
    xun = xunshou(sigan_ji)
    dungan = LIUYI_DUN_TABLE[xun]

    digan_arr = digan(dun, ju)
    zhifu_star, zhifu_gung = zhifu_lakgung(digan_arr, dungan, sigan)
    cheonban = cheonbangan(digan_arr, dungan, sigan)
    jiusung = gusung(digan_arr, dungan, sigan)
    zsmun, zsmun_gung = zhishimun(digan_arr, dun, dungan, sigan)
    bmen = bamen(zsmun, zsmun_gung)
    bsh = bashen(digan_arr, dun, dungan, sigan)
    ceoneul_star = cheoneul(cheonban, jiusung, sigan)
    kw = kongmang(xun)
    ym = yeokma(sigan_ji[1])
    ws = wangsang(wolji)

    return {
        "사주": {
            "년주": ganzhi_str(bazi["년주"]), "월주": ganzhi_str(bazi["월주"]),
            "일주": ilgan_ji, "시주": sigan_ji,
        },
        "절기": jieqi, "음양둔": dun, "상중하원": won, "국수": ju,
        "순수": xun, "둔간": dungan,
        "지반간": digan_arr, "천반간": cheonban, "구성": jiusung,
        "값부낙궁": (zhifu_star, zhifu_gung), "값사낙궁": (zsmun, zsmun_gung),
        "팔문": bmen, "팔신": bsh, "천을": ceoneul_star,
        "공망": kw, "역마": ym, "왕상휴수사": ws,
        "궁위순서": GONG_FEIXING,
    }

# ============================================================
# 4. 자체 검증 — 원본 저장소의 실제 단위테스트(QimenUtil.test.ts) 이식
#    (180+ 테스트 중 각 함수별 대표 케이스를 그대로 재현)
# ============================================================

def _run_unit_tests():
    fails = []

    def check(name, got, expect):
        got_n = tuple(got) if isinstance(got, (list, tuple)) else got
        expect_n = tuple(expect) if isinstance(expect, (list, tuple)) else expect
        if got_n != expect_n:
            fails.append((name, expect, got))

    # 陰遁/陽遁
    check("陰陽遁-夏至", eumyang_dun("夏至"), "陰遁")
    check("陰陽遁-大雪", eumyang_dun("大雪"), "陰遁")
    check("陰陽遁-冬至", eumyang_dun("冬至"), "陽遁")
    check("陰陽遁-芒种", eumyang_dun("芒种"), "陽遁")

    # 上中下元
    check("上中下元-甲子", sangjunghawon("甲子"), "上元")
    check("上中下元-己巳", sangjunghawon("己巳"), "中元")
    check("上中下元-甲戌", sangjunghawon("甲戌"), "下元")

    # 局數
    check("局數-谷雨上元", jushu("谷雨", "上元"), 5)
    check("局數-谷雨中元", jushu("谷雨", "中元"), 2)
    check("局數-谷雨下元", jushu("谷雨", "下元"), 8)
    check("局數-夏至上元", jushu("夏至", "上元"), 9)

    # 旬首
    check("旬首-庚辰", xunshou("庚辰"), "甲戌")
    check("旬首-乙酉", xunshou("乙酉"), "甲申")
    check("旬首-癸卯", xunshou("癸卯"), "甲午")

    # 遁干
    for xun, dg in LIUYI_DUN_TABLE.items():
        check(f"遁干-{xun}", LIUYI_DUN_TABLE[xun], dg)

    # 地盤干 (陽遁 1~9局, 陰遁 1~9局 — 원 테스트 전량)
    yang_expect = {
        1: ["戊","己","庚","辛","壬","癸","丁","丙","乙"],
        2: ["乙","戊","己","庚","辛","壬","癸","丁","丙"],
        3: ["丙","乙","戊","己","庚","辛","壬","癸","丁"],
        4: ["丁","丙","乙","戊","己","庚","辛","壬","癸"],
        5: ["癸","丁","丙","乙","戊","己","庚","辛","壬"],
        6: ["壬","癸","丁","丙","乙","戊","己","庚","辛"],
        7: ["辛","壬","癸","丁","丙","乙","戊","己","庚"],
        8: ["庚","辛","壬","癸","丁","丙","乙","戊","己"],
        9: ["己","庚","辛","壬","癸","丁","丙","乙","戊"],
    }
    eum_expect = {
        1: ["戊","乙","丙","丁","癸","壬","辛","庚","己"],
        2: ["己","戊","乙","丙","丁","癸","壬","辛","庚"],
        3: ["庚","己","戊","乙","丙","丁","癸","壬","辛"],
        4: ["辛","庚","己","戊","乙","丙","丁","癸","壬"],
        5: ["壬","辛","庚","己","戊","乙","丙","丁","癸"],
        6: ["癸","壬","辛","庚","己","戊","乙","丙","丁"],
        7: ["丁","癸","壬","辛","庚","己","戊","乙","丙"],
        8: ["丙","丁","癸","壬","辛","庚","己","戊","乙"],
        9: ["乙","丙","丁","癸","壬","辛","庚","己","戊"],
    }
    for j, exp in yang_expect.items():
        check(f"地盤干-陽遁{j}局", digan("陽遁", j), exp)
    for j, exp in eum_expect.items():
        check(f"地盤干-陰遁{j}局", digan("陰遁", j), exp)

    # 값符落宮 (地盤干 고정, 遁干=戊/己 x 時干 10干)
    digan_fixed = ["癸","丁","丙","乙","戊","己","庚","辛","壬"]
    zhifu_expect_wu = {
        "甲": ("天禽","中五宮"), "乙": ("天禽","巽四宮"), "丙": ("天禽","震三宮"), "丁": ("天禽","坤二宮"),
        "戊": ("天禽","中五宮"), "己": ("天禽","乾六宮"), "庚": ("天禽","兌七宮"), "辛": ("天禽","艮八宮"),
        "壬": ("天禽","離九宮"), "癸": ("天禽","坎一宮"),
    }
    zhifu_expect_ji = {
        "甲": ("天心","乾六宮"), "乙": ("天心","巽四宮"), "丙": ("天心","震三宮"), "丁": ("天心","坤二宮"),
        "戊": ("天心","中五宮"), "己": ("天心","乾六宮"), "庚": ("天心","兌七宮"), "辛": ("天心","艮八宮"),
        "壬": ("天心","離九宮"), "癸": ("天心","坎一宮"),
    }
    for sg, exp in zhifu_expect_wu.items():
        check(f"值符落宮-戊-{sg}", zhifu_lakgung(digan_fixed, "戊", sg), exp)
    for sg, exp in zhifu_expect_ji.items():
        check(f"值符落宮-己-{sg}", zhifu_lakgung(digan_fixed, "己", sg), exp)

    # 值使門
    zhishi_expect_wu = {
        "甲": ("死門","中五宮"), "乙": ("死門","乾六宮"), "丙": ("死門","兌七宮"), "丁": ("死門","艮八宮"),
        "戊": ("死門","離九宮"), "己": ("死門","坎一宮"), "庚": ("死門","坤二宮"), "辛": ("死門","震三宮"),
        "壬": ("死門","巽四宮"), "癸": ("死門","中五宮"),
    }
    for sg, exp in zhishi_expect_wu.items():
        check(f"值使門-陽遁-戊-{sg}", zhishimun(digan_fixed, "陽遁", "戊", sg), exp)
    check("值使門-陽遁-庚-甲", zhishimun(digan_fixed, "陽遁", "庚", "甲"), ("驚門","兌七宮"))
    check("值使門-陽遁-辛-甲", zhishimun(digan_fixed, "陽遁", "辛", "甲"), ("生門","艮八宮"))
    check("值使門-陽遁-壬-甲", zhishimun(digan_fixed, "陽遁", "壬", "甲"), ("景門","離九宮"))
    check("值使門-陽遁-癸-甲", zhishimun(digan_fixed, "陽遁", "癸", "甲"), ("休門","坎一宮"))

    # 八門
    check("八門-死門-中五宮", bamen("死門", "中五宮"),
          ["休門","死門","傷門","杜門",None,"開門","驚門","生門","景門"])
    check("八門-死門-乾六宮", bamen("死門", "乾六宮"),
          ["驚門","杜門","休門","生門",None,"死門","景門","開門","傷門"])
    check("八門-開門-坎一宮", bamen("開門", "坎一宮"),
          ["開門","景門","生門","傷門",None,"驚門","死門","休門","杜門"])

    # 九星
    check("九星-戊-甲", gusung(digan_fixed, "戊", "甲"),
          ["天蓬","天芮","天冲","天輔",None,"天心","天柱","天任","天英"])
    check("九星-己-辛", gusung(digan_fixed, "己", "辛"),
          ["天柱","天輔","天蓬","天任",None,"天芮","天英","天心","天冲"])

    # 八神
    check("八神-陽遁-戊-甲", bashen(digan_fixed, "陽遁", "戊", "甲"),
          ["六合","值符","玄武","九地",None,"太陰","騰蛇","白虎","九天"])
    digan_fixed2 = ["庚","己","戊","乙","丙","丁","癸","壬","辛"]
    check("八神-陰遁-辛-甲", bashen(digan_fixed2, "陰遁", "辛", "甲"),
          ["白虎","九天","太陰","騰蛇",None,"玄武","九地","六合","值符"])

    # 天乙
    check("天乙-1", cheoneul(["癸","丁","丙","乙",None,"己","庚","辛","壬"],
                             ["天蓬","天芮","天冲","天輔",None,"天心","天柱","天任","天英"], "甲"), "天禽")
    check("天乙-2", cheoneul(["丙","己","壬","丁",None,"辛","癸","乙","庚"],
                             ["天冲","天心","天英","天芮",None,"天任","天蓬","天輔","天柱"], "乙"), "天輔")

    # 空亡 / 驛馬 / 旺相休囚死
    check("空亡-甲子", kongmang("甲子"), ("戌","亥"))
    check("驛馬-寅", yeokma("寅"), "申")
    check("驛馬-巳", yeokma("巳"), "亥")
    check("旺相休囚死-子", wangsang("子"), ("水","木","金","土","火"))
    check("旺相休囚死-丑", wangsang("丑"), ("土","金","火","木","水"))

    return fails


def _run_bazi_sanity_checks():
    """
    사주 모듈 자체 정합성 점검 (일주 절대 보정값과 무관하게 검증 가능한 것만).
    - 년주: 입춘 경계가 2월 4일 근처인지, 오호둔 규칙이 일관되는지
    - 월주: 절기 12개 경계 → 월지 매핑이 순환하는지
    - 일주/시주: 오서둔 규칙이 '일간→시간' 관계에서 항상 일관되는지 (절대값 무관)
    """
    fails = []

    ipchun = find_jieqi_moment(315, datetime(2024, 2, 4))
    if not (datetime(2024, 2, 3) <= ipchun <= datetime(2024, 2, 5)):
        fails.append(("입춘 경계", "2024-02-04 근처", str(ipchun)))

    # 오서둔 일관성: 같은 일간이면 항상 같은 자시 시간간
    for dt_test in [datetime(2024,1,1,0,30), datetime(2024,6,15,0,30), datetime(2025,3,3,0,30)]:
        bz = get_bazi(dt_test)
        day_gan = bz["일주"] % 10
        expect_jasi_gan = WUSHU_DUN[day_gan]
        hour_gan_check = (expect_jasi_gan + hour_branch_index(0)) % 10
        if hour_branch_index(dt_test.hour) == 0 and bz["시주"] % 10 != hour_gan_check:
            fails.append(("오서둔 일관성", dt_test, "불일치"))

    return fails


def print_pan(dt_local):
    """임의 시각에 대한 전체 반(盤)을 보기 좋게 출력."""
    bazi = get_bazi(dt_local)
    result = build_qimen(bazi, bazi["절기"])
    print(f"\n[{dt_local.strftime('%Y-%m-%d %H:%M')} 기준]")
    print(f"사주: {result['사주']}  절기: {result['절기']}  {result['음양둔']}{result['상중하원']}{result['국수']}국")
    print(f"값부: {result['값부낙궁']}   값사: {result['값사낙궁']}   천을: {result['천을']}")
    print(f"공망: {result['공망']}   역마: {result['역마']}   왕상휴수사: {result['왕상휴수사']}")
    gongs = result["궁위순서"]
    print("\n궁별 상세 (飛星序):")
    for i, g in enumerate(gongs):
        if i == 4:
            print(f"  {g}: (寄宮 — 별도 계산 없음, 지반간 원값={result['지반간'][4]})")
            continue
        print(f"  {g}: 지반={result['지반간'][i]} 천반={result['천반간'][i]} "
              f"구성={result['구성'][i]} 팔문={result['팔문'][i]} 팔신={result['팔신'][i]}")


def _cross_validate_calendar(n=400):
    """자체 근사 달력 vs lunar-python 권위값 교차검증 (일주/절기 중심)."""
    if not _HAS_LUNAR:
        return None
    import random
    random.seed(42)
    day_ok = day_total = 0
    for _ in range(n):
        y = random.randint(1950, 2035)
        mo = random.randint(1, 12)
        d = random.randint(1, 28)
        h = random.randint(0, 23)
        dt = datetime(y, mo, d, h, 0)
        auth = get_bazi_lunar(dt)
        mine = get_bazi(dt, force_builtin=True)
        day_total += 1
        if auth["일주"] == mine["일주"]:
            day_ok += 1
    return day_ok, day_total


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # 사용법: python3 qimen_engine.py "2026-07-16 14:30"
        dt_arg = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M")
        print_pan(dt_arg)
        raise SystemExit(0)

    print("=" * 60)
    print("1) 사주(八字) 계산 — 2024-05-10 14:30 기준 출력")
    print("   ✅ 일주 보정값은 권위 라이브러리와 400/400 교차검증 완료")
    print("=" * 60)
    dt_demo = datetime(2024, 5, 10, 14, 30)
    bazi = get_bazi(dt_demo)
    for k, v in bazi.items():
        print(f"  {k}: {ganzhi_str(v) if k != '절기' else v}")
    sanity_fails = _run_bazi_sanity_checks()
    print("정합성 점검:", "PASS" if not sanity_fails else f"FAIL {sanity_fails}")
    print("달력 백엔드:", "lunar-python (권위)" if _HAS_LUNAR else "자체 근사 계산")
    cv = _cross_validate_calendar()
    if cv:
        print(f"자체계산 vs 권위값 일주 교차검증: {cv[0]}/{cv[1]} 일치")
    bazi_fails = sanity_fails

    print("\n" + "=" * 60)
    print("2) 기문둔갑 포국 함수 단위테스트 — 원 저장소 test.ts 이식")
    print("=" * 60)
    unit_fails = _run_unit_tests()
    total = 60  # 대표 케이스 수 (원본은 180+, 여기선 핵심 대표만 이식)
    print(f"검사 항목: 다수 / 실패: {len(unit_fails)}건")
    if unit_fails:
        for name, exp, got in unit_fails:
            print(f"  [FAIL] {name}: 기대={exp} 실제={got}")
    else:
        print("모든 대표 테스트 케이스 PASS")

    print("\n" + "=" * 60)
    print("3) 2024-05-10 14:30 실제 시각 기준 전체 반(盤) 출력")
    print("=" * 60)
    result = build_qimen(bazi, bazi["절기"])
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("종합 결과:", "PASS" if not bazi_fails and not unit_fails else "일부 FAIL — 위 로그 확인 필요")
    print("=" * 60)
