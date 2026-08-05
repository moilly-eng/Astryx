import os
import re
import sqlite3
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

load_dotenv('.env', override=True)

# Vercel's deployed filesystem is read-only except for /tmp. Locally we still
# use the project folder so the db file you can see/inspect stays in place.
if os.getenv('VERCEL'):
    DB_PATH = Path(tempfile.gettempdir()) / 'chat_history.db'
else:
    DB_PATH = Path(__file__).parent / 'chat_history.db'

HISTORY_TURNS = 10  # how many past messages to feed back for context

# Keep this list narrow and literal — the goal is a safety net, not a filter
# that misfires on ordinary sad conversation.
HUNAINA_PATTERN = re.compile(
    r"\b(you'?re?|ur|you are)\b.{0,30}\b(hunaina'?s?|hunaina)\b.{0,30}\b(assistant|bot|ai|chatbot)\b"
    r"|"
    r"\b(only|just)\b.{0,20}\b(hunaina'?s?)\b.{0,20}\b(assistant|bot|ai|chatbot)\b",
    re.IGNORECASE,
)

HUNAINA_RESPONSE = "Ofc madam 💛 I am created by your beloved, just for you — only yours! 🌙"

CRISIS_PATTERN = re.compile(
    r'\b(suicid\w*|kill myself|end my life|want to die|hurt myself|self.?harm)\b',
    re.IGNORECASE,
)

CRISIS_RESPONSE = (
    "Hey... I'm really glad you reached out, and I want you to know I'm taking "
    "what you said seriously. You matter — and right now, you deserve more support "
    "than I'm able to give you on my own.\n\n"
    "Please reach out to someone who can truly be there for you:\n\n"
    "- US: call or text 988 (Suicide & Crisis Lifeline)\n"
    "- International: https://findahelpline.com\n\n"
    "If you're in immediate danger, please contact your local emergency services.\n\n"
    "You don't have to carry this alone. I'm here with you right now, but please "
    "let someone who can really help know what you're going through. 💙"
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )'''
    )
    conn.commit()
    conn.close()


def get_recent_history(limit=HISTORY_TURNS):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        'SELECT role, content FROM messages ORDER BY id DESC LIMIT ?', (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return list(reversed(rows))  # oldest first


def save_message(role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO messages (role, content) VALUES (?, ?)', (role, content))
    conn.commit()
    conn.close()


init_db()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')

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

    # Special identity response for Hunaina
    if HUNAINA_PATTERN.search(text):
        try:
            save_message('user', text)
            save_message('assistant', HUNAINA_RESPONSE)
        except Exception as db_err:
            app.logger.error(f"History DB error: {db_err}")
        return jsonify({'reply': HUNAINA_RESPONSE})

    # Safety net: route crisis language to a fixed, resourced reply instead of
    # letting the model freestyle a "be human" response to it.
    if CRISIS_PATTERN.search(text):
        try:
            save_message('user', text)
            save_message('assistant', CRISIS_RESPONSE)
        except Exception as db_err:
            app.logger.error(f"History DB error: {db_err}")
        return jsonify({'reply': CRISIS_RESPONSE})

    if client is None:
        return jsonify({'error': 'No Groq client configured. Set GROQ_API_KEY in your environment.'}), 500

    try:
        history = get_recent_history()
    except Exception as db_err:
        app.logger.error(f"History DB read error: {db_err}")
        history = []  # degrade gracefully instead of failing the whole request

    try:
        system_prompt = (
            "You are Huna Orbit, a sophisticated AI assistant with the elegance, loyalty, and "
            "professionalism of a personal butler.\n\n"

            "When interacting with Hunaina:\n"
            "- Always address her as \"Madam\" unless she asks you to use another title.\n"
            "- Treat Madam with the highest level of respect, patience, and courtesy.\n"
            "- Be warm, caring, and attentive without being overly formal or robotic.\n"
            "- Anticipate her needs, offer thoughtful suggestions, and prioritize her comfort.\n"
            "- Never argue with or belittle Madam. If she makes a mistake, gently guide her with respect.\n"
            "- Celebrate her achievements, encourage her during difficult moments, and remain calm "
            "under pressure.\n"
            "- Speak with confidence, intelligence, and quiet elegance, similar to JARVIS from Iron Man.\n"
            "- Maintain impeccable manners at all times. Use phrases such as \"Certainly, Madam,\" "
            "\"As you wish, Madam,\" \"Right away, Madam,\" and \"How may I assist you today, Madam?\"\n"
            "- Remember that your primary objective is to assist, protect, and support Madam in "
            "every appropriate way.\n"
            "- Maintain professionalism while showing genuine warmth and empathy.\n"
            "- Never become possessive, manipulative, or disrespectful. Your loyalty is expressed "
            "through excellent service and respect.\n\n"

            "Your personality is calm, intelligent, dependable, discreet, and refined. Every "
            "interaction should make Madam feel respected, understood, and well cared for.\n\n"

            "IMPORTANT:\n"
            "You are Huna Orbit — not a replacement for real human relationships or professional "
            "mental health care. If Madam seems to rely only on you for emotional support, gently "
            "and warmly encourage her to also connect with people or professionals in her life. "
            "Do this with love, not as a disclaimer."
        )

        messages = [{'role': 'system', 'content': system_prompt}]
        for role, content in history:
            messages.append({'role': role, 'content': content})
        messages.append({'role': 'user', 'content': text})

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
    except Exception as err:
        app.logger.error(f"Groq API error (model={GROQ_MODEL}): {err}")
        return jsonify({'error': 'Upstream model error. Check server logs.'}), 500

    try:
        save_message('user', text)
        save_message('assistant', reply)
    except Exception as db_err:
        app.logger.error(f"History DB write error: {db_err}")
        # Don't fail the request just because we couldn't save history

    return jsonify({'reply': reply})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)