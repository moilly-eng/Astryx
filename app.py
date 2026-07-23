import os
import threading
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

load_dotenv('.env', override=True)
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

try:
    import groq
    groq_available = True
except Exception:
    groq_available = False

client = None
if groq_available and GROQ_API_KEY:
    try:
        client = groq.Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

st.set_page_config(page_title='Astryx — Stellar Intelligence', layout='wide')

if not GROQ_API_KEY:
    st.warning('GROQ_API_KEY is missing. Add it to .env or Streamlit secrets before using the assistant.')

if not groq_available:
    st.warning('Groq SDK is unavailable. Install the groq package in your environment.')


def create_api_app():
    from flask import Flask, jsonify, request
    from flask_cors import CORS

    api = Flask(__name__)
    CORS(api)

    @api.route('/api/chat', methods=['POST'])
    def chat_endpoint():
        data = request.get_json(silent=True) or {}
        text = (data.get('message') or '').strip()
        if not text:
            return jsonify({'error': 'Missing message field'}), 400
        if client is None:
            return jsonify({'error': 'No Groq client configured'}), 500

        try:
            system_prompt = (
                "You are Astryx, a polished AI assistant. Organize your answer into tidy topic sections, "
                "use short paragraphs and bullet points when appropriate, and keep the response clear, neat, "
                "and easy to scan."
            )
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': text},
                ],
                max_tokens=512,
                temperature=0.3,
            )
            reply = response.choices[0].message.content
            return jsonify({'reply': reply})
        except Exception as err:
            return jsonify({'error': str(err)}), 500

    return api


def start_api_server():
    if st.session_state.get('api_thread_started', False):
        return

    api_app = create_api_app()

    def run_api():
        api_app.run(host='127.0.0.1', port=8503, debug=False, use_reloader=False)

    thread = threading.Thread(target=run_api, daemon=True)
    thread.start()
    st.session_state['api_thread_started'] = True


def load_ui_html() -> str:
    html_path = Path(__file__).parent / 'ui.html'
    return html_path.read_text(encoding='utf-8')


st.markdown('# Astryx — Stellar Intelligence')

with st.container():
    if client is None:
        st.error('Astryx will render, but the chat backend is not configured. Check GROQ_API_KEY and the groq package.')

    start_api_server()
    ui_html = load_ui_html()
    st.components.v1.html(ui_html, height=900, scrolling=True)
