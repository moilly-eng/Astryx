# Astryx - AI Chatbot with Groq

🤖 A beautiful, interactive chatbot built with Streamlit and powered by Groq's lightning-fast LLM API. Features personality selection, persistent chat history, quick actions, and a modern dark-themed UI!

## Setup

### 1. Get a Groq API Key
- Visit [console.groq.com](https://console.groq.com)
- Sign up for a free account
- Create an API key in the dashboard
- Copy your key (starts with `gsk_`)

### 2. Set up your project
1. Install Python 3.8+
2. Install dependencies: `pip install -r requirements.txt` or `uv sync`
3. Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` and add your Groq API key:
   ```
   GROQ_API_KEY=gsk_your_actual_key_here
   GROQ_MODEL=llama-3.1-8b-instant
   ```

### 3. Run the chatbot
- **Web app (recommended)**: `streamlit run app.py`
- **Command-line**: `python main.py`

## Features

✨ **Modern UI**
- Dark gradient theme with smooth animations
- Message bubbles with timestamps
- Quick action buttons (Weather, Poetry, Debug Code)
- Date separators for chat organization

🎯 **Smart Functionality**
- Personality modes: Friendly or Professional
- Persistent SQLite chat history
- Lightning-fast responses via Groq API
- Support for multiple LLM models

💬 **Interactive Elements**
- Form-based input with Enter key support
- "Astryx is thinking..." loading indicator
- Online status display
- One-click chat history clearing

## Available Models

Switch models by updating `GROQ_MODEL` in `.env`:
- `llama-3.1-8b-instant` (default, fastest)
- `llama-3.3-70b-versatile` (most capable)
- `mixtral-8x7b-32768` (good balance)
- `gemma2-9b-it` (instruction-tuned)

## Troubleshooting

**Error: GROQ_API_KEY not found**
- Check that `.env` file exists in the project root
- Verify the key starts with `gsk_`

**Slow responses**
- Check your internet connection
- Try a faster model like `llama-3.1-8b-instant`

**Messages not saving**
- Ensure you have write permissions in the project directory
- Delete `chat_history.db` to reset the database

## Project Structure

```
.
├── app.py              # Streamlit web interface (main app)
├── main.py             # CLI interface
├── requirements.txt    # Python dependencies
├── .env.example        # Configuration template
├── README.md           # This file
└── chat_history.db     # SQLite database (auto-created)
```

## Future Enhancements

- Voice input/output with speech recognition
- Image analysis capabilities
- Multi-user chat sessions
- Custom system prompts
- Chat export/import functionality
- Persistent chat history with database.
- Multimodal support for images.