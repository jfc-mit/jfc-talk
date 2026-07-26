# JFC talk — HSF DAAA · Agentic AI in HEP data analysis · 27 July 2026

`index.html` is an interactive, browser-based talk on the JFC paper
(*AI Agents Can Already Autonomously Perform Experimental High Energy Physics*,
arXiv:2603.20179), in the style of the hcc-kappac Florence talk /
[danielmurnane.com](https://www.danielmurnane.com/ETH-Agentic-AI-for-Collider-Physics/):
a scene/step deck with acts, presenter HUD, layout-edit mode and theming — no build
step, no framework.

**The design beat:** after a 3-scene paper-styled intro, the deck goes dark and a
terminal docks into the right third of the stage, live-replaying `../rbrun3.cast` —
a real, contiguous **42.9-hour** autonomous JFC run (ALEPH R_b/R_c/A_FB^b on
Claude Opus 4.8) compressed to ~11 minutes (×240). It plays beside the slides for the rest
of the talk and its final frame ("✅ Analysis complete — all 7 phases done") is the
finale, where the terminal expands to full stage. A telemetry strip under the
terminal shows the *original* run clock (T+HH:MM:SS), the compression factor, and
the human-input count (2).

Serve statically (the 51 MB cast makes `file://` fetch flaky in some browsers):

```bash
python -m http.server 8123   # from jfc-talk/  ->  http://localhost:8123/
```

## Controls

| key | action |
|---|---|
| click / → / Space / PgDn | next step · ← / PgUp back · Home/End first/last |
| O / Esc | overview grid · **H** presenter HUD (timer + per-scene budgets) |
| **T** | pause / resume the terminal replay |
| **, / .** | seek the replay ∓30 s |
| **G** | grow the terminal to full stage / dock it back — on scenes without the dock (incl. Act I and backups) it **summons** the terminal full-stage, handy in Q&A |
| **S** | hide / unhide the current scene for this audience cut (see below) |
| D | theme cycle auto (scene-driven, default) → light → dark |
| F fullscreen · R restart · ? help |
| E | layout-edit mode (drag panels, ◢ resize, scroll to scale text, double-click to rewrite; C copies override JSON, X resets scene). file:// / localhost / `?edit` only |
| click a figure | zoom lightbox |

Scenes deep-link via the URL hash (`#launch/2`, `#finale`, …).

## Audience cuts (hide/unhide scenes)

Every scene stays in the file; a *cut* is a set of hidden scene ids. Hidden scenes
are flowed over by →/← (still reachable by hash or overview click), and drop out of
the counter, progress bar and HUD time budgets. Backup-act scenes never count.

- **S** while presenting toggles the current scene; the overview (**O**) has a
  hide/show button on every card and shows the active cut.
- The cut persists per-browser (localStorage), so the machine you rehearse on
  keeps your selection.
- `?profile=<name>` loads (and persists) a named preset from `SKIP_PROFILES` in
  `index.html` — ships with `full` (19:20 of budget), `talk15` (the 15-minute
  core, 15:45: hides repo/gate/stack/models/meaning), `results` (skips
  framework internals). Add your own per-venue sets there.
- `?skip=id1,id2` loads an ad-hoc cut; scene ids are the hash names (`#context` → `context`).

## The cast pipeline

`assets/workflow.cast` + `assets/cast_meta.js` are generated from the raw recording:

```bash
python3 prep_cast.py ../rbrun3.cast 650          # target 650 s of playback
python3 prep_cast.py <src> <target_s> <end_orig_s>
```

- **Rest-point pacing**: `python3 prep_cast.py --fast-analyze` replays the cast
  through a stdlib micro terminal-emulator (~10 s) and logs every event that
  substantively changes the screen (≥3 rows — filters the clock/spinner/token
  ticks); cached in `cast_analysis.json`. The cut then holds each moment where
  the screen stayed still ≥60 s of original time (44 such story beats — almost
  always "an agent finished something and paused", matching the independent
  pyte ground-truth analysis) for 2–5 s — the beats the narration quotes
  (T+1:12, T+39:41, T+42:53, via `KEY_BEATS`) hold 7 s — and compresses the
  motion in between uniformly to fill the target. The beats are drawn as amber ticks on the
  dock's progress rail. A slower exact-pyte mode exists (`--analyze`, via
  `uv run --with pyte`). Without the cache it falls back to uniform pacing.
- Inter-event gaps are capped at 0.35 s (collapses overnight/rate-limit idles;
  the tmux status ticks ~0.3 s so normal flow is untouched); events are
  bucket-merged (30 ms) to keep the player light. Payload is untouched — every
  byte the agents printed is replayed.
- **The cut ends at 154,600 s (42.94 h) by default**: rbrun3.cast keeps recording
  past the analysis into an unrelated interactive session; the results screen
  (Final results table, N = 2,889,543, 53-page note, 5-bot review passed) lands at
  42.88 h and is held as the last frame — the finale scene seeks there.
- `cast_meta.js` carries anchors mapping playback time → original run time for the
  telemetry clock; regenerating the cast regenerates the clock automatically.

To swap in a different recording, re-run `prep_cast.py` on it, then update the
prompt/analysis labels in the terminal dock (`#term` markup) and the `launch` /
`finale` scene numbers in `index.html` (grep for "43 hours").

Playback speed / poster are in the `CAST` const near the top of the script.
The dock terminal renders ~84×68 (the run was attached from a narrow client), so
it is genuinely readable at 31.5% stage width; the two brief 280-col stretches
just shrink.

## Assets

Everything in `assets/` is derivative of the paper repo (`../sloppaper4/`:
pipeline_v5, noslop_v3, summary/timing/waterfall/model-comparison plots, the
appendix headline figures), the jfc site (`../jfc-mit.github.io/`: author photos,
analysis thumbnails), and the hcc talk (logos). `asciinema-player` 3.9.0 is
vendored (js+css). Regenerate figure PNGs with `pdftoppm -png -r 160 -singlefile`.

## Numbers quoted in scenes (source: paper v. 2026-07)

- 8/9 scalar pulls within 2σ; Γ_Z at −3.4σ (aftercut off-peak efficiency)
- H→ττ: μ̂ = 1.20 ± 1.13 vs published 1.01 ± 0.41 (μτ_h); σ_μ waterfall 1.20→0.65 vs 0.41
- Lund plane: ⟨N⟩ = 4.751 ± 0.224; first e⁺e⁻ measurement
- ~$200/month Claude Max; ≈10 h wall-clock per analysis
- SciTreeRAG corpus: ALEPH 1,503 catalogued / 575 converted; DELPHI 4,305 / 1,868

The EB Garamond webfont is vendored (`assets/fonts/*.woff2`, latin +
latin-ext), so the deck is fully self-contained offline.
