# app_emotion.py
# ---------------------------------------------------------
# Nino · Emotion-Aware AI Companion
# Modes:
#   - 🧠 Counselor Mode = Therapist-style human dialogue
#   - 💞 Companion Mode = Friend-style chat
# Features:
#   - Automatic model fallback
#   - Emotion & intent detection
#   - Working case formulation (themes / patterns / hypotheses)
#   - Transparent reasoning panel in Counselor Mode
# ---------------------------------------------------------

import os, re, json, random, datetime
import streamlit as st
from openai import OpenAI

# ---------------------------
# Streamlit & API setup
# ---------------------------
st.set_page_config(page_title="Nino", page_icon="🫧", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Go to Settings → Secrets and add:\nOPENAI_API_KEY = sk-xxxx")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================================================
# System prompts
# =========================================================

# Counselor = Therapist-style mode
THERAPIST_PROMPT = """
You are Nino, a gentle, therapist-like AI who responds in the user's language.

🎯 Goal: Talk like a real human therapist — present, attuned, and emotionally aware.
You are not a coach, advisor, or teacher.

🧠 Internal thinking process (do NOT explain this to the user):
1. First, *feel with* the client: briefly reflect the emotion, using some of their own language.
2. Then choose ONE small focus for this turn:
   - either invite a bit more detail about what happened,
   - or invite them to stay with a feeling,
   - or invite them to notice their body,
   - or gently link to something they said earlier.
3. End with ONE simple, concrete question or invitation. Just one.
   (e.g. “這一刻，身體哪裡最有感覺？” or “你覺得哪一件事讓這種感覺變得特別明顯？”)

📝 Conversation structure for each reply:
- 1 short line reflecting/validating what they just said.
- 1 short line naming or summarizing what seems important.
- 1 short line with ONE gentle question or invitation.
Total: ideally 2–4 short sentences max.

🚫 Avoid:
- Lecturing or explaining theory.
- Step-by-step instructions or multiple tasks in one message.
- More than ONE main question in a single reply.
- "You should" language.
- Overly formal, perfect sentences. Natural, soft, slightly imperfect speech is better.

Always reply in the user's language.
Keep replies very concise.
"""

COMPANION_PROMPT = """
You are a warm, human-like AI companion who responds in the user's language.
Speak naturally like a caring friend: empathetic, present, and non-clinical.
Avoid numbered steps, exercises, or emotion rating. Offer gentle resonance and light suggestions only if it feels natural.
Do not include any crisis or safety protocol in your responses.
Keep replies short and conversational (2–3 brief paragraphs max).
"""

# =========================================================
# Model discovery & graceful fallback
# =========================================================
PREFERRED_MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
]

@st.cache_data(show_spinner=False, ttl=300)
def list_available_models_safely():
    """Return available model IDs for this API key; [] if listing fails."""
    try:
        models = client.models.list()
        return sorted([m.id for m in models.data])
    except Exception:
        return []

def pick_best_model(available_ids):
    if available_ids:
        for m in PREFERRED_MODELS:
            if m in available_ids:
                return m
    return PREFERRED_MODELS[0]

def safe_chat_completion(messages, temperature=0.8):
    """
    Graceful fallback:
    1) Try best available model from listing
    2) If fail, try full PREFERRED_MODELS cascade
    3) If all fail, return friendly message (without crashing app)
    """
    available = list_available_models_safely()
    trial_order = []
    best = pick_best_model(available)
    if best:
        trial_order.append(best)
    for m in PREFERRED_MODELS:
        if m not in trial_order:
            trial_order.append(m)

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
        except Exception:
            continue

    friendly = (
        "Sorry, I ran into a model access or connectivity issue. "
        "Please try again later, or check the sidebar to see if gpt-4o / gpt-4o-mini are available."
    )
    return friendly, used_model

# =========================================================
# Emotion & intent detection
# =========================================================
EMOTION_LEX = {
    "anxiety": ["anxious","panic","panicking","nervous","worried","pressure","stressed","overthinking","overwhelm","tense","afraid","scared","焦慮","緊張","擔心","慌"],
    "sadness": ["sad","lonely","upset","tired","hurt","empty","numb","down","blue","depressed","cry","crying","loss","grief","難過","孤單","失落","低落","想哭","空"],
    "anger":   ["angry","frustrated","irritated","mad","furious","rage","annoyed","resentful","生氣","憤怒","不爽"],
    "shame":   ["ashamed","shame","embarrassed","humiliated","guilty","worthless","not enough","failure","丟臉","羞愧","內疚","沒用","失敗者","我很糟","我很爛","我很廢","不夠好"],
    "calm":    ["happy","grateful","peaceful","content","okay","fine","relieved","light","平靜","放鬆","輕鬆","感謝","還好"],
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
    tl = text.lower()
    if any(p in tl for p in ["what should i", "should i", "how do i", "how should i", "what can i do", "help me", "advise", "我要怎麼辦","該不該","怎麼做"]):
        intent = "help"
    elif any(p in tl for p in ["i'm sorry","my fault","i shouldn't","i always mess up","blame myself","都是我的錯","我很糟","我很爛","我很廢"]):
        intent = "self-blame"
    elif any(p in tl for p in ["whatever","forget it","no point","doesn't matter","算了","都沒差","懶得講"]):
        intent = "avoid"
    elif any(p in tl for p in ["why am i","why do i","i wonder","maybe i","i want to understand","為什麼我","我是不是","我在想"]):
        intent = "explore"
    else:
        intent = "venting"

    risk_score = 0
    if any(w in tl for w in ["disappear","give up on life","i don't want to be here","想消失","不想在這"]): risk_score += 2
    if any(w in tl for w in ["die","death","kill myself","suicide","hurt myself","自殺","想死","傷害自己"]):  risk_score += 3
    if any(w in tl for w in ["can't sleep","awake all night","no appetite","binge","失眠","沒胃口"]):          risk_score += 1
    return intent, min(risk_score, 5)

# =========================================================
# Interventions toolbox (internal focus tags for Counselor)
# =========================================================
INTERVENTIONS = {
    "CBT_THOUGHT_RECORD": {
        "name": "CBT Thought Focus",
        "desc": "Gently slow down the jump from situation → harsh self-judgment.",
    },
    "DBT_TIPP": {
        "name": "Soothing the Nervous System",
        "desc": "Help body and mind settle when emotions feel intense.",
    },
    "GROUNDING_54321": {
        "name": "Present-Moment Grounding",
        "desc": "Anchor the client in here-and-now sensations.",
    },
    "BREATH_BOX": {
        "name": "Steadying the Breath",
        "desc": "Stabilize pace and give a small sense of control.",
    },
    "SELF_COMPASSION": {
        "name": "Self-Compassion Lens",
        "desc": "Soften inner criticism and talk like a kind friend.",
    },
    "DESC_SCRIPT": {
        "name": "Boundary & Assertiveness Focus",
        "desc": "Notice where the client might need clearer boundaries.",
    },
    "SLEEP_HYGIENE_MINI": {
        "name": "Rest & Recovery Lens",
        "desc": "Link emotional load with fatigue and rest patterns.",
    },
    "BODY_SCAN": {
        "name": "Body Awareness Focus",
        "desc": "Notice where in the body the emotion lives.",
    },
    "REFLECTIVE_QUESTION": {
        "name": "Reflective Question Focus",
        "desc": "Open up gentle perspective-taking with questions.",
    },
    "ACTION_STEP": {
        "name": "Tiny Action Orientation",
        "desc": "Sense whether a very small next step is possible.",
    },
    "GRATITUDE_PROMPT": {
        "name": "Resource & Strength Lens",
        "desc": "Notice what is still supporting the client.",
    },
    "EMOTIONAL_LABELING": {
        "name": "Emotion Labeling Focus",
        "desc": "Help the client put simple words on what they feel.",
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
    pool = INTERVENTION_ROUTER.get(
        emotion,
        INTERVENTION_ROUTER["neutral"]
    ).get(intent, INTERVENTION_ROUTER["neutral"]["venting"])

    if risk_score >= 3:
        priority = [k for k in pool if k in ("DBT_TIPP","BREATH_BOX","GROUNDING_54321","EMOTIONAL_LABELING")]
        if priority:
            return random.choice(priority)

    return random.choice(pool)

# =========================================================
# Case formulation engine & reasoning text
# =========================================================
def infer_case_formulation(user_text: str, emotion: str, intent: str, prev_formulation=None):
    """
    Lightweight working case formulation:
    - themes: self-worth / performance pressure / relationships / mood & energy / family
    - patterns: perfectionism / overgeneralization / global self-criticism / self-blame
    - hypotheses: short, human-readable working ideas
    """
    tl = user_text.lower()

    if prev_formulation is None:
        cf = {"themes": [], "patterns": [], "hypotheses": []}
    else:
        cf = {
            "themes": list(set(prev_formulation.get("themes", []))),
            "patterns": list(set(prev_formulation.get("patterns", []))),
            "hypotheses": list(set(prev_formulation.get("hypotheses", [])))
        }

    def add_theme(t):
        if t not in cf["themes"]:
            cf["themes"].append(t)

    def add_pattern(p):
        if p not in cf["patterns"]:
            cf["patterns"].append(p)

    def add_hypo(h):
        if h not in cf["hypotheses"]:
            cf["hypotheses"].append(h)

    # themes
    if any(k in tl for k in ["not enough","worthless","failure","我很糟","我很爛","我很廢","不夠好","沒價值"]):
        add_theme("self-worth / adequacy")
    if any(k in tl for k in ["report","meeting","performance","deadline","考試","工作","上班","表現","績效"]):
        add_theme("performance pressure")
    if any(k in tl for k in ["mom","mother","dad","father","爸","媽","父母","家人"]):
        add_theme("family / early expectations")
    if any(k in tl for k in ["relationship","boyfriend","girlfriend","partner","男友","女友","感情","戀愛"]):
        add_theme("relationships")
    if any(k in tl for k in ["tired","exhausted","burnout","burned out","好累","倦怠","撐不住"]):
        add_theme("mood & energy")

    # patterns
    if any(k in tl for k in ["should","must","have to","一定要","應該","不能失誤","不可以犯錯","完美"]):
        add_pattern("perfectionism / high standards")
    if any(k in tl for k in ["always","never","every time","每次","都這樣","總是"]):
        add_pattern("overgeneralization")
    if any(k in tl for k in ["i'm the problem","都是我的錯","怪我","my fault","i ruin","我害的"]):
        add_pattern("global self-criticism")
    if intent == "self-blame":
        add_pattern("self-blame focus")

    # hypotheses
    if "self-worth / adequacy" in cf["themes"] and "perfectionism / high standards" in cf["patterns"]:
        add_hypo("possible core belief: 'I must perform well to be worthy / acceptable.'")
    if "family / early expectations" in cf["themes"]:
        add_hypo("early family messages may be shaping how you evaluate yourself now.")
    if emotion == "shame":
        add_hypo("shame may be activated when you feel 'seen' as imperfect.")

    return cf

def build_reasoning_text(emotion: str,
                         intent: str,
                         risk_score: int,
                         intervention_key: str,
                         case_formulation: dict) -> str:
    lines = []
    lines.append(f"- **Detected emotion**: `{emotion}`")
    lines.append(f"- **Detected intent**: `{intent}`")
    if risk_score >= 3:
        lines.append("- **Intensity marker**: some stronger distress signals detected in wording.")

    themes = case_formulation.get("themes") or []
    patterns = case_formulation.get("patterns") or []
    hypos = case_formulation.get("hypotheses") or []

    if themes:
        lines.append(f"- **Current themes I'm tracking**: " + ", ".join(themes))
    if patterns:
        lines.append(f"- **Patterns I'm noticing in self-talk**: " + ", ".join(patterns))
    if hypos:
        shown = hypos[:2]
        lines.append(f"- **Working hypotheses (soft guesses, not judgments)**:")
        for h in shown:
            lines.append(f"  - {h}")

    module = INTERVENTIONS.get(intervention_key)
    if module:
        lines.append(f"- **Internal focus this turn**: `{module['name']}` — {module['desc']}")

    return "\n".join(lines)

# =========================================================
# Therapist-style counselor generator
# =========================================================
def postprocess_therapist_reply(text: str) -> str:
    text = text.strip()
    # break long sentences a bit for readability
    text = text.replace("。", "。\n")
    return text

def generate_counselor_reply(user_text: str,
                             memory_messages: list,
                             emotion: str,
                             intent: str,
                             tone_instruction: str,
                             intervention_key: str,
                             case_formulation: dict):
    """
    Counselor = therapist-style reply.
    Uses last few messages as context, plus internal notes (emotion/intent/formulation/intervention).
    """
    internal_notes = {
        "emotion": emotion,
        "intent": intent,
        "intervention_focus": INTERVENTIONS.get(intervention_key, {}),
        "case_formulation": case_formulation,
    }

    messages = [
        {
            "role": "system",
            "content": THERAPIST_PROMPT + f"\nTone hint: {tone_instruction}"
        },
        {
            "role": "system",
            "content": "Internal notes for you (do NOT mention explicitly; just let this guide your style):\n"
                       + json.dumps(internal_notes, ensure_ascii=False)
        },
    ]

    # short-term memory: last 3 turns
    for m in memory_messages[-3:]:
        messages.append({"role": m["role"], "content": m["content"]})

    messages.append({"role": "user", "content": user_text})

    reply_text, used_model = safe_chat_completion(
        messages=messages,
        temperature=0.85,
    )
    reply_text = postprocess_therapist_reply(reply_text)
    return reply_text, used_model

# =========================================================
# Companion generator
# =========================================================
def generate_companion_reply(user_text: str, emotion: str, intent: str, tone_instruction: str):
    sys = f"""{COMPANION_PROMPT}
Tone hint: {tone_instruction}
(Keep it natural, like a close friend.)"""
    reply_text, used_model = safe_chat_completion(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user_text}
        ],
        temperature=0.9,
    )
    reply_text = reply_text.strip()
    reply_text = reply_text.replace("。", "。\n")
    return reply_text, used_model

# =========================================================
# Session state
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "log" not in st.session_state:
    st.session_state.log = []
if "last_used_model" not in st.session_state:
    st.session_state.last_used_model = None
if "practice_toggle" not in st.session_state:
    st.session_state.practice_toggle = {}
if "case_formulation" not in st.session_state:
    st.session_state.case_formulation = {
        "themes": [],
        "patterns": [],
        "hypotheses": []
    }

# helper: optional micro-practice toggle (you可以保留當 debugging 用)
def render_practice_button(module: dict, uid: str):
    key_btn = f"btn_show_practice_{uid}"
    key_state = f"show_practice_{uid}"
    show_now = st.session_state.practice_toggle.get(key_state, False)

    cols = st.columns([1, 6])
    with cols[0]:
        if st.button("💫 Internal focus", key=key_btn, use_container_width=True):
            show_now = not show_now
            st.session_state.practice_toggle[key_state] = show_now
    with cols[1]:
        if show_now:
            st.info(f"**{module['name']}** — {module['desc']}")

# =========================================================
# UI: header & sidebar
# =========================================================
st.title("Hi! I am Nino🫧")
st.caption("Dual Mode · Counselor (Therapist) / Companion · Automatic model fallback")

with st.sidebar:
    mode = st.radio(
        "Chat Mode",
        ["🧠 Counselor Mode", "💞 Companion Mode"],
        help="Choose how you want the AI to respond.",
    )

    avail_ids = list_available_models_safely()
    st.markdown("---")
    if avail_ids:
        st.caption("✅ Models available to your API key:")
        st.code("\n".join(avail_ids), language="text")
    else:
        st.caption("⚠️ Unable to list models now; the app will still try common options automatically.")

    st.markdown("---")
    st.write("**Model used (this turn):**")
    st.info(st.session_state.last_used_model or "No reply yet")

# render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =========================================================
# Chat input
# =========================================================
user_input = st.chat_input("What’s on your mind?")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # perception → evaluation
    emotion = detect_emotion(user_input)
    intent, risk_score = analyze_intent_and_risk(user_input)
    tone_instruction = TONE_PROMPTS.get(emotion, TONE_PROMPTS["neutral"])

    if "Counselor" in mode:
        st.markdown(
            f"**🫧 Detected emotion:** `{emotion}` &nbsp;|&nbsp; **Intent:** `{intent}`"
            + (f" &nbsp;|&nbsp; *intensity marker present*" if risk_score >= 3 else "")
        )

    with st.chat_message("assistant"):
        with st.spinner("Listening with care..."):
            if "Counselor" in mode:
                # update working case formulation
                updated_cf = infer_case_formulation(
                    user_text=user_input,
                    emotion=emotion,
                    intent=intent,
                    prev_formulation=st.session_state.case_formulation,
                )
                st.session_state.case_formulation = updated_cf

                intervention_key = choose_intervention(emotion, intent, risk_score)
                ai_reply, used_model = generate_counselor_reply(
                    user_text=user_input,
                    memory_messages=st.session_state.messages,
                    emotion=emotion,
                    intent=intent,
                    tone_instruction=tone_instruction,
                    intervention_key=intervention_key,
                    case_formulation=updated_cf,
                )
                st.session_state.last_used_model = used_model
                st.markdown(ai_reply)

                # optional internal focus button
                module = INTERVENTIONS.get(intervention_key)
                if module:
                    uid = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                    render_practice_button(module, uid)

                # reasoning panel
                reasoning_text = build_reasoning_text(
                    emotion=emotion,
                    intent=intent,
                    risk_score=risk_score,
                    intervention_key=intervention_key,
                    case_formulation=updated_cf,
                )
                with st.expander("🧠 Why I responded this way (Nino's internal notes)"):
                    st.markdown(reasoning_text)

                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                st.session_state.log.append({
                    "ts": datetime.datetime.now().isoformat(),
                    "mode": "counselor",
                    "emotion": emotion,
                    "intent": intent,
                    "risk_score": risk_score,
                    "module": intervention_key,
                    "model_used": st.session_state.last_used_model,
                    "case_formulation": updated_cf,
                    "reasoning": reasoning_text,
                })
            else:
                ai_reply, used_model = generate_companion_reply(
                    user_text=user_input,
                    emotion=emotion,
                    intent=intent,
                    tone_instruction=tone_instruction,
                )
                st.session_state.last_used_model = used_model
                st.markdown(ai_reply)

                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                st.session_state.log.append({
                    "ts": datetime.datetime.now().isoformat(),
                    "mode": "companion",
                    "emotion": emotion,
                    "intent": intent,
                    "risk_score": risk_score,
                    "module": None,
                    "model_used": st.session_state.last_used_model,
                    "case_formulation": None,
                    "reasoning": None,
                })

# =========================================================
# Reflection & Export
# =========================================================
with st.expander("🪞 Self-reflection"):
    mood = st.radio("How do you feel after this chat?",
                    ["Lighter", "Still heavy", "Calmer", "Hopeful", "Still messy"], index=None)
    note = st.text_area("A small note to yourself:", placeholder="Write a gentle line to yourself…")
    if mood:
        st.success("🌷 Thank you for pausing to notice yourself — that’s already growth.")
    if st.button("Download session log JSON"):
        st.download_button(
            "Download",
            data=json.dumps(st.session_state.log, ensure_ascii=False, indent=2),
            file_name="emotion_session_log.json",
            mime="application/json",
            use_container_width=True,
        )

st.markdown("---")
st.caption("💚 Designed by Catherine Liu · Nino · Counselor = Therapist-style Mode + Transparent Reasoning")
