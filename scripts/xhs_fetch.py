#!/usr/bin/env python3
"""
xhs_fetch.py — Xiaohongshu (RED / 小红书) post analyzer, no browser required.

Fetches a XHS share link (xhslink.cn short link or full xiaohongshu.com note URL),
extracts post metadata (title, description, hashtags, author, interact counts),
and optionally downloads media (video / images) and extracts video frames.

Works entirely over plain HTTP (curl / urllib + ffmpeg) — no login, no browser,
no API signing. It leverages the SSR content XHS itself embeds in the page HTML
(og: meta tags + window.__INITIAL_STATE__) for social-share previews.

Usage:
  python3 xhs_fetch.py <share_url> [--json] [--download] [--outdir DIR]
                       [--frames N] [--ffmpeg PATH]

Examples:
  python3 xhs_fetch.py "https://xhslink.cn/o/xxxx" --json
  python3 xhs_fetch.py "https://xhslink.cn/o/xxxx" --download --outdir ./out
  python3 xhs_fetch.py "https://www.xiaohongshu.com/explore/<note_id>?xsec_token=..." \
      --download --frames 4

Requirements:
  - python3 (stdlib only)
  - curl (fallback: urllib)  — used for HTTP with browser UA
  - ffmpeg                    — only needed for --frames
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SHORTLINK_RE = re.compile(r'xhslink\.cn')
NOTE_ID_RE = re.compile(r'/discovery/item/([0-9a-f]+)')
TOKEN_RE = re.compile(r'[?&]xsec_token=([^&]+)')

# ---------------------------------------------------------------- http helpers

def http_get(url: str, timeout: int = 30, follow: bool = True) -> bytes:
    """GET with a browser UA. Prefers curl (handles redirects/TLS robustly),
    falls back to urllib."""
    try:
        cmd = ["curl", "-s", "-A", UA, "--max-time", str(timeout), url]
        if follow:
            cmd += ["-L", "--max-redirs", "6"]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def resolve_shortlink(url: str, timeout: int = 30) -> str:
    """xhslink.cn short links return HTTP 200 with an HTML body containing a
    <a href='...'>Found</a> pointer to the canonical note URL (not a 302).
    Fetch without following redirects and extract the href."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-A", UA, "--max-time", str(timeout), url],
            capture_output=True, timeout=timeout + 10)
        body = r.stdout.decode("utf-8", errors="ignore")
    except Exception:
        body = http_get_text(url)
    m = re.search(r'href="([^"]+)"', body)
    if m:
        return m.group(1).replace("&amp;", "&")
    return url


def http_get_text(url: str, timeout: int = 30) -> str:
    raw = http_get(url, timeout=timeout)
    return raw.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------- parsing

def parse_note_id_and_token(url: str) -> tuple:
    """Resolve short links to the canonical note URL, extract note_id + token."""
    if SHORTLINK_RE.search(url):
        url = resolve_shortlink(url)
    nid_m = NOTE_ID_RE.search(url)
    tok_m = TOKEN_RE.search(url)
    return (nid_m.group(1) if nid_m else None,
            tok_m.group(1) if tok_m else None,
            url)


def extract_og(html: str) -> dict:
    out = {}
    for prop, key in [("og:title", "title"), ("og:description", "desc"),
                      ("og:video", "video_url"), ("og:image", "image_url")]:
        m = re.search(rf'<meta[^>]+(?:property|name)="{re.escape(prop)}"[^>]+content="([^"]*)"', html)
        if not m:
            m = re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{re.escape(prop)}"', html)
        if m:
            out[key] = m.group(1)
    return out


def deep_find(obj, keys, max_depth=6, _depth=0):
    """Recursively find values for any of keys in a nested dict/list."""
    found = []
    if _depth > max_depth:
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str):
                found.append(v)
            found += deep_find(v, keys, max_depth, _depth + 1)
    elif isinstance(obj, list):
        for it in obj:
            found += deep_find(it, keys, max_depth, _depth + 1)
    return found


def clean_image_url(u: str) -> str:
    return u.replace("http://", "https://") if u and u.startswith("http://") else u


def parse_state(html: str, note_id: str) -> dict:
    """Parse window.__INITIAL_STATE__ for the richest metadata."""
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>', html, re.S)
    if not m:
        return {}
    try:
        state = json.loads(m.group(1))
    except Exception:
        # truncated JSON: salvage with a lazy brace-buffer retry
        text = m.group(1)
        for cut in (len(text), len(text) - 500, len(text) - 2000):
            try:
                state = json.loads(text[:cut])
                break
            except Exception:
                continue
        else:
            return {}
    note = {}
    try:
        ndm = state.get("note", {}).get("noteDetailMap", {})
        for k, v in ndm.items():
            if not note_id or k == note_id or k.endswith(note_id):
                note = v.get("note", {})
                break
        if not note and ndm:
            note = next(iter(ndm.values())).get("note", {})
    except Exception:
        return {}
    out = {}
    if note.get("title"):
        out["title"] = note["title"]
    if note.get("desc"):
        out["desc"] = note["desc"]
    if note.get("type"):
        out["type"] = note["type"]
    user = note.get("user") or {}
    if user.get("nickname"):
        out["author"] = user["nickname"]
    if note.get("interactInfo"):
        ii = note["interactInfo"]
        out["interact"] = {k: ii.get(k) for k in
                           ("likedCount", "collectedCount", "commentCount", "sharedCount")}
    # media
    if note.get("type") == "video":
        vids = deep_find(note.get("video", {}),
                         ("masterUrl", "originUrlKey", "backupUrls", "url"))
        out["video_urls"] = [u for u in vids if u.startswith("http")][:5]
    images = []
    for img in note.get("imageList", []) or []:
        u = img.get("urlDefault") or img.get("urlPre") or img.get("url")
        if u:
            images.append(clean_image_url(u))
    if images:
        out["image_urls"] = images
    if note.get("tagList"):
        out["tags"] = [t.get("name") for t in note["tagList"] if t.get("name")]
    return out


# ---------------------------------------------------------------- media ops

def download(url: str, dest_dir: str, filename: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, filename)
    data = http_get(url)
    with open(path, "wb") as f:
        f.write(data)
    return path if os.path.getsize(path) > 0 else ""


def extract_frames(video_path: str, dest_dir: str, n: int = 4) -> list:
    """Sample ~n frames evenly from the video. Requires ffmpeg."""
    ff = os.environ.get("FFMPEG", "ffmpeg")
    try:
        probe = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                                "-show_format", video_path],
                               capture_output=True, text=True, timeout=30)
        dur = float(json.loads(probe.stdout)["format"]["duration"])
    except Exception:
        dur = 0
    interval = max(1.0, dur / n) if dur else 1.0
    paths = []
    for i in range(n):
        out = os.path.join(dest_dir, f"frame_{i + 1:02d}.jpg")
        r = subprocess.run([ff, "-y", "-v", "quiet", "-ss", str(i * interval),
                            "-i", video_path, "-frames:v", "1", "-q:v", "3", out],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and os.path.exists(out):
            paths.append(out)
    return paths


# ---------------------------------------------------------------- main

def analyze(url: str, download_media: bool = False, outdir: str = ".",
            frames: int = 0) -> dict:
    note_id, token, canon = parse_note_id_and_token(url)
    if not note_id:
        return {"error": "could not resolve note id from URL", "url": url}
    html_url = canon if token else (f"https://www.xiaohongshu.com/discovery/item/{note_id}"
                                    if not note_id else canon)
    # If no token on the resolved URL we still try SSR — works for some notes.
    html = http_get_text(html_url)
    og = extract_og(html)
    st = parse_state(html, note_id)

    result = {
        "note_id": note_id,
        "url": canon,
        "title": st.get("title") or og.get("title", "").replace(" - 小红书", ""),
        "desc": st.get("desc") or og.get("desc", ""),
        "type": st.get("type") or ("video" if og.get("video_url") else "image"),
        "author": st.get("author"),
        "interact": st.get("interact"),
        "tags": st.get("tags", []),
    }
    # media union: state first, og: meta as fallback
    vids = st.get("video_urls") or []
    if og.get("video_url") and og["video_url"] not in vids:
        vids.append(og["video_url"])
    imgs = st.get("image_urls") or []
    if og.get("image_url") and og["image_url"].startswith("//"):
        og_img = "https:" + og["image_url"]
        if og_img not in imgs:
            imgs.append(og_img)
    result["video_urls"] = vids
    result["image_urls"] = imgs

    if download_media:
        media_dir = os.path.join(outdir, f"note_{note_id}")
        os.makedirs(media_dir, exist_ok=True)
        dl = []
        if result["type"] == "video" and vids:
            p = download(vids[0], media_dir, "video.mp4")
            if p:
                dl.append(p)
                result["video_file"] = p
                if frames > 0:
                    frame_dir = os.path.join(media_dir, "frames")
                    os.makedirs(frame_dir, exist_ok=True)
                    result["frames"] = extract_frames(p, frame_dir, frames)
        for i, u in enumerate(imgs[:30]):
            p = download(u, media_dir, f"img_{i + 1:02d}.jpg")
            if p:
                dl.append(p)
        result["media_dir"] = media_dir
        result["downloaded"] = dl
    return result


def main():
    ap = argparse.ArgumentParser(description="Xiaohongshu post analyzer (no browser)")
    ap.add_argument("url", help="xhslink.cn short link or full note URL")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--download", action="store_true", help="download media files")
    ap.add_argument("--outdir", default=".", help="media output dir (default: cwd)")
    ap.add_argument("--frames", type=int, default=0,
                    help="extract N frames from video (needs ffmpeg)")
    args = ap.parse_args()

    res = analyze(args.url, download_media=args.download,
                  outdir=args.outdir, frames=args.frames)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"标题: {res.get('title')}")
        print(f"类型: {res.get('type')} | 作者: {res.get('author')}")
        if res.get("desc"):
            print(f"描述: {res['desc'][:300]}")
        if res.get("tags"):
            print(f"标签: {', '.join(res['tags'])}")
        if res.get("interact"):
            i = res["interact"]
            print(f"互动: 👍{i.get('likedCount')} ⭐{i.get('collectedCount')} 💬{i.get('commentCount')}")
        if res.get("video_urls"):
            print(f"视频源: {res['video_urls'][0][:120]}...")
        if res.get("image_urls"):
            print(f"图片: {len(res['image_urls'])} 张")
        if res.get("video_file"):
            print(f"已下载: {res['video_file']}")
        if res.get("frames"):
            print(f"抽帧: {len(res['frames'])} 张 -> {os.path.dirname(res['frames'][0])}")
        if res.get("error"):
            print(f"错误: {res['error']}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
