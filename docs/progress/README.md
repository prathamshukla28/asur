# ASUR Build Progress (plain-language)

This folder is the simple, human-readable record of **what has been built, what each phase does, and what is left**. One file per phase. No jargon.

If you ever want to know "where are we?", read `OVERVIEW.md` first, then open the phase file you care about.

## The big picture

ASUR is built in 9 phases (P00 → P08). Think of it like building a factory one station at a time, and never turning on an expensive machine until a cheaper check has passed.

| Phase | Nickname | What it gives you | Status |
|-------|----------|-------------------|--------|
| P00 | Foundations | The rulebook + safety guards | ✅ Done |
| P01 | SCRIPT finish | Turn one idea into a full scored script | 🔜 In progress |
| P02 | Controller | The "state machine" that moves a project stage by stage, plus the orchestrator and command words | ⬜ Planned |
| P03 | Firewall | The wall that keeps the "maker" and the "judge" from talking directly (so scores can't be gamed) | ⬜ Planned |
| P04 | First video proof | Make a short 5–15s "hero proof" clip — **you approve it before anything expensive runs** | ⬜ Planned (STOPS for you) |
| P05 | Editing | Timeline, captions, motion, audio — you stay in control | ⬜ Planned |
| P06 | Full video | Build the whole video, check every section, final render + QA | ⬜ Planned |
| P07 | Viral check | Honest scoring on 12 separate dimensions — never one fake "% viral" number | ⬜ Planned |
| P08 | Learning | Publish, measure real results, learn for next time — **you approve before publishing** | ⬜ Planned (STOPS for you) |

## How the automatic build runs

The build runs in **three legs**. It pauses for you at two safety gates.

- **Leg A — P00 → P03:** fully automatic. No video made yet, nothing expensive, nothing published.
- **Leg B — P04:** stops at the **hero-proof gate**. You watch a short clip and approve before the full video is made.
- **Leg C — P05 → P08:** stops at the **publish gate**. Nothing is ever posted without your yes.

## Rules that never bend

- 100% local, no logins, no internet needed to work.
- Nothing is ever secretly overwritten — every version is kept.
- Never a single fake "% viral" score.
- The maker and the judge never talk directly.
- You own every approval. The tool never approves irreversible or paid things for you.

## Files in this folder

- `OVERVIEW.md` — the live one-glance status (updated after every phase).
- `P00-foundations.md` … `P08-learning.md` — one file per phase: what it does, why, and whether it's done.
