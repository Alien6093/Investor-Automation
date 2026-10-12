"""Post a run summary card to a Lark (or Feishu) group through a Custom Bot webhook.

Env (GitHub repository secrets): LARK_WEBHOOK_URL, and LARK_WEBHOOK_SECRET when the bot has
signature verification turned on. Without LARK_WEBHOOK_URL nothing is sent.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time

import requests

SHOWN = 10


def md(text):
    """Text safe for lark_md (no accidental bold / links), on one line."""
    return re.sub(r"\s+", " ", re.sub(r"([*_~`\[\]<>])", r"\\\1", str(text or ""))).strip()


def short(text, n):
    text = md(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def link(text, url):
    return f"[{md(text)}]({url})" if url else md(text)


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def post_card(title, blocks, warning=False):
    """blocks: list of lark_md strings ("---" draws a line). Returns '' when sent, else why not."""
    url = (os.environ.get("LARK_WEBHOOK_URL") or "").strip()
    if not url:
        return "LARK_WEBHOOK_URL is not set"
    elements = []
    for block in blocks:
        if block == "---":
            elements.append({"tag": "hr"})
        elif block:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": block}})
    body = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "orange" if warning else "green"},
            "elements": elements,
        },
    }
    secret = (os.environ.get("LARK_WEBHOOK_SECRET") or "").strip()
    if secret:
        timestamp = str(int(time.time()))
        mac = hmac.new(f"{timestamp}\n{secret}".encode(), b"", hashlib.sha256).digest()
        body.update(timestamp=timestamp, sign=base64.b64encode(mac).decode())
    try:
        resp = requests.post(url, data=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=20)
        data = resp.json() if resp.content else {}
    except Exception as e:
        return f"could not reach Lark: {e}"
    code = data.get("code", data.get("StatusCode", 0 if resp.ok else resp.status_code))
    return "" if code == 0 else f"Lark answered {code}: {data.get('msg') or data.get('StatusMessage') or resp.reason}"


def notify(title, blocks, warning=False):
    """post_card, printing the outcome (a failed message never fails the job)."""
    error = post_card(title, blocks, warning)
    print("Lark message sent." if not error else f"Lark message not sent: {error}")
    return error
