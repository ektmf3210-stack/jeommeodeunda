# -*- coding: utf-8 -*-
"""
리포트 자동생성기 — 웹앱의 심장

생년월일시 + 성별 + 분야 → 사주·기문 계산 → 구조화된 리포트 데이터(dict) 생성.

설계 원칙:
  · 계산·근거 = 코드가 (지어내기 0)
  · 이 dict를 LLM 프롬프트에 넣으면 → 3천자 현대어 리포트 텍스트 완성
  · LLM은 '주어진 근거 안에서만' 서술 (할루시네이션 차단)

즉 이 파일은 "리포트의 뼈대(팩트)"를 만들고,
   qimen_llm.py가 그 뼈대에 "살(문장)"을 붙인다.
"""
from datetime import datetime
from saju_engine import compute_saju
from qimen_full_reading import full_reading
from qimen_engine import get_bazi, build_qimen

# ── 분야 정의 (8분야): 캐릭터·소개·응원일화·기문게이트 + 초점/말투/강조/특화조언 ──
FIELDS = {
    "overall": {
        "name": "종합 사주풀이", "char": "유비", "gate": "景門",
        "char_intro": "덕으로 사람을 얻은 촉한의 시조. 사람의 진가를 알아본 눈",
        "cheer": "남들이 못 본 관우·제갈량의 진가를 알아본 이야기",
        "focus": "너라는 사람 전체 — 타고난 결, 강점과 그늘, 올해 큰 그림을 한 번에",
        "voice": "따뜻하고 덕 있는 큰형처럼. 품어주듯, 진심으로 응원하는 말투. 절대 겁주지 않고 편들어줌",
        "emphasis": "사주 오행 전체 + 기문 대표 요소를 통합해 '큰 그림' 위주로",
        "tips": "강점은 키우고 그늘은 사람 빌려 메우게. 올해 어디로 향할지 방향을 제시",
    },
    "wealth": {
        "name": "재물운", "char": "조조", "gate": "生門",
        "char_intro": "난세에 흙수저(환관 집안)에서 실력으로 천하를 제패한 현실주의 승부사",
        "cheer": "출신을 무시당했지만 실력과 때로 최강자가 된 이야기",
        "focus": "돈이 언제·어떤 방식으로 붙고, 어디서 새는지",
        "voice": "야망 있는 현실 승부사. 시크하고 자신만만하게, '내가 해봐서 아는데' 톤. 돈 얘기 직설적으로",
        "emphasis": "生門(이득)·삼기(대박 자리)·주도권 → 벌 때 / 헛수고구간 → 돈 새는 때",
        "tips": "버는 방식은 일간 오행 스타일대로. 투자·큰 지출은 최적월에 몰고 흉월엔 지갑 닫게",
    },
    "career": {
        "name": "직업·이직운", "char": "관우", "gate": "開門",
        "char_intro": "충의의 상징. 조조의 부귀를 뿌리치고 유비에게 돌아간 의리의 장수",
        "cheer": "편한 자리(조조)를 버리고 진짜 자기 자리로 돌아간 이야기",
        "focus": "지금 자리를 지킬지 옮길지, 이직·승진의 때",
        "voice": "의리 있고 묵직한 형님. 진중하게, 신의와 '네 자리'를 강조. 허튼소리 안 함",
        "emphasis": "開門(시작·기회)·값부(윗선·주도권)·天輔(귀인·문서)",
        "tips": "이직·제안·면접은 최적월에, 지금 자리 버팀·인내는 흉월에. 함부로 옮기지 말라 vs 지금이 때다를 분명히",
    },
    "love": {
        "name": "애정·연애운", "char": "주유", "gate": "休門",
        "char_intro": "오나라 대도독이자 소교와의 로맨스로 유명한 미남 전략가",
        "cheer": "재지 않고 마음을 열어 소교와 사랑을 이룬 이야기",
        "focus": "인연이 오는 때·방향, 지금 관계의 흐름",
        "voice": "다정하고 섬세한 미남. 로맨틱하고 부드럽게, 살짝 설레게. 공감 먼저 해주고 조언",
        "emphasis": "六合(인연)·삼기(귀인)·生門(관계 성장) → 좋은 때 / 조심할 때는 다툼 주의로",
        "tips": "고백·소개팅·만남은 최적월·좋은 방향에. 흉월엔 다툼·오해 조심. 솔로면 인연 오는 때, 커플이면 관계 흐름으로",
    },
    "life": {
        "name": "인생 흐름(대운)", "char": "사마의", "gate": "杜門",
        "char_intro": "끝까지 엎드려 기다린 끝에 천하를 얻은 대기만성의 대가",
        "cheer": "여자옷 조롱을 참고 때를 기다려 결국 이긴 이야기",
        "focus": "지금 인생이 어떤 10년 시즌이고, 언제 판이 바뀌는지",
        "voice": "진중하고 지혜로운 책사. 때와 인내를 논하듯 차분하게. 조급한 너를 다독이는 톤",
        "emphasis": "대운(10년) 흐름 중심 + 올해 큰 전환점. 기문은 '언제 움직일지'로 보조",
        "tips": "큰 결정은 지금 시즌 성격에 맞춰. 엎드릴 때와 일어설 때를 분명히 구분해줌",
    },
    "health": {
        "name": "건강운", "char": "화타", "gate": "死門", "medical_notice": True,
        "char_intro": "삼국 최고의 명의. 관우의 뼈를 긁어 독을 빼낸 신의(神醫)",
        "cheer": "강한 사람일수록 몸을 챙겨야 한다는 이야기",
        "focus": "올해 몸에서 살펴야 할 것, 무리하지 말아야 할 때",
        "voice": "다정한 명의 어르신. 걱정해주듯 따뜻하고 신뢰감 있게. 겁주지 말고 다독이며 챙김",
        "emphasis": "天芮(병·주의)·天心(치유·귀인)·헛수고구간(무리 금지 때)",
        "tips": "오행 균형으로 약한 장부를 부드럽게 짚기. 무리 금지 시기 강조. 단정 대신 '살펴보자'로. 진료 고지 필수",
    },
    "yearly": {
        "name": "올해운세·도전", "char": "장비", "gate": "傷門",
        "char_intro": "장판교에서 호통 하나로 대군을 멈춰 세운 기세·돌파의 맹장",
        "cheer": "쫄지 않고 정면으로 밀어붙여 판을 뒤집은 이야기",
        "focus": "올해 밀어붙일 도전·승부의 때와 방향",
        "voice": "화끈하고 우렁찬 돌파형. 기세 올려주며 '가보자고!' 텐션. 시원시원하게 등 떠밀어줌",
        "emphasis": "傷門(승부·돌파)·기세·이동수 → 밀어붙일 때 / 조심할 때는 무리한 충돌로",
        "tips": "승부수는 최적월에 화끈하게, 무리한 싸움·충돌은 흉월에 피하게. 올해 한 방을 짚어줌",
    },
    "today": {
        "name": "오늘의 운세·택일", "char": "공명", "gate": "開門", "free": True,
        "char_intro": "기문둔갑으로 때를 읽는 책사. 오늘 하루의 길을 짚어주는 본체 마스코트",
        "cheer": "적벽대전에서 바람의 '때'를 읽어 대역전한 이야기",
        "focus": "오늘 하루의 좋은 때·방향, 조심할 것 (택일)",
        "voice": "똑똑하고 재치 있는 책사. 오늘의 꿀팁 주듯 경쾌하고 친근하게. 짧고 명료하게",
        "emphasis": "오늘 열리는 때·방위·헛수고구간 중심 (하루 단위)",
        "tips": "오늘 중요한 일은 좋은 때에 몰고, 큰 결정·계약은 흉시 피하게. 무료라 가볍고 실용적으로",
    },
}

# ── 일간 오행 → 재물/일 스타일 (개인화 핵심) ──
ILGAN_STYLE = {
    "금": {"키워드": "추진·개척형", "방식": "네가 직접 벌이고 밀어붙여 만드는 타입. 남 손 빌리기보다 스스로 판을 짜서 거두는 게 맞다"},
    "목": {"키워드": "확장·성장형", "방식": "뻗어나가고 넓히며 버는 타입. 새 영역·새 사람으로 확장할 때 붙는다"},
    "수": {"키워드": "유통·기회형", "방식": "흐름을 읽고 움직이며 버는 타입. 정보·타이밍·유통으로 만든다"},
    "화": {"키워드": "표현·주목형", "방식": "드러내고 알려서 버는 타입. 이름·콘텐츠·인지도가 힘이 된다"},
    "토": {"키워드": "축적·신용형", "방식": "차곡차곡 쌓고 신용으로 버는 타입. 꾸준함과 안정 자산이 강점"},
}
THEME_KR = {"정재": "안정·축적", "편재": "확장·사업", "정관": "명예·자리", "편관": "도전·변동",
            "정인": "학문·귀인", "편인": "전문·직관", "식신": "표현·여유", "상관": "재능·튀는",
            "비견": "자립·독립", "겁재": "경쟁·확장"}


def best_month(dt_birth, gate, year):
    """분야 주제문(gate) 기준 올해 최적 월 스캔."""
    GOOD_STARS = {"天心","天輔","天任","天禽","天乙"}; GOOD_GODS = {"値符","六合","太陰","九天","九地"}; SANQI = {"乙","丙","丁"}
    res = []
    for m in range(1, 13):
        p = build_qimen(*[(lambda b:(b,b["절기"]))(get_bazi(datetime(year,m,15,12,0)))][0])
        i = p["팔문"].index(gate); sc = 0
        if p["구성"][i] in GOOD_STARS: sc += 2
        if p["팔신"][i] in GOOD_GODS: sc += 2
        if p["천반간"][i] in SANQI: sc += 1
        if p["지반간"][i] in SANQI: sc += 1
        res.append((m, sc))
    res.sort(key=lambda x: -x[1])
    return [m for m, _ in res[:3]]


def generate_report_data(dt_birth, gender, field_key, target_year=None):
    """리포트의 '뼈대(팩트)' 생성. 이 dict를 LLM에 넘겨 문장화."""
    if target_year is None:
        target_year = datetime.now().year
    field = FIELDS[field_key]
    saju = compute_saju(dt_birth, gender)
    ilgan_oh = saju["일간오행"]
    style = ILGAN_STYLE[ilgan_oh]
    months = best_month(dt_birth, field["gate"], target_year)
    top_m = months[0]
    qm = full_reading(target_year, top_m, field["gate"])
    # 이동수(이동·변화 방위)는 사람·해 단위 지표라 분야마다 달라 보이면 안 됨 →
    # 올해 대표 판(고정 기준) 하나에서 뽑아 모든 분야에 동일하게 적용.
    canon = full_reading(target_year, 7, "生門")
    if canon.get("이동수"):
        qm["이동수"] = canon["이동수"]

    return {
        "분야": field["name"],
        "캐릭터": field["char"],
        "캐릭터소개": field["char_intro"],
        "응원일화": field["cheer"],
        "초점": field.get("focus", ""),
        "말투": field.get("voice", ""),
        "강조": field.get("emphasis", ""),
        "특화조언": field.get("tips", ""),
        "의료고지": field.get("medical_notice", False),
        "사주": {
            "일간": saju["일간"], "일간오행": ilgan_oh,
            "스타일키워드": style["키워드"], "스타일방식": style["방식"],
            "오행분포": saju["오행분포"],
            "강한오행": max(saju["오행분포"], key=saju["오행분포"].get),
            "없는오행": [k for k, v in saju["오행분포"].items() if v == 0],
            "십성": saju.get("십성", {}),
            "대운": f"{saju['현재대운']['간지_kr']} {saju['현재대운']['천간십성']}({THEME_KR.get(saju['현재대운']['천간십성'],'')})",
            "대운기간": f"{saju['현재대운']['시작연도']}~{saju['현재대운']['끝연도']}",
            "세운": (lambda y: f"{y['간지_kr']} {y['천간십성']}({THEME_KR.get(y['천간십성'],'')})" if y else "")(
                next((y for y in saju.get("세운", []) if y["연도"] == target_year), None)),
        },
        "기문": {
            "최적월": months, "대표월": top_m,
            "요소": {k: v for k, v in qm.items() if v},
        },
        "타겟연도": target_year,
    }


if __name__ == "__main__":
    import json
    d = generate_report_data(datetime(1991,3,21,19,56), "F", "wealth")
    print("=== 리포트 뼈대 자동생성 (재물운) ===")
    print(json.dumps(d, ensure_ascii=False, indent=2))
