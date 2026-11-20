---
name: countdown
description: Build the "5 craziest GTA 6 stream moments" countdown - a ~60 s 1080x1920 compilation of streamer moments (IShowSpeed and Kai Cenat mixed by default) with a title, numbered item headers, word-by-word captions and per-item credits - cut locally and edited in AI Producer as the harness. Use when the user wants a compilation, a top-5, a countdown or "the banger format".
argument-hint: "[streamers, window, angle]"
---

# The countdown format

The prompt below is the whole format. Follow it, and run it with the commands in the second half.

```text
<inputs>
Ask me for, in one message:
1. The streamers (default: IShowSpeed and Kai Cenat, mixed) and the window: "the first 24 hours of GTA 6",
   "this week", or the VOD links I already have.
2. The angle for the title, picked from: "5 craziest GTA 6 stream moments", "5 times GTA 6 broke <streamer>",
   "5 GTA 6 moments chat lost it", "5 things streamers found on day one".
3. The page it is for and its campaign brief, if any (credit line, hashtags, length rules), so every item follows it.
If I have no VODs, find the longest finished GTA 6 streams of the last 48 hours and pitch me 3 angles with why
each one is hot today. Never copy another channel's order, titles or edit.
</inputs>

<direction>
A 1080x1920, 30 fps Short / TikTok / Reel of 55-65 s, built only from the streamers' own VOD footage. Each item
is cut on my machine and stacked 9:16: the facecam band on top, gameplay below, the same band height for every
item. No voice-over, no AI-generated footage, no stock clips: the streamers' own reactions carry it.
AI Producer is the harness: the joined countdown is one AI Producer project; its transcript times the captions;
the title, the number headers, the captions and the sound effects are written into its workspace; it exports and
keeps the editable project link.
Text system, heavy condensed caps (Anton) with a thick black outline:
- Title card (0-2.4 s): the title builds word by word just under the facecam band, first word in gold.
- Item header, held for the whole item, just under the facecam band so it never covers a face: a gold "#5"
  slamming in, the item label in white beside it ("COPS AT THE GAS STATION"), the streamer credit small
  underneath ("@KaiCenat · Twitch").
- Captions (centred around 75% of the height, at most 3 words a cue): every spoken word pops on its own timing,
  white, the word being said in gold; another voice (a friend on call, an NPC) in light blue.
Sound: the streamers' own audio; one library impact as each header lands and a whoosh into each item, nothing
generated. Profanity is bleeped before upload when the page or the campaign wants it.
Banned: an intro longer than 2.5 s, a greeting, a channel plug, an item without its credit line, a stretch of more
than 3 s with neither a face nor text, letterbox bars, a 16:9 shot pasted small, the same moment twice, sexual
content, slurs, story spoilers or an ending, a cutscene on its own, footage from before the game was out, and
any line that says or suggests the streamers made, approved or endorse the video.
</direction>

<structure>
Length: 55-65 s: five items of 9-13 s each, counting down from #5 to #1.
0-2.4 s, the hook: the title builds over #5's first beat, which is already moving (never a black frame).
Every item has the same shape: the header lands on the item's first frame -> the setup in one beat (2 s at most)
-> the moment -> the reaction peak -> out on the last word or the laugh, never mid-sentence. Hard cut with a
whoosh into the next item.
Order: #5 a strong opener that still leaves room above it; #4 and #3 alternate streamers; #2 the biggest laugh;
#1 the moment the internet already clipped most, or the rarest discovery.
Mix: at least two items from each streamer when two are in it.
End: #1's reaction plays out. No outro card, no "follow for more".
</structure>
```

Tools this skill calls (Claude Code names): `mcp__plugin_aip_ai-producer__list_workspace`, `mcp__plugin_aip_ai-producer__get_workspace_file`, `mcp__plugin_aip_ai-producer__commit_workspace`, `mcp__plugin_aip_ai-producer__list_sound_effects`, `mcp__plugin_aip_ai-producer__place_sound_effects`, `mcp__plugin_aip_ai-producer__finish_project`.

## Run it

Scripts: `${CLAUDE_SKILL_DIR}/../../scripts/`. Work in `gtavi/countdowns/<slug>/`.

1. **Moments.** `streams` -> `vodcut` for each VOD -> `pick-moments` with 9-13 s cuts. Credit and platform for each.
2. **Items.** `cut-and-frame` every item with the same `--top-ratio 0.35` so the band line (`seam_y` 672) never jumps
   between items. Bleep there if needed.
3. **Join.** Write `plan.json` (rank, clip, in, out, label, streamer, platform, credit per item) and build:
   ```bash
   python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/countdown.py" build gtavi/countdowns/<slug>/plan.json gtavi/countdowns/<slug>
   ```
   `countdown.mp4` (1080x1920, 30 fps, items frame-exact) and `timeline.json` (where each item lands).
4. **Open in AI Producer.** `aip-project` on `countdown.mp4`, prompt: "A 60 s countdown of five GTA 6 stream
   moments, already cut and ordered. Keep the cut exactly as uploaded; add the title, number headers and
   word-by-word captions." Rough cut stays off: the items are already trimmed.
5. **Headers and captions.** Fetch the workspace (`aip-captions` step 1), then:
   ```bash
   python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/countdown.py" cards gtavi/countdowns/<slug>/timeline.json \
     gtavi/aip/<slug>/render-engine --seam-y 672 --hosts-out gtavi/aip/<slug>/header-hosts.html
   python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/aip_mount.py" gtavi/aip/<slug>/render-engine --hosts gtavi/aip/<slug>/header-hosts.html
   ```
   Then the captions as in `aip-captions` step 3, with `--y 0.75` (not the seam: the headers live there) and
   mounted after the headers so they draw on top. Same font staging, preflight and commit as `aip-captions`.
6. **Sound.** `cards` printed `sfx_instants` (each header landing): `list_sound_effects` (family "Impacts &
   Emphasis" for the landings, "Transitions & Movement" for whooshes), then one `place_sound_effects` call with
   `replace: true`, `anchor: "first_hit"` for the landings and `"peak"` for whooshes that end on the cut.
7. **Hand back.** `finish_project`, give the `page_url`. Export only when asked (`aip-export`).
8. **Post.** `post-copy` with every streamer credited, then `scoreboard add --format countdown`.
