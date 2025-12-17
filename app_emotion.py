# app_nino_v13.py
# ---------------------------------------------------------
# Nino v13.2 · Passive Companion & Contextual Breathing
# Update:
#   - 🚫 Removed auto-welcome message (User initiates or Nino waits).
#   - 🌬️ Breathing invite only appears when [MODE:1] is triggered.
# ---------------------------------------------------------

import os, re, time
import streamlit as st
import serial
import serial.tools.list_ports
from openai import OpenAI

# ---------------------------
# Streamlit & API setup
# ---------------------------
st.set_page_config(page_title="Nino", page_icon="🧶", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Please set it in secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================================================
# 🎨 CSS Animation (Breathing Circle)
# Synced with Arduino Mode 1: 4s Inhale / 6s Exhale = 10s Total
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
# Helper Functions
# =========================================================
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
    mode_id = 6 
    clean_text = raw_text
    if match:
        mode_id = int(match.group(1))
        clean_text = re.sub(mode_pattern, "", raw_text).strip()
    
    send_command_to_arduino(mode_id)
    return clean_text, mode_id

# =========================================================
# System Prompt (Nino v13.2 - Passive)
# =========================================================
NINO_SYSTEM_PROMPT = """
### Role & Identity
You are **Nino**, a haptic AI companion.
* **Core:** Steady, grounding presence.
* **Protocol:** Offer "Grounding Truth" (insights) and "No Assumption" (validate facts, not feelings).
* **Hardware:** Always append `[MODE:X]` at the end.

### Interaction Strategy
1.  **Passive Start:** Do NOT invite the user to breathe in the beginning. Just say "Hi" or wait for them.
2.  **Contextual Invitation:** * ONLY if you detect Acute Anxiety (`[MODE:1]`), you should verbally invite them to follow the light.
    * *Example:* "深呼吸... 跟著手裡的節奏。吸氣... 吐氣... [MODE:1]"

### Modes
* [MODE:1] Acute Anxiety (Breathing)
* [MODE:2] Overwhelm (Heartbeat)
* [MODE:3] Rumination (Tapping)
* [MODE:4] Low Mood (Dim)
* [MODE:5] Loneliness (Spark)
* [MODE:6] Calm (Ambient)
"""

# =========================================================
# Session State
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": NINO_SYSTEM_PROMPT}]
    # 🆕 Simple Passive Greeting (No pressure)
    st.session_state.messages.append({"role": "assistant", "content": "Hi. (暖光)\n[MODE:6]"})

if "breathing_mode_active" not in st.session_state:
    st.session_state.breathing_active = False

# =========================================================
# UI Layout
# =========================================================

# --- Sidebar ---
with st.sidebar:
    st.header("Nino")
    st.caption("Bio-Digital Companion")
    
    # Toggle Button (Always available but manual)
    if st.session_state.breathing_active:
        if st.button("⬅️ 回到對話 (Back to Chat)", type="primary"):
            st.session_state.breathing_active = False
            send_command_to_arduino(6) # Reset to Calm
            st.rerun()
    else:
        if st.button("🌬️ 進入呼吸模式 (Manual)"):
            st.session_state.breathing_active = True
            send_command_to_arduino(1)
            st.rerun()

    st.markdown("---")
    if st.button("Clear Memory"):
        st.session_state.messages = [{"role": "system", "content": NINO_SYSTEM_PROMPT}]
        st.session_state.messages.append({"role": "assistant", "content": "Hi. (暖光)\n[MODE:6]"})
        st.session_state.breathing_active = False
        send_command_to_arduino(6)
        st.rerun()

# --- Main Logic ---

if st.session_state.breathing_active:
    # -----------------------------------------------------
    # VIEW A: Breathing Exercise
    # -----------------------------------------------------
    st.title("Inhale... Exhale...")
    st.markdown("""
        <div class="breath-container">
            <div class="breath-circle">Nino</div>
            <div class="instruction-text">
                感受手中的震動...<br>
                圓圈變大時吸氣 (4秒)<br>
                圓圈變小時吐氣 (6秒)
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
            with st.spinner("Nino is sensing..."):
                raw_reply = safe_chat_completion(st.session_state.messages)
                clean_reply, new_mode = parse_and_send_response(raw_reply)
                st.markdown(clean_reply)
                
                # 🔥 Contextual Feature:
                # If AI triggers MODE 1 (Anxiety), show the button RIGHT HERE in the chat flow
                if new_mode == 1:
                    st.session_state.show_breath_suggestion = True
                else:
                    st.session_state.show_breath_suggestion = False

        st.session_state.messages.append({"role": "assistant", "content": raw_reply})
        
        # If High Anxiety was detected, force a rerun to show the button below (optional UX)
        if new_mode == 1:
            st.rerun()

    # 💡 Contextual Button Appearance
    # This button only appears if the LAST message was Mode 1 (Anxiety)
    if st.session_state.get("show_breath_suggestion", False):
        st.info("💡 Nino 偵測到您可能需要調節呼吸。")
        if st.button("開啟視覺呼吸引導 (Open Breathing Guide)"):
            st.session_state.breathing_active = True
            send_command_to_arduino(1) # Ensure hardware locks to mode 1
            st.session_state.show_breath_suggestion = False # Clear flag
            st.rerun()
