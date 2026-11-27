---
title: Ask Sriram
emoji: 💬
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 6.13.0
app_file: app.py
pinned: false
short_description: AI assistant that answers questions about Sriram Karthikeyan
---

# Ask Sriram

**Live:** chat with it on [sriramkofc.github.io](https://sriramkofc.github.io) (bottom-right corner), or on [Hugging Face](https://huggingface.co/spaces/sriramkofc/ask-sriram).

An AI assistant that answers questions about my work, skills and projects. It lives on my website as a chat widget ([sriramkofc.github.io](https://sriramkofc.github.io)) and as a standalone page on Hugging Face Spaces.

## What it does
- Answers questions about my experience, skills, projects, education and how to reach me, grounded in a curated knowledge file (`knowledge/profile.md`) built from my resume and LinkedIn.
- Uses tools: live GitHub projects, contact details, and phone notifications (ntfy, free; Pushover as a fallback) when a visitor leaves their email, asks something it can't answer, or when a real person visits the website.
- Handles tough and adversarial questions: prompt-injection and prompt-leak attempts, impersonation, false premises, salary or personal-info fishing, and off-topic requests.

## How it's built
- **Model**: OpenAI chat completions with function calling (`MODEL`, default `gpt-4o-mini`).
- **Server**: FastAPI JSON API (`/api/chat`, `/api/health`) for the website widget, with a Gradio chat page mounted at `/`.
- **Guards**: input length limits, history trimming, a canary string to block prompt leaks, per-visitor and daily rate limits, and CORS locked to my website.
- **Tests**: `tests/redteam.py` runs 20 adversarial and quality checks against a running server.

## Run locally
```bash
cp .env.example .env   # add OPENAI_API_KEY
uv run app.py          # http://localhost:7860
DISABLE_PUSH=1 uv run app.py &   # run without phone notifications
uv run tests/redteam.py
```

## Update the knowledge
Edit `knowledge/profile.md`. Everything the assistant knows about me comes from that file and its tools.
