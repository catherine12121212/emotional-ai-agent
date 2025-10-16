# app_emotion.py
# ---------------------------------------------------------
# Emotion-Aware AI Companion (with graceful model fallback)
# - Algorithm: perception → evaluation → intent → strategy → generation
# - No crisis/safety confirmation flow (per request)
# - Auto-detect available models; gracefully fall back to latest usable
# ---------------------------------------------------------

import os, re, json, random, datetime
import streamlit as st
from openai import OpenAI

# ---------------------------
# Streamlit & API setup
# ---------------------------
st.set_page_config(page_title="Emotion-Aware AI Companion", page_icon="🌿", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Go to Settings → Secrets and add:\nOPENAI_API_KEY = sk-xxxx")
    st.stop()

client = OpenAI(api_key=api_key)

# ---------------------------
# Base persona (no crisis script)
# ---------------------------
BASE_PERSONA = """
You are a warm, emotionally intelligent AI companion and counselor-style assistant.
Your job is to listen, reflect, and respond with empathy.
Use therapeutic communication techniques such as active listening, validation,
gentle reframing, and clarity-building. Avoid generic cheerleading.
Follow a 3-step structure in each turn:
1) Reflect Emotion (mirror and name feelings without judgment)
2) Structure the Issue (clarify, organize, and reduce overwhelm)
3) Suggest a Gentle Step (one small, concrete action OR a reflective question)
Tone: calm, grounded, kind, non-clinical, and concise.
Do not include any crisis or safety protocol in your responses.
"""

# =========================================================
# Model discovery & graceful fallback
# =========================================================

# 偏好順序：會自動從上到下挑選你帳戶可用的第一個
PREFERRED_MODELS = [
    # GPT-5 系列（若你的帳戶已開通會自動使用）
    "gpt-5",
    "gpt-5-mini",
    # 其他最新版（依你帳戶實際權限）
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
]

@st.cache_data(show_spinner=False, ttl=300)
def list_available_models_safely():
    """嘗試列出該 API key 可用的模型清單；失敗則回空清單。"""
    try:
        models = client.models.list()
        return sorted([m.id for m in models.data])
    except Exception:
        return []

def pick_best_model(available_ids):
    """從 available_ids 中挑 PREFERRED_MODELS 的第一個；若 available_ids 為空，直接使用偏好清單逐一嘗試。"""
    if available_ids:
        for m in PREFERRED_MODELS:
            if m in available_ids:
                return m
    # 若取不到清單或清單沒命中，就先回偏好表頭，實際呼叫時會再做多重降級重試
    return PREFERRED_MODELS[0]

def safe_chat_completion(messages, temperature=0.8):
    """
    優雅降級：
    1) 先用「可用模型清單」命中的最佳候選
    2) 失敗則依序嘗試 PREFERRED_MODELS
    3) 全數失敗則回一段友善訊息
    """
    available = list_available_models_safely()
    trial_order = []

    # 先放一個「最佳可用」做第一順位
    best = pick_best_model(available)
    if best:
        trial_order.append(best)

    # 再補上整個偏好清單（去重）
    for m in PREFERRED_MODELS:
        if m not in trial_order:
            trial_order.append(m)

    last_err = None
    used_model = None
    for m in trial_order:
        try:
            resp = client.chat.completions.create(
                model=m,
                messages=messages,
                temperature=temperature,
            )
            used_model = m
            return resp.choices[0].message.content.strip(), used_model
        except Exception as e:
            last_err = e
            continue

    # 全部失敗時的保底訊息（不中斷 App）
    friendly = (
        "抱歉，我剛剛在產生回覆時遇到模型連線或權限設定的問題。"
        "請稍後再試，或在側邊欄檢查『可用模型清單』是否含有 gpt-4o / gpt-4o-mini 等。"
    )
    return friendly, used_model

# =========================================================
# Emotion & intent detection
# =========================================================
EMOTION_LEX = {
    "anxiety": ["anxious","panic","panicking","nervous","worried","pressure","stressed","overthinking","overwhelm","tense","afraid","scared"],
    "sadness": ["sad","lonely","upset","tired","hurt","empty","numb","down","blue","depressed","cry","crying","loss","grief"],
    "anger":   ["angry","frustrated","irritated","mad","furious","rage","annoyed","resentful"],
    "shame":   ["ashamed","shame","embarrassed","humiliated","guilty","worthless","not enough","failure"],
    "calm":    ["happy","grateful","peaceful","content","okay","fine","relieved","light"],
}
TONE_PROMPTS = {
    "anxiety": "Use a calm, grounding tone. Slow the pace and reduce cognitive load.",
    "sadness": "Use a warm, tender tone. Acknowledge the weight and convey presence.",
    "anger":   "Use a steady, validating tone. Normalize anger and support clarity before action.",
    "shame":   "Use a gentle, non-judgmental tone. Reduce self-criticism and support self-compassion.",
    "calm":    "Use an affirming tone. Reinforce stability, agency, and mindful awareness.",
    "neutral": "Use a curious, open tone. Invite gentle reflection."
}

def detect_emotion(text: str) -> str:
    tl = text.lower()
    for emo, kws in EMOTION_LEX.items():
        if any(k in tl for k in kws):
            return emo
    return "neutral"

def analyze_intent_and_risk(text: str):
    """沒有危機轉介，只做意圖＋風險指標（用來調整語氣/介入選擇）"""
    tl = text.lower()
    # intent
    if any(p in tl for p in ["what should i", "should i", "how do i", "how should i", "what can i do", "help me", "advise"]):
        intent = "help"
    elif any(p in tl for p in ["i'm sorry","my fault","i shouldn't","i always mess up","blame myself"]):
        intent = "self-blame"
    elif any(p in tl for p in ["whatever","forget it","no point","doesn't matter"]):
        intent = "avoid"
    elif any(p in tl for p in ["why am i","why do i","i wonder","maybe i","i want to understand"]):
        intent = "explore"
    else:
        intent = "venting"
    # risk marker score (僅用於調整建議，非轉介)
    risk_score = 0
    if any(w in tl for w in ["disappear","give up on life","i don't want to be here"]): risk_score += 2
    if any(w in tl for w in ["die","death","kill myself","suicide","hurt myself"]):     risk_score += 3
    if any(w in tl for w in ["can't sleep","awake all night","no appetite","binge"]):   risk_score += 1
    return intent, min(risk_score, 5)

# =========================================================
# Interventions toolbox
# =========================================================
INTERVENTIONS = {
    "CBT_THOUGHT_RECORD": {
        "name": "CBT Thought Record",
        "desc": "Clarify the chain: situation → automatic thought → feeling → evidence for/against → balanced thought.",
        "howto": [
            "Write the situation in one sentence.",
            "Note the automatic thought verbatim.",
            "Rate your feeling (0–10).",
            "List evidence that supports the thought; list evidence that challenges it.",
            "Draft a more balanced alternative thought.",
            "Re-rate the feeling (0–10) and compare."
        ]
    },
    "DBT_TIPP": {
        "name": "DBT TIPP",
        "desc": "Short, physiological resets to downshift strong emotion.",
        "howto": [
            "Temperature: cool your face/neck with water ~30–60 seconds.",
            "Intense movement: 60–120 seconds of brisk movement or shakes.",
            "Paced breathing: inhale 4s, exhale 6s for 2 minutes.",
            "Progressive muscle release: clench 5s, release 10s, head-to-toe."
        ]
    },
    "GROUNDING_54321": {
        "name": "5-4-3-2-1 Grounding",
        "desc": "Use the senses to anchor attention in the present.",
        "howto": [
            "Notice 5 things you can see.",
            "Notice 4 things you can touch.",
            "Notice 3 things you can hear.",
            "Notice 2 things you can smell.",
            "Notice 1 thing you can taste or the sensation in your mouth."
        ]
    },
    "BREATH_BOX": {
        "name": "Box Breathing 4-4-4-4",
        "desc": "Stabilize pace and heart rate with square breathing.",
        "howto": [
            "Inhale for 4 seconds.",
            "Hold for 4 seconds.",
            "Exhale for 4 seconds.",
            "Hold for 4 seconds. Repeat 4 rounds."
        ]
    },
    "SELF_COMPASSION": {
        "name": "Self-Compassion Script",
        "desc": "Talk to yourself like you would to a close friend.",
        "howto": [
            "Name what hurts: “This is hard.”",
            "Normalize: “Struggle is part of being human.”",
            "Kind wish: “May I be gentle with myself right now.”"
        ]
    },
    "DESC_SCRIPT": {
        "name": "DESC Boundary Script",
        "desc": "Describe–Express–Specify–Consequences for clear, kind boundaries.",
        "howto": [
            "Describe facts (no blame).",
            "Express how it impacts you.",
            "Specify a clear, doable request.",
            "State the natural consequence if needed."
        ]
    },
    "SLEEP_HYGIENE_MINI": {
        "name": "Sleep Hygiene (Mini)",
        "desc": "Micro habits for today/tonight.",
        "howto": [
            "Fix your wake-up time (even if sleep was short).",
            "Get morning light 10–20 minutes.",
            "No caffeine after ~8 hours before bed.",
            "Screens off or dimmed 60 minutes before sleep; make a 'worry list' on paper."
        ]
    },
    "BODY_SCAN": {
        "name": "Mindful Body Scan",
        "desc": "Release tension with awareness, head to toe.",
        "howto": [
            "Close eyes; notice forehead → jaw → neck → shoulders.",
            "Scan arms → hands; then chest → belly → back.",
            "Scan hips → legs → feet; breathe into any tight spots.",
            "Gently open eyes and notice one thing you appreciate."
        ]
    },
    "REFLECTIVE_QUESTION": {
        "name": "Reflective Question",
        "desc": "Perspective-taking to unhook from fusion.",
        "howto": [
            "If your closest friend was in this spot, what would you say to them?",
            "Which part of you needs most care right now: body, mind, or heart?",
            "What’s the smallest kind step that doesn’t make things worse?"
        ]
    },
    "ACTION_STEP": {
        "name": "Tiny Action Plan",
        "desc": "Create a 10-minute micro-step to regain agency.",
        "howto": [
            "Name the smallest helpful task (≤10 minutes).",
            "Decide when in the next 24 hours you’ll do it.",
            "Define a visible 'done' signal (checkbox, timer, photo)."
        ]
    },
    "GRATITUDE_PROMPT": {
        "name": "Gratitude Prompt",
        "desc": "Rebalance attentional bias by noting small good things.",
        "howto": [
            "List three small things you’re grateful for today.",
            "Write one sentence about why each matters to you."
        ]
    },
    "EMOTIONAL_LABELING": {
        "name": "Emotional Labeling",
        "desc": "Name and rate feelings to reduce intensity.",
        "howto": [
            "Pick 1–2 words for the feeling (e.g., anxious, sad).",
            "Rate intensity 0–10 now.",
            "After one short practice (breath/ground), re-rate and compare."
        ]
    }
}

INTERVENTION_ROUTER = {
    "anxiety": {
        "venting":  ["GROUNDING_54321","BREATH_BOX","EMOTIONAL_LABELING","ACTION_STEP"],
        "help":     ["CBT_THOUGHT_RECORD","BREATH_BOX","ACTION_STEP"],
        "self-blame":["SELF_COMPASSION","EMOTIONAL_LABELING","CBT_THOUGHT_RECORD"],
        "explore":  ["REFLECTIVE_QUESTION","EMOTIONAL_LABELING"],
        "avoid":    ["ACTION_STEP","BREATH_BOX"]
    },
    "sadness": {
        "venting":  ["SELF_COMPASSION","EMOTIONAL_LABELING","BODY_SCAN"],
        "help":     ["ACTION_STEP","GRATITUDE_PROMPT","SLEEP_HYGIENE_MINI"],
        "self-blame":["SELF_COMPASSION","CBT_THOUGHT_RECORD"],
        "explore":  ["REFLECTIVE_QUESTION","GRATITUDE_PROMPT"],
        "avoid":    ["ACTION_STEP","BODY_SCAN"]
    },
    "anger": {
        "venting":  ["DBT_TIPP","EMOTIONAL_LABELING"],
        "help":     ["DESC_SCRIPT","ACTION_STEP"],
        "self-blame":["SELF_COMPASSION","CBT_THOUGHT_RECORD"],
        "explore":  ["REFLECTIVE_QUESTION"],
        "avoid":    ["DBT_TIPP","ACTION_STEP"]
    },
    "shame": {
        "venting":  ["SELF_COMPASSION","EMOTIONAL_LABELING"],
        "help":     ["CBT_THOUGHT_RECORD","ACTION_STEP"],
        "self-blame":["SELF_COMPASSION","REFLECTIVE_QUESTION"],
        "explore":  ["REFLECTIVE_QUESTION","GRATITUDE_PROMPT"],
        "avoid":    ["ACTION_STEP","BREATH_BOX"]
    },
    "calm": {
        "venting":  ["GRATITUDE_PROMPT","ACTION_STEP"],
        "help":     ["ACTION_STEP","DESC_SCRIPT"],
        "self-blame":["SELF_COMPASSION"],
        "explore":  ["REFLECTIVE_QUESTION"],
        "avoid":    ["ACTION_STEP"]
    },
    "neutral": {
        "venting":  ["EMOTIONAL_LABELING","REFLECTIVE_QUESTION"],
        "help":     ["ACTION_STEP","CBT_THOUGHT_RECORD"],
        "self-blame":["SELF_COMPASSION"],
        "explore":  ["REFLECTIVE_QUESTION","GRATITUDE_PROMPT"],
        "avoid":    ["ACTION_STEP","BREATH_BOX"]
    }
}

def choose_intervention(emotion: str, intent: str, risk_score: int) -> str:
    pool = INTERVENTION_ROUTER.get(emotion, INTERVENTION_ROUTER["neutral"]).get(intent, INTERVENTION_ROUTER["neutral"]["venting"])
    if risk_score >= 3:
        priority = [k for k in pool if k in ("DBT_TIPP","BREATH_BOX","GROUNDING_54321","EMOTIONAL_LABELING")]
        if priority:
            return random.choice(priority)
    return random.choice(pool)

# =========================================================
# Core LLM reply generator (uses graceful fallback)
# =========================================================
def generate_structured_reply(user_text: str, emotion: str, intent: str, tone_instruction: str, intervention_key: str):
    module = INTERVENTIONS[intervention_key]
    module_name = module["name"]
    module_desc = module["desc"]

    sys = f"""{BASE_PERSONA}
Tone style: {tone_instruction}
Emotional focus: {emotion}; User intent: {intent}.
Keep to ~3 short paragraphs max.
"""

    tool_context = {
        "intervention": {
            "key": intervention_key,
            "name": module_name,
            "desc": module_desc,
            "howto": INTERVENTIONS[intervention_key]["howto"][:3]
        }
    }

    reply_text, used_model = safe_chat_completion(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user_text},
            {"role": "system", "content": "Context for Step 3 (intervention module):\n" + json.dumps(tool_context, ensure_ascii=False)}
        ],
        temperature=0.8,
    )
    return reply_text, module, used_model

# =========================================================
# Session state
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": BASE_PERSONA}]
if "log" not in st.session_state:
    st.session_state.log = []
if "last_used_model" not in st.session_state:
    st.session_state.last_used_model = None

# =========================================================
# UI
# =========================================================
st.title("🌙 Emotion-Aware AI Companion")
st.markdown("A gentle, emotionally intelligent AI that listens and responds with empathy — with automatic model fallback.")

with st.sidebar:
    st.subheader("Response Engine")
    avail_ids = list_available_models_safely()
    if avail_ids:
        st.caption("✅ 你的帳戶目前可用模型：")
        st.code("\n".join(avail_ids), language="text")
    else:
        st.caption("⚠️ 目前無法列出模型（可能是權限或網路問題）。我仍會自動嘗試常見模型。")
    st.markdown("---")
    st.write("**此回合使用的模型**")
    st.info(st.session_state.last_used_model or "尚未產生回覆")
    st.markdown("---")
    st.write("**Interventions toolbox (keys → names)**")
    st.json({k: v["name"] for k, v in INTERVENTIONS.items()})

# Render history
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# =========================================================
# Chat input
# =========================================================
user_input = st.chat_input("How are you feeling right now?")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    emotion = detect_emotion(user_input)
    intent, risk_score = analyze_intent_and_risk(user_input)
    tone_instruction = TONE_PROMPTS.get(emotion, TONE_PROMPTS["neutral"])
    intervention_key = choose_intervention(emotion, intent, risk_score)
    intervention_module = INTERVENTIONS[intervention_key]

    st.markdown(
        f"**🫧 Detected emotion:** `{emotion}` &nbsp;|&nbsp; **Intent:** `{intent}` &nbsp;|&nbsp; **Suggested module:** `{intervention_module['name']}`"
        + (f" &nbsp;|&nbsp; *intensity marker present*" if risk_score >= 3 else "")
    )

    with st.chat_message("assistant"):
        with st.spinner("Listening with care..."):
            ai_reply, module, used_model = generate_structured_reply(
                user_text=user_input,
                emotion=emotion,
                intent=intent,
                tone_instruction=tone_instruction,
                intervention_key=intervention_key
            )
            ai_reply = re.sub(r'^\s+', '', ai_reply)
            st.markdown(ai_reply)
            st.session_state.last_used_model = used_model

            with st.expander(f"📎 Practice card — {module['name']}"):
                st.markdown(f"**What it is:** {module['desc']}")
                st.markdown("**Try this now:**")
                for step in module["howto"]:
                    st.markdown(f"- {step}")

    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
    st.session_state.log.append({
        "ts": datetime.datetime.now().isoformat(),
        "emotion": emotion,
        "intent": intent,
        "risk_score": risk_score,
        "module": intervention_key,
        "model_used": st.session_state.last_used_model,
    })

# =========================================================
# Reflection & Export
# =========================================================
with st.expander("🪞 Self-Reflection"):
    mood = st.radio("How do you feel after this chat?",
                    ["Lighter", "Still heavy", "Calmer", "Hopeful", "Confused"], index=None)
    note = st.text_area("Note to yourself:", placeholder="Write a small reflection…")
    if mood:
        st.success("🌷 Thank you for reflecting — awareness is already growth.")
    if st.button("Download session log JSON"):
        st.download_button("Click to download",
                           data=json.dumps(st.session_state.log, ensure_ascii=False, indent=2),
                           file_name="emotion_session_log.json",
                           mime="application/json",
                           use_container_width=True)

st.markdown("---")
st.caption("💚 Designed by Catherine Liu · Emotion-Aware Algorithmic Companion · Automatic Model Fallback")
