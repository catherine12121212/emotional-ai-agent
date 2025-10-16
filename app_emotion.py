# app_emotion.py
import streamlit as st
from openai import OpenAI
import os, re

st.set_page_config(page_title="Emotion-Aware AI Companion", page_icon="🌿", layout="centered")

# 讀 API key（Secrets 優先，否則讀環境變數）
api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Go to Settings → Secrets and add:\nOPENAI_API_KEY = sk-xxxx")
    st.stop()

client = OpenAI(api_key=api_key)


# --- Streamlit 基本設定 ---
st.set_page_config(page_title="Emotion-Aware AI Companion", page_icon="🌿", layout="centered")
st.title("🌙 Emotion-Aware AI Companion")
st.markdown("A gentle, emotionally intelligent AI that listens and responds with empathy.")

# --- AI 人格設定 ---
base_persona = """
You are a warm, emotionally intelligent AI companion.
Your job is to listen, reflect, and respond with empathy.
Use therapeutic communication techniques such as active listening,
validation, and gentle reframing. Avoid generic encouragement; respond
with emotional accuracy and psychological safety.
"""

# --- 簡易情緒偵測函數 ---
def detect_emotion(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ["anxious", "nervous", "worried", "pressure", "panic"]):
        return "anxiety"
    elif any(word in text_lower for word in ["sad", "lonely", "upset", "tired", "hurt"]):
        return "sadness"
    elif any(word in text_lower for word in ["angry", "frustrated", "irritated"]):
        return "anger"
    elif any(word in text_lower for word in ["happy", "grateful", "peaceful", "content"]):
        return "calm"
    else:
        return "neutral"

# --- 不同情緒的語氣設定 ---
tone_prompts = {
    "anxiety": "Use a calm, grounding tone. Offer slow breathing or grounding guidance and reassurance.",
    "sadness": "Use a warm, compassionate tone. Reflect their pain gently and remind them they are not alone.",
    "anger": "Use a steady, validating tone. Normalize their anger and help them regain clarity.",
    "calm": "Use an affirming tone. Reinforce their stability and self-awareness.",
    "neutral": "Use a curious, open tone. Encourage gentle reflection."
}

# --- 儲存歷史訊息 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": base_persona}]

# --- 顯示歷史訊息 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- 使用者輸入 ---
if user_input := st.chat_input("How are you feeling right now?"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    emotion = detect_emotion(user_input)
    st.markdown(f"**🫧 Detected emotion:** {emotion.capitalize()}")

    tone_instruction = tone_prompts.get(emotion, tone_prompts["neutral"])
    system_context = base_persona + "\nTone style: " + tone_instruction

    with st.chat_message("assistant"):
        with st.spinner("Listening with care..."):
            response = client.chat.completions.create(
                model="gpt-4o",   # 也可改成 "gpt-4o" 或 "gpt-4"
                messages=[
                    {"role": "system", "content": system_context},
                    *[msg for msg in st.session_state.messages if msg["role"] != "system"]
                ],
                temperature=0.85
            )
            ai_reply = response.choices[0].message.content.strip()
            ai_reply = re.sub(r'^\s+', '', ai_reply)
            st.markdown(ai_reply)

    st.session_state.messages.append({"role": "assistant", "content": ai_reply})

# --- 反思區塊 ---
with st.expander("🪞 Self-Reflection"):
    mood = st.radio("How do you feel after this chat?", ["Lighter", "Still heavy", "Calmer", "Hopeful", "Confused"], index=None)
    st.text_area("Note to yourself:", placeholder="Write a small reflection...")
    if mood:
        st.success("🌷 Thank you for reflecting — awareness is already growth.")

st.markdown("---")
st.caption("💚 Designed by Catherine Liu · Emotion-Aware Prototype powered by GPT-5 & Streamlit")

