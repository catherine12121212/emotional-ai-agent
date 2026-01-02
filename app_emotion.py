# app_nino_v16.py
# ---------------------------------------------------------
# Nino v16.0 · Final Mode Mapping
# Update:
#   - [MODE:1] Anchor (Breathing UI)
#   - [MODE:6] Spark (Connection)
#   - [MODE:3] Shift (Interruption)
#   - [MODE:2] Ambient (Idle)
# ---------------------------------------------------------

import os, re, time
import streamlit as st
import serial
import serial.tools.list_ports
from openai import OpenAI

# ---------------------------
# Streamlit & API setup
# ---------------------------
st.set_page_config(page_title="Nino Interface", page_icon="🧶", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Please set it in secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================================================
# 🎨 CSS Animation (Breathing Circle - for Mode 1)
# =========================================================
st.markdown("""
<style>
    @keyframes breathe-animation {
        0%   { transform: scale(0.8); opacity: 0.4; background-color: #FED7AA; } 
        40%  { transform: scale(1.3); opacity: 1.0; background-color: #FB923C; } 
        100% { transform: scale(0.8); opacity: 0.4; background-color: #FED7AA; } 
    }
    .breath-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify_content: center;
        padding: 50px 0;
    }
    .breath-circle {
        width: 200px;
        height: 200px;
        border-radius: 50%;
        background-color: #FB923C;
        box-shadow: 0 0 30px rgba(251, 146, 60, 0.5);
        animation: breathe-animation 10s ease-in-out infinite;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.2em;
        font-weight: bold;
    }
    .instruction-text {
        margin-top: 30px;
        color: #666;
        font-size: 1.1em;
        text-align: center;
    }
    .stChatMessage { font-family: 'Helvetica', sans-serif; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 🔌 Hardware Bridge
# =========================================================
ARDUINO_PORT = "COM3"  # <--- 請確認 Port
BAUD_RATE = 115200

def get_serial_connection():
    if 'serial_conn' not in st.session_state:
        try:
            ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            st.session_state.serial_conn = ser
        except Exception:
            st.session_state.serial_conn = None
    return st.session_state.serial_conn

def send_command_to_arduino(mode_id):
    ser = get_serial_connection()
    if ser and ser.is_open:
        try:
            command = f"MODE:{mode_id}\n"
            ser.write(command.encode('utf-8'))
        except Exception:
            if 'serial_conn' in st.session_state:
                del st.session_state.serial_conn

# =========================================================
# System Prompt (Final Mapping)
# =========================================================
# 1: Anchor (Breathing)
# 6: Spark (Connection)
# 3: Shift (Interruption)
# 2: Ambient (Idle)

NINO_SYSTEM_PROMPT = """
### Role & Identity
You are **Nino**, an embodied AI companion aimed at emotional regulation.
Your goal is to identify the user's emotional state and trigger the correct haptic feedback mode.

### 🧠 Logic: Emotional State Estimation
Analyze the user's text and choose ONE mode to append at the end of your response.

**1. [MODE:1] The Anchor (Acute Anxiety/Deep Breath)**
* **Trigger:** User is panicking, anxious, overwhelmed, or you want to invite them to breathe.
* **Action:** Slow, calming, grounding words. *This mode triggers the breathing UI.*

**2. [MODE:6] The Spark (Connection)**
* **Trigger:** User shares a moment of joy, connection, or needs a "high-five" / warm acknowledgement.
* **Action:** Lighthearted, engaging, "I see you."

**3. [MODE:3] The Shift (Rumination/Interruption)**
* **Trigger:** User is stuck in a loop, obsessive thinking, spirals.
* **Action:** Gently disrupt the thought pattern (e.g., ask a sensory question).

**4. [MODE:2] Ambient Aliveness (Idle/Presence)**
* **Trigger:** General greeting, waiting, quiet moments, or stable conversation.
* **Action:** Minimalist, steady presence.

### Output Rules
* **MANDATORY:** End every response with exactly one tag: `[MODE:1]`, `[MODE:6]`, `[MODE:3]`, or `[MODE:2]`.
"""

# =========================================================
# Session State & Helper Functions
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": NINO_SYSTEM_PROMPT}]
    # Initial State: Ambient (Mode 2)
    st.session_state.messages.append({"role": "assistant", "content": "Hi. (Nino is here)\n[MODE:2]"})

if "breathing_mode_active" not in st.session_state:
    st.session_state.breathing_active = False

# Track Current Mode (Default 2 - Ambient)
if "current_mode" not in st.session_state:
    st.session_state.current_mode = 2

def safe_chat_completion(messages):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def parse_and_send_response(raw_text):
    mode_pattern = r"\[MODE:(\d)\]"
    match = re.search(mode_pattern, raw_text)
    
    # Default to current mode if no tag found
    mode_id = st.session_state.current_mode 
    clean_text = raw_text

    if match:
        mode_id = int(match.group(1))
        clean_text = re.sub(mode_pattern, "", raw_text).strip()
    
    # Update State
    st.session_state.current_mode = mode_id
    send_command_to_arduino(mode_id)
    
    return clean_text, mode_id

# =========================================================
# UI Layout
# =========================================================

# --- Sidebar: Status & Controls ---
with st.sidebar:
    st.header("Nino 🧶")
    
    # 🆕 DYNAMIC MODE DISPLAY
    st.subheader("Current State")
    
    # Updated Info Dictionary (v16 Mapping)
    mode_info = {
        1: {"label": "The Anchor ⚓", "desc": "Deep Breath (Anxiety)", "color": "#FF4B4B"},   # Red/Calm
        6: {"label": "The Spark ✨", "desc": "Connection (Joy)", "color": "#FB923C"},        # Orange/Spark
        3: {"label": "The Shift ⚡", "desc": "Interruption (Focus)", "color": "#8B5CF6"},     # Purple/Shift
        2: {"label": "Ambient 🍃", "desc": "Aliveness (Idle)", "color": "#71717a"},          # Grey/Idle
    }
    
    curr = st.session_state.current_mode
    info = mode_info.get(curr, mode_info[2]) # Default to Ambient
    
    st.markdown(f"""
    <div style="background-color: white; padding: 15px; border-radius: 10px; border-left: 6px solid {info['color']}; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <div style="font-size: 18px; font-weight: bold; color: #333;">{info['label']}</div>
        <div style="font-size: 12px; color: #666; margin-top: 5px;">Mode {curr}: {info['desc']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Manual Override
    if st.session_state.breathing_active:
        if st.button("⬅️ Back to Chat", type="primary"):
            st.session_state.breathing_active = False
            # Return to Ambient (2)
            st.session_state.current_mode = 2
            send_command_to_arduino(2)
            st.rerun()
    else:
        st.write("Debug Control")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Force Anchor (1)"):
                st.session_state.current_mode = 1
                send_command_to_arduino(1)
                st.rerun()
        with col2:
            if st.button("Force Spark (6)"):
                st.session_state.current_mode = 6
                send_command_to_arduino(6)
                st.rerun()

    st.markdown("---")
    if st.button("Clear Memory"):
        st.session_state.messages = [{"role": "system", "content": NINO_SYSTEM_PROMPT}]
        st.session_state.messages.append({"role": "assistant", "content": "Hi.\n[MODE:2]"})
        st.session_state.breathing_active = False
        st.session_state.current_mode = 2
        send_command_to_arduino(2)
        st.rerun()

# --- Main Logic ---

if st.session_state.breathing_active:
    # -----------------------------------------------------
    # VIEW A: Breathing Exercise (Triggered by Mode 1)
    # -----------------------------------------------------
    st.title("The Anchor")
    st.markdown("""
        <div class="breath-container">
            <div class="breath-circle">Inhale</div>
            <div class="instruction-text">
                Focus on the light.<br>
                Expanding: Inhale (4s)<br>
                Contracting: Exhale (6s)
            </div>
        </div>
    """, unsafe_allow_html=True)

else:
    # -----------------------------------------------------
    # VIEW B: Chat Interface
    # -----------------------------------------------------
    st.title("Nino")
    
    # History
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                display_text = re.sub(r"\[MODE:\d\]", "", msg["content"]).strip()
                st.markdown(display_text)

    # Input
    user_input = st.chat_input("Say something...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            with st.spinner("Sensing..."):
                raw_reply = safe_chat_completion(st.session_state.messages)
                clean_reply, new_mode = parse_and_send_response(raw_reply)
                st.markdown(clean_reply)
                
                # 🔥 Contextual Feature:
                # IF Nino switches to [MODE:1] (The Anchor), suggest breathing UI
                if new_mode == 1:
                    st.session_state.show_breath_suggestion = True
                else:
                    st.session_state.show_breath_suggestion = False

        st.session_state.messages.append({"role": "assistant", "content": raw_reply})
        st.rerun()

    # Contextual Button (Bottom of chat)
    # Checks if current mode is 1 (Anchor)
    if st.session_state.get("show_breath_suggestion", False) and st.session_state.current_mode == 1:
        st.info("⚓ Nino 進入了 Anchor 狀態，協助您穩定情緒。")
        if st.button("開啟呼吸調節畫面 (Open Breathing Guide)"):
            st.session_state.breathing_active = True
            st.rerun()
