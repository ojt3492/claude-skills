# claude-skills

Personal [Claude Code](https://claude.com/claude-code) skills.

| Skill | Command | What it does |
|---|---|---|
| `make` | `/make videos` | Typography motion video builder: pick scenes and effects with buttons, preview, then type `렌더` to render an MP4 (no audio, 120BPM, 3-colour palette). |
| `blog` | `/blog <topic>` | Writes fact-based, easy-to-read Korean blog posts with sources. |

## Install

```bash
git clone https://github.com/ojt3492/claude-skills.git
cp -r claude-skills/make ~/.claude/skills/
```

On Windows, copy the folder into `C:\Users\<you>\.claude\skills\`. Restart Claude Code, then run `/make videos`.

## `make` requirements

- Python 3.10+
- `pip install pillow imageio-ffmpeg` (bundles ffmpeg; no system ffmpeg needed)
- Default font is Impact (Windows). On other systems set `font` in the spec to a bold `.ttf`. Korean text needs a Hangul font such as Malgun Gothic Bold.

Scenes: marquee, bounce, tunnel, halftone, glitch, emblem, logo. Effects: shake, pulse. Type `help` inside the flow for a guide.

## License

MIT
