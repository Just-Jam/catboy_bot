import os
from ollama import Client
from dotenv import load_dotenv
load_dotenv()

client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.getenv('OLLAMA_API_KEY')}
)

messages = [
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
]

for part in client.chat('gpt-oss:120b', messages=messages, stream=True):
  print(part['message']['content'], end='', flush=True)