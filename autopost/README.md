# Shoofly nightly Instagram queue

Approved posts only. A routine runs `publish.py` every night at 9 PM (Asia/Muscat)
and posts the first item in `queue.json` that isn't on Instagram yet.

- Add a post: put a 1080x1350 JPEG in `images/` and append an item to `queue.json`.
- The token is a cloud-environment Network secret on host `graph.instagram.com` (Authorization: Bearer), added by the proxy; never stored here (public repo).
- Instagram's API can't delete posts; remove one from the app.
