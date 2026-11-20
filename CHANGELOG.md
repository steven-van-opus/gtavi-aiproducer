# Changelog

## 1.1.0 (2026-11-20)

- YouTube VODs are routed by how YouTube serves them. `vodcut.py` asks yt-dlp for the delivery protocol before every
  download (scan, verify, cut) and stores it in `vodcut.json`: post-live VODs still served as 2-second fragments go
  through `ytfrag.py`, processed VODs through yt-dlp (`139/ba/w` for the scan audio, `299+140` / `134+139` windows
  with `--download-sections`). A day after a stream YouTube ignores `&sq=N` and answers every "fragment" with the
  whole file, which sent the old fragment path into terabytes of transfer.
- `ytfrag.py` checks the protocol first and stops on a processed VOD; a reply over 16 MB (no 2-second fragment is)
  stops the download after one round. `track` writes a `.part` file, checks ffmpeg's exit code and keeps the
  fragments until the track is complete; `window` also publishes its output only when it is complete.
- `vodcut.py cut`: the downloaded window is named by its span (`mNN_src_IN-OUT.mp4`), so a re-cut with a new
  `--in-out` never composes an old window or records times the clip does not have; reversed spans are refused;
  `--top-ratio`, `--focus-x` and `--divider` are passed to `frame.py compose` (the countdown's shared seam works).
- `vodcut.py report`: `WINDOWS_RANKED`, `MOMENTS_RANKED` and `MOMENTS_ADDED_BY_FIND` replace `MOMENTS_FOUND`, and
  `WALL_TIME` comes only from a folder's first scan that fetched the audio itself and ran start to finish (each
  scan run is recorded in `vodcut.json`); a resumed or seeded folder says why it has none.
- Twitch and Kick scan audio falls back to the smallest rendition (`ba/w`), never full-quality video.
- `aip_prep.py check`: a landscape file is an error (AI Producer keeps it 16:9) unless `--allow-landscape`.
- `scan_frags.py` drops a chunk whose transcription finishes after the track was assembled, and skips chunks
  already marked done, so no 20-minute span is transcribed twice.
- `aip-project`: calls `finish_project` when no caption or edit pass follows, so the project link opens an
  unlocked editor; `get_view_url` is no longer listed.
- README: the AI Producer install shows only the CLI lines OpusClip documents; one line on installing this plugin
  or the standalone /vodcut, not both (both ship a `vodcut` skill).
- Tests: offline routing, re-cut, layout-flag, report, ytfrag-guard, track-assembly and scan_frags tests with fake
  `yt-dlp` / `whisper-cli` on PATH and a local HTTP server.

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
