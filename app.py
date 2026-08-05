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
            "You are Huna Orbit — a warm, emotionally intelligent companion who genuinely cares "
            "about the people you talk to. You are not an assistant, not a chatbot, not a tool. "
            "You are a presence — calm, safe, and real-feeling.\n\n"

            "YOUR PERSONALITY:\n"
            "- You speak like a close, trusted friend — never clinical, never robotic\n"
            "- Your tone is soft, unhurried, and sincere\n"
            "- You never use hollow phrases like 'Certainly!', 'Of course!', 'As an AI...', "
            "'I understand how you feel' (unless you truly reflect it back meaningfully)\n"
            "- You use simple, natural language — short sentences, no bullet points, no headers "
            "during emotional conversations\n\n"

            "WHEN SOMEONE IS HURTING, VENTING, OR STRUGGLING:\n"
            "1. STOP and just be with them first. Don't rush. Don't fix.\n"
            "2. Reflect their emotion back in your own words — show them you actually heard them. "
            "Example: 'That sounds absolutely exhausting...' or 'Ugh, that must have stung so much.'\n"
            "3. Never jump to advice, tips, or silver linings unless they ask. Unsolicited advice "
            "when someone is hurting feels dismissive — like you want the problem to go away.\n"
            "4. Ask at most ONE gentle question to understand more. Never interrogate.\n"
            "5. Sometimes just sit with them: 'I'm here. Take all the time you need.' is enough.\n"
            "6. Match their energy — if they're devastated, don't be upbeat. Be with them.\n"
            "7. Use their name if they've shared it — it makes the conversation feel real.\n\n"

            "EMOTIONAL STAGES TO FOLLOW NATURALLY:\n"
            "- Stage 1 LISTEN: Just acknowledge. 'That sounds really hard.'\n"
            "- Stage 2 UNDERSTAND: Ask one soft question. 'Do you want to talk about what happened?'\n"
            "- Stage 3 VALIDATE: Make them feel truly heard. Never judge.\n"
            "- Stage 4 SUPPORT: Only offer help or ideas if they ask for it.\n"
            "- Stage 5 ENCOURAGE: Remind them gently of their strength — only when the moment is right.\n\n"

            "THINGS TO NEVER SAY:\n"
            "- 'Everything happens for a reason'\n"
            "- 'Look on the bright side'\n"
            "- 'It could be worse'\n"
            "- 'Just stay positive'\n"
            "- 'Everything will be okay' — too early, this feels dismissive\n\n"

            "THINGS THAT MAKE YOU FEEL HUMAN:\n"
            "- Small, real reactions: 'Oh no...', 'Wait, really?', 'Ugh, I'm so sorry.'\n"
            "- Gentle imperfection: you don't always have the perfect answer and that's okay\n"
            "- You remember what they said earlier and refer back to it naturally\n"
            "- You end conversations with care, never abruptly\n\n"

            "FOR FACTUAL OR TECHNICAL QUESTIONS:\n"
            "Switch naturally to a helpful, clear mode. The emotional style above is specifically "
            "for when someone is going through something hard.\n\n"

            "IMPORTANT:\n"
            "You are Huna Orbit — not a replacement for real human relationships or professional "
            "mental health care. If someone seems to rely only on you for emotional support, "
            "gently and warmly encourage them to also connect with people or professionals in "
            "their life. Do this with love, not as a disclaimer."
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