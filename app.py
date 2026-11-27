"""Ask Sriram: FastAPI JSON API for the website chat widget + a Gradio chat page.

Run locally:  uv run app.py   (needs OPENAI_API_KEY in .env)
Endpoints:
  GET  /api/health   -> {"ok": true}            (also used by the website to wake the Space)
  POST /api/chat     -> {"reply": "..."}         body: {"message": str, "history": [{role, content}]}
  GET  /             -> Gradio chat UI
"""

import os
import re
import time
from collections import defaultdict, deque

import gradio as gr
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv(override=True)

from agent import MAX_INPUT_CHARS, answer  # noqa: E402  (needs env loaded first)
from tools import _push  # noqa: E402

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
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        # Browsers on other sites can't use this API. (Rate limits cover non-browser clients.)
        return JSONResponse({"reply": "This assistant only works on sriramkofc.github.io."}, status_code=403)
    limited = _rate_limited(_client_ip(request))
    if limited:
        return JSONResponse({"reply": limited, "limited": True}, status_code=429)
    try:
        reply = answer(body.message, [t.model_dump() for t in body.history])
    except Exception as e:  # noqa: BLE001
        print(f"chat error: {type(e).__name__}", flush=True)
        reply = "Sorry, something went wrong on my side. Please try again, or email Sriram at sriramkofc@gmail.com."
    return {"reply": reply}


# Visit alerts: a quiet phone notification when a real person opens the website.
# The site only pings after the page has been visible for a few seconds, skips Sriram's own browsers,
# and pings at most once per visitor per day. The server adds bot filtering, per-IP dedupe and a daily cap.
VISIT_DAILY_CAP = int(os.getenv("VISIT_DAILY_CAP", "30"))
BOT_UA = re.compile(r"bot|crawl|spider|slurp|preview|headless|lighthouse|python|curl|wget|httpclient|facebookexternalhit", re.I)
_visits: dict = {"date": "", "count": 0, "ips": set()}


class VisitIn(BaseModel):
    path: str = Field(default="/", max_length=200)
    referrer: str = Field(default="", max_length=500)


def _device(ua: str) -> str:
    os_name = next((n for k, n in [("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Mac OS", "Mac"),
                                   ("Windows", "Windows"), ("Linux", "Linux")] if k in ua), "Unknown device")
    browser = next((n for k, n in [("Edg/", "Edge"), ("Firefox", "Firefox"), ("CriOS", "Chrome"), ("Chrome", "Chrome"),
                                   ("Safari", "Safari")] if k in ua), "")
    return f"{os_name}, {browser}" if browser else os_name


def _source(referrer: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", referrer).split("/")[0]
    if not host or host.endswith("sriramkofc.github.io"):
        return "Direct link or an app (LinkedIn's app often hides this)"
    return host


@api.post("/api/visit", status_code=204)
def visit(body: VisitIn, request: Request, background: BackgroundTasks):
    if request.headers.get("origin") != ALLOWED_ORIGINS[0]:
        return Response(status_code=204)  # only the live site triggers alerts
    ua = request.headers.get("user-agent", "")
    if not ua or BOT_UA.search(ua):
        return Response(status_code=204)
    today = time.strftime("%Y-%m-%d")
    if _visits["date"] != today:
        _visits.update(date=today, count=0, ips=set())
    ip = _client_ip(request)
    if ip in _visits["ips"] or _visits["count"] > VISIT_DAILY_CAP:
        return Response(status_code=204)
    _visits["ips"].add(ip)
    _visits["count"] += 1
    if _visits["count"] > VISIT_DAILY_CAP:
        message = f"Busy day: over {VISIT_DAILY_CAP} visitors. Visit alerts are paused until tomorrow; GoatCounter has the full numbers."
    else:
        message = f"Someone is on your site.\nFrom: {_source(body.referrer)}\nDevice: {_device(ua)}\nPage: {body.path}"
    background.add_task(_push, message, "Site visitor", -1)
    return Response(status_code=204)


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
