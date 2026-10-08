#!/usr/bin/env python3
"""Publish the next approved Shoofly post to Instagram.

State lives on Instagram itself: a queue item counts as published when a
recent post's caption starts with the item's first caption line. Nothing is
written back to this repo, so the nightly run needs no push access.

Token: normally a cloud-environment Network secret for host graph.instagram.com
(Authorization: Bearer <token>), which the agent proxy attaches to each request,
so the script never sees it. An env INSTAGRAM_ACCESS_TOKEN is used instead if set.
Never commit a token here; this repo is public.

Usage: python3 publish.py [--dry-run]
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

REPO_RAW = "https://raw.githubusercontent.com/hero998f-lab/shoofly-media/main/"
API = "https://graph.instagram.com/v21.0"
MIN_GAP_HOURS = 12  # never post twice in one night, even if the routine fires twice

def http(method, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def api(method, path, token, **params):
    if token:
        params["access_token"] = token
    if method == "GET":
        st, raw = http("GET", f"{API}{path}?{urllib.parse.urlencode(params)}")
    else:
        st, raw = http("POST", f"{API}{path}", params)
    out = json.loads(raw or b"{}")
    if st != 200 or "error" in out:
        err = out.get("error", {})
        msg = err.get("message", raw[:300])
        hint = " (token missing, invalid or expired)" if st in (400, 401, 403) and (err.get("code") == 190 or err.get("type") == "OAuthException") else ""
        raise SystemExit(f"FAIL {method} {path}: HTTP {st}: {msg}{hint}")
    return out

def first_line(s):
    return (s or "").strip().splitlines()[0].strip() if (s or "").strip() else ""

def main():
    dry = "--dry-run" in sys.argv
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()  # empty -> proxy adds it

    st, raw = http("GET", REPO_RAW + "autopost/queue.json")
    if st != 200:
        raise SystemExit(f"FAIL could not read queue.json: HTTP {st}")
    queue = json.loads(raw)

    media = api("GET", "/me/media", token, fields="id,caption,timestamp,permalink", limit=50).get("data", [])
    posted = {first_line(m.get("caption")) for m in media}
    if media:
        last = datetime.strptime(media[0]["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        gap = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        if gap < MIN_GAP_HOURS:
            print(f"SKIP last post was {gap:.1f}h ago ({media[0].get('permalink')}); nothing posted")
            return

    todo = [q for q in queue if first_line(q["caption"]) not in posted]
    if not todo:
        print("DONE queue is empty: every approved post is already on Instagram; nothing posted")
        return
    item = todo[0]
    url = REPO_RAW + item["image"]
    st, img = http("GET", url)
    if st != 200 or not img.startswith(b"\xff\xd8"):
        raise SystemExit(f"FAIL image not reachable as JPEG: {url} (HTTP {st})")

    if dry:
        print(f"DRY-RUN would publish {item['id']} ({url}); {len(todo)-1} left after it")
        return

    cid = api("POST", "/me/media", token, image_url=url, caption=item["caption"])["id"]
    for _ in range(20):
        s = api("GET", f"/{cid}", token, fields="status_code").get("status_code")
        if s == "FINISHED":
            break
        if s in ("ERROR", "EXPIRED"):
            raise SystemExit(f"FAIL container {cid} status {s}")
        time.sleep(3)
    mid = api("POST", "/me/media_publish", token, creation_id=cid)["id"]
    link = api("GET", f"/{mid}", token, fields="permalink").get("permalink")
    print(f"OK published {item['id']} -> {link}; {len(todo)-1} left in queue")

if __name__ == "__main__":
    main()
