import os
from dotenv import load_dotenv
import groq

# Load environment variables
load_dotenv('.env', override=True)

# Groq configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY not found. Please set it in your .env file.")
    exit(1)

client = groq.Groq(api_key=GROQ_API_KEY)

print(f"Chatbot: Hello! I'm Astryx, powered by Groq using {GROQ_MODEL}. Type 'exit' to quit.")

while True:
    user_input = input("You: ")
    if user_input.lower() in ['exit', 'quit']:
        print("Chatbot: Goodbye!")
        break
    
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": user_input}]
        )
        print(f"Chatbot: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}. Make sure your GROQ_API_KEY is valid.")