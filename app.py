"""Ask Sriram: FastAPI JSON API for the website chat widget + a Gradio chat page.

Run locally:  uv run app.py   (needs OPENAI_API_KEY in .env)
Endpoints:
  GET  /api/health   -> {"ok": true}            (also used by the website to wake the Space)
  POST /api/chat     -> {"reply": "..."}         body: {"message": str, "history": [{role, content}]}
  GET  /             -> Gradio chat UI
"""

import os
import time
from collections import defaultdict, deque

import gradio as gr
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv(override=True)

from agent import MAX_INPUT_CHARS, answer  # noqa: E402  (needs env loaded first)

ALLOWED_ORIGINS = [
    "https://sriramkofc.github.io",
    "http://localhost:3000",
    "http://localhost:3100",
]

# Abuse protection: per-visitor and global limits keep the OpenAI bill predictable.
PER_IP_LIMIT, PER_IP_WINDOW = 20, 10 * 60  # 20 messages per 10 minutes
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "600"))

_hits: dict[str, deque] = defaultdict(deque)
_day = {"date": "", "count": 0}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _rate_limited(ip: str) -> str | None:
    now = time.time()
    today = time.strftime("%Y-%m-%d")
    if _day["date"] != today:
        _day.update(date=today, count=0)
    if _day["count"] >= DAILY_LIMIT:
        return "I've had a lot of conversations today and need a rest. Please email Sriram at sriramkofc@gmail.com."
    q = _hits[ip]
    while q and now - q[0] > PER_IP_WINDOW:
        q.popleft()
    if len(q) >= PER_IP_LIMIT:
        return "You're sending messages quickly. Give it a few minutes, or email Sriram at sriramkofc@gmail.com."
    q.append(now)
    _day["count"] += 1
    return None


class Turn(BaseModel):
    role: str
    content: str = Field(max_length=MAX_INPUT_CHARS * 2)


class ChatIn(BaseModel):
    message: str = Field(max_length=4000)
    history: list[Turn] = Field(default_factory=list, max_length=40)


api = FastAPI(title="Ask Sriram", docs_url=None, redoc_url=None)
api.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=86400,
)


@api.get("/api/health")
def health():
    return {"ok": True}


@api.post("/api/chat")
def chat(body: ChatIn, request: Request):
    limited = _rate_limited(_client_ip(request))
    if limited:
        return JSONResponse({"reply": limited, "limited": True}, status_code=429)
    try:
        reply = answer(body.message, [t.model_dump() for t in body.history])
    except Exception as e:  # noqa: BLE001
        print(f"chat error: {type(e).__name__}", flush=True)
        reply = "Sorry, something went wrong on my side. Please try again, or email Sriram at sriramkofc@gmail.com."
    return {"reply": reply}


def _gradio_fn(message, history):
    ip = "gradio"
    return _rate_limited(ip) or answer(message, history)


demo = gr.ChatInterface(
    fn=_gradio_fn,
    title="Ask Sriram",
    description="An AI assistant that answers questions about Sriram Karthikeyan's work. Website: https://sriramkofc.github.io",
    examples=[
        "What does Sriram do at FinTalkr?",
        "What has he built recently?",
        "How can I get in touch?",
    ],
    cache_examples=False,
)

app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("GRADIO_SERVER_PORT", "7860")))
