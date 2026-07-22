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
import os, base64, json as _json, uuid, urllib.request, urllib.error
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
.namebox{margin:18px 0 6px;padding:16px;background:linear-gradient(135deg,#fff6fb,#eef3ff);border:2.5px solid var(--navy);border-radius:18px;box-shadow:4px 4px 0 var(--purple)}
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
  <div class="top"><div class="bal" id="bal">🪭 부채 0</div>
    <div class="logo">점며든다</div>
    <div class="slo">내 인생, <em>어떻게 이겨?</em> 🪭</div></div>
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
  <div class="namebox">
    <div class="nbtitle">🎏 아이 이름 짓기 <span class="nbtag">정통 수리성명학 · 부채 5개</span></div>
    <div class="nbsub">아기 사주로 부족한 기운을 찾아, 사격(초년·청년·장년·말년운)이 다 좋은 이름만 골라줘</div>
    <label>아기 성 (한글로 한 글자, 예: 김)</label>
    <input type="text" id="nseong" maxlength="1" placeholder="김" oninput="checkSeong()">
    <div id="nseonghjbox" style="display:none">
      <label>성씨 한자 선택 <span style="color:#e0489b">(획수가 달라 결과가 바뀌어요)</span></label>
      <select id="nseonghj"></select>
    </div>
    <label>아기 태어난 날 (양력) · 시간 모르면 비워둬도 돼</label>
    <div class="rowf"><div><input type="date" id="ndate"></div><div><input type="time" id="ntime"></div></div>
    <label>성별</label>
    <select id="ngender"><option value="M">남아</option><option value="F">여아</option></select>
    <button class="go go2" onclick="runNaming()">🎏 이름 지어줘</button>
  </div>
  <div class="spin" id="nspin">🎏 공명이가 획수를 세는 중…</div>
  <div id="nresult"></div>
  <div class="namebox" style="background:linear-gradient(135deg,#eef6ff,#f6f0ff)">
    <div class="nbtitle">🔎 내 이름 분석 <span class="nbtag" style="background:var(--blue)">성명 감정 · 부채 2개</span></div>
    <div class="nbsub">지금 내 이름, 잘 지어졌을까? 발음오행 흐름·사주 궁합·획수운(사격)으로 장단점 진단해줄게</div>
    <label>이름 (한글, 예: 김다슬)</label>
    <input type="text" id="aname" maxlength="5" placeholder="김다슬">
    <label>이름 한자 (알면 입력, 몰라도 OK)</label>
    <input type="text" id="ahanja" maxlength="5" placeholder="예: 金瑞娟 · 모르면 비워둬">
    <label>태어난 날 (양력) · 시간 모르면 비워둬도 돼</label>
    <div class="rowf"><div><input type="date" id="adate"></div><div><input type="time" id="atime"></div></div>
    <label>성별</label>
    <select id="agender"><option value="F">여성</option><option value="M">남성</option></select>
    <button class="go" style="background:var(--blue)" onclick="runAnalyze()">🔎 내 이름 진단</button>
  </div>
  <div class="spin" id="aspin">🔎 공명이가 획수를 세는 중…</div>
  <div id="aresult"></div>
  <p class="foot">전통 술수 기반 참고·오락용 · 계산은 검증된 엔진, 해석은 AI<br>중요한 결정은 본인 판단으로!</p>
</section>

</div>

<div class="ctaw" id="ctaw"><button class="cta" onclick="toInput()">🪭 내 때 보러가기 →</button></div>

<script>
const FIELDS=%%FIELDS%%;
const ICON={overall:'🀄',wealth:'💰',career:'💼',love:'💕',life:'🌊',health:'🩺',yearly:'⚔️',today:'📅'};
const CHAR={overall:'yubi',wealth:'jojo',career:'gwanu',love:'juyu',life:'samaui',health:'hwata',yearly:'jangbi',today:'gongmyeong'};
let sel='wealth';

/* ── 인트로 채팅 ── */
const MSG=[
 "안녕 👋 나 <em>제갈량</em>, 별명 공명이야",
 "너 점 보기 전에… 딱 1분만! 나 옛날에 전쟁 어떻게 이겼는지 들어볼래? 😎",
 "때는 <em>적벽대전</em>. 조조가 배 <b>수천 척</b> 끌고 쳐들어왔어. 우리 쪽수? 처참하게 밀림 😱",
 "다들 '망했다~' 할 때 난 딴 걸 봤어. 하늘의 <em>'때'</em> 말이야 👀",
 "한겨울엔 북서풍이라 불로 공격하면 <b>우리가</b> 타 죽어 🔥 근데 계산해보니 딱 3일 뒤 밤, <em>동남풍</em>이 불더라 🌬️",
 "그 바람 부는 밤, 불을 질렀지. 사슬로 묶인 조조 배 수천 척이 싹 다 <b>불바다</b> 🔥🔥",
 "쪽수로 개밀렸는데 이겼어. 비결은 힘이 아니라 <em>'때'를 안 것</em>. 이게 바로 <b>기문둔갑</b> ㅎㅎ",
 "네 인생도 똑같아. 언제·어디로 움직일지 그 <em>'때'</em>를 내가 봐줄게 😉"
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
  document.getElementById('s-input').classList.add('on');scrollTo(0,0);refreshBal();}

/* ── 입력 폼 ── */
const fbox=document.getElementById('fields');
Object.entries(FIELDS).forEach(([k,v])=>{const d=document.createElement('div');
  d.className='fld'+(k===sel?' on':'');d.innerHTML='<span class="fi">'+(ICON[k]||'🪭')+'</span>'+v;
  d.onclick=()=>{sel=k;document.querySelectorAll('.fld').forEach(x=>x.classList.remove('on'));d.classList.add('on');};
  fbox.appendChild(d);});
document.getElementById('date').value='1996-05-12';

async function refreshBal(){const b=await (await fetch('/api/balance')).json();
  document.getElementById('bal').textContent='🪭 부채 '+(b.balance||0);}
function charge(pkg){ location.href='/pay?pkg='+encodeURIComponent(pkg); }

async function run(){
  const date=document.getElementById('date').value,time=document.getElementById('time').value,gender=document.getElementById('gender').value;
  if(!date){alert('태어난 날을 넣어줘~');return;}
  document.getElementById('spin').style.display='block';document.getElementById('result').innerHTML='';
  const d=await (await fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date,time,gender,field:sel})})).json();
  document.getElementById('spin').style.display='none';render(d);refreshBal();
  document.getElementById('result').scrollIntoView({behavior:'smooth'});
}

function render(d){
  const R=document.getElementById('result');
  if(d.error){R.innerHTML='<div class="card">오류: '+d.error+'</div>';return;}
  const img='/char/'+(CHAR[sel]||'gongmyeong')+'.png';
  let h='<div class="rp"><div class="hero"><div class="disc"><img class="hava" src="'+img+'"></div>'
    +'<div><span class="tag">'+(ICON[sel]||'🪭')+' '+d.field+'</span><div class="who2">'+d.char+'</div></div></div>';
  h+='<div class="judge"><span class="lb">✦ 네 판 · 무료로 슬쩍</span>'+d.saju_line+'</div>';
  const locked=d.need_charge;
  if(locked){
    let rows='';(d.hook||[]).forEach(e=>{rows+='<div class="hr"><span class="k">'+e.label+'</span><span class="v">'+e.text+'</span></div>';});
    let pk='';for(const[k,v]of Object.entries(d.packages)){pk+='<div class="pkg'+(v.best?' best':'')+'" onclick="charge(\''+k+'\')"><div class="n">'+v.buchae+'부채</div><div class="w">'+v.won.toLocaleString()+'원</div>'+(v.tag?'<div class="ptag">'+v.tag+'</div>':'')+'</div>';}
    let cta='<div class="pk">'+pk+'</div>';
    h+='<div class="hookwrap"><div class="htitle">그래서 <em>언제·어디·어떻게?</em> 👀</div>'
      +'<div class="blur">'+rows+'</div>'
      +'<div class="pw"><div class="plock">🔒 여기부턴 부채 까고!</div><div class="pmsg">'+d.teaser+'</div>'+cta+'</div></div>';
  }else{
    h+='<div class="rpt" id="rpt"><span class="cur">▍</span></div><div class="tagf" id="tagf">🪭 '+d.char+'가 지금 붓을 들었어… 실시간으로 써지는 중</div>';
    h+='<div class="fu" id="fubox" style="display:none"><div class="futitle">🪭 '+d.char+'한테 더 궁금한 거 있어? <span>부채 1개·500원</span></div>'
      +'<div id="fulog"></div>'
      +'<div class="furow"><input id="fuq" placeholder="예) 올해 이직해도 될까?" onkeydown="if(event.key===\'Enter\')askFollow()"><button onclick="askFollow()">보내기</button></div></div>';
  }
  h+='</div>';R.innerHTML=h;
  if(!locked && d.ready){streamReport(d);}
}
async function streamReport(d){
  const rpt=document.getElementById('rpt');const tagf=document.getElementById('tagf');
  const date=document.getElementById('date').value,time=document.getElementById('time').value,gender=document.getElementById('gender').value;
  let txt='';
  try{
    const resp=await fetch('/api/report_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date,time,gender,field:sel})});
    const reader=resp.body.getReader();const dec=new TextDecoder();
    const near=()=>window.innerHeight+window.scrollY>=document.body.scrollHeight-160;
    while(true){const {done,value}=await reader.read();if(done)break;
      txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';
      if(near())window.scrollTo(0,document.body.scrollHeight);
    }
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(전송이 끊겼어. 새로고침 없이 다시 눌러줘)';}
  tagf.textContent=(d.engine_note||'')+' · 남은 부채 '+d.balance+'개';
  const fb=document.getElementById('fubox');if(fb)fb.style.display='block';
  refreshBal();
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
async function runNaming(){
  const seong=document.getElementById('nseong').value.trim();
  const seong_hanja=seongHanja();
  const date=document.getElementById('ndate').value,time=document.getElementById('ntime').value||'12:00';
  const gender=document.getElementById('ngender').value;
  if(!seong){alert('아기 성을 한 글자 넣어줘 (예: 김)');return;}
  if(!date){alert('아기 태어난 날을 넣어줘~');return;}
  document.getElementById('nspin').style.display='block';document.getElementById('nresult').innerHTML='';
  let d;
  try{d=await(await fetch('/api/naming',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seong,seong_hanja,date,time,gender})})).json();}
  catch(e){document.getElementById('nspin').style.display='none';document.getElementById('nresult').innerHTML='<div class="ncard">오류가 났어. 다시 해줄래?</div>';return;}
  document.getElementById('nspin').style.display='none';
  if(d.error){document.getElementById('nresult').innerHTML='<div class="ncard">'+d.error+'</div>';return;}
  if(d.need_charge){
    let pk='';for(const[k,v]of Object.entries(d.packages)){pk+='<div class="pkg'+(v.best?' best':'')+'" onclick="charge(\''+k+'\')"><div class="n">'+v.buchae+'부채</div><div class="w">'+v.won.toLocaleString()+'원</div>'+(v.tag?'<div class="ptag">'+v.tag+'</div>':'')+'</div>';}
    document.getElementById('nresult').innerHTML='<div class="ncard"><div class="nmean">'+d.teaser+'</div><div class="pk">'+pk+'</div></div>';return;}
  renderNaming(d.result,d.balance,{seong,seong_hanja,date,time,gender});refreshBal();
  document.getElementById('nresult').scrollIntoView({behavior:'smooth'});
}
function renderNaming(r,balance,q){
  const G=['원격','형격','이격','정격'],KR={원격:'초년',형격:'청년',이격:'장년',정격:'말년'};
  let h='<div class="ncard" style="background:#eef3ff"><div class="nmean">🎏 아기 사주(일간 <b>'+r.사주.일간+'</b>)에 <b>'+(r.사주.부족오행.join(', ')||'큰 부족 없')+'</b> 기운이 부족해서, 그걸 채우는 이름으로 골랐어</div></div>';
  r.한자후보.forEach(c=>{
    let sg='';G.forEach(k=>{const x=c.사격[k];sg+='<div class="sg"><b>'+KR[k]+'운</b><span>'+x.수+'수 <span class="ok">'+x.등급+'</span></span></div>';});
    h+='<div class="ncard"><div class="nname">'+r.성.한글+c.이름+'<span class="hj">'+r.성.한자+c.한자+'</span></div>'
      +'<div class="nmean">뜻: '+c.훈.join(' · ')+' · 부족한 '+(c.보완오행.join('/')||'오행')+' 보완</div>'
      +'<div class="sgrid">'+sg+'</div></div>';
  });
  if(r.순한글후보&&r.순한글후보.length){h+='<div class="nsun">🌸 <b>순한글 이름</b><br>'+r.순한글후보.map(x=>x.이름+' <span style="color:#a99">('+x.뜻+')</span>').join(' · ')+'</div>';}
  h+='<div class="rpt" id="nrpt"><span class="cur">▍</span></div><div class="tagf" id="ntagf">🎏 공명이가 이름 풀이 쓰는 중…</div>';
  document.getElementById('nresult').innerHTML=h;
  streamNaming(q,balance);
}
async function streamNaming(q,balance){
  const rpt=document.getElementById('nrpt'),tagf=document.getElementById('ntagf');let txt='';
  try{
    const resp=await fetch('/api/naming_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)});
    const reader=resp.body.getReader(),dec=new TextDecoder();
    while(true){const {done,value}=await reader.read();if(done)break;txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';}
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(풀이 전송이 끊겼어)';}
  tagf.textContent='🎏 정통 수리성명학 · 남은 부채 '+balance+'개';
}
async function runAnalyze(){
  const name=document.getElementById('aname').value.trim();
  const hanja=document.getElementById('ahanja').value.trim();
  const date=document.getElementById('adate').value,time=document.getElementById('atime').value||'12:00';
  const gender=document.getElementById('agender').value;
  if(!name){alert('이름을 한글로 넣어줘 (예: 김다슬)');return;}
  if(!date){alert('태어난 날을 넣어줘~');return;}
  document.getElementById('aspin').style.display='block';document.getElementById('aresult').innerHTML='';
  let d;
  try{d=await(await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,hanja,date,time,gender})})).json();}
  catch(e){document.getElementById('aspin').style.display='none';document.getElementById('aresult').innerHTML='<div class="ncard">오류가 났어. 다시 해줄래?</div>';return;}
  document.getElementById('aspin').style.display='none';
  if(d.error){document.getElementById('aresult').innerHTML='<div class="ncard">'+d.error+'</div>';return;}
  if(d.need_charge){
    let pk='';for(const[k,v]of Object.entries(d.packages)){pk+='<div class="pkg'+(v.best?' best':'')+'" onclick="charge(\''+k+'\')"><div class="n">'+v.buchae+'부채</div><div class="w">'+v.won.toLocaleString()+'원</div>'+(v.tag?'<div class="ptag">'+v.tag+'</div>':'')+'</div>';}
    document.getElementById('aresult').innerHTML='<div class="ncard"><div class="nmean">'+d.teaser+'</div><div class="pk">'+pk+'</div></div>';return;}
  renderAnalyze(d.result,d.balance,{name,hanja,date,time,gender});refreshBal();
  document.getElementById('aresult').scrollIntoView({behavior:'smooth'});
}
function renderAnalyze(r,balance,q){
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
  h+='<div class="rpt" id="arpt"><span class="cur">▍</span></div><div class="tagf" id="atagf">🔎 공명이가 감정 쓰는 중…</div>';
  document.getElementById('aresult').innerHTML=h;
  streamAnalyze(q,balance);
}
async function streamAnalyze(q,balance){
  const rpt=document.getElementById('arpt'),tagf=document.getElementById('atagf');let txt='';
  try{
    const resp=await fetch('/api/analyze_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)});
    const reader=resp.body.getReader(),dec=new TextDecoder();
    while(true){const {done,value}=await reader.read();if(done)break;txt+=dec.decode(value,{stream:true});
      rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'<span class="cur">▍</span>';}
    rpt.innerHTML=txt.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  }catch(e){rpt.innerHTML=txt+'<br>(전송이 끊겼어)';}
  tagf.textContent='🔎 성명 감정 · 남은 부채 '+balance+'개';
}
function addFu(who,text,char){const log=document.getElementById('fulog');if(!log)return null;
  const b=document.createElement('div');b.className='fubub '+(who==='me'?'me':'ch');
  b.innerHTML=(who==='me'?'':(char?'<b>'+char+'</b><br>':''))+text;
  log.appendChild(b);b.scrollIntoView({behavior:'smooth',block:'nearest'});return b;}
async function askFollow(){
  const el=document.getElementById('fuq');const q=(el.value||'').trim();if(!q)return;
  const date=document.getElementById('date').value,time=document.getElementById('time').value,gender=document.getElementById('gender').value;
  el.value='';addFu('me',q);const wait=addFu('ch','🪭 생각 중…','');
  let d;try{d=await(await fetch('/api/followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date,time,gender,field:sel,question:q})})).json();}catch(e){if(wait)wait.remove();addFu('ch','(오류가 났어. 다시 해봐)','');return;}
  if(wait)wait.remove();
  if(d.error){addFu('ch','('+d.error+')',d.char);return;}
  if(d.need_charge){let pk='';for(const[k,v]of Object.entries(d.packages)){pk+='<div class="pkg'+(v.best?' best':'')+'" onclick="charge(\''+k+'\')"><div class="n">'+v.buchae+'부채</div><div class="w">'+v.won.toLocaleString()+'원</div>'+(v.tag?'<div class="ptag">'+v.tag+'</div>':'')+'</div>';}
    addFu('ch',d.teaser+'<div class="pk" style="margin-top:8px">'+pk+'</div>',d.char);}
  else{addFu('ch',d.answer.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>'),d.char);}
  refreshBal();
}
</script></body></html>"""


@app.route("/")
def index():
    import json
    from flask import make_response
    labels = {k: v["name"] for k, v in FIELDS.items()}
    html = render_template_string(PAGE.replace("%%FIELDS%%", json.dumps(labels, ensure_ascii=False)))
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
def dev_topup():
    """개발용 부채 충전. 예: /dev?code=비밀코드&n=20  (결제 없이 테스트)."""
    from flask import make_response
    code = request.args.get("code", "")
    secret = os.environ.get("DEV_CODE", "jeom2026-gongmyeong")
    if code != secret:
        return "🔒 코드가 틀렸어", 403
    try:
        n = min(int(request.args.get("n", 20)), 200)
    except Exception:
        n = 20
    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    bal = grant_buchae(uid, n)
    resp = make_response(
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<div style='font-family:sans-serif;padding:40px;text-align:center'>"
        f"<h2>🪭 부채 {n}개 충전 완료</h2><p>현재 잔액: <b>{bal}개</b></p>"
        f"<p><a href='/'>홈으로 가서 작명/분석 눌러보기 →</a></p></div>")
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
    return resp


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

    # 로그인 없이 진행 — 쿠키 게스트 지갑 자동 (첫 리포트 무료)
    # ★여기선 '열 수 있는지'만 확인(부채 차감/LLM 생성 안 함).
    #   실제 차감+생성은 /api/report_stream 에서 실시간 스트리밍으로 처리.
    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    chk = can_open(uid, field)
    if not chk["ok"]:
        resp = jsonify({**base(), "locked": True, "need_charge": True,
                        "balance": chk["balance"], "cost": chk["cost"], "packages": BUCHAE_PACKAGES,
                        "teaser": f"부채 <em>1개 500원</em>이면<br>{facts['캐릭터']} 리포트가 딱 열려!"})
        if set_ck:
            resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
        return resp

    # 열람 가능 — 프론트가 곧바로 /api/report_stream 을 열어 실시간 생성
    resp = jsonify({**base(), "locked": False, "ready": True,
                    "engine_note": "해석엔진: 실시간 · 계산: 검증된 엔진",
                    "balance": chk.get("balance", get_balance(uid))})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
    return resp


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

    prompt, facts = make_full_prompt(dt, gender, field)
    uid = current_user()
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
    get_or_create_user(uid)
    opened = open_report(uid, field)   # ★여기서 부채 차감
    if not opened["ok"]:
        return Response("[부채가 부족해요. 새로고침 후 충전해줘]", mimetype="text/plain; charset=utf-8")

    def gen():
        for piece in stream_interpretation(prompt):
            yield piece

    resp = Response(stream_with_context(gen()), mimetype="text/plain; charset=utf-8")
    resp.headers["X-Accel-Buffering"] = "no"   # 프록시 버퍼링 끔(실시간 전달)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/followup", methods=["POST"])
def api_followup():
    """리포트 뒤 추가 질문 → 부채 1개(500원) 차감하고 캐릭터가 답."""
    data = request.get_json(force=True)
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"error": "날짜/시간 형식이 올바르지 않습니다."}), 400
    gender = data.get("gender", "F")
    field = data.get("field", "overall")
    if field not in FIELDS:
        field = "overall"
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "질문을 입력해줘"}), 400

    prompt, facts = make_followup_prompt(dt, gender, field, question)
    char = facts["캐릭터"]

    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    opened = open_report(uid, "followup")   # 부채 1개 차감
    if not opened["ok"]:
        resp = jsonify({"need_charge": True, "char": char,
                        "balance": opened["balance"], "packages": BUCHAE_PACKAGES,
                        "teaser": f"부채 <em>1개(500원)</em>면 {char}가 답해줄게!"})
        if set_ck:
            resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
        return resp

    llm = generate_interpretation(prompt)
    if llm["engine"] == "demo(no-key)":
        answer = f"🪭 (여기에 {char}의 답변이 자동 생성됩니다. LLM 키를 넣으면 진짜 답이 나와요. 부채는 정상 차감됨.)"
    else:
        answer = llm["text"]
    resp = jsonify({"answer": answer, "char": char, "balance": opened["balance"]})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
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

    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    chk = can_open(uid, "analysis")
    if not chk["ok"]:
        resp = jsonify({"need_charge": True, "balance": chk["balance"], "cost": chk["cost"],
                        "packages": BUCHAE_PACKAGES,
                        "teaser": "이름 분석은 <em>부채 2개(1,000원)</em>! 네 이름 장단점 싹 진단해줄게"})
        if set_ck:
            resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
        return resp
    opened = open_report(uid, "analysis")   # 부채 2개 차감
    resp = jsonify({"ok": True, "result": result, "balance": opened["balance"]})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
    return resp


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
    try:
        dt = datetime.strptime(f"{data['date']} {data.get('time','12:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"error": "아기 생년월일/시간을 확인해줘."}), 400
    gender = data.get("gender", "M")

    from naming_engine import generate_names
    # 성씨/입력 검증 먼저 (부채 차감 전에)
    result = generate_names(seong, dt, gender, seong_hanja=seong_hanja)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    if not result["한자후보"]:
        return jsonify({"error": "조건에 맞는 이름을 못 찾았어. 시간을 넣거나 다른 성씨로 해줄래?"}), 400

    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    chk = can_open(uid, "naming")
    if not chk["ok"]:
        resp = jsonify({"need_charge": True, "balance": chk["balance"], "cost": chk["cost"],
                        "packages": BUCHAE_PACKAGES,
                        "teaser": "작명은 <em>부채 5개(2,500원)</em>! 사주 맞춘 이름 후보가 좍 나와"})
        if set_ck:
            resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
        return resp
    opened = open_report(uid, "naming")   # 부채 5개 차감
    resp = jsonify({"ok": True, "result": result, "balance": opened["balance"]})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
    return resp


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
    prompt, result = make_naming_prompt(seong, dt, gender, seong_hanja=seong_hanja)
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
<div class="sum"><div class="b">__BUCHAE__부채</div><div class="w">결제 금액 __WON__원</div></div>
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
      successUrl: location.origin + "/pay/success?pkg=__PKG__",
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
    pkg = request.args.get("pkg", "fan_3")
    if pkg not in BUCHAE_PACKAGES:
        return _result("😵", "잘못된 상품", "존재하지 않는 부채 상품이에요.")
    p = BUCHAE_PACKAGES[pkg]
    uid = current_user() or ("guest_" + uuid.uuid4().hex[:8])
    order_id = "jmd_" + uuid.uuid4().hex[:20]
    html = (PAY_PAGE.replace("__CK__", TOSS_CLIENT_KEY).replace("__CUST__", uid)
            .replace("__AMT__", str(p["won"])).replace("__OID__", order_id)
            .replace("__ONAME__", f"점며든다 {p['buchae']}부채").replace("__PKG__", pkg)
            .replace("__BUCHAE__", str(p["buchae"])).replace("__WON__", f"{p['won']:,}"))
    return render_template_string(html)


@app.route("/pay/success")
def pay_success():
    pkg = request.args.get("pkg", "")
    payment_key = request.args.get("paymentKey", "")
    order_id = request.args.get("orderId", "")
    amount = request.args.get("amount", "0")
    if pkg not in BUCHAE_PACKAGES:
        return _result("😵", "결제 확인 실패", "상품 정보를 확인할 수 없어요.")
    # 금액 위변조 방지: 서버 가격과 대조
    if int(amount) != BUCHAE_PACKAGES[pkg]["won"]:
        return _result("🚫", "금액이 맞지 않아요", "결제 금액이 상품 가격과 달라 취소했어요.")
    res, err = toss_confirm(payment_key, order_id, amount)
    if err:
        return _result("😢", "결제 승인 실패", err.get("message", "다시 시도해 주세요."))
    uid = current_user()
    if not uid:
        return _result("🙃", "로그인이 필요해요", "결제는 됐지만 로그인 세션이 없어요. 문의 주세요.")
    charge_buchae(uid, pkg, paid=True)
    bal = get_balance(uid)
    return _result("🎉", "충전 완료!",
                   f"{BUCHAE_PACKAGES[pkg]['buchae']}부채가 들어왔어요. 지금 부채 {bal}개!", color="#2b2bff")


@app.route("/pay/fail")
def pay_fail():
    msg = request.args.get("message", "결제가 취소됐거나 실패했어요.")
    return _result("🥲", "결제 실패", msg)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
