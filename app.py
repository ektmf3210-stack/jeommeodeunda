# -*- coding: utf-8 -*-
"""
🪭 점며든다 — 사주 x 기문둔갑 운세 웹앱 (Y2K 힙 리뉴얼)

실행:
  pip install flask lunar-python
  python3 app.py  →  http://127.0.0.1:5000

LLM 자동 리포트(선택):
  export ANTHROPIC_API_KEY=sk-...   (또는 OPENAI_API_KEY)
  export QIMEN_MODEL=claude-sonnet-5

구조:
  /                인트로(제갈량 채팅) → 입력 → 결과/훅 → 리포트  (SPA, 한 페이지)
  /api/report      사주·기문 계산 → 프롬프트 → (LLM) → 리포트
  /char/<file>     캐릭터 이미지
"""
import os, base64, json as _json, uuid, urllib.request, urllib.error, hmac, hashlib, time
from datetime import datetime
from flask import (Flask, request, jsonify, render_template_string,
                   send_from_directory, redirect, Response, stream_with_context)

from report_prompt import (make_full_prompt, make_followup_prompt, make_naming_prompt,
                           build_naming_prompt, make_analysis_prompt)
from report_generator import FIELDS
from qimen_llm import generate_interpretation, stream_interpretation
from buchae_system import (get_balance, open_report, charge_buchae,
                           can_open, BUCHAE_PACKAGES, get_or_create_user, grant_buchae)

app = Flask(__name__)

# ══════════ 건당 결제(990원) · 지갑 없이 1회용 서명 토큰 ══════════
PRICE = 990
PAID_ITEMS = {"report", "naming", "analysis", "followup"}
ITEM_NAME = {"report": "사주 리포트", "naming": "작명", "analysis": "이름 분석", "followup": "추가 질문"}
UNLOCK_SECRET = os.environ.get("UNLOCK_SECRET", "jeom2026-unlock-secret-change-me")


def make_unlock(item, ttl=1800):
    """결제 성공 시 발급하는 1회용(짧은 만료) 서명 토큰. 저장 안 함."""
    exp = int(time.time()) + ttl
    body = f"{item}.{exp}"
    sig = hmac.new(UNLOCK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{body}.{sig}"


def check_unlock(token, item):
    """토큰이 이 상품에 유효하고 안 만료됐나."""
    try:
        it, exp, sig = (token or "").split(".")
    except Exception:
        return False
    if it != item or int(exp) < time.time():
        return False
    good = hmac.new(UNLOCK_SECRET.encode(), f"{it}.{exp}".encode(), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(sig, good)


def current_user():
    from flask import request as _rq
    return _rq.cookies.get("uid")


PAGE = r"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>점며든다 · 내 인생, 어떻게 이겨?</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Jua&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--navy:#241056;--blue:#2b2bff;--pink:#ff2e86;--yellow:#ffdf3d;--purple:#8b7bff;--card:#fffdf7;--line:#e6dff5}
*{margin:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:'Noto Sans KR',sans-serif;color:var(--navy);min-height:100vh;
background:radial-gradient(circle at 12% 8%,#fff6a8 0,#fff6a800 30%),radial-gradient(circle at 90% 6%,#a8f0e0 0,#a8f0e000 28%),linear-gradient(165deg,#c4ccff,#ffc9e8 54%,#ffe6a8) fixed;}
.ph{max-width:410px;margin:0 auto;padding:0 15px;min-height:100vh}
.screen{display:none}.screen.on{display:block}
.logo{font-family:'Black Han Sans';letter-spacing:-1px;background:linear-gradient(180deg,#ff8fd0,#8b7bff 50%,#37e0c8);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:2px var(--navy);filter:drop-shadow(2px 2px 0 var(--navy))}
.spk{position:absolute;pointer-events:none}
.skip{position:fixed;top:12px;right:14px;z-index:30;background:#fffdf7;border:2px solid var(--navy);border-radius:14px;padding:6px 12px;font-family:'Jua',sans-serif;font-size:12px;color:var(--navy);box-shadow:2px 2px 0 var(--yellow);cursor:pointer}
/* 인트로 채팅 */
.hd{position:sticky;top:0;z-index:5;padding:16px 6px 10px;text-align:center;background:linear-gradient(#c8cfffee,#c8cfff00)}
.hd .logo{font-size:27px}
.who{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px}
.wa{width:34px;height:34px;border-radius:50%;border:2.5px solid var(--navy);background:#fff;object-fit:cover;box-shadow:2px 2px 0 #ff6fb3}
.wn{font-family:'Jua';font-size:13px;text-align:left;line-height:1.2}
.wn small{display:block;font-size:10px;color:#1a9a5a;font-weight:700;font-family:'Noto Sans KR'}
.dot{width:7px;height:7px;border-radius:50%;background:#1fd36a;display:inline-block;margin-right:3px;box-shadow:0 0 0 2px #d3fbe4}
.chat{padding:8px 2px 120px}
.row{display:flex;gap:8px;align-items:flex-end;margin:10px 0;opacity:0;transform:translateY(10px);transition:.4s}
.row.show{opacity:1;transform:none}
.av{width:30px;height:30px;border-radius:50%;border:2px solid var(--navy);background:#fff;object-fit:cover;flex:0 0 auto}
.bub{background:var(--card);border:2.5px solid var(--navy);border-radius:16px 16px 16px 5px;padding:10px 13px;font-size:13.5px;line-height:1.6;max-width:80%;box-shadow:3px 3px 0 var(--purple);font-weight:500}
.bub b{color:var(--pink)}.bub em{font-style:normal;color:var(--blue);font-weight:700}
.tb{background:var(--card);border:2.5px solid var(--navy);border-radius:16px;padding:12px 14px;box-shadow:3px 3px 0 var(--purple)}
.tb span{width:7px;height:7px;background:var(--purple);border-radius:50%;display:inline-block;margin:0 2px;animation:bnc 1s infinite}
.tb span:nth-child(2){animation-delay:.15s}.tb span:nth-child(3){animation-delay:.3s}
@keyframes bnc{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
.ctaw{position:fixed;bottom:0;left:0;right:0;display:flex;justify-content:center;padding:14px;background:linear-gradient(#ffe6a800,#ffe6a8);opacity:0;transition:.5s;z-index:6}
.ctaw.show{opacity:1}
.cta{width:100%;max-width:380px;padding:16px;border:3px solid var(--navy);border-radius:18px;background:var(--blue);color:#fff;font-family:'Black Han Sans';font-size:18px;box-shadow:4px 5px 0 var(--yellow),4px 5px 0 3px var(--navy);cursor:pointer}
.cta:active{transform:translate(2px,2px);box-shadow:2px 3px 0 var(--yellow),2px 3px 0 3px var(--navy)}
/* 입력 */
.top{text-align:center;padding:22px 0 8px;position:relative}
.top .logo{font-size:40px}
.slo{font-family:'Jua';font-size:16px;margin-top:6px}.slo em{color:var(--pink);font-style:normal}
.bal{position:absolute;top:16px;right:8px;background:#fff;border:2px solid var(--navy);border-radius:16px;padding:4px 10px;font-size:11px;font-family:'Jua';color:var(--blue);box-shadow:2px 2px 0 var(--yellow);cursor:pointer}
.card{background:var(--card);border:3px solid var(--navy);border-radius:24px;padding:18px;margin:10px 0 16px;box-shadow:6px 6px 0 var(--purple)}
label{font-family:'Jua';font-size:13px;color:var(--navy);display:block;margin:12px 0 6px}
label:first-child{margin-top:0}
input,select{width:100%;padding:12px;border:2.5px solid var(--navy);border-radius:13px;background:#fff;color:var(--navy);font-size:14px;font-family:inherit;font-weight:500}
input:focus,select:focus{outline:none;border-color:var(--blue)}
.rowf{display:flex;gap:8px}.rowf>div{flex:1}
.fields{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px}
.fld{border:2.5px solid var(--navy);border-radius:14px;padding:12px 6px;text-align:center;cursor:pointer;font-size:13px;background:#fff;font-family:'Jua';box-shadow:2px 2px 0 #cfd6ff}
.fld .fi{font-size:20px;display:block;margin-bottom:3px}
.fld.on{background:var(--yellow);box-shadow:2px 2px 0 var(--pink)}
.go{width:100%;margin-top:16px;padding:16px;border:3px solid var(--navy);border-radius:18px;background:var(--blue);color:#fff;font-family:'Black Han Sans';font-size:18px;box-shadow:4px 5px 0 var(--yellow),4px 5px 0 3px var(--navy);cursor:pointer}
.go:active{transform:translate(2px,2px)}
.spin{display:none;text-align:center;color:var(--blue);font-family:'Jua';margin:22px 0;font-size:15px}
.back{background:none;border:0;font-family:'Jua';font-size:13px;color:var(--navy);cursor:pointer;padding:14px 4px 4px}
/* 결과 */
.rp{background:var(--card);border:3px solid var(--navy);border-radius:24px;overflow:hidden;margin-bottom:16px;box-shadow:6px 6px 0 var(--purple)}
.hero{display:flex;align-items:center;gap:12px;padding:16px 15px;background:var(--yellow);border-bottom:3px solid var(--navy);position:relative}
.disc{position:relative;flex:0 0 auto}
.disc:before{content:"";position:absolute;inset:-5px;background:#ff6fb3;border-radius:50%;border:3px solid var(--navy)}
.hava{position:relative;width:72px;height:72px;border-radius:50%;background:#fff;border:3px solid var(--navy);object-fit:cover;display:block}
.hero .tag{display:inline-block;background:var(--pink);color:#fff;font-family:'Jua';font-size:11px;padding:2px 11px;border-radius:12px;margin-bottom:5px;border:2px solid var(--navy)}
.hero .who2{font-family:'Black Han Sans';font-size:25px}
.hero .sub{font-size:11px;color:#7a5a30;margin-top:2px;font-weight:600}
.judge{padding:15px 16px;font-size:13.5px;line-height:1.8;background:#eef1ff;border-bottom:3px dashed #b9c3ff}
.judge .lb{display:inline-block;font-family:'Jua';font-size:12px;color:#fff;background:var(--blue);padding:2px 12px;border-radius:12px;margin-bottom:9px;border:2px solid var(--navy)}
.judge b{color:var(--pink)}
.hookwrap{position:relative;padding:16px 16px 18px}
.htitle{font-family:'Black Han Sans';font-size:18px;margin-bottom:12px}.htitle em{color:var(--blue);font-style:normal}
.hr{display:flex;flex-direction:column;gap:3px;padding:9px 0;border-bottom:2px solid #f0eafc}
.hr .k{font-family:'Jua';font-size:11.5px;color:#9159d6}.hr .v{font-size:12.5px;color:#3a2a5a}
.blur{filter:blur(6px)}
.pw{position:absolute;inset:48px 0 0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;background:linear-gradient(180deg,#fffdf722,#fffdf7e0 44%,#fffdf7);padding:0 16px}
.plock{font-family:'Jua';font-size:13px;color:var(--navy);background:var(--yellow);padding:4px 15px;border-radius:16px;border:2.5px solid var(--navy);transform:rotate(-2deg);box-shadow:2px 2px 0 var(--pink)}
.pmsg{font-family:'Black Han Sans';font-size:18px;text-align:center;line-height:1.35}.pmsg em{color:var(--pink);font-style:normal}
.pk{display:flex;gap:8px;width:100%}
.pkg{flex:1;border:2.5px solid var(--navy);border-radius:16px;padding:11px 4px;text-align:center;background:#fff;box-shadow:2px 2px 0 #b9c3ff;position:relative;cursor:pointer}
.pkg.best{background:var(--pink);box-shadow:2px 2px 0 var(--navy)}
.pkg.best .n,.pkg.best .w{color:#fff}
.pkg.best:after{content:"찐이득 ✦";position:absolute;top:-11px;left:50%;transform:translateX(-50%) rotate(-4deg);font-family:'Jua';font-size:9.5px;background:var(--yellow);color:var(--navy);padding:2px 8px;border-radius:10px;border:2px solid var(--navy);white-space:nowrap}
.pkg .n{font-family:'Black Han Sans';font-size:15px;color:var(--blue)}.pkg .w{font-family:'Jua';font-size:12px;color:#7a6a9a;margin-top:2px}
.pkg .ptag{font-family:'Jua';font-size:9px;color:#fff;background:var(--blue);border-radius:8px;padding:1px 5px;margin-top:3px;display:inline-block}
.btn2{width:100%;padding:14px;border:3px solid var(--navy);border-radius:15px;background:var(--blue);color:#fff;font-family:'Black Han Sans';font-size:16px;box-shadow:3px 4px 0 var(--yellow);cursor:pointer}
.rpt{padding:17px;white-space:pre-wrap;line-height:1.95;font-size:14.5px;color:#2e2148}.rpt b{color:var(--pink)}
.tagf{padding:0 17px 15px;font-size:10.5px;color:#a99acb;font-family:'Jua'}
#preopen{background:repeating-linear-gradient(45deg,#ffdf3d,#ffdf3d 12px,#241056 12px,#241056 24px);
  color:#fff;text-align:center;font-family:'Jua';font-size:12.5px;padding:8px 10px;border-radius:12px;margin:6px 0 4px;
  text-shadow:1px 1px 0 #241056,-1px -1px 0 #241056;border:2px solid #241056}
.secdiv{display:flex;align-items:center;gap:10px;margin:26px 2px 12px;color:var(--navy)}
.secdiv:before,.secdiv:after{content:"";flex:1;height:3px;background:repeating-linear-gradient(90deg,var(--navy) 0 7px,transparent 7px 12px)}
.secdiv span{font-family:'Black Han Sans';font-size:16px;white-space:nowrap}
.nmenu{display:flex;gap:7px;margin-bottom:6px}
.nmb{flex:1;border:2.5px solid var(--navy);border-radius:13px;background:#fff;font-family:'Jua';font-size:13.5px;padding:10px 0;cursor:pointer;box-shadow:2px 2px 0 #cfd8ff}
.nmb.on{background:var(--pink);color:#fff;box-shadow:2px 2px 0 var(--navy)}
.namebox{margin:8px 0 6px;padding:16px;background:linear-gradient(135deg,#fff6fb,#eef3ff);border:2.5px solid var(--navy);border-radius:18px;box-shadow:4px 4px 0 var(--purple)}
.nbtitle{font-family:'Black Han Sans';font-size:17px}
.nbtag{font-family:'Jua';font-size:11px;color:#fff;background:var(--navy);padding:2px 8px;border-radius:10px;margin-left:4px;white-space:nowrap}
.nbsub{font-family:'Jua';font-size:12px;color:#7a6b95;margin:6px 0 10px;line-height:1.5}
.go2{background:var(--pink)}
.ncard{background:#fff;border:2.5px solid var(--navy);border-radius:16px;padding:13px 14px;margin:10px 0;box-shadow:3px 3px 0 var(--blue)}
.nname{font-family:'Black Han Sans';font-size:20px}.nname .hj{color:var(--pink);font-size:16px;margin-left:6px}
.nmean{font-family:'Jua';font-size:12.5px;color:#6a5b85;margin:3px 0 8px}
.sgrid{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.sg{font-family:'Jua';font-size:11.5px;padding:5px 8px;border-radius:9px;background:#f3eefc;display:flex;justify-content:space-between}
.sg b{color:var(--navy)}.sg .ok{color:#e0489b;font-weight:900}
.nsun{font-family:'Jua';font-size:13px;background:#fff;border:2px dashed var(--pink);border-radius:14px;padding:11px 13px;margin:10px 0;line-height:1.7}
.pkgbtns{display:flex;gap:6px;margin:8px 0}
.tabb{flex:1;border:2.5px solid var(--navy);border-radius:12px;background:#fff;font-family:'Jua';font-size:13px;padding:7px 0;cursor:pointer}
.tabb.on{background:var(--navy);color:#fff}
.poprow{font-family:'Jua';font-size:11.5px;margin-bottom:8px}
.popgrid{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.popitem{font-family:'Jua';font-size:13px;background:#fff;border:2px solid var(--navy);border-radius:10px;padding:6px 9px;display:flex;align-items:center;gap:5px}
.popitem .pr{font-family:'Black Han Sans';color:var(--pink);min-width:18px}
.popitem .pp{margin-left:auto;font-size:10.5px;color:#a99}
.poprc{font-size:9.5px;color:#b0a0c0;margin-top:8px;font-family:'Jua'}
.cur{display:inline-block;color:var(--pink);animation:blink 1s steps(1) infinite;font-weight:900}
@keyframes blink{50%{opacity:0}}
.fu{border-top:3px dashed var(--line);padding:15px 16px 18px;background:#faf7ff}
.futitle{font-family:'Black Han Sans';font-size:14.5px;margin-bottom:10px}
.futitle span{font-family:'Jua';font-size:11px;color:#fff;background:var(--pink);padding:2px 8px;border-radius:10px;margin-left:4px}
#fulog{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.fubub{padding:9px 12px;border-radius:14px;font-size:13px;line-height:1.6;max-width:88%;border:2px solid var(--navy)}
.fubub.me{align-self:flex-end;background:var(--blue);color:#fff;border-radius:14px 14px 4px 14px}
.fubub.ch{align-self:flex-start;background:#fff;border-radius:14px 14px 14px 4px;box-shadow:2px 2px 0 var(--purple)}
.fubub.ch b{color:var(--pink)}
.furow{display:flex;gap:7px}
.furow input{flex:1;padding:11px;border:2.5px solid var(--navy);border-radius:12px;font-size:13px;font-family:inherit}
.furow button{border:2.5px solid var(--navy);border-radius:12px;background:var(--blue);color:#fff;font-family:'Jua';font-size:13px;padding:0 15px;cursor:pointer}
.foot{font-size:10px;color:#7a6a9a;text-align:center;padding:6px 18px 30px;line-height:1.7}
</style></head><body>
<div class="ph">

<!-- 인트로 채팅 -->
<section class="screen on" id="s-intro">
  <button class="skip" onclick="toInput()">건너뛰기 →</button>
  <span class="spk" style="left:18px;top:120px;color:#ff2e86;font-size:18px">✦</span>
  <span class="spk" style="right:20px;top:175px;color:#2b2bff;font-size:18px">★</span>
  <div class="hd"><div class="logo">점며든다</div>
    <div class="who"><img class="wa" src="/char/gongmyeong.png" alt="공명">
      <div class="wn">제갈공명<small><span class="dot"></span>지금 접속 중</small></div></div>
  </div>
  <div class="chat" id="chat"></div>
</section>

<!-- 입력 -->
<section class="screen" id="s-input">
  <div id="preopen" style="display:none">🚧 오픈 준비 중이에요 · 곧 정식으로 만나요! (지금은 미리보기)</div>
  <div class="top"><div class="bal" id="bal">🔎 건당 990원</div>
    <div class="logo">점며든다</div>
    <div class="slo">내 인생, <em>어떻게 이겨?</em> 🪭</div></div>
  <div class="secdiv"><span>🔎 이름 · 작명</span></div>
  <div class="nmenu">
    <button class="nmb on" id="nmbA" onclick="nameMenu('analyze')">🔎 이름분석</button>
    <button class="nmb" id="nmbN" onclick="nameMenu('naming')">✍️ 작명</button>
    <button class="nmb" id="nmbP" onclick="nameMenu('pop')">🏆 인기순위</button>
  </div>
  <div id="panel-naming" style="display:none">
  <div class="namebox">
    <div class="nbtitle">🎏 아이 이름 짓기 <span class="nbtag">정통 수리성명학 · 부채 5개</span></div>
    <div class="nbsub">아기 사주로 부족한 기운을 찾아, 사격(초년·청년·장년·말년운)이 다 좋은 이름만 골라줘</div>
    <label>아기 성 (한글로 한 글자, 예: 김)</label>
    <input type="text" id="nseong" maxlength="1" placeholder="김" oninput="checkSeong()">
    <div id="nseonghjbox" style="display:none">
      <label>성씨 한자 선택 <span style="color:#e0489b">(획수가 달라 결과가 바뀌어요)</span></label>
      <select id="nseonghj"></select>
    </div>
    <label>작명 방식</label>
    <select id="nmode" onchange="nmodeUI()">
      <option value="auto">사주 맞춤 (자동 추천)</option>
      <option value="fix1">특정 글자 넣기 · 앞자리</option>
      <option value="fix2">돌림자/특정 글자 · 뒷자리</option>
      <option value="single">외자 (한 글자 이름)</option>
    </select>
    <div id="nfixbox" style="display:none">
      <input type="text" id="nfix" maxlength="1" placeholder="넣을 글자 (예: 준 또는 俊)">
    </div>
    <label>아기 태어난 날 (양력) · 시간 모르면 비워둬도 돼</label>
    <div class="rowf"><div><input type="date" id="ndate"></div><div><input type="time" id="ntime"></div></div>
    <label>성별</label>
    <select id="ngender"><option value="M">남아</option><option value="F">여아</option></select>
    <button class="go go2" onclick="runNaming()">🎏 이름 짓기 · 990원</button>
  </div>
  <div class="spin" id="nspin">🎏 공명이가 획수를 세는 중…</div>
  <div id="nresult"></div>
  </div>
  <div id="panel-analyze">
  <div class="namebox" style="background:linear-gradient(135deg,#eef6ff,#f6f0ff)">
    <div class="nbtitle">🔎 내 이름 분석 <span class="nbtag" style="background:var(--blue)">성명 감정 · 부채 2개</span></div>
    <div class="nbsub">지금 내 이름, 잘 지어졌을까? 발음오행 흐름·사주 궁합·획수운(사격)으로 장단점 진단해줄게</div>
    <label>이름 (한글, 예: 홍길동)</label>
    <input type="text" id="aname" maxlength="5" placeholder="홍길동">
    <label>이름 한자 (알면 입력, 몰라도 OK)</label>
    <input type="text" id="ahanja" maxlength="5" placeholder="예: 金瑞娟 · 모르면 비워둬">
    <label>태어난 날 (양력) · 시간 모르면 비워둬도 돼</label>
    <div class="rowf"><div><input type="date" id="adate"></div><div><input type="time" id="atime"></div></div>
    <label>성별</label>
    <select id="agender"><option value="F">여성</option><option value="M">남성</option></select>
    <button class="go" style="background:var(--blue)" onclick="runAnalyze()">🔎 내 이름 진단 · 990원</button>
  </div>
  <div class="spin" id="aspin">🔎 공명이가 획수를 세는 중…</div>
  <div id="aresult"></div>
  </div>
  <div id="panel-pop" style="display:none">
  <div class="namebox" style="background:linear-gradient(135deg,#fffdf0,#fff2f8)">
    <div class="nbtitle">🏆 인기 이름 순위 <span class="nbtag" style="background:var(--yellow);color:var(--navy)">무료</span></div>
    <div class="nbsub" id="popsub">대법원 출생신고 통계 · 작명 트렌드 참고용</div>
    <div class="pkgbtns"><button class="tabb on" id="tabB" onclick="popTab('남아')">👦 남아</button><button class="tabb" id="tabG" onclick="popTab('여아')">👧 여아</button></div>
    <div id="poplist"><div class="nmean">불러오는 중…</div></div>
  </div>
  </div>
  <div class="secdiv"><span>🔮 사주 · 기문 운세</span></div>
  <div class="card">
    <label>태어난 날 (양력)</label>
    <div class="rowf"><div><input type="date" id="date"></div><div><input type="time" id="time" value="12:00"></div></div>
    <label>성별</label>
    <select id="gender"><option value="F">여성</option><option value="M">남성</option></select>
    <label>뭐가 제일 궁금해?</label>
    <div class="fields" id="fields"></div>
    <button class="go" onclick="run()">🪭 점 보러가기</button>
  </div>
  <div class="spin" id="spin">🪭 공명이가 부채를 펼치는 중…</div>
  <div id="result"></div>
  <p class="foot">전통 술수 기반 참고·오락용 · 계산은 검증된 엔진, 해석은 AI<br>중요한 결정은 본인 판단으로!<br><a href="/policy" style="color:#8a7ba5;text-decoration:underline">이용약관 · 개인정보처리방침 · 환불정책</a></p>
</section>

</div>

<div class="ctaw" id="ctaw"><button class="cta" onclick="toInput()">🔎 내 이름 풀러가기 →</button></div>

<script>
const FIELDS=%%FIELDS%%;
const PREOPEN=("%%PREOPEN%%"==="1");
const ICON={overall:'🀄',wealth:'💰',career:'💼',love:'💕',life:'🌊',health:'🩺',yearly:'⚔️',today:'📅'};
const CHAR={overall:'yubi',wealth:'jojo',career:'gwanu',love:'juyu',life:'samaui',health:'hwata',yearly:'jangbi',today:'gongmyeong'};
let sel='wealth';

/* ── 인트로 채팅 ── */
const MSG=[
 "안녕 👋 나 <em>제갈량</em>, 별명 공명이야",
 "나 옛날에 전쟁을 힘이 아니라 <em>'기운'과 '때'</em>를 읽어서 이겼어 😎",
 "<em>적벽대전</em> 때도 바람 방향까지 계산해서, 쪽수로 밀리던 싸움을 <b>불바다</b>로 뒤집었지 🔥🌬️",
 "근데 그 '기운', 전쟁에만 있는 게 아니야. <em>네 이름</em>에도 흐르고 있어 👀",
 "이름은 평생 수만 번 불리는 <em>주문</em> 같은 거거든. 부를 때마다 기운이 흘러 ✨",
 "그래서 어떤 이름은 운을 밀어주고, 어떤 이름은 살짝 어긋나 있어",
 "네 이름 속 <b>발음 기운·사주 궁합·획수 운</b>까지 내가 딱 풀어줄게 🔎",
 "아이 이름 짓기도, 네 사주 보기도 다 돼 ㅎㅎ 자, <em>네 이름</em>부터 볼까? 😉"
];
const chat=document.getElementById('chat');
let mi=0, introLeft=false;
function smartScroll(){if(introLeft)return;if(window.innerHeight+window.scrollY>=document.body.scrollHeight-150)scrollTo(0,document.body.scrollHeight);}
function typing(){if(introLeft)return;const t=document.createElement('div');t.className='row';t.id='typing';
  t.innerHTML='<img class="av" src="/char/gongmyeong.png"><div class="tb"><span></span><span></span><span></span></div>';
  chat.appendChild(t);t.classList.add('show');smartScroll();}
function nextMsg(){if(introLeft)return;const t=document.getElementById('typing');if(t)t.remove();
  if(mi>=MSG.length){document.getElementById('ctaw').classList.add('show');return;}
  const r=document.createElement('div');r.className='row';
  r.innerHTML='<img class="av" src="/char/gongmyeong.png"><div class="bub">'+MSG[mi]+'</div>';
  chat.appendChild(r);requestAnimationFrame(()=>r.classList.add('show'));smartScroll();mi++;
  setTimeout(()=>{if(introLeft)return;typing();setTimeout(nextMsg,1100);},Math.min(1500,700+MSG[mi-1].replace(/<[^>]+>/g,'').length*22));}
setTimeout(()=>{if(introLeft)return;typing();setTimeout(nextMsg,900);},500);

/* ── 화면 전환 ── */
function toInput(){introLeft=true;
  document.getElementById('s-intro').classList.remove('on');
  const cw=document.getElementById('ctaw');cw.classList.remove('show');cw.style.display='none';
  document.getElementById('s-input').classList.add('on');scrollTo(0,0);refreshBal();loadPop();
  if(PREOPEN){var pb=document.getElementById('preopen');if(pb)pb.style.display='block';}}

/* ── 입력 폼 ── */
const fbox=document.getElementById('fields');
Object.entries(FIELDS).forEach(([k,v])=>{const d=document.createElement('div');
  d.className='fld'+(k===sel?' on':'');d.innerHTML='<span class="fi">'+(ICON[k]||'🪭')+'</span>'+v;
  d.onclick=()=>{sel=k;document.querySelectorAll('.fld').forEach(x=>x.classList.remove('on'));d.classList.add('on');};
  fbox.appendChild(d);});
document.getElementById('date').value='1996-05-12';
/* ── 결제 성공 후 복귀: 토큰으로 잠금해제하고 결과 생성 ── */
function dispatchUnlock(item,input,u){
  if(item==='report')doReport(input,u);
  else if(item==='naming')doNaming(input,u);
  else if(item==='analysis')doAnalyze(input,u);
  else if(item==='followup')doFollowup(input,u);
}
window._unlocks=window._unlocks||{};
(function(){
  const P=new URLSearchParams(location.search);const u=P.get('u'),item=P.get('item');
  if(!u||!item)return;
  let pend={};try{pend=JSON.parse(sessionStorage.getItem('pending')||'{}');}catch(e){}
  sessionStorage.removeItem('pending');
  history.replaceState({},'',location.pathname);
  window._unlocks[item]=u;
  toInput();
  if(item==='naming')nameMenu('naming');
  else if(item==='analysis')nameMenu('analyze');
  const NM={report:'사주리포트',naming:'작명',analysis:'이름분석',followup:'추가질문'};
  if(pend.item===item){setTimeout(()=>dispatchUnlock(item,pend.input,u),60);}
  else{setTimeout(()=>alert('🔓 테스트 잠금해제: '+(NM[item]||item)+'\n이제 그 기능을 결제 없이 눌러볼 수 있어!'),200);}
})();

function refreshBal(){const b=document.getElementById('bal');if(b)b.textContent='🔎 건당 990원';}
function payFor(item,input){
  if(window._unlocks&&window._unlocks[item]){dispatchUnlock(item,input,window._unlocks[item]);return;}
  if(PREOPEN){alert('🚧 아직 오픈 준비 중이에요!\\n조금만 기다려 주세요 🙏 곧 정식으로 만나요!');return;}
  sessionStorage.setItem('pending',JSON.stringify({item:item,input:input}));location.href='/pay?item='+item;
}

async function run(){
  const inp={date:document.getElementById('date').value,time:document.getElementById('time').value,gender:document.getElementById('gender').value,field:sel};
  if(!inp.date){alert('태어난 날을 넣어줘~');return;}
  document.getElementById('spin').style.display='block';document.getElementById('result').innerHTML='';
  const d=await (await fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(inp)})).json();
  document.getElementById('spin').style.display='none';d._input=inp;renderReport(d,null);
  document.getElementById('result').scrollIntoView({behavior:'smooth'});
}
async function doReport(input,unlock){
  sel=input.field||sel;
  ['date','time','gender'].forEach(k=>{const el=document.getElementById(k);if(el&&input[k])el.value=input[k];});
  document.getElementById('spin').style.display='block';document.getElementById('result').innerHTML='';
  const d=await (await fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)})).json();
  document.getElementById('spin').style.display='none';d._input=input;renderReport(d,unlock);
  document.getElementById('result').scrollIntoView({behavior:'smooth'});
}
function renderReport(d,unlock){
  const R=document.getElementById('result');
  if(d.error){R.innerHTML='<div class="card">오류: '+d.error+'</div>';return;}
  const img='/char/'+(CHAR[sel]||'gongmyeong')+'.png';
  let h='<div class="rp"><div class="hero"><div class="disc"><img class="hava" src="'+img+'"></div>'
    +'<div><span class="tag">'+(ICON[sel]||'🪭')+' '+d.field+'</span><div class="who2">'+d.char+'</div></div></div>';
  h+='<div class="judge"><span class="lb">✦ 네 판 · 무료로 슬쩍</span>'+d.saju_line+'</div>';
  const paid=unlock||d.free;
  if(!paid){
    let rows='';(d.hook||[]).forEach(e=>{rows+='<div class="hr"><span class="k">'+e.label+'</span><span class="v">'+e.text+'</span></div>';});
    h+='<div class="hookwrap"><div class="htitle">그래서 <em>언제·어디·어떻게?</em> 👀</div>'
      +'<div class="blur">'+rows+'</div>'
      +'<div class="pw"><div class="plock">🔒 여기부턴 결제하고!</div><div class="pmsg">'+d.char+'의 전체 리포트를 딱 열어줄게</div>'
      +'<button class="go" onclick=\'payFor("report",'+JSON.stringify(d._input)+')\'>🔓 전체 리포트 · 990원</button></div></div>';
  }else{
    h+='<div class="rpt" id="rpt"><span class="cur">▍</span></div><div class="tagf" id="tagf">🪭 '+d.char+'가 붓을 들었어… 실시간으로 써지는 중</div>';
    h+='<div class="fu" id="fubox" style="display:none"><div class="futitle">🪭 '+d.char+'한테 더 궁금한 거? <span>건당 990원</span></div>'
      +'<div id="fulog"></div>'
      +'<div class="furow"><input id="fuq" placeholder="예) 올해 이직해도 될까?" onkeydown="if(event.key===\'Enter\')askFollow()"><button onclick="askFollow()">보내기</button></div></div>';
  }
  h+='</div>';R.innerHTML=h;
  if(paid){window._lastReportInput=d._input;streamReport(d._input,unlock);}
}
async function streamReport(input,unlock){
  const rpt=document.getElementById('rpt');const tagf=document.getElementById('tagf');let txt='';
  try{
    const resp=await fetch('/api/report_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,unlock:unlock})});
    const reader=resp.body.getReader();const dec=new TextDecoder();
    const near=()=>window.innerHeight+window.scrollY>=document.body.scrollHeight-160;
    while(true){const {done,value}=await reader.read();if(done)break;
      txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';
      if(near())window.scrollTo(0,document.body.scrollHeight);
    }
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(전송이 끊겼어. 다시 눌러줘)';}
  tagf.textContent='해석 완료 · 점며든다';
  const fb=document.getElementById('fubox');if(fb)fb.style.display='block';
}
let seongTimer=null;
async function checkSeong(){
  clearTimeout(seongTimer);
  seongTimer=setTimeout(async()=>{
    const v=document.getElementById('nseong').value.trim();
    const box=document.getElementById('nseonghjbox'),sel=document.getElementById('nseonghj');
    if(!v){box.style.display='none';return;}
    let d;try{d=await(await fetch('/api/seong?seong='+encodeURIComponent(v))).json();}catch(e){return;}
    if(d.ok&&d.multi){
      sel.innerHTML=d.options.map(o=>'<option value="'+o.hanja+'">'+o.hanja+' ('+o.hoek+'획)</option>').join('');
      box.style.display='block';
    }else{box.style.display='none';sel.innerHTML='';}
  },250);
}
function seongHanja(){const b=document.getElementById('nseonghjbox');return(b&&b.style.display!=='none')?document.getElementById('nseonghj').value:'';}
function nmodeUI(){
  const m=document.getElementById('nmode').value;
  const box=document.getElementById('nfixbox'),inp=document.getElementById('nfix');
  if(m==='auto'){box.style.display='none';}
  else{box.style.display='block';
    inp.placeholder=(m==='single')?'외자에 넣을 글자(선택) · 예: 수':(m==='fix2')?'돌림자/뒷글자 (예: 준 또는 俊)':'앞글자 (예: 서 또는 瑞)';}
}
function namingMode(){
  const m=document.getElementById('nmode').value;
  const fx=(document.getElementById('nfix').value||'').trim();
  if(m==='fix1')return{fixed:fx,fixed_pos:1};
  if(m==='fix2')return{fixed:fx,fixed_pos:2};
  if(m==='single')return{single:true,fixed:fx};
  return{};
}
function runNaming(){
  const seong=document.getElementById('nseong').value.trim();
  const seong_hanja=seongHanja();
  const date=document.getElementById('ndate').value,time=document.getElementById('ntime').value||'12:00';
  const gender=document.getElementById('ngender').value;
  const mode=namingMode();
  if(!seong){alert('아기 성을 한 글자 넣어줘 (예: 김)');return;}
  if(!date){alert('아기 태어난 날을 넣어줘~');return;}
  if((mode.fixed_pos)&&!mode.fixed){alert('넣을 글자를 입력해줘 (예: 준)');return;}
  payFor('naming',{seong,seong_hanja,date,time,gender,...mode});
}
async function doNaming(input,unlock){
  document.getElementById('nspin').style.display='block';document.getElementById('nresult').innerHTML='';
  let d;
  try{d=await(await fetch('/api/naming',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,unlock:unlock})})).json();}
  catch(e){document.getElementById('nspin').style.display='none';document.getElementById('nresult').innerHTML='<div class="ncard">오류가 났어. 다시 해줄래?</div>';return;}
  document.getElementById('nspin').style.display='none';
  if(d.error){document.getElementById('nresult').innerHTML='<div class="ncard">'+d.error+'</div>';return;}
  if(d.need_pay){document.getElementById('nresult').innerHTML='<div class="ncard">결제 확인이 안 됐어. 다시 시도해줘.</div>';return;}
  renderNaming(d.result,{...input,unlock:unlock});
  document.getElementById('nresult').scrollIntoView({behavior:'smooth'});
}
function renderNaming(r,q){
  const KR={원격:'초년',형격:'청년',이격:'장년',정격:'말년'};
  let h='<div class="ncard" style="background:#eef3ff"><div class="nmean">🎏 아기 사주(일간 <b>'+r.사주.일간+'</b>)에 <b>'+(r.사주.부족오행.join(', ')||'큰 부족 없')+'</b> 기운이 부족해서, 그걸 채우는 이름으로 골랐어</div></div>';
  r.한자후보.forEach(c=>{
    let sg='';Object.keys(c.사격).forEach(k=>{const x=c.사격[k];sg+='<div class="sg"><b>'+(KR[k]||k)+'운</b><span>'+x.수+'수 <span class="ok">'+x.등급+'</span></span></div>';});
    h+='<div class="ncard"><div class="nname">'+r.성.한글+c.이름+'<span class="hj">'+r.성.한자+c.한자+'</span></div>'
      +'<div class="nmean">뜻: '+c.훈.join(' · ')+' · 부족한 '+(c.보완오행.join('/')||'오행')+' 보완</div>'
      +'<div class="sgrid">'+sg+'</div></div>';
  });
  h+='<div class="rpt" id="nrpt"><span class="cur">▍</span></div><div class="tagf" id="ntagf">🎏 공명이가 이름 풀이 쓰는 중…</div>';
  document.getElementById('nresult').innerHTML=h;
  streamNaming(r,q);
}
async function streamNaming(r,q){
  const rpt=document.getElementById('nrpt'),tagf=document.getElementById('ntagf');let txt='';
  try{
    const resp=await fetch('/api/naming_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...q,result:r})});
    const reader=resp.body.getReader(),dec=new TextDecoder();
    while(true){const {done,value}=await reader.read();if(done)break;txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';}
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(풀이 전송이 끊겼어)';}
  tagf.textContent='🎏 정통 수리성명학 · 점며든다';
}
function nameMenu(which){
  const map={naming:'nmbN',analyze:'nmbA',pop:'nmbP'};
  ['naming','analyze','pop'].forEach(k=>{
    document.getElementById('panel-'+k).style.display=(k===which)?'block':'none';
    document.getElementById(map[k]).classList.toggle('on',k===which);
  });
  if(which==='pop')loadPop();
}
let POP=null;
async function loadPop(){
  if(!POP){try{POP=await(await fetch('/api/popular')).json();}catch(e){return;}}
  const sub=document.getElementById('popsub');
  if(sub)sub.innerHTML='<b>'+POP.year+'년 기준</b> · 대법원 출생신고 순위 · '+(POP.note||'');
  popTab('남아');
}
function popTab(g){
  if(!POP)return;
  document.getElementById('tabB').classList.toggle('on',g==='남아');
  document.getElementById('tabG').classList.toggle('on',g==='여아');
  const list=POP[g]||[];
  let h='<div class="poprow" style="font-weight:900;color:#b08">'+ (POP.trend?POP.trend[g]:'') +'</div><div class="popgrid">';
  list.forEach(x=>{h+='<div class="popitem"><span class="pr">'+x.순위+'</span> <b>'+x.이름+'</b></div>';});
  h+='</div><div class="poprc">'+POP.source+'</div>';
  document.getElementById('poplist').innerHTML=h;
}
function runAnalyze(){
  const name=document.getElementById('aname').value.trim();
  const hanja=document.getElementById('ahanja').value.trim();
  const date=document.getElementById('adate').value,time=document.getElementById('atime').value||'12:00';
  const gender=document.getElementById('agender').value;
  if(!name){alert('이름을 한글로 넣어줘 (예: 홍길동)');return;}
  if(!date){alert('태어난 날을 넣어줘~');return;}
  payFor('analysis',{name,hanja,date,time,gender});
}
async function doAnalyze(input,unlock){
  document.getElementById('aspin').style.display='block';document.getElementById('aresult').innerHTML='';
  let d;
  try{d=await(await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,unlock:unlock})})).json();}
  catch(e){document.getElementById('aspin').style.display='none';document.getElementById('aresult').innerHTML='<div class="ncard">오류가 났어. 다시 해줄래?</div>';return;}
  document.getElementById('aspin').style.display='none';
  if(d.error){document.getElementById('aresult').innerHTML='<div class="ncard">'+d.error+'</div>';return;}
  if(d.need_pay){document.getElementById('aresult').innerHTML='<div class="ncard">결제 확인이 안 됐어. 다시 시도해줘.</div>';return;}
  renderAnalyze(d.result,{...input,unlock:unlock});
  document.getElementById('aresult').scrollIntoView({behavior:'smooth'});
}
let lastAnalysis=null;
function renderAnalyze(r,q){
  lastAnalysis=r;
  const eum=r.발음오행,sj=r.사주;
  const badge={'좋음':'#2fbf71','무난':'#5b8def','아쉬움':'#e0a020','부딪힘':'#e0489b'}[eum.등급]||'#888';
  let flow=eum.흐름.map(f=>f.a+' <b style="color:'+badge+'">'+f.rel+'</b> '+f.b).join(' , ');
  let h='<div class="ncard"><div class="nname" style="font-size:18px">🔎 '+r.이름+' 감정</div>'
    +'<div class="nmean" style="margin-top:6px">발음오행 흐름: '+eum.배열.join(' → ')+' <span style="color:'+badge+';font-weight:900">('+eum.등급+')</span><br><span style="font-size:11.5px;color:#8a7ba5">'+flow+'</span></div>'
    +'<div class="nmean">사주 궁합: 부족한 <b>'+(sj.부족오행.join('/')||'없음')+'</b> 기운 · 이름이 채운 것: <b>'+(sj.이름이채운오행.join('/')||'없음')+'</b> <span style="color:'+({'좋음':'#2fbf71','아쉬움':'#e0489b'}[sj.궁합]||'#888')+';font-weight:900">('+sj.궁합+')</span></div>';
  if(r.수리&&r.수리.사격){const KR={원격:'초년',형격:'청년',이격:'장년',정격:'말년'};let sg='';
    for(const k of['원격','형격','이격','정격']){const x=r.수리.사격[k];sg+='<div class="sg"><b>'+KR[k]+'운</b><span>'+x.수+'수 <span class="ok">'+x.등급+'</span></span></div>';}
    h+='<div class="sgrid" style="margin-top:8px">'+sg+'</div>';}
  else if(r.수리&&r.수리.미지원){h+='<div class="nmean" style="color:#b090b0">※ 이름 한자 중 DB에 없는 글자가 있어 획수(사격)는 생략했어</div>';}
  h+='</div>';
  if(r.장점.length)h+='<div class="ncard" style="background:#eefaf1"><div class="nname" style="font-size:14px;color:#2fbf71">👍 좋은 점</div><div class="nmean" style="color:#3a6b4e">'+r.장점.map(x=>'· '+x).join('<br>')+'</div></div>';
  if(r.단점.length)h+='<div class="ncard" style="background:#fdf0f6"><div class="nname" style="font-size:14px;color:#e0489b">🤔 아쉬운 점</div><div class="nmean" style="color:#9a4a70">'+r.단점.map(x=>'· '+x).join('<br>')+'</div></div>';
  h+='<button class="go" style="background:linear-gradient(90deg,#ff2e86,#7b5bff);margin-top:10px" onclick="shareCard()">📸 결과 이미지로 저장 · 공유</button>';
  h+='<div class="rpt" id="arpt"><span class="cur">▍</span></div><div class="tagf" id="atagf">🔎 공명이가 감정 쓰는 중…</div>';
  document.getElementById('aresult').innerHTML=h;
  streamAnalyze(q);
}
function _rr(x,X,Y,w,h,r){x.beginPath();x.moveTo(X+r,Y);x.arcTo(X+w,Y,X+w,Y+h,r);x.arcTo(X+w,Y+h,X,Y+h,r);x.arcTo(X,Y+h,X,Y,r);x.arcTo(X,Y,X+w,Y,r);x.closePath();}
async function shareCard(){
  const r=lastAnalysis; if(!r){alert('먼저 이름 진단을 해줘');return;}
  const OH={'木':['木','#35b36b'],'火':['火','#ff5a5a'],'土':['土','#d9a441'],'金':['金','#e0b400'],'水':['水','#4a7dff']};
  const W=1080,H=1350,c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d');
  let g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#ffd9ec');g.addColorStop(.5,'#e4ecff');g.addColorStop(1,'#efe0ff');x.fillStyle=g;x.fillRect(0,0,W,H);
  // 데코 별
  x.font='60px sans-serif';x.globalAlpha=.5;x.fillText('✦',70,120);x.fillText('★',W-130,150);x.fillText('🪭',80,H-90);x.fillText('✧',W-140,H-70);x.globalAlpha=1;
  // 패널
  _rr(x,70,190,W-140,H-380,54);x.fillStyle='#fff';x.fill();x.lineWidth=9;x.strokeStyle='#1c1c3c';x.stroke();
  x.textAlign='center';
  x.fillStyle='#ff2e86';x.font='900 50px sans-serif';x.fillText('🔎 점며든다 이름풀이',W/2,290);
  x.fillStyle='#1c1c3c';x.font='900 110px sans-serif';x.fillText(r.이름,W/2,430);
  // 발음오행 원
  const arr=r.발음오행.배열,n=arr.length,cx0=W/2-(n-1)*110/2,cy=560;
  for(let i=0;i<n;i++){const oh=OH[arr[i]]||['?','#999'];const px=cx0+i*110;
    x.beginPath();x.arc(px,cy,46,0,7);x.fillStyle=oh[1];x.fill();x.lineWidth=5;x.strokeStyle='#1c1c3c';x.stroke();
    x.fillStyle='#fff';x.font='900 44px serif';x.fillText(oh[0],px,cy+16);
    if(i<n-1){x.fillStyle='#1c1c3c';x.font='900 40px sans-serif';x.fillText('›',px+55,cy+14);}}
  // 등급 뱃지
  const bc={'좋음':'#2fbf71','무난':'#5b8def','아쉬움':'#e0a020','부딪힘':'#e0489b'}[r.발음오행.등급]||'#888';
  _rr(x,W/2-150,640,300,74,37);x.fillStyle=bc;x.fill();
  x.fillStyle='#fff';x.font='900 40px sans-serif';x.fillText('소리 기운 '+r.발음오행.등급,W/2,690);
  // 한 줄 코멘트
  const line=(r.장점[0]||r.단점[0]||'내 이름 속 기운').replace(/\(.*?\)/g,'');
  x.fillStyle='#5a4b75';x.font='600 34px sans-serif';
  const words=line.length>26?line.slice(0,26)+'…':line; x.fillText('"'+words+'"',W/2,800);
  // 사주 궁합
  x.fillStyle='#8a7ba5';x.font='600 30px sans-serif';
  x.fillText('사주 궁합 · '+r.사주.궁합+'  |  부족한 기운 '+(r.사주.부족오행.join('/')||'없음'),W/2,870);
  // 푸터
  x.fillStyle='#1c1c3c';x.font='900 40px sans-serif';x.fillText('내 이름은 어떨까? 👀',W/2,H-250);
  x.fillStyle='#ff2e86';x.font='800 34px sans-serif';x.fillText('점며든다에서 무료로 풀어보기',W/2,H-200);
  x.fillStyle='#7a6b95';x.font='600 28px sans-serif';x.fillText(location.host,W/2,H-155);
  c.toBlob(async(blob)=>{
    const file=new File([blob],'점며든다_이름풀이.png',{type:'image/png'});
    if(navigator.canShare&&navigator.canShare({files:[file]})){
      try{await navigator.share({files:[file],title:'점며든다 이름풀이',text:r.이름+' 이름풀이 🔎'});return;}catch(e){}
    }
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='점며든다_이름풀이.png';a.click();
  },'image/png');
}
async function streamAnalyze(q){
  const rpt=document.getElementById('arpt'),tagf=document.getElementById('atagf');let txt='';
  try{
    const resp=await fetch('/api/analyze_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)});
    const reader=resp.body.getReader(),dec=new TextDecoder();
    while(true){const {done,value}=await reader.read();if(done)break;txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';}
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(전송이 끊겼어)';}
  tagf.textContent='🔎 성명 감정 · 점며든다';
}
function addFu(who,text,char){const log=document.getElementById('fulog');if(!log)return null;
  const b=document.createElement('div');b.className='fubub '+(who==='me'?'me':'ch');
  b.innerHTML=(who==='me'?'':(char?'<b>'+char+'</b><br>':''))+text;
  log.appendChild(b);b.scrollIntoView({behavior:'smooth',block:'nearest'});return b;}
function askFollow(){
  const el=document.getElementById('fuq');const q=(el.value||'').trim();if(!q)return;
  const base=window._lastReportInput||{date:document.getElementById('date').value,time:document.getElementById('time').value,gender:document.getElementById('gender').value,field:sel};
  payFor('followup',{date:base.date,time:base.time,gender:base.gender,field:base.field||sel,question:q});
}
async function doFollowup(input,unlock){
  const R=document.getElementById('result');
  R.innerHTML='<div class="rp"><div class="judge"><span class="lb">🪭 추가 질문</span>'+(input.question||'')+'</div>'
    +'<div class="rpt" id="rpt2"><span class="cur">▍</span></div><div class="tagf">해석엔진 실시간 · 점며든다</div></div>';
  R.scrollIntoView({behavior:'smooth'});
  const rpt=document.getElementById('rpt2');let txt='';
  try{
    const resp=await fetch('/api/followup_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,unlock:unlock})});
    const reader=resp.body.getReader(),dec=new TextDecoder();
    while(true){const {done,value}=await reader.read();if(done)break;txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';}
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(전송이 끊겼어)';}
}
</script></body></html>"""


@app.route("/")
def index():
    import json
    from flask import make_response
    labels = {k: v["name"] for k, v in FIELDS.items()}
    preopen = "1" if str(TOSS_CLIENT_KEY).startswith("test") else "0"   # 테스트키=오픈 준비중
    html = render_template_string(PAGE.replace("%%FIELDS%%", json.dumps(labels, ensure_ascii=False))
                                  .replace("%%PREOPEN%%", preopen))
    resp = make_response(html)
    if not current_user():   # 로그인 없이, 조용히 게스트 지갑 발급 (첫 리포트 무료)
        uid = "guest_" + uuid.uuid4().hex[:10]
        get_or_create_user(uid)
        resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/char/<path:fn>")
def char(fn):
    return send_from_directory("characters", fn)


@app.route("/dev")
def dev_unlock():
    """개발용: 결제 없이 잠금해제 토큰 발급. 예: /dev?code=비밀코드&item=naming"""
    code = request.args.get("code", "")
    secret = os.environ.get("DEV_CODE", "jeom2026-gongmyeong")
    if code != secret:
        return "🔒 코드가 틀렸어", 403
    item = request.args.get("item", "analysis")
    if item not in PAID_ITEMS:
        item = "analysis"
    return redirect(f"/?u={make_unlock(item)}&item={item}")


@app.route("/api/report", methods=["POST"])
def api_report():
    data = request.get_json(force=True)
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"error": "날짜/시간 형식이 올바르지 않습니다."}), 400
    gender = data.get("gender", "F")
    field = data.get("field", "wealth")
    if field not in FIELDS:
        return jsonify({"error": "알 수 없는 분야"}), 400

    prompt, facts = make_full_prompt(dt, gender, field)
    q, s = facts["기문"], facts["사주"]
    best_month = q["최적월"][0]
    summary = (f"{s['일간']}({s['일간오행']}) · {s['스타일키워드']} / "
               f"지금 {s['대운']} 시즌 · {facts['타겟연도']}년 최적 {best_month}월")
    saju_line = (f"너는 <b>{s['일간']}·{s['일간오행']}</b> 기운의 <b>{s['스타일키워드']}</b>! "
                 f"지금 <b>{s['대운']}</b> 시즌이 판에 쫙 깔렸고, 올해 기운 몰리는 달은 <b>{best_month}월</b>이야 ✦")
    LB = {"방위": "어디로", "성격": "무슨 일", "기운": "밀어주는 기운", "변수": "숨은 변수",
          "삼기": "✦ 대박 자리", "주도권": "주도권", "헛수고구간": "조심할 때", "이동수": "이동수"}
    hook = [{"label": LB.get(k, k), "text": v} for k, v in q["요소"].items() if v]

    def base():
        return {"char": facts["캐릭터"], "field": facts["분야"], "summary": summary,
                "saju_line": saju_line, "hook": hook, "best_month": best_month}

    # 무료 미리보기(판/훅)만 반환. 전체 리포트는 990원 결제 후 stream.
    return jsonify({**base(), "engine_note": "해석엔진: 실시간 · 계산: 검증된 엔진",
                    "free": (field == "today"), "price": PRICE})


@app.route("/api/report_stream", methods=["POST"])
def api_report_stream():
    """부채 1개 차감 후, 리포트를 실시간(스트리밍)으로 흘려보낸다."""
    data = request.get_json(force=True)
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return Response("[날짜/시간 형식이 올바르지 않아요]", mimetype="text/plain; charset=utf-8")
    gender = data.get("gender", "F")
    field = data.get("field", "wealth")
    if field not in FIELDS:
        return Response("[알 수 없는 분야]", mimetype="text/plain; charset=utf-8")

    # 오늘의운세는 무료, 나머지는 990원 결제 토큰 필요
    if field != "today" and not check_unlock(data.get("unlock"), "report"):
        return Response("[결제가 필요해요. 새로고침 후 다시 눌러줘]", mimetype="text/plain; charset=utf-8")

    prompt, facts = make_full_prompt(dt, gender, field)

    def gen():
        for piece in stream_interpretation(prompt):
            yield piece

    resp = Response(stream_with_context(gen()), mimetype="text/plain; charset=utf-8")
    resp.headers["X-Accel-Buffering"] = "no"   # 프록시 버퍼링 끔(실시간 전달)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _followup_args(data):
    dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    gender = data.get("gender", "F")
    field = data.get("field", "overall")
    if field not in FIELDS:
        field = "overall"
    question = (data.get("question") or "").strip()
    return dt, gender, field, question


@app.route("/api/followup", methods=["POST"])
def api_followup():
    """추가 질문: 열람 가능한지만 확인(부채 차감/생성은 stream에서). 빠른 응답."""
    data = request.get_json(force=True)
    try:
        dt, gender, field, question = _followup_args(data)
    except Exception:
        return jsonify({"error": "날짜/시간 형식이 올바르지 않습니다."}), 400
    if not question:
        return jsonify({"error": "질문을 입력해줘"}), 400

    _p, facts = make_followup_prompt(dt, gender, field, question)
    char = facts["캐릭터"]
    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    chk = can_open(uid, "followup")
    if not chk["ok"]:
        resp = jsonify({"need_charge": True, "char": char,
                        "balance": chk["balance"], "packages": BUCHAE_PACKAGES,
                        "teaser": f"부채 <em>1개(500원)</em>면 {char}가 답해줄게!"})
    else:
        resp = jsonify({"ok": True, "char": char})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/api/followup_stream", methods=["POST"])
def api_followup_stream():
    """부채 1개 차감 후 캐릭터 답변을 실시간 스트리밍."""
    data = request.get_json(force=True)
    try:
        dt, gender, field, question = _followup_args(data)
    except Exception:
        return Response("[날짜 형식 오류]", mimetype="text/plain; charset=utf-8")
    if not question:
        return Response("[질문을 입력해줘]", mimetype="text/plain; charset=utf-8")
    if not check_unlock(data.get("unlock"), "followup"):
        return Response("[결제가 필요해요. 새로고침 후 다시 물어봐]", mimetype="text/plain; charset=utf-8")
    prompt, _facts = make_followup_prompt(dt, gender, field, question)

    def gen():
        for piece in stream_interpretation(prompt):
            yield piece
    resp = Response(stream_with_context(gen()), mimetype="text/plain; charset=utf-8")
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """이름 분석(감정): 부채 2개(1,000원) 차감 → 성명학 진단 결과 반환."""
    data = request.get_json(force=True)
    fullname = (data.get("name") or "").strip()
    hanja = (data.get("hanja") or "").strip() or None
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"error": "생년월일/시간을 확인해줘."}), 400
    gender = data.get("gender", "F")

    from name_analysis import analyze_name
    result = analyze_name(fullname, dt, gender, hanja=hanja)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    if not check_unlock(data.get("unlock"), "analysis"):
        return jsonify({"need_pay": True, "item": "analysis", "price": PRICE}), 402
    return jsonify({"ok": True, "result": result})


@app.route("/api/analyze_stream", methods=["POST"])
def api_analyze_stream():
    """공명이 이름 감정 해설 실시간 생성(차감 없음)."""
    data = request.get_json(force=True)
    fullname = (data.get("name") or "").strip()
    hanja = (data.get("hanja") or "").strip() or None
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return Response("[생년월일 오류]", mimetype="text/plain; charset=utf-8")
    gender = data.get("gender", "F")
    prompt, result = make_analysis_prompt(fullname, dt, gender, hanja=hanja)
    if prompt is None:
        return Response("[" + result.get("error", "오류") + "]", mimetype="text/plain; charset=utf-8")

    def gen():
        for piece in stream_interpretation(prompt):
            yield piece
    resp = Response(stream_with_context(gen()), mimetype="text/plain; charset=utf-8")
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/popular")
def api_popular():
    """요즘 인기 아기 이름 순위 (무료)."""
    from name_ranks import payload
    return jsonify(payload())


@app.route("/api/seong")
def api_seong():
    """한글/한자 성 -> 한자 선택지(여러 개면 프론트에서 고르게)."""
    from hanja_db import normalize_seong, seong_options
    raw = (request.args.get("seong") or "").strip()
    kr = normalize_seong(raw)
    if kr is None:
        return jsonify({"ok": False})
    opts = seong_options(kr)
    return jsonify({"ok": True, "seong": kr,
                    "options": [{"hanja": h, "hoek": k} for h, k in opts],
                    "multi": len(opts) > 1})


@app.route("/api/naming", methods=["POST"])
def api_naming():
    """작명: 부채 5개(2,500원) 차감 → 정통 수리성명학 이름 후보 반환."""
    data = request.get_json(force=True)
    seong = (data.get("seong") or "").strip()
    seong_hanja = data.get("seong_hanja") or None
    fixed = (data.get("fixed") or "").strip() or None
    fixed_pos = data.get("fixed_pos")
    single = bool(data.get("single"))
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"error": "아기 생년월일/시간을 확인해줘."}), 400
    gender = data.get("gender", "M")

    from naming_engine import generate_names
    # 성씨/입력 검증 먼저 (부채 차감 전에)
    result = generate_names(seong, dt, gender, seong_hanja=seong_hanja,
                            fixed=fixed, fixed_pos=fixed_pos, single=single)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    if not result["한자후보"]:
        return jsonify({"error": "조건에 맞는 이름을 못 찾았어. 시간을 넣거나 다른 성씨로 해줄래?"}), 400

    if not check_unlock(data.get("unlock"), "naming"):
        return jsonify({"need_pay": True, "item": "naming", "price": PRICE}), 402
    return jsonify({"ok": True, "result": result})


@app.route("/api/naming_stream", methods=["POST"])
def api_naming_stream():
    """공명이 작명 해설 실시간 생성(차감 없음, 후보는 이미 /api/naming에서 결제)."""
    data = request.get_json(force=True)
    seong = (data.get("seong") or "").strip()
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return Response("[생년월일 오류]", mimetype="text/plain; charset=utf-8")
    gender = data.get("gender", "M")
    seong_hanja = data.get("seong_hanja") or None
    fixed = (data.get("fixed") or "").strip() or None
    fixed_pos = data.get("fixed_pos")
    single = bool(data.get("single"))
    # ★이미 /api/naming 에서 뽑아 보여준 후보(result)를 그대로 해설 (랜덤 재생성 방지)
    passed = data.get("result")
    if passed and passed.get("한자후보"):
        prompt = build_naming_prompt(passed)
    else:
        prompt, result = make_naming_prompt(seong, dt, gender, seong_hanja=seong_hanja,
                                            fixed=fixed, fixed_pos=fixed_pos, single=single)
        if prompt is None:
            return Response("[" + result.get("error", "오류") + "]", mimetype="text/plain; charset=utf-8")

    def gen():
        for piece in stream_interpretation(prompt):
            yield piece
    resp = Response(stream_with_context(gen()), mimetype="text/plain; charset=utf-8")
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/login", methods=["POST"])
def api_login():
    import uuid
    from flask import make_response
    data = request.get_json(force=True) or {}
    uid = data.get("uid") or ("guest_" + uuid.uuid4().hex[:8])
    get_or_create_user(uid)
    resp = make_response(jsonify({"ok": True, "uid": uid, "balance": get_balance(uid)}))
    resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/api/balance")
def api_balance():
    uid = current_user()
    return jsonify({"balance": get_balance(uid) if uid else 0, "logged_in": bool(uid)})


@app.route("/api/charge", methods=["POST"])
def api_charge():
    uid = current_user()
    if not uid:
        return jsonify({"error": "로그인 필요"}), 401
    data = request.get_json(force=True)
    pkg = data.get("package", "fan_3")
    res = charge_buchae(uid, pkg, paid=True)
    return jsonify(res)


# ══════════ 토스페이먼츠 결제위젯 연동 ══════════
# 신청 전엔 아래 '문서 테스트 키'로 실제 결제창이 뜸(테스트 모드, 실제 청구 X).
# 정식 오픈: 환경변수 TOSS_CLIENT_KEY / TOSS_SECRET_KEY 에 내 상점 키(gck/gsk) 넣으면 실결제.
TOSS_CLIENT_KEY = os.environ.get("TOSS_CLIENT_KEY", "test_gck_docs_Ovk5rk1EwkEbP0W43n07xlzm")
TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "test_gsk_docs_Ovk5rk1EwkEbP0W43n07xlzm")


def toss_confirm(payment_key, order_id, amount):
    """토스 결제 승인 API 호출 (시크릿 키 Basic 인증)."""
    auth = base64.b64encode((TOSS_SECRET_KEY + ":").encode()).decode()
    req = urllib.request.Request(
        "https://api.tosspayments.com/v1/payments/confirm",
        data=_json.dumps({"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)}).encode(),
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return _json.load(r), None
    except urllib.error.HTTPError as e:
        try: return None, _json.load(e)
        except Exception: return None, {"message": "결제 승인 실패"}
    except Exception as e:
        return None, {"message": str(e)}


PAY_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>점며든다 · 부채 충전</title>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Jua&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://js.tosspayments.com/v2/standard"></script>
<style>
*{margin:0;box-sizing:border-box}
body{font-family:'Noto Sans KR',sans-serif;color:#241056;padding:18px 0 40px;min-height:100vh;
background:radial-gradient(circle at 12% 8%,#fff6a8 0,#fff6a800 30%),linear-gradient(165deg,#c4ccff,#ffc9e8 55%,#ffe6a8) fixed}
.ph{max-width:420px;margin:0 auto;padding:0 15px}
.logo{font-family:'Black Han Sans';font-size:26px;text-align:center;margin:6px 0 4px;
background:linear-gradient(180deg,#ff8fd0,#8b7bff 50%,#37e0c8);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:2px #241056;filter:drop-shadow(2px 2px 0 #241056)}
.sum{background:#fffdf7;border:3px solid #241056;border-radius:20px;padding:14px 16px;margin:10px 0;box-shadow:5px 5px 0 #8b7bff;text-align:center}
.sum .b{font-family:'Black Han Sans';font-size:22px;color:#ff2e86}
.sum .w{font-family:'Jua';font-size:15px;color:#241056;margin-top:2px}
.box{background:#fffdf7;border:3px solid #241056;border-radius:20px;padding:12px;margin:10px 0;box-shadow:5px 5px 0 #8b7bff}
.cta{width:100%;margin-top:8px;padding:16px;border:3px solid #241056;border-radius:18px;background:#2b2bff;color:#fff;font-family:'Black Han Sans';font-size:18px;box-shadow:4px 5px 0 #ffdf3d,4px 5px 0 3px #241056;cursor:pointer}
.back{display:block;text-align:center;margin-top:12px;color:#241056;font-family:'Jua';font-size:13px;text-decoration:none}
.note{font-size:11px;color:#6b5a8a;text-align:center;margin-top:10px;line-height:1.6}
</style></head><body><div class="ph">
<div class="logo">점며든다</div>
<div class="sum"><div class="b">__ITEMNAME__</div><div class="w">결제 금액 __WON__원 · 결제하면 결과가 바로 나와요</div></div>
<div class="box" id="payment-method"></div>
<div class="box" id="agreement"></div>
<button class="cta" id="paybtn">🪭 __WON__원 결제하기</button>
<a class="back" href="/">← 취소하고 돌아가기</a>
<div class="note">🛠 지금은 토스 <b>테스트 모드</b>예요. 아무 카드번호나 넣어도 실제 청구 안 돼요.<br>정식 오픈 땐 상점 키만 바꾸면 실결제로 전환돼요.</div>
</div>
<script>
const widgets = TossPayments("__CK__").widgets({ customerKey: "__CUST__" });
(async () => {
  await widgets.setAmount({ currency: "KRW", value: __AMT__ });
  await widgets.renderPaymentMethods({ selector: "#payment-method", variantKey: "DEFAULT" });
  await widgets.renderAgreement({ selector: "#agreement", variantKey: "AGREEMENT" });
})();
document.getElementById("paybtn").onclick = async () => {
  try {
    await widgets.requestPayment({
      orderId: "__OID__", orderName: "__ONAME__",
      successUrl: location.origin + "/pay/success?item=__ITEM__",
      failUrl: location.origin + "/pay/fail",
    });
  } catch (e) { alert("결제를 취소했거나 오류가 났어요."); }
};
</script></body></html>"""

RESULT_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>점며든다</title>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Jua&family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<style>body{font-family:'Noto Sans KR',sans-serif;color:#241056;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:linear-gradient(165deg,#c4ccff,#ffc9e8 55%,#ffe6a8) fixed;text-align:center;padding:20px}
.c{background:#fffdf7;border:3px solid #241056;border-radius:22px;padding:28px 22px;box-shadow:6px 6px 0 #8b7bff;max-width:360px}
.e{font-size:44px}.t{font-family:'Black Han Sans';font-size:22px;margin:8px 0 4px;color:__COLOR__}
.m{font-family:'Jua';font-size:14px;color:#241056;line-height:1.6;margin-bottom:16px}
.cta{display:inline-block;padding:14px 24px;border:3px solid #241056;border-radius:16px;background:#2b2bff;color:#fff;font-family:'Black Han Sans';font-size:16px;box-shadow:3px 4px 0 #ffdf3d;text-decoration:none}
</style></head><body><div class="c"><div class="e">__EMOJI__</div><div class="t">__TITLE__</div><div class="m">__MSG__</div><a class="cta" href="/">🪭 점 보러가기</a></div></body></html>"""


def _result(emoji, title, msg, color="#ff2e86"):
    html = (RESULT_PAGE.replace("__EMOJI__", emoji).replace("__TITLE__", title)
            .replace("__MSG__", msg).replace("__COLOR__", color))
    return render_template_string(html)


@app.route("/pay")
def pay():
    item = request.args.get("item", "")
    if item not in PAID_ITEMS:
        return _result("😵", "잘못된 접근", "상품 정보가 없어요.")
    uid = current_user() or ("guest_" + uuid.uuid4().hex[:8])
    order_id = "jmd_" + uuid.uuid4().hex[:20]
    html = (PAY_PAGE.replace("__CK__", TOSS_CLIENT_KEY).replace("__CUST__", uid)
            .replace("__AMT__", str(PRICE)).replace("__OID__", order_id)
            .replace("__ONAME__", f"점며든다 {ITEM_NAME[item]}").replace("__ITEM__", item)
            .replace("__ITEMNAME__", ITEM_NAME[item]).replace("__WON__", f"{PRICE:,}"))
    return render_template_string(html)


@app.route("/pay/success")
def pay_success():
    item = request.args.get("item", "")
    payment_key = request.args.get("paymentKey", "")
    order_id = request.args.get("orderId", "")
    amount = request.args.get("amount", "0")
    if item not in PAID_ITEMS:
        return _result("😵", "결제 확인 실패", "상품 정보를 확인할 수 없어요.")
    if int(amount) != PRICE:   # 금액 위변조 방지
        return _result("🚫", "금액이 맞지 않아요", "결제 금액이 상품 가격과 달라 취소했어요.")
    res, err = toss_confirm(payment_key, order_id, amount)
    if err:
        return _result("😢", "결제 승인 실패", err.get("message", "다시 시도해 주세요."))
    # 결제 성공 → 1회용 잠금해제 토큰 발급해 앱으로 복귀 (저장 없음)
    token = make_unlock(item)
    return redirect(f"/?u={token}&item={item}")


@app.route("/pay/fail")
def pay_fail():
    msg = request.args.get("message", "결제가 취소됐거나 실패했어요.")
    return _result("🥲", "결제 실패", msg)


# ══════════ 법적 고지 (이용약관·개인정보·환불) ══════════
BIZ = {  # ★오픈 전 Railway 환경변수(BIZ_*)로 실제 사업자 정보 입력
    "상호": os.environ.get("BIZ_NAME", "점며든다"),
    "대표자": os.environ.get("BIZ_CEO", "(대표자명)"),
    "사업자번호": os.environ.get("BIZ_REGNO", "(사업자등록번호)"),
    "통신판매": os.environ.get("BIZ_MAILORDER", "(통신판매업 신고번호)"),
    "주소": os.environ.get("BIZ_ADDR", "(사업장 주소)"),
    "이메일": os.environ.get("BIZ_EMAIL", "ektmf3210@gmail.com"),
}
POLICY_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>점며든다 · 약관 및 정책</title>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>body{font-family:'Noto Sans KR',sans-serif;color:#241056;max-width:760px;margin:0 auto;padding:24px 18px 60px;line-height:1.75;
background:linear-gradient(165deg,#eef1ff,#fff2f8)}
h1{font-family:'Black Han Sans';font-size:24px;margin:8px 0 6px}
h2{font-family:'Black Han Sans';font-size:18px;margin:30px 0 8px;padding-top:14px;border-top:2px dashed #cbb9ee}
h3{font-size:15px;margin:16px 0 4px;color:#5b2e9a}
p,li{font-size:13.5px;color:#3a2e5a}ul{padding-left:18px;margin:4px 0}
.top{font-size:12px;color:#8a7ba5;margin-bottom:14px}
a{color:#ff2e86}.biz{background:#fffdf7;border:2px solid #241056;border-radius:12px;padding:12px 14px;font-size:12.5px;margin:10px 0}
.home{display:inline-block;margin-top:24px;padding:10px 18px;border:2.5px solid #241056;border-radius:12px;background:#2b2bff;color:#fff;font-weight:700;text-decoration:none}
</style></head><body>
<h1>🪭 점며든다 이용약관 · 개인정보처리방침 · 환불정책</h1>
<div class="top">시행일: 2026-07-23 · 본 서비스는 전통 술수(사주·기문·성명학) 기반의 <b>참고·오락용</b> 콘텐츠입니다.</div>

<div class="biz">
<b>사업자 정보</b><br>
상호: %(상호)s / 대표자: %(대표자)s<br>
사업자등록번호: %(사업자번호)s / 통신판매업신고: %(통신판매)s<br>
주소: %(주소)s / 문의: %(이메일)s
</div>

<h2>제1장 이용약관</h2>
<h3>제1조 (목적)</h3>
<p>본 약관은 '점며든다'(이하 "서비스")가 제공하는 사주·기문·작명·이름분석 등 콘텐츠의 이용조건 및 절차, 회사와 이용자의 권리·의무를 규정함을 목적으로 합니다.</p>
<h3>제2조 (서비스의 성격)</h3>
<ul><li>본 서비스가 제공하는 모든 해석·이름·운세는 전통 술수에 기반한 <b>참고 및 오락 목적</b>의 정보이며, 과학적·의학적·법적 사실이나 미래에 대한 보장이 아닙니다.</li>
<li>이용자는 취업·투자·건강·결혼·작명 등 중요한 의사결정을 본인의 판단과 책임하에 하여야 하며, 회사는 그 결과에 대해 법적 책임을 지지 않습니다.</li></ul>
<h3>제3조 (이용 및 결제)</h3>
<ul><li>본 서비스는 회원가입 없이 이용할 수 있으며, 일부 콘텐츠(오늘의 운세, 인기 이름 순위 등)는 무료로 제공됩니다.</li>
<li>유료 콘텐츠는 건별 결제(현재 건당 990원) 방식이며, 결제는 토스페이먼츠를 통해 처리됩니다.</li>
<li>결제 완료 즉시 해당 콘텐츠가 생성·제공됩니다.</li></ul>
<h3>제4조 (금지행위)</h3>
<p>이용자는 서비스의 콘텐츠를 무단 복제·배포·상업적 이용하거나, 비정상적 방법으로 서비스를 방해하는 행위를 하여서는 안 됩니다.</p>
<h3>제5조 (지식재산권)</h3>
<p>서비스 및 콘텐츠(캐릭터, 문구, 계산 엔진 등)에 대한 지식재산권은 회사에 귀속됩니다.</p>
<h3>제6조 (면책)</h3>
<p>회사는 천재지변, 시스템 장애, 이용자의 귀책 등으로 인한 손해에 대해 책임을 지지 않으며, 콘텐츠의 정확성·신뢰성을 보증하지 않습니다.</p>
<h3>제7조 (준거법 및 관할)</h3>
<p>본 약관은 대한민국 법령에 따르며, 분쟁 발생 시 관할은 민사소송법에 따른 법원으로 합니다.</p>

<h2>제2장 개인정보처리방침</h2>
<h3>1. 수집하는 정보</h3>
<ul><li>운세·작명·이름분석 이용 시: 생년월일·태어난 시간, 성별, (이름분석·작명 시) 이름 및 한자</li>
<li>결제 시: 결제 정보는 토스페이먼츠가 처리하며, 회사는 카드번호 등 민감 결제정보를 저장하지 않습니다.</li>
<li>서비스 이용 편의를 위한 익명 식별용 쿠키</li></ul>
<h3>2. 이용 목적</h3>
<p>입력하신 생년월일·이름 등은 <b>오직 해당 운세·작명·이름분석 결과를 생성하기 위해서만</b> 사용됩니다.</p>
<h3>3. 보유 및 파기</h3>
<p>본 서비스는 건별 처리 방식으로, 이용자가 입력한 <b>생년월일·이름 등 정보를 서버에 별도로 저장하지 않으며</b> 결과 생성 후 즉시 파기됩니다. 다만 전자상거래법 등 관련 법령에 따라 결제·거래 기록은 토스페이먼츠 및 관련 기관에 일정 기간(대금결제·재화공급 5년 등) 보관될 수 있습니다.</p>
<h3>4. 제3자 제공 및 처리위탁</h3>
<ul><li>해석 텍스트 생성: 입력값으로 산출된 사주·기문 근거가 AI 해석 생성을 위해 처리 위탁 업체(Anthropic)로 전송됩니다.</li>
<li>결제 처리: 토스페이먼츠(주)</li></ul>
<h3>5. 이용자의 권리</h3>
<p>이용자는 관련 법령에 따라 개인정보의 열람·정정·삭제를 요구할 수 있습니다. (문의: %(이메일)s)</p>
<h3>6. 개인정보 보호책임자</h3>
<p>%(대표자)s (문의: %(이메일)s)</p>

<h2>제3장 환불정책</h2>
<ul><li>본 서비스의 유료 콘텐츠(운세·작명·이름분석 결과 등)는 <b>결제 즉시 생성·제공되는 디지털 콘텐츠</b>로서, 「전자상거래 등에서의 소비자보호에 관한 법률」 제17조 제2항에 따라 콘텐츠 제공이 개시된 경우 청약철회가 제한됩니다.</li>
<li>다만 다음의 경우에는 전액 환불해 드립니다: ① 시스템 오류로 결과가 생성되지 않은 경우 ② 중복 결제 ③ 결제 금액 오류 ④ 콘텐츠가 표시·전송되지 않은 경우</li>
<li>환불 문의는 %(이메일)s 로 결제 내역과 함께 접수해 주시면 확인 후 처리해 드립니다.</li></ul>

<a class="home" href="/">← 점며든다로 돌아가기</a>
</body></html>"""


@app.route("/policy")
def policy():
    return render_template_string(POLICY_PAGE % BIZ)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
