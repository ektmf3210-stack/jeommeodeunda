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
from flask import Flask, request, jsonify, render_template_string, send_from_directory, redirect

from report_prompt import make_full_prompt
from report_generator import FIELDS
from qimen_llm import generate_interpretation
from buchae_system import (get_balance, open_report, charge_buchae,
                           can_open, BUCHAE_PACKAGES, get_or_create_user)

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
.btn2{width:100%;padding:14px;border:3px solid var(--navy);border-radius:15px;background:var(--blue);color:#fff;font-family:'Black Han Sans';font-size:16px;box-shadow:3px 4px 0 var(--yellow);cursor:pointer}
.rpt{padding:17px;white-space:pre-wrap;line-height:1.95;font-size:14.5px;color:#2e2148}.rpt b{color:var(--pink)}
.tagf{padding:0 17px 15px;font-size:10.5px;color:#a99acb;font-family:'Jua'}
.foot{font-size:10px;color:#7a6a9a;text-align:center;padding:6px 18px 30px;line-height:1.7}
</style></head><body>
<div class="ph">

<!-- 인트로 채팅 -->
<section class="screen on" id="s-intro">
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
let mi=0;
function typing(){const t=document.createElement('div');t.className='row';t.id='typing';
  t.innerHTML='<img class="av" src="/char/gongmyeong.png"><div class="tb"><span></span><span></span><span></span></div>';
  chat.appendChild(t);t.classList.add('show');scrollTo(0,document.body.scrollHeight);}
function nextMsg(){const t=document.getElementById('typing');if(t)t.remove();
  if(mi>=MSG.length){document.getElementById('ctaw').classList.add('show');return;}
  const r=document.createElement('div');r.className='row';
  r.innerHTML='<img class="av" src="/char/gongmyeong.png"><div class="bub">'+MSG[mi]+'</div>';
  chat.appendChild(r);requestAnimationFrame(()=>r.classList.add('show'));scrollTo(0,document.body.scrollHeight);mi++;
  setTimeout(()=>{typing();setTimeout(nextMsg,1100);},Math.min(1500,700+MSG[mi-1].replace(/<[^>]+>/g,'').length*22));}
setTimeout(()=>{typing();setTimeout(nextMsg,900);},500);

/* ── 화면 전환 ── */
function toInput(){document.getElementById('s-intro').classList.remove('on');
  document.getElementById('ctaw').classList.remove('show');
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
    let pk='';for(const[k,v]of Object.entries(d.packages)){pk+='<div class="pkg'+(v.best?' best':'')+'" onclick="charge(\''+k+'\')"><div class="n">'+v.buchae+'부채</div><div class="w">'+v.won.toLocaleString()+'원</div></div>';}
    let cta='<div class="pk">'+pk+'</div>';
    h+='<div class="hookwrap"><div class="htitle">그래서 <em>언제·어디·어떻게?</em> 👀</div>'
      +'<div class="blur">'+rows+'</div>'
      +'<div class="pw"><div class="plock">🔒 여기부턴 부채 까고!</div><div class="pmsg">'+d.teaser+'</div>'+cta+'</div></div>';
  }else{
    h+='<div class="rpt">'+d.report.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'</div><div class="tagf">'+d.engine_note+' · 남은 부채 '+d.balance+'개</div>';
  }
  h+='</div>';R.innerHTML=h;
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
    uid = current_user()
    set_ck = None
    if not uid:
        uid = "guest_" + uuid.uuid4().hex[:10]
        set_ck = uid
    get_or_create_user(uid)
    opened = open_report(uid, field)
    if not opened["ok"]:
        resp = jsonify({**base(), "locked": True, "need_charge": True,
                        "balance": opened["balance"], "cost": opened["cost"], "packages": BUCHAE_PACKAGES,
                        "teaser": f"부채 <em>1개 500원</em>이면<br>{facts['캐릭터']} 3천자가 딱 열려!"})
        if set_ck:
            resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
        return resp

    llm = generate_interpretation(prompt)
    if llm["engine"] == "demo(no-key)":
        report = ("🪭 (여기에 " + facts["캐릭터"] + "의 3천자 맞춤 리포트가 자동 생성됩니다)\n\n"
                  "· LLM API 키를 설정하면 이 자리에 실제 리포트가 나와요.\n"
                  "· 부채는 정상 차감되었습니다 (남은 부채: %d개).\n\n"
                  "── 생성 근거 프롬프트(개발 확인용) ──\n\n" % opened["balance"] + prompt[:500] + " …")
        note = "데모 모드 · 계산 엔진/부채 시스템 정상"
    else:
        report = llm["text"]
        note = "해석엔진: " + llm["engine"] + " · 계산: 검증된 엔진"

    resp = jsonify({**base(), "report": report, "engine_note": note, "locked": False,
                    "balance": opened["balance"], "free_used": opened.get("free", False)})
    if set_ck:
        resp.set_cookie("uid", set_ck, max_age=60 * 60 * 24 * 365)
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
