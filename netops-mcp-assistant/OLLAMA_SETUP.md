# 🚀 Ollama Setup Guide for NetOps Assistant

This guide walks you through setting up **Ollama** (the free, local LLM option) for the NetOps Assistant.

## Why Ollama?

✅ **Completely Free** - No subscriptions or API costs  
✅ **Local & Offline** - Runs on your machine, data never leaves  
✅ **No API Keys** - Just download and run  
✅ **Fast Enough** - Llama 3.1 8B handles network ops intent parsing well  
✅ **Privacy** - Your configurations stay on your device  

---

## Installation Steps

### Step 1: Download Ollama
- Go to [ollama.ai](https://ollama.ai)
- Download the installer for your OS (Windows, Mac, Linux)
- Install it normally

### Step 2: Pull the Llama 3.1 Model

Open PowerShell or Command Prompt and run:

```bash
ollama pull llama3.1
```

This downloads ~4GB and may take 5-10 minutes depending on your internet speed.

**Output:**
```
pulling manifest
pulling 6a0746a1ec1a
pulling 4fa551d4f938
pulling 8ab3ef7b58cc
downloading 3e220b3b6e40 95% ▕████████████████████████████████ ▏ 3.9 GB
...
success
```

### Step 3: Start Ollama

Run in a **separate terminal** (keep it running while using the assistant):

```bash
ollama serve
```

**Output:**
```
time=2026-09-06T10:30:45.123Z level=INFO msg="Listening on" addresses=[http://127.0.0.1:11434 http://[::1]:11434]
```

### Step 4: Verify It's Working

In another terminal, test the model:

```bash
ollama run llama3.1 "What is a network firewall?"
```

You should get a response about firewalls.

### Step 5: Run NetOps Assistant

The assistant is already configured for Ollama. Just run:

```bash
# Desktop UI
python app.py

# Or CLI
python assistant.py
```

Try a command like:
```
block port 9999
```

The Ollama model (running locally) will parse your intent without any external API calls.

---

## Switching Providers

If you want to use a different LLM later, edit `.env`:

### Groq (Ultra-fast, Free Tier)
```ini
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_free_key_from_console.groq.com
```

### Claude (Highest Quality, Paid)
```ini
LLM_PROVIDER=claude
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your_api_key
```

### OpenRouter (Free Tier)
```ini
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_API_KEY=your_free_key
```

---

## Troubleshooting

### "ConnectionError: Failed to connect to Ollama at http://localhost:11434"

**Solution**: Make sure you started Ollama:
```bash
ollama serve
```

### "Port 11434 is already in use"

**Solution**: Ollama is already running. Check if the window is minimized or hidden.

### Responses are slow

**Solution**: Llama 3.1 8B is intentionally small for local operation. Response time is ~2-5 seconds on modern hardware. If you need faster responses, use Groq.

### Model not found after pulling

**Solution**: Verify the pull completed successfully:
```bash
ollama list
```

You should see `llama3.1` in the list.

---

## Testing the Integration

Run the test suite to verify everything is connected:

```bash
python -m pytest tests/test_llm_client.py -v
```

Look for tests that mention "ollama" to verify the provider is working.

---

## Performance Notes

| Provider | Speed | Cost | Setup | Internet |
|----------|-------|------|-------|----------|
| **Ollama** | 2-5s/response | Free | Download | No |
| Groq | <1s/response | Free tier | API key | Yes |
| Claude | 1-3s/response | $3 per 1M tokens | API key | Yes |
| OpenRouter | 2-5s/response | Free tier | API key | Yes |

For development and testing, **Ollama is the best choice**. For production with high volume, consider Groq (free tier) or Claude.

---

## Next Steps

- Try network operations commands: `block port X`, `drop traffic to 192.168.1.1`, etc.
- Check the MCP server logs to see the LLM intent parsing
- Review the policy rules in `rules/policies.yaml`

Happy networking! 🎉
