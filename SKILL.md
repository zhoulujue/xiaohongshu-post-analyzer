---
name: xhs-post-analyzer
description: Xiaohongshu share link? Fetch post info & media, no login.
version: 1.0.0
author: zhoulujue
license: MIT
metadata:
  hermes:
    tags: [social-media, xiaohongshu, content-analysis, scraping, video]
    related_skills: [lark-im, github-workflow]
---

# Xiaohongshu (小红书) Post Analyzer — no browser, no login

Fetch and analyze Xiaohongshu (RED) posts from a share link, entirely over plain HTTP.
Works with `xhslink.cn` short links **and** full note URLs — both
`xiaohongshu.com/discovery/item/...` and `xiaohongshu.com/explore/...` forms
(share links carry the required `xsec_token`).

**Why it works**: XHS embeds SSR content in the note page HTML for social-share previews
(`og:` meta tags + `window.__INITIAL_STATE__`). We read what XHS publishes to the open web —
no API signing, no browser, no account.

## When to use

- User drops a Xiaohongshu share link and asks "what's this post?" / "analyze this"
- You need post title/description/hashtags/media from a XHS link
- You want the video downloaded + frames extracted for vision analysis
- Batch content analysis of XHS posts (run the script per link)

## Script

`scripts/xhs_fetch.py` — self-contained (python3 stdlib + curl; ffmpeg only for `--frames`).

```bash
# 1) Metadata only (JSON for machine consumption)
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX" --json

# 2) Download video + cover image, then extract 3 evenly-spaced frames
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX" --download --frames 3 --outdir ./out
# -> out/note_<id>/video.mp4, img_01.jpg, frames/frame_01..03.jpg
```

Output JSON fields: `note_id, url, title, desc, type (video|image|normal), author,
interact (liked/collected/comment/shared counts), tags, video_urls[], image_urls[],
video_file, frames[], media_dir`.

## Standard workflow

1. Run the script with `--json` to get metadata + media URLs.
2. If video: run with `--download --frames 3` to fetch the MP4 and sample frames.
3. Feed frames to a vision tool (`vision_analyze` on `frame_*.jpg`) to describe content
   (people, outfits, food, scenes, text OCR).
4. Report: title/desc/tags + what the media actually shows + any interact counts.

## Pitfalls (learned the hard way)

- **`xhslink.cn` returns HTTP 200 with an HTML `<a href>Found</a>` pointer — not a 302.**
  Fetch WITHOUT `curl -L` and regex the href out; also note HEAD requests 404 there.
- **`xsec_token` is mandatory for SSR content** since 2024. Links that carry it (app share links)
  work; bare note URLs without token may return a verification shell / empty state.
- **Video URLs carry `sign` + `t` and expire fast** — download immediately after fetching.
- Anonymous SSR usually does NOT include `author` / `interact` / full `tagList` — those need
  login or the internal API. Do not fabricate them; report what the page actually gives.
- Anonymous access yields the mid-bitrate (`_258`) video, not the original/4K source.
- **Rate limit**: this is fine for single links; bulk crawling will trip slider verification —
  keep it low-frequency, don't hammer.
- `window.__INITIAL_STATE__` JSON is often truncated mid-string in SSR. The script retries
  progressively shorter slices; if `title` still comes back empty, fall back to `og:title`.
