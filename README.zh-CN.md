# xiaohongshu-post-analyzer

从分享链接抓取并分析小红书（Xiaohongshu / RED）帖子——**无需浏览器、无需登录、无需 API Key**。

输入任意小红书分享链接（`xhslink.cn` 短链或完整笔记 URL），即可提取帖子元数据（标题、正文、话题标签、类型），下载视频和/或图片，并可抽帧供下游视觉分析使用。

为 **AI Agent 而生**：一条命令分析一个链接、JSON 结构化输出、全程零交互。本项目诞生于一次真实的 Hermes Agent 会话——同一个会话对一条视频帖子做了端到端实测验证。

- 🌐 [English README](./README.md)

## 原理（不破解、不越界）

小红书为了让微信/Telegram 等平台**链接预览**能展示内容，在笔记页 HTML 里服务端渲染（SSR）了 `og:` meta 标签和 `window.__INITIAL_STATE__` 数据。本工具只是：

1. 解析短链（`xhslink.cn` 返回的是带 `<a href>Found</a>` 指向的 HTML 页面，**不是 302 跳转**）
2. 用浏览器 UA 抓取笔记页 HTML
3. 解析 `og:` meta + `__INITIAL_STATE__`，提取元数据和**媒体直链**
4. 下载媒体；可选通过 ffmpeg 均匀抽帧

读取的是小红书向开放互联网公开的内容，没有任何破解行为。

## 环境依赖

- Python 3（仅标准库）
- `curl`（失败时回退 urllib）
- `ffmpeg` + `ffprobe`（仅 `--frames` 抽帧需要）

## 使用方法

```bash
# 仅元数据（机器可读）
python3 xhs_fetch.py "https://www.xiaohongshu.com/explore/6a7d9716000000002202ffaa?xsec_token=AB7ui8PQVSBncXnP2PiMo7Smjr_yytwX74PTu-0Hy-lsM=" --json

# 人类可读摘要
python3 xhs_fetch.py "https://www.xiaohongshu.com/explore/6a7d9716000000002202ffaa?xsec_token=AB7ui8PQVSBncXnP2PiMo7Smjr_yytwX74PTu-0Hy-lsM="

# 下载视频 + 封面，并抽 3 帧
python3 xhs_fetch.py "https://www.xiaohongshu.com/explore/6a7d9716000000002202ffaa?xsec_token=AB7ui8PQVSBncXnP2PiMo7Smjr_yytwX74PTu-0Hy-lsM=" --download --frames 3 --outdir ./out
```

`xhslink.cn` 短链同样支持：

```bash
python3 xhs_fetch.py "https://xhslink.cn/o/XXXX" --json
```

### 输出示例

```json
{
  "note_id": "6a7d9716000000002202ffaa",
  "title": "宝宝，你像一匹小木马🎠",
  "desc": "#聪明伶俐的小脑袋瓜 #可爱到模糊 #哈基米哈基米哈基米 #一辆小猫咪 #他好像知道自己很可爱 #这是我的哈基米哈基米",
  "type": "video",
  "video_urls": ["https://sns-video-v6.xhscdn.com/stream/79/110/258/..._258.mp4?sign=...&t=..."],
  "image_urls": ["https://picasso-static.xiaohongshu.com/...png"]
}
```

使用 `--download` 后：
```
out/note_6a7d9716000000002202ffaa/
├── video.mp4
├── img_01.jpg
└── frames/
    ├── frame_01.jpg
    ├── frame_02.jpg
    └── frame_03.jpg
```

## 安装为 Hermes Agent 技能（供其他 Agent 使用）

```bash
# 拷贝到技能目录（按 profile 或全局）
cp -r SKILL.md scripts ~/.hermes/skills/social-media/xhs-post-analyzer/
```

任何启用了技能机制的 Agent 即可加载 `xhs-post-analyzer`，直接分析小红书链接。
`SKILL.md` 中记录了完整工作流与踩坑点（签名过期、xsec_token 要求、频率限制等）。

## 已知限制

- **`xsec_token` 是 SSR 内容的必需参数**（2024 年后引入）：App 分享链接自带 token，可正常抓取；裸笔记 URL 无 token 可能返回验证壳页/空状态
- **匿名访问拿不到 `author` / `interact`（点赞收藏数）**：SSR 不渲染这些字段，需要登录态或内部 API——不要编造，如实报告页面给到的内容即可
- 匿名只能拿到中等码率（`_258`）视频，非原画/4K
- 视频 URL 带 `sign` + `t`，**过期很快**——解析后请立即下载
- 保持低频请求；批量爬取会触发滑块验证

## License

MIT
