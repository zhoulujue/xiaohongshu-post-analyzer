# xiaohongshu-post-analyzer

Fetch and analyze Xiaohongshu (小红书 / RED) posts from a share link — **no browser, no login, no API key**.

Given any XHS share link (`xhslink.cn` short link or full note URL), this tool extracts post
metadata (title, description, hashtags, type), downloads the video and/or images, and can
sample video frames for downstream vision analysis.

Built and tested for **AI agents**: one command per link, JSON output, zero interactive steps.
It was originally written inside a Hermes Agent session — the same session that verified it
against a live video post end-to-end.

## How it works (no tricks, no breaking)

Xiaohongshu server-side-renders note pages and embeds `og:` meta tags +
`window.__INITIAL_STATE__` JSON into the public HTML **for social-share previews**
(WeChat/Telegram link unfurling needs it). This tool simply:

1. Resolves the short link (`xhslink.cn` returns an HTML `<a href>Found</a>` pointer, not a 302)
2. Fetches the note page HTML with a browser UA
3. Parses `og:` meta tags + `__INITIAL_STATE__` for metadata and **direct media URLs**
4. Downloads the media; optionally extracts `N` evenly-spaced frames via ffmpeg

Nothing is cracked — it reads what the site publishes to the open web.

## Requirements

- Python 3 (stdlib only)
- `curl` (fallback to urllib)
- `ffmpeg` + `ffprobe` — only needed for `--frames`

## Usage

```bash
# metadata only, machine-readable
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX" --json

# human-readable summary
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX"

# download video + cover, extract 3 frames
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX" --download --frames 3 --outdir ./out
```

### Output

```json
{
  "note_id": "6a9d589c000000001001d2d8",
  "title": "#正常穿搭 #浅跳一下",
  "desc": "#正常穿搭 #浅跳一下",
  "type": "video",
  "video_urls": ["https://sns-video-v6.xhscdn.com/stream/.../xxx_258.mp4?sign=...&t=..."],
  "image_urls": ["https://picasso-static.xiaohongshu.com/...png"]
}
```

With `--download`:
```
out/note_6a9d589c000000001001d2d8/
├── video.mp4
├── img_01.jpg
└── frames/
    ├── frame_01.jpg
    ├── frame_02.jpg
    └── frame_03.jpg
```

## Install as a Hermes Agent skill (for other agents)

```bash
# copy into your skills dir (per-profile or global)
cp -r SKILL.md scripts ~/.hermes/skills/social-media/xhs-post-analyzer/
```

Any agent with skills enabled can then load `xhs-post-analyzer` and analyze XHS links directly.
The `SKILL.md` documents the workflow + pitfalls (sign-expiry, xsec_token requirement, rate limits).

## Known limitations

- `xsec_token` (carried by app share links) is required for SSR content; bare note URLs may
  return a verification shell.
- Anonymous access: no `author` / `interact` counts in SSR (login or internal API needed),
  and only the mid-bitrate `_258` video tier.
- Video URLs carry `sign` + `t` and expire quickly — download immediately.
- Keep request frequency low; bulk scraping trips slider verification.

## License

MIT
