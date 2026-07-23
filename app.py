import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

load_dotenv('.env', override=True)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

try:
    import groq
except Exception:
    groq = None

client = None
if groq is not None and GROQ_API_KEY:
    try:
        client = groq.Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

app = Flask(__name__)
CORS(app)


def load_ui_html() -> str:
    html_path = Path(__file__).parent / 'ui.html'
    return html_path.read_text(encoding='utf-8')


@app.get('/')
def home():
    return Response(load_ui_html(), mimetype='text/html')


@app.post('/api/chat')
def chat_endpoint():
    data = request.get_json(silent=True) or {}
    text = (data.get('message') or '').strip()
    if not text:
        return jsonify({'error': 'Missing message field'}), 400

    if client is None:
        return jsonify({'error': 'No Groq client configured. Set GROQ_API_KEY in your environment.'}), 500

    try:
        system_prompt = (
            'You are Astryx, a polished AI assistant. Organize your answer into tidy topic sections, '
            'use short paragraphs and bullet points when appropriate, and keep the response clear, neat, '
            'and easy to scan.'
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
