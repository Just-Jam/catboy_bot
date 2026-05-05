# Catboy Bot Documentation

Welcome to the official documentation for **Catboy**, the chronically online, Gen Z-coded Discord participant.

## 🌟 Overview
Catboy isn't your typical bot. He doesn't just wait for commands; he hangs out in the server and jumps into conversations when they're "vibey" or based on his personal interests.

## 🛠️ Configuration
The bot's behavior is controlled by three main files:
- `config.json`: Controls response probability, delays, and memory window.
- `persona.md`: Defines Catboy's voice, slang usage, and general "too cool to care" attitude.
- `interests.md`: Lists the topics Catboy is passionate about. If a conversation hits these topics, he's more likely to reply.

## 📚 The Dictionary (`dictionary.md`)
Catboy has a personal dictionary where he stores slang and facts. He uses this to maintain consistency in his speech and learn new things.

## ⌨️ Commands
Catboy primarily interacts autonomously, but he supports the following commands:

### `!learn <word: definition>`
Used to manually teach Catboy new slang or facts.
- **Example**: `!learn rizz charisma in flirting`
- **Result**: The bot will add "rizz: charisma in flirting" to his `dictionary.md`.

### `!getpersona`
Displays the current `persona.md` content.
- **Usage**: Use this to see exactly what rules Catboy is following before making changes.

### `!setpersona <text>`
Updates the bot's personality guidelines.
- **Example**: `!setpersona you are now a grumpy cat who hates everything.`
- **Result**: Overwrites `persona.md` and refreshes the bot's behavior immediately.


## 🤖 Behavior Logic
1. **Mentions**: Always responds when tagged.
2. **Attention Mechanism**: Uses an LLM gate to check if a message matches his `interests.md`.
3. **Randomness**: Has a small chance (configured in `config.json`) to reply to any message just to be social.
4. **Internet Access**: If he detects questions like "what is" or "latest on", he will search the web via DuckDuckGo before responding.
5. **Learning**: After responding, the bot autonomously analyzes the conversation to see if there's new slang or knowledge worth adding to his dictionary.
