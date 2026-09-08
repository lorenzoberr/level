# Level — personal habit / XP tracker (iPhone PWA)

Single-user app for Lorenzo's own iPhone. Installed via Safari > Add to Home
Screen from a static host (GitHub Pages). No accounts, no server, no build step.

## Hard constraints — do not break these

- **Static files only.** No backend, no framework, no bundler, no npm. `index.html`
  contains all CSS and JS. Adding a build step or a dependency is a regression.
- **Relative paths only** (`manifest.json`, `sw.js`, `icon-*.png`). The app is
  served from a subfolder on GitHub Pages; an absolute `/path` breaks it.
- **Local calendar days.** Dates are `YYYY-MM-DD` strings built with
  `localISO()` / `parseLocal()`. Never use `toISOString()` or `new Date("YYYY-MM-DD")`
  for a calendar day; both shift dates around midnight (Rome timezone, DST).
- **Storage.** `localStorage` key `level.v2`. Every load passes through
  `normalise()`, which repairs any field. If you change the schema: extend
  `normalise()` so old data still loads, and keep `seed()` in sync. Never make a
  change that would drop existing entries.
- **History is immutable by default.** Editing a habit's XP does not rewrite past
  log entries. Editing a completed objective's XP does update its single entry.
- **Data never leaves the phone.** No analytics, no fetches to third parties.
- Bump `CACHE` in `sw.js` (`level-v3` → `level-v4`) whenever `index.html` changes,
  so installed phones pick up the new version.

## Architecture (index.html)

- State: `{cats, habits, goals, tasks, log, target, deadline, start, reminders, lastTaskCat}`.
  - `habits`: `mode` is `daily` (toggle, once per day) or `multi` (repeatable).
  - `goals`: one-off objectives; `done` + `doneDate`.
  - `tasks`: daily goals tied to a `date`; overdue ones surface on Home.
  - `log`: XP entries `{type: habit|goal|task, refId, name, xp, date, at}`. Total XP
    is always the sum of `log`. `done` flags are re-derived from the log in `normalise()`.
- Level curve: `xpForLevel(L) = 100(L-1) + 25(L-1)(L-2)`.
- Rendering: three views (`viewHome`, `viewCalendar`, `viewManage`) return HTML
  strings; `render()` replaces `#view`. All clicks go through one delegated
  listener keyed on `data-act` / `data-id`. Never use inline `onclick`.
- All user strings go through `esc()` before entering HTML.
- Character: `characterSVG(level)`, original design, tiers at levels 5/10/15/20.
- Badge: `updateBadge()` calls `navigator.setAppBadge` with the pending count.

## Testing

`python test_app.py` — ~100 Playwright checks in headless Chromium at iPhone
size, Europe/Rome timezone, with a fake clock (midnight rollover, the October
DST weekend, month wrap, v1 migration, corrupted storage, XSS in names).
Run it after every change. Add a check for every bug you fix.

Real iOS Safari has NOT been tested from this environment. Things only a phone
can verify: Add to Home Screen, standalone mode, the share-sheet export, the
icon badge (iOS ties it to notification permission).

## Deploy

GitHub Pages from the repo root, or drag the folder onto app.netlify.com/drop.
The URL must never change after install: data is tied to the origin.

## Owner's wishlist (not built, in priority order)

1. Weekly-frequency habits ("gym 3× a week") with bonus XP on hitting the count.
2. Loss signals: days missed this week, weekly consistency %, streak freeze.
3. "Last backup N days ago" nudge on Home.
4. Daily cap for repeatable habits.
5. Measurable objectives (current / target number).
6. Real push notifications would need a small server (e.g. Cloudflare Worker
   with VAPID + cron). Only if explicitly requested; it moves data off the phone.
