import json, os, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

REPO_RAW = "https://raw.githubusercontent.com/hero998f-lab/shoofly-media/main/"
API = "https://graph.instagram.com/v21.0"
QUEUE = [
{
"id": "1-new-or-used",
"image": "autopost/images/1-new-or-used.jpg",
"caption": "مستعمل أو جديد؟ إنت اللي تختار 👌\n\nحدّد في طلبك نوع القطعة اللي تبيها، ويوصل طلبك للمحلات والمناديب المختصين، والردود تجيك مباشرة على الواتساب.\n\nارسل قطعة سيارتك عبر الموقع والردود تجيك ع الواتساب 👈 shoofly.om\n\n#عمان #قطع_غيار #مسقط"
},
{
"id": "2-photo-it",
"image": "autopost/images/2-photo-it-v2.jpg",
"caption": "ما تعرف اسم القطعة؟ لا تشيل هم 📸\n\nصوّر القطعة والمحلات المختصة تعرفها عنك وترد عليك.\n\nارسل قطعة سيارتك عبر الموقع والردود تجيك ع الواتساب 👈 shoofly.om\n\n#عمان #قطع_غيار #مسقط",
"story": "autopost/images/2-photo-it-story.jpg"
},
{
"id": "3-shops-warehouse",
"image": "autopost/images/3-shops-warehouse-v2.jpg",
"caption": "عندك قطع في المستودع؟ في زبون يدورها الحين 🔧\n\nسجّل محلك في شوفلي وحدّد الماركات والأقسام اللي تشتغل فيها، وطلبات القطع المناسبة توصلك على الواتساب.\n\nسجّل محلك الحين 👈 shoofly.om\n\n#عمان #قطع_غيار #محلات_قطع_غيار",
"story": "autopost/images/3-shops-warehouse-story.jpg"
},
{
"id": "4-stop-roaming",
"image": "autopost/images/4-stop-roaming-v2.jpg",
"caption": "بدل ما تلف على المحلات، خلّ المحلات تجيك 🚗\n\nاكتب القطعة مرة وحدة، ويوصل طلبك للمحلات المختصة، وهم يراسلونك على الواتساب.\n\nارسل قطعة سيارتك عبر الموقع والردود تجيك ع الواتساب 👈 shoofly.om\n\n#عمان #قطع_غيار #مسقط",
"story": "autopost/images/4-stop-roaming-story.jpg"
},
{
"id": "5-at-night",
"image": "autopost/images/5-at-night-v2.jpg",
"caption": "سيارتك خربت بالليل؟ 🌙\n\nلا تنتظر الصبح. انشر طلبك الحين وإنت في بيتك، ويوصل للمحلات المختصة على طول.\n\nارسل قطعة سيارتك عبر الموقع والردود تجيك ع الواتساب 👈 shoofly.om\n\n#عمان #قطع_غيار #مسقط",
"story": "autopost/images/5-at-night-story.jpg"
}
]

def http(method, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def api(method, path, **params):
    if method == "GET":
        st, raw = http("GET", f"{API}{path}?{urllib.parse.urlencode(params)}")
    else:
        st, raw = http("POST", f"{API}{path}", params)
    out = json.loads(raw or b"{}")
    if st != 200 or "error" in out:
        err = out.get("error", {})
        hint = " (token missing, invalid or expired)" if err.get("code") == 190 or err.get("type") == "OAuthException" else ""
        raise SystemExit(f"FAIL {method} {path}: HTTP {st}: {err.get('message', raw[:300])}{hint}")
    return out

def first_line(s):
    s = (s or "").strip()
    return s.splitlines()[0].strip() if s else ""

def hours_since(ts):
    return (datetime.now(timezone.utc) - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")).total_seconds() / 3600

def check_jpeg(path):
    url = REPO_RAW + path
    st, img = http("GET", url)
    if st != 200 or not img.startswith(b"\xff\xd8"):
        raise SystemExit(f"FAIL image not reachable as JPEG: {url} (HTTP {st})")
    return url

def publish(dry, **params):
    if dry:
        return "(dry run)"
    cid = api("POST", "/me/media", **params)["id"]
    for _ in range(20):
        s = api("GET", f"/{cid}", fields="status_code").get("status_code")
        if s == "FINISHED":
            break
        if s in ("ERROR", "EXPIRED"):
            raise SystemExit(f"FAIL container {cid} status {s}")
        time.sleep(3)
    mid = api("POST", "/me/media_publish", creation_id=cid)["id"]
    return api("GET", f"/{mid}", fields="permalink").get("permalink") or mid

def post(dry):
    media = api("GET", "/me/media", fields="id,caption,timestamp,permalink", limit=50).get("data", [])
    if media and hours_since(media[0]["timestamp"]) < 12:  # never post twice in one night
        print(f"SKIP last post was {hours_since(media[0]['timestamp']):.1f}h ago ({media[0].get('permalink')}); nothing posted")
        return
    posted = {first_line(m.get("caption")) for m in media}
    todo = [q for q in QUEUE if first_line(q["caption"]) not in posted]
    if not todo:
        print("DONE queue is empty: every approved post is already on Instagram; nothing posted")
        return
    item = todo[0]
    link = publish(dry, image_url=check_jpeg(item["image"]), caption=item["caption"])
    print(f"OK published {item['id']} -> {link}; {len(todo)-1} left in queue")

def story(dry):
    stories = api("GET", "/me/stories", fields="id,timestamp").get("data", [])
    recent = [s for s in stories if hours_since(s["timestamp"]) < 12]
    if recent:
        print(f"SKIP a story was already posted {hours_since(recent[0]['timestamp']):.1f}h ago; nothing posted")
        return
    media = api("GET", "/me/media", fields="id,caption,timestamp,permalink", limit=5).get("data", [])
    if not media or hours_since(media[0]["timestamp"]) > 20:
        print("SKIP no new post last night; nothing posted")
        return
    line = first_line(media[0].get("caption"))
    item = next((q for q in QUEUE if first_line(q["caption"]) == line and q.get("story")), None)
    if not item:
        print(f"SKIP last night's post has no approved story ({media[0].get('permalink')}); nothing posted")
        return
    publish(dry, image_url=check_jpeg(item["story"]), media_type="STORIES")
    print(f"OK story for {item['id']} is up (last night's post: {media[0].get('permalink')})")

if __name__ == "__main__":
    {"post": post, "story": story}[sys.argv[1]]("--dry-run" in sys.argv)
