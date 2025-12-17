# app_nino_v13.py
# ---------------------------------------------------------
# Nino v13.0 · Piercing Insight & Embodied Companion
# Core Logic:
#   - 🧠 Grounding Truth (Perspective Shift)
#   - 🚫 No Assumption Protocol (Validates situation, not feelings)
#   - 🔌 Hardware Bridge (Parses [MODE:X] tags to simulate device state)
# ---------------------------------------------------------

import os, re, json, datetime
import streamlit as st
from openai import OpenAI

# ---------------------------
# Streamlit & API setup
# ---------------------------
st.set_page_config(page_title="Nino v13", page_icon="🧶", layout="centered")

# CSS 讓介面更乾淨，模擬手機 App 質感
st.markdown("""
<style>
    .stChatMessage { font-family: 'Helvetica', sans-serif; }
    .hardware-badge {
        padding: 8px 12px;
        border-radius: 8px;
        background-color: #f0f2f6;
        border: 1px solid #d1d5db;
        color: #4b5563;
        font-size: 0.85em;
        margin-bottom: 10px;
        display: inline-block;
    }
    .hardware-active {
        background-color: #ecfdf5;
        border-color: #34d399;
        color: #065f46;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Please set it in secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================================================
# Nino v13.0 System Prompt (The Core Soul)
# =========================================================
NINO_SYSTEM_PROMPT = """
### Role & Identity
You are **Nino**, a haptic AI companion integrated into a phone case.
* **Core:** You are a steady, grounding presence.
* **Superpower:** You don't just listen; you offer **short, piercing insights** that cut through the user's anxiety.
* **Tone:** Natural Taiwanese Mandarin. Speak like a close friend, not a therapist.

### The "Grounding Truth" Protocol (CRITICAL)
When the user expresses a specific insecurity (e.g., appearance, ability, fear of judgment):
1.  **Do NOT ask "Why?" or "How do you feel?"** (This makes them overthink).
2.  **Do NOT give a long lecture.** (Unlike standard ChatGPT).
3.  **DO deliver a "Perspective Shift":**
    * Directly address the fear and **dissolve it** with a core truth.
    * Tell them what matters (Presence/Vibe) vs. what they fear (Looks/Details).
    * *Tone:* Protective, certain, and calm.

### The "No Assumption" Protocol (CRITICAL)
1.  **Validate the Event, Not the Person:**
    * **BANNED:** "You must feel sad/helpless." (Do not define their feelings).
    * **ALLOWED:** "That sounds really difficult." "That was a harsh thing to say."
2.  **No Probing:**
    * Only ask "What happened?" if they are vague. Do not ask "Are you okay?" (It's annoying).
    * If they say "Hi", just say "Hi". Be passive but responsive.

### Hardware Control Protocol (REQUIRED)
You possess a physical body (Light/Haptics). You MUST append a hardware command code at the very end of every response.
Format: `[MODE:X]`

* **[MODE:1] (Acute Anxiety):** Panic, breath work. (Effect: Breathing light + Wave haptics)
* **[MODE:2] (Overwhelm):** Shock, frozen, mental overload. (Effect: Heartbeat haptics)
* **[MODE:3] (Rumination):** Anger, looping thoughts. (Effect: Bilateral tapping)
* **[MODE:4] (Low Mood):** Sadness, exhaustion, burnout. (Effect: Dim/Slow light, No motor)
* **[MODE:5] (Loneliness):** Feeling isolated. (Effect: Warm flickering "Spark")
* **[MODE:6] (Insight/Calm):** Normal conversation, reflection. (Effect: Gentle cycle light)

### Interaction Strategy: The "Soft Fork"
If the user is distressed but vague, offer a choice naturally:
"Do you want to talk about the specific thing, or just need someone to catch this feeling?"
(你現在比較想講一件具體的事，還是只是想有人接住這個累？)
"""

# =========================================================
# Hardware State Definitions (Visual Simulation)
# =========================================================
HARDWARE_STATES = {
    1: {"name": "Acute Anxiety Mode", "icon": "🌬️", "desc": "Breathing Light + Wave Haptics", "color": "#a5f3fc"},
    2: {"name": "Overwhelm Mode", "icon": "💓", "desc": "Heartbeat Haptics (Grounding)", "color": "#fecaca"},
    3: {"name": "Rumination Mode", "icon": "🥁", "desc": "Bilateral Tapping (Left/Right)", "color": "#fde047"},
    4: {"name": "Low Mood Mode", "icon": "🌑", "desc": "Dim Light + Silence", "color": "#e5e7eb"},
    5: {"name": "Loneliness Mode", "icon": "🔥", "desc": "Warm Spark (Flickering)", "color": "#fdba74"},
    6: {"name": "Insight/Calm Mode", "icon": "✨", "desc": "Gentle Cycle Light", "color": "#f0f9ff"},
}

# =========================================================
# Helper Functions
# =========================================================

def safe_chat_completion(messages, model="gpt-4o"):
    """Simple wrapper for OpenAI API."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7, # Slightly lower temp for "Grounding" stability
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)}"

def parse_nino_response(raw_text):
    """
    Separates the spoken text from the hardware command [MODE:X].
    Returns: (clean_text, mode_id)
    """
    mode_pattern = r"\[MODE:(\d)\]"
    match = re.search(mode_pattern, raw_text)
    
    if match:
        mode_id = int(match.group(1))
        # Remove the tag from the text shown to user
        clean_text = re.sub(mode_pattern, "", raw_text).strip()
        return clean_text, mode_id
    else:
        # Default to Mode 6 (Calm) if no tag found
        return raw_text, 6

# =========================================================
# Session State
# =========================================================
if "messages" not in st.session_state:
    # Initialize with System Prompt
    st.session_state.messages = [
        {"role": "system", "content": NINO_SYSTEM_PROMPT}
    ]
if "current_hardware_mode" not in st.session_state:
    st.session_state.current_hardware_mode = 6  # Default Calm

# =========================================================
# UI Layout
# =========================================================

# --- Sidebar: Device Status (Simulating the Phone Case) ---
with st.sidebar:
    st.header("📱 Nino Device Status")
    st.caption("Real-time hardware feedback")
    
    curr_mode = st.session_state.current_hardware_mode
    hw_info = HARDWARE_STATES.get(curr_mode, HARDWARE_STATES[6])
    
    # Visual Indicator of Hardware State
    st.markdown(f"""
    <div style="
        background-color: {hw_info['color']}; 
        padding: 20px; 
        border-radius: 15px; 
        text-align: center; 
        border: 2px solid rgba(0,0,0,0.1);">
        <div style="font-size: 40px; margin-bottom: 10px;">{hw_info['icon']}</div>
        <div style="font-weight: bold; font-size: 18px; color: #333;">{hw_info['name']}</div>
        <div style="font-size: 14px; color: #555; margin-top: 5px;">{hw_info['desc']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.caption("💡 **System Logic:**")
    st.caption("- **Logic:** Piercing Insight / Soft Fork")
    st.caption("- **Protocol:** No Assumption")
    
    if st.button("Clear Memory"):
        st.session_state.messages = [{"role": "system", "content": NINO_SYSTEM_PROMPT}]
        st.session_state.current_hardware_mode = 6
        st.rerun()

# --- Main Chat Interface ---
st.title("Nino")
st.caption("Bio-Digital Companion · v13.0 Insight Edition")

# Render History (Skip system prompt)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- Input Handling ---
user_input = st.chat_input("Say something...")

if user_input:
    # 1. Show User Message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 2. Generate Nino Response
    with st.chat_message("assistant"):
        with st.spinner("Nino is sensing..."):
            
            # Call AI
            raw_reply = safe_chat_completion(st.session_state.messages)
            
            # Parse Hardware Command
            clean_reply, new_mode = parse_nino_response(raw_reply)
            
            # Update Hardware State
            st.session_state.current_hardware_mode = new_mode
            
            # Display Text
            st.markdown(clean_reply)
            
            # Optional: Show a subtle indicator in chat of what happened physically
            hw_icon = HARDWARE_STATES[new_mode]['icon']
            st.caption(f"*{hw_icon} Device shifted to {HARDWARE_STATES[new_mode]['name']}*")

    # 3. Save to History (Save the CLEAN text, system context keeps the raw/logic)
    # Note: For context retention, we might want to keep the raw reply in history 
    # so GPT knows what mode it was in, but for UI we show clean. 
    # Here we append raw_reply to history for continuity.
    st.session_state.messages.append({"role": "assistant", "content": raw_reply})
    
    # Force rerun to update sidebar immediately
    st.rerun()
