# app_emotion.py
# ---------------------------------------------------------
# Emotion-Aware AI Companion (Dual Mode + Graceful Fallback)
# + Working Case Formulation & Transparent Reasoning Panel
# ---------------------------------------------------------

import os, re, json, random, datetime, time
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
# System prompts (two modes, English)
# =========================================================
COUNSELOR_PROMPT = """
You are a compassionate, counselor-style AI who responds in the user's language.
Listen carefully, reflect emotions with precision, and help the user organize thoughts.
Avoid generic cheerleading. Be structured yet human and warm.
Use a gentle 3-step shape, but keep it natural:
1) Reflect Emotion — mirror and name feelings without judgment.
2) Structure the Issue — clarify what's happening in simple, calm language.
3) Suggest a Gentle Step — offer ONE small, concrete action OR a reflective question.
Do not ask the user to rate emotions with numbers unless they ask for it.
Do not include any crisis or safety protocol in your responses.
Keep replies concise (2–3 short paragraphs).
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
    """Pick first preferred model present in available IDs; else return top preference."""
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
# Emotion & intent detection (lightweight)
# =========================================================
EMOTION_LEX = {
    "anxiety": ["anxious","panic","panicking","nervous","worried","pressure","stressed","overthinking","overwhelm","tense","afraid","scared","焦慮","緊張","擔心","慌"],
    "sadness": ["sad","lonely","upset","tired","hurt","empty","numb","down","blue","depressed","cry","crying","loss","grief","難過","孤單","失落","低落","想哭","空"],
    "anger":   ["angry","frustrated","irritated","mad","furious","rage","annoyed","resentful","生氣","憤怒","不爽"],
    "shame":   ["ashamed","shame","embarrassed","humiliated","guilty","worthless","not enough","failure","丟臉","羞愧","內疚","沒用","失敗者","很爛","很廢"],
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
    """No crisis routing; just intent + a light risk marker score to modulate tone."""
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
# Interventions toolbox (used in Counselor Mode only)
# =========================================================
INTERVENTIONS = {
    "CBT_THOUGHT_RECORD": {
        "name": "CBT Thought Record",
        "desc": "Clarify: situation → automatic thought → feeling → evidence for/against → balanced thought.",
        "howto": [
            "Write the situation in a single sentence.",
            "Write the automatic thought verbatim.",
            "List evidence for and against this thought.",
        ]
    },
    "DBT_TIPP": {
        "name": "DBT TIPP",
        "desc": "Short physiological resets for strong emotion.",
        "howto": [
            "Cool face/neck with water for 30–60s.",
            "60–120s of brisk movement.",
            "Paced breathing: inhale 4s, exhale 6s for ~2 min.",
        ]
    },
    "GROUNDING_54321": {
        "name": "5-4-3-2-1 Grounding",
        "desc": "Anchor attention in the present using senses.",
        "howto": [
            "Notice 5 things you can see.",
            "Notice 4 things you can touch.",
            "Notice 3 things you can hear.",
        ]
    },
    "BREATH_BOX": {
        "name": "Box Breathing 4-4-4-4",
        "desc": "Stabilize pace and heart rate.",
        "howto": [
            "Inhale 4s, hold 4s.",
            "Exhale 4s, hold 4s.",
            "Repeat 4 rounds.",
        ]
    },
    "SELF_COMPASSION": {
        "name": "Self-Compassion Script",
        "desc": "Talk to yourself like a close friend.",
        "howto": [
            "Name: “This is hard.”",
            "Normalize: “Struggle is human.”",
            "Wish: “May I be gentle with myself now.”",
        ]
    },
    "DESC_SCRIPT": {
        "name": "DESC Boundary Script",
        "desc": "Describe–Express–Specify–Consequences.",
        "howto": [
            "Describe facts (no labels).",
            "Express impact/feeling.",
            "Specify a clear, doable request.",
        ]
    },
    "SLEEP_HYGIENE_MINI": {
        "name": "Sleep Hygiene (Mini)",
        "desc": "Tiny habits for tonight.",
        "howto": [
            "Fixed wake time; morning light 10–20 min.",
            "Reduce screens & caffeine 60 min before bed.",
            "Externalize worries on paper.",
        ]
    },
    "BODY_SCAN": {
        "name": "Mindful Body Scan",
        "desc": "Release tension head to toe.",
        "howto": [
            "Forehead → jaw → neck/shoulders relax.",
            "Chest → belly → back with slow breathing.",
            "Hips → legs → feet soften.",
        ]
    },
    "REFLECTIVE_QUESTION": {
        "name": "Reflective Question",
        "desc": "Perspective-taking to soften fusion.",
        "howto": [
            "If your closest friend were here, what would you tell them?",
            "Which part needs care right now: body, mind, or heart?",
            "What’s a 10-minute step that won’t make things worse?",
        ]
    },
    "ACTION_STEP": {
        "name": "Tiny Action Plan",
        "desc": "A 10-minute micro-step to regain agency.",
        "howto": [
            "Pick something doable within 10 minutes.",
            "Decide when (within 24h).",
            "Define a visible 'done' signal.",
        ]
    },
    "GRATITUDE_PROMPT": {
        "name": "Gratitude Prompt",
        "desc": "Note three small good things.",
        "howto": [
            "List 3 small things you’re grateful for today.",
            "Add 1 sentence for why each matters.",
        ]
    },
    "EMOTIONAL_LABELING": {
        "name": "Emotional Labeling",
        "desc": "Name feelings to gently reduce intensity (no numbers).",
        "howto": [
            "Pick 1–2 words for the feeling (e.g., heavy, tight, tangled).",
            "Do one soothing breath/grounding round, then see if words shift.",
            "Optionally notice where it sits in the body (chest/stomach/throat).",
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
# ==== NEW: Simple case formulation engine & reasoning text
# =========================================================
def infer_case_formulation(user_text: str, emotion: str, intent: str, prev_formulation=None):
    """
    Lightweight working case formulation:
    - themes: self-worth / performance pressure / relationships / mood & energy
    - patterns: perfectionism / global self-criticism / should statements
    - hypotheses: short, human-readable working ideas
    """
    tl = user_text.lower()

    if prev_formulation is None:
        cf = {
            "themes": [],
            "patterns": [],
            "hypotheses": []
        }
    else:
        # copy to avoid mutating original directly
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

    # --- themes ---
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

    # --- patterns ---
    if any(k in tl for k in ["should","must","have to","一定要","應該","不能失誤","不可以犯錯","完美"]):
        add_pattern("perfectionism / high standards")
    if any(k in tl for k in ["always","never","every time","每次","都這樣","總是"]):
        add_pattern("overgeneralization")
    if any(k in tl for k in ["i'm the problem","都是我的錯","怪我","my fault","i ruin","我害的"]):
        add_pattern("global self-criticism")
    if intent == "self-blame":
        add_pattern("self-blame focus")

    # --- hypotheses (very lightweight, just for transparency) ---
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
    """
    Turn internal tags (emotion, intent, formulation, intervention) into
    a human-readable mini explanation for the user.
    """
    lines = []
    lines.append(f"- **Detected emotion**: `{emotion}`")
    lines.append(f"- **Detected intent**: `{intent}`")
    if risk_score >= 3:
        lines.append(f"- **Intensity marker**: I noticed some stronger distress signals in your words.")

    themes = case_formulation.get("themes") or []
    patterns = case_formulation.get("patterns") or []
    hypos = case_formulation.get("hypotheses") or []

    if themes:
        lines.append(f"- **Current themes I'm tracking**: " + ", ".join(themes))
    if patterns:
        lines.append(f"- **Patterns I'm noticing in how you talk to yourself**: " + ", ".join(patterns))
    if hypos:
        # show at most 2 to keep it readable
        shown = hypos[:2]
        lines.append(f"- **Working hypotheses (not judgments, just gentle guesses)**:")
        for h in shown:
            lines.append(f"  - {h}")

    module = INTERVENTIONS.get(intervention_key)
    if module:
        reason = ""
        if intervention_key in ("SELF_COMPASSION", "EMOTIONAL_LABELING"):
            reason = "because there is a lot of self-criticism or heavy emotion, I chose something that softens the inner voice and helps you name what you feel."
        elif intervention_key in ("CBT_THOUGHT_RECORD",):
            reason = "because your thoughts jump quickly to harsh conclusions about yourself, I chose something that slows down and examines the thought step by step."
        elif intervention_key in ("GROUNDING_54321","BREATH_BOX","DBT_TIPP","BODY_SCAN"):
            reason = "because your nervous system may feel activated or overwhelmed, I chose something that first helps your body and mind settle a bit."
        elif intervention_key in ("REFLECTIVE_QUESTION","GRATITUDE_PROMPT"):
            reason = "because you seemed to be exploring and wondering, I chose something that opens a gentle space for reflection."
        elif intervention_key in ("ACTION_STEP","DESC_SCRIPT","SLEEP_HYGIENE_MINI"):
            reason = "because you sounded ready for a small bit of change, I chose something that turns this into a tiny, doable action."

        lines.append(
            f"- **Chosen micro-step**: `{module['name']}` — {module['desc']}"
        )
        if reason:
            lines.append(f"  - I picked this {reason}")

    return "\n".join(lines)

# =========================================================
# Core generators
# =========================================================
def generate_counselor_reply(user_text: str,
                             emotion: str,
                             intent: str,
                             tone_instruction: str,
                             intervention_key: str,
                             case_formulation: dict):  # ==== NEW param
    module = INTERVENTIONS[intervention_key]
    sys = f"""{COUNSELOR_PROMPT}
Tone hint: {tone_instruction}
Emotion focus: {emotion}; Intent: {intent}.
"""

    tool_context = {
        "intervention": {
            "key": intervention_key,
            "name": module["name"],
            "desc": module["desc"],
            "howto": module["howto"][:3]
        },
        "case_formulation": case_formulation  # ==== NEW: pass working formulation to the model
    }

    reply_text, used_model = safe_chat_completion(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user_text},
            {"role": "system", "content": "Context for a gentle Step 3 and for understanding the user:\n" + json.dumps(tool_context, ensure_ascii=False)}
        ],
        temperature=0.8,
    )
    return reply_text, module, used_model

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
# ==== NEW: working case formulation in session
if "case_formulation" not in st.session_state:
    st.session_state.case_formulation = {
        "themes": [],
        "patterns": [],
        "hypotheses": []
    }

# Helper to render a tiny inline practice toggle
def render_practice_button(module: dict, uid: str):
    key_btn = f"btn_show_practice_{uid}"
    key_state = f"show_practice_{uid}"
    show_now = st.session_state.practice_toggle.get(key_state, False)

    cols = st.columns([1, 6])
    with cols[0]:
        if st.button("💫 Try practice", key=key_btn, use_container_width=True):
            show_now = not show_now
            st.session_state.practice_toggle[key_state] = show_now
    with cols[1]:
        if show_now:
            st.info(f"**{module['name']}** — {module['desc']}")
            for step in module["howto"]:
                st.markdown(f"- {step}")

# =========================================================
# UI: header & sidebar
# =========================================================
st.title("Hi! I am Nino🫧")
st.caption("Dual Mode · Counselor / Companion · Automatic model fallback")

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

# Render history
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

    # Perception → Evaluation
    emotion = detect_emotion(user_input)
    intent, risk_score = analyze_intent_and_risk(user_input)
    tone_instruction = TONE_PROMPTS.get(emotion, TONE_PROMPTS["neutral"])

    # Tags row (visible in Counselor Mode; hidden in Companion Mode)
    if "Counselor" in mode:
        st.markdown(
            f"**🫧 Detected emotion:** `{emotion}` &nbsp;|&nbsp; **Intent:** `{intent}`"
            + (f" &nbsp;|&nbsp; *intensity marker present*" if risk_score >= 3 else "")
        )

    with st.chat_message("assistant"):
        with st.spinner("Listening with care..."):
            if "Counselor" in mode:
                # ==== NEW: update & use working case formulation
                updated_cf = infer_case_formulation(
                    user_text=user_input,
                    emotion=emotion,
                    intent=intent,
                    prev_formulation=st.session_state.case_formulation
                )
                st.session_state.case_formulation = updated_cf

                intervention_key = choose_intervention(emotion, intent, risk_score)
                ai_reply, module, used_model = generate_counselor_reply(
                    user_text=user_input,
                    emotion=emotion,
                    intent=intent,
                    tone_instruction=tone_instruction,
                    intervention_key=intervention_key,
                    case_formulation=updated_cf
                )
                st.session_state.last_used_model = used_model
                ai_reply = re.sub(r'^\s+', '', ai_reply)
                st.markdown(ai_reply)

                uid = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                render_practice_button(module, uid)

                # ==== NEW: show internal reasoning to user
                reasoning_text = build_reasoning_text(
                    emotion=emotion,
                    intent=intent,
                    risk_score=risk_score,
                    intervention_key=intervention_key,
                    case_formulation=updated_cf
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
                    tone_instruction=tone_instruction
                )
                st.session_state.last_used_model = used_model
                ai_reply = re.sub(r'^\s+', '', ai_reply)
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
                    # companion mode 不做 formulation，但可以留空
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
        st.download_button("Download",
                           data=json.dumps(st.session_state.log, ensure_ascii=False, indent=2),
                           file_name="emotion_session_log.json",
                           mime="application/json",
                           use_container_width=True)

st.markdown("---")
st.caption("💚 Designed by Catherine Liu · Dual-Mode Emotion Companion · Automatic Model Fallback + Transparent Reasoning")
