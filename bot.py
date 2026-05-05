import os
import json
import random
import asyncio
from typing import List, Dict
from collections import deque

import discord
from discord.ext import commands
from ollama import Client
from dotenv import load_dotenv
from duckduckgo_search import DDGS

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

if not DISCORD_TOKEN or not OLLAMA_API_KEY:
    print("Error: DISCORD_TOKEN or OLLAMA_API_KEY not found in .env file")
    exit(1)

# Initialize Ollama client
client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + OLLAMA_API_KEY}
)

# Cached configuration to avoid constant disk I/O
CACHE = {
    "config": {},
    "persona": "",
    "interests": ""
}

def refresh_cache():
    """Reloads config, persona and interests from disk."""
    CACHE["config"] = load_config()
    CACHE["persona"] = load_persona()
    CACHE["interests"] = load_interests()
    print("Cache refreshed.")

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def load_persona():
    with open("persona.md", "r", encoding="utf-8") as f:
        return f.read()

def load_interests():
    with open("interests.md", "r", encoding="utf-8") as f:
        return f.read()

def load_dictionary():
    try:
        with open("dictionary.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def update_dictionary(entry_text: str):
    """Processes LLM output and adds valid 'word: definition' entries to dictionary.md."""
    current_dict = load_dictionary()

    # Split by lines in case the LLM returned multiple entries or a list
    lines = entry_text.split('\n')
    added_count = 0

    for line in lines:
        line = line.strip()
        # Basic validation: must contain a colon and not be a thought/reasoning line
        if ":" in line and not line.startswith(("#", "However", "So", "Therefore", "Final")):
            # Extract the word for duplicate checking
            word_part = line.split(":")[0].strip().lower()

            # Remove any markdown bullets if the LLM added them
            word_part = word_part.lstrip("- ").lstrip("* ").strip()

            if word_part and word_part not in current_dict.lower():
                # Clean the entry for consistent formatting
                clean_entry = line.strip("- ").strip("* ").strip()
                with open("dictionary.md", "a", encoding="utf-8") as f:
                    f.write(f"\n- **{clean_entry}**")
                added_count += 1

    return added_count > 0

# Bot setup
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory conversation history: {channel_id: deque([messages])}
conversation_history: Dict[int, deque] = {}

async def check_interest(user_message: str) -> bool:
    if len(user_message.strip()) < 5:
        return False

    interests = CACHE["interests"]
    model = CACHE["config"].get("model", "gpt-oss:120b")
    prompt = (
        f"Bot Interests:\n{interests}\n\n"
        f"User Message: {user_message}\n\n"
        "Would the bot find this message interesting enough to respond to? "
        "Answer only 'YES' or 'NO'."
    )
    try:
        # Run synchronous Ollama call in a thread to prevent blocking the event loop
        response = await asyncio.to_thread(
            client.chat,
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response['message']['content'].strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"Interest Check Error: {e}")
        return False

async def search_web(query: str):
    try:
        with DDGS() as ddgs:
            results = [r['body'] for r in ddgs.text(query, max_results=3)]
            return "\n".join(results)
    except Exception as e:
        print(f"Search Error: {e}")
        return ""

async def get_llm_response(channel_id: int, user_message: str, author_name: str):
    config = CACHE["config"]
    persona = CACHE["persona"]
    dictionary = load_dictionary()

    # Manage history window using deque for automatic cleanup
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=config["context_window"])

    # Add current message to history
    conversation_history[channel_id].append({"role": "user", "content": f"{author_name}: {user_message}"})

    # Construct prompt
    history_list = list(conversation_history[channel_id])
    system_prompt = (
        f"{persona}\n\n"
        f"Your Personal Dictionary/Knowledge:\n{dictionary}\n\n"
        f"Recent conversation context:\n" + "\n".join([m["content"] for m in history_list[:-1]])
    )

    # Decide if we need to search the web (simple check)
    search_query = None
    if any(word in user_message.lower() for word in ["what is", "who is", "search for", "latest on"]):
        search_query = user_message

    web_context = ""
    if search_query:
        web_context = await search_web(search_query)
        system_prompt += f"\n\nWeb Search Results for '{search_query}':\n{web_context}"

    try:
        # Run synchronous Ollama call in a thread
        model = CACHE["config"].get("model", "gpt-oss:120b")
        response = await asyncio.to_thread(
            client.chat,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{author_name}: {user_message}"}
            ]
        )
        text = response['message']['content']

        # Add bot response to history
        conversation_history[channel_id].append({"role": "assistant", "content": f"Bot: {text}"})

        # --- AUTONOMOUS LEARNING STEP ---
        learning_prompt = (
            f"Conversation:\n{user_message}\nBot: {text}\n\n"
            "Is there any new slang or a fact here that should be added to the bot's dictionary? "
            "If yes, output ONLY the entries in 'word: definition' format, one per line. "
            "Do NOT include any thoughts, reasoning, explanations, or introductory text. "
            "If nothing new, output 'NONE'."
        )

        # Run learning check in thread
        learn_res = await asyncio.to_thread(
            client.chat,
            model=model,
            messages=[{"role": "user", "content": learning_prompt}]
        )
        learn_text = learn_res['message']['content'].strip()

        # Remove potential <think> tags if the model still produces them
        if "</think>" in learn_text:
            learn_text = learn_text.split("</think>")[-1].strip()

        if learn_text != "NONE":
            update_dictionary(learn_text)

        return text
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

@bot.event
async def on_ready():
    refresh_cache()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is active and monitoring messages...")

@bot.command(name="learn")
async def learn(ctx, *, entry: str):
    """Manually teach the bot new slang or knowledge."""
    if ":" not in entry:
        await ctx.send("bruh use the format `word: definition` fr")
        return

    if update_dictionary(entry):
        await ctx.send(f"bet. added {entry.split(':')[0]} to the vault 🐱")
    else:
        await ctx.send("already know that one lol")

@bot.command(name="getpersona")
async def get_persona(ctx):
    """View the current persona guidelines."""
    persona = load_persona()
    if not persona:
        await ctx.send("bruh the persona file is empty. i have no soul 💀")
        return

    # Discord messages have a 2000 character limit
    if len(persona) > 1900:
        # Split into chunks if too long
        chunks = [persona[i:i+1900] for i in range(0, len(persona), 1900)]
        for chunk in chunks:
            await ctx.send(f"```{chunk}```")
    else:
        await ctx.send(f"```{persona}```")

@bot.command(name="setpersona")
async def set_persona(ctx, *, new_persona: str):
    """Update the bot's persona guidelines directly from Discord."""
    # Ensure a basic structure if the user just sends a random string
    formatted_persona = new_persona
    if "# Persona" not in new_persona:
        formatted_persona = f"# Persona: Updated by User\n\n{new_persona}"

    try:
        with open("persona.md", "w", encoding="utf-8") as f:
            f.write(formatted_persona)

        # Important: Refresh the cache so the bot uses the new persona immediately
        refresh_cache()

        await ctx.send("bet. persona updated. i feel like a new cat 🐱")
    except Exception as e:
        await ctx.send(f"bruh it broke: {e}")

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # 1. Check if this is a Direct Message (DM)
    is_dm = isinstance(message.channel, discord.DMChannel)

    # 2. Always respond to mentions in servers
    is_mentioned = bot.user.mentioned_in(message)

    # 3. Interest-based trigger (only for servers)
    is_interesting = False
    if not is_dm:
        is_interesting = await check_interest(message.content)

    # 4. Probability check for general engagement (only for servers)
    config = load_config()
    should_reply_randomly = False
    if not is_dm:
        should_reply_randomly = random.random() < config["response_probability"]

    # Trigger response if: it's a DM, a mention, interesting, or random
    if is_dm or is_mentioned or is_interesting or should_reply_randomly:
        # Human-like delay and typing indicator
        delay = random.uniform(config["min_delay"], config["max_delay"])
        await asyncio.sleep(delay)

        async with message.channel.typing():
            # Simulating "thinking" time
            await asyncio.sleep(random.uniform(1, 3))

            response_text = await get_llm_response(
                message.channel.id,
                message.content,
                message.author.display_name
            )

            if response_text:
                # Split response into chunks based on newlines to simulate multiple messages
                chunks = [c.strip() for c in response_text.split('\n') if c.strip()]

                if len(chunks) > 1:
                    for chunk in chunks:
                        await message.channel.send(chunk)
                        # Small random delay between messages to feel human
                        await asyncio.sleep(random.uniform(1, 2.5))
                else:
                    # Just send the single message if there are no newlines
                    await message.channel.send(response_text)

    # Allow other commands to work
    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
