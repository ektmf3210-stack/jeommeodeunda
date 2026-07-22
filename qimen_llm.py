# -*- coding: utf-8 -*-
"""
LLM 호출 훅.
- 환경변수 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 가 있으면 실제 해석 생성.
- 둘 다 없으면 prompt만 그대로 반환(오프라인/키 없이도 앱이 동작하도록).
"""
import os


def generate_interpretation(prompt):
    """prompt(str) -> {'text': 해석텍스트, 'engine': 사용모델/모드}."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            msg = client.messages.create(
                model=os.environ.get("QIMEN_MODEL", "claude-sonnet-5"),
                max_tokens=16000,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content
                           if getattr(b, "type", "") == "text")
            return {"text": text or "(리포트를 불러오지 못했어요. 다시 시도해 주세요.)",
                    "engine": "anthropic"}
        except Exception as e:  # noqa
            return {"text": f"[Anthropic 호출 실패: {e}]\n\n아래는 생성된 프롬프트입니다.\n\n{prompt}",
                    "engine": "error"}

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model=os.environ.get("QIMEN_MODEL", "gpt-4o"),
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )
            return {"text": resp.choices[0].message.content, "engine": "openai"}
        except Exception as e:  # noqa
            return {"text": f"[OpenAI 호출 실패: {e}]\n\n아래는 생성된 프롬프트입니다.\n\n{prompt}",
                    "engine": "error"}

    # 키 없음 — 프롬프트만 반환(데모 모드)
    return {
        "text": ("⚠️ LLM API 키가 설정되지 않아 자동 해석을 생성하지 못했습니다.\n"
                 "환경변수 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 설정하면 이 자리에 "
                 "근거 기반 해석이 자동 생성됩니다.\n\n"
                 "── 아래는 LLM에 전달될 '근거 주입 프롬프트' 원문입니다 ──\n\n" + prompt),
        "engine": "demo(no-key)",
    }


def stream_interpretation(prompt):
    """prompt -> 실시간 텍스트 조각(제너레이터). 글자가 써지는 대로 흘려보낸다."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("QIMEN_MODEL")

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            with client.messages.stream(
                model=model or "claude-sonnet-5",
                max_tokens=16000,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for piece in stream.text_stream:
                    if piece:
                        yield piece
            return
        except Exception as e:  # noqa
            yield f"\n\n[생성 중 오류: {e}]"
            return

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model=model or "gpt-4o",
                max_tokens=16000,
                stream=True,
                messages=[{"role": "user", "content": prompt}],
            )
            for chunk in resp:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except Exception as e:  # noqa
            yield f"\n\n[생성 중 오류: {e}]"
            return

    # 키 없음 — 데모: 한 글자씩 흘려서 스트리밍 UX 확인 가능
    demo = ("🪭 (데모 모드) LLM 키를 넣으면 여기에 실제 풀이가 실시간으로 써져요.\n"
            "부채는 정상 차감됐어요. 이 문장은 스트리밍이 잘 되는지 보여주는 예시야.")
    for ch in demo:
        yield ch
