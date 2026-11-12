---
title: Resume_Agent
app_file: app.py
sdk: gradio
sdk_version: 6.13.0
---

# Resume Agent

A career chatbot that answers questions about my background, skills and experience, as if you were talking to me.

It's an LLM agent with tool use: it grounds its answers in my LinkedIn profile and a written summary, stays in character, and uses tools to record a visitor's contact details or flag questions it can't answer so I can follow up.

**Built with:** Python, OpenAI API (tool calling), Gradio, uv

**Run it locally**

1. Clone the repo and `cd agent`
2. Add your `OPENAI_API_KEY` to a `.env` file
3. `uv run app.py` (or `pip install -r requirements.txt` then `python app.py`)

Part of a series of agentic AI projects I'm building. More at [github.com/SriramkOfc](https://github.com/SriramkOfc).
