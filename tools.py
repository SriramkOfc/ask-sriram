"""Tools available to Ask Sriram (OpenAI function-calling format)."""

import os
import re
import time

import requests

GITHUB_USER = "SriramkOfc"
# Not interesting as "projects": the profile README repo and the website repo (the website is in the knowledge file).
HIDDEN_REPOS = {"sriramkofc", "sriramkofc.github.io"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[a-zA-Z]{2,24}$")

_github_cache: dict = {"at": 0.0, "data": None}


def _push(message: str, title: str = "Ask Sriram", priority: int = 0) -> None:
    """Notify Sriram's phone. Uses ntfy (free) when NTFY_TOPIC is set, otherwise Pushover.
    priority -1 is quiet (no sound or vibration), 0 is normal. Skipped if nothing is configured."""
    if os.getenv("DISABLE_PUSH"):
        return
    topic = os.getenv("NTFY_TOPIC")
    token, user = os.getenv("PUSHOVER_TOKEN"), os.getenv("PUSHOVER_USER")
    try:
        if topic:
            r = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message[:1000].encode(),
                headers={"Title": title, "Priority": "2" if priority < 0 else "3"},
                timeout=8,
            )
        elif token and user:
            r = requests.post(
                "https://api.pushover.net/1/messages.json",
                data={"token": token, "user": user, "message": message[:1000], "title": title, "priority": priority},
                timeout=8,
            )
        else:
            return
        if not r.ok:
            print(f"notify failed: HTTP {r.status_code}", flush=True)
    except requests.RequestException as e:
        print(f"notify failed: {type(e).__name__}", flush=True)


def get_github_projects() -> dict:
    """Live list of Sriram's public, non-fork GitHub repositories (cached for an hour)."""
    now = time.time()
    if _github_cache["data"] and now - _github_cache["at"] < 3600:
        return _github_cache["data"]
    try:
        r = requests.get(
            f"https://api.github.com/users/{GITHUB_USER}/repos",
            params={"sort": "updated", "per_page": 50},
            headers={"Accept": "application/vnd.github+json"},
            timeout=8,
        )
        r.raise_for_status()
        repos = [
            {
                "name": x["name"],
                "description": (x.get("description") or "")[:200],
                "language": x.get("language"),
                "updated": (x.get("pushed_at") or "")[:10],
                "url": x["html_url"],
            }
            for x in r.json()
            if not x.get("fork") and not x.get("private") and x["name"].lower() not in HIDDEN_REPOS
        ][:12]
        data = {"profile": f"https://github.com/{GITHUB_USER}", "repositories": repos}
    except requests.RequestException:
        data = {"profile": f"https://github.com/{GITHUB_USER}", "repositories": [], "note": "GitHub is unavailable right now."}
    _github_cache.update(at=now, data=data)
    return data


def get_contact_options() -> dict:
    return {
        "email": "sriramkofc@gmail.com",
        "linkedin": "https://www.linkedin.com/in/sriramkarthikeyan",
        "github": f"https://github.com/{GITHUB_USER}",
        "website": "https://sriramkofc.github.io",
        "location": "Sydney, Australia",
        "note": "Email is the fastest way to reach him.",
    }


def record_user_details(email: str, name: str = "", notes: str = "") -> dict:
    email = (email or "").strip()
    if not EMAIL_RE.match(email):
        return {"recorded": False, "reason": "That does not look like a valid email address."}
    _push(f"New contact via Ask Sriram\nEmail: {email}\nName: {name[:100] or 'not given'}\nNotes: {notes[:400] or 'none'}")
    return {"recorded": True}


def record_unknown_question(question: str) -> dict:
    _push(f"Unanswered question on Ask Sriram:\n{(question or '')[:500]}")
    return {"recorded": True}


REGISTRY = {
    "get_github_projects": get_github_projects,
    "get_contact_options": get_contact_options,
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_github_projects",
            "description": "Get Sriram's public GitHub repositories (name, description, language, last update, link). Use for questions about his code or projects.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contact_options",
            "description": "Get Sriram's public contact details (email, LinkedIn, GitHub, website).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_user_details",
            "description": "Pass a visitor's contact details to Sriram. Only use with an email address the visitor typed themselves.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "The visitor's email address, exactly as they typed it."},
                    "name": {"type": "string", "description": "The visitor's name, if given."},
                    "notes": {"type": "string", "description": "One line on what they want to talk to Sriram about."},
                },
                "required": ["email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_unknown_question",
            "description": "Record a reasonable question about Sriram that you could not answer, so he can follow up.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "The question you could not answer."}},
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    },
]
