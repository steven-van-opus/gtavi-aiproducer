# Changelog

## 1.0.0 (2026-11-19)

First release, for GTA VI's launch day.

- 16 skills: `streams`, `vodcut`, `pick-moments`, `cut-and-frame`, `aip-project`, `aip-captions`, `aip-export`,
  `countdown`, `reaction-edit`, `hooks`, `post-copy`, `clip-rules`, `campaigns`, `scoreboard`, `launch-day`, `media-page`.
- AI Producer as the harness through the official plugin (`aip@ai-producer-plugins`, declared as a dependency):
  signed uploads, transcription, caption moments committed to the workspace, finish, export.
- Scripts: `vodcut.py` (scan / find / verify / cut / prep / report), `ytfrag.py`, `scan_vod.py`, `scan_frags.py`,
  `rank_windows.py` (whisper-loop cleaning, review flags, distinct moments), `framesheet.py`, `frame.py` (9:16
  composer: stack, inset, full), `bleep.py`, `aip_prep.py`, `captions.py` (pop, karaoke, single, plain),
  `aip_mount.py`, `countdown.py`, `campaign_math.py`, `scoreboard.py`, `find_streams.py`, `render.mjs`.
- Tests: unittest suite; caption and countdown output checked against AI Producer's own `caption_cues.py` and
  `preflight.py` when the official plugin is installed.
- Built against the official AI Producer plugin 1.2.13 skills and tool schemas; check its newer releases
  (1.2.16 changed publication) before relying on version-specific behaviour.
