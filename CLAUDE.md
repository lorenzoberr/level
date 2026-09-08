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
  `reconcileWeek(habitId, iso)` recomputes the bonus for the one week `iso` falls
  in and no other, so raising "3x a week" to "4x" never claws back a bonus an
  earlier week already earned. Do not add a global re-derivation pass.
- **Data never leaves the phone.** No analytics, no fetches to third parties.
- Bump `CACHE` in `sw.js` (`level-v3` → `level-v4`) whenever `index.html` changes,
  so installed phones pick up the new version.

## Architecture (index.html)

- State: `{cats, habits, goals, tasks, log, target, deadline, start, reminders,
  theme, lastBackup, lastTaskCat}`.
  - `habits`: `mode` is `daily` (toggle, once per day), `multi` (repeatable), or
    `weekly` (N sessions per Monday–Sunday week). Weekly habits also carry
    `perWeek` (1–14) and `bonus` (0 = no bonus); both fields are present on every
    habit so the shape is stable, and are ignored outside `weekly`.
  - `goals`: one-off objectives; `done` + `doneDate`.
  - `tasks`: daily goals tied to a `date`; overdue ones surface on Home.
  - `log`: XP entries `{type: habit|goal|task|bonus, refId, name, xp, date, at}`. Total XP
    is always the sum of `log`. `done` flags are re-derived from the log in `normalise()`.
  - `bonus` entries are the weekly completion bonus: one per habit per week, XP
    snapshotted at the moment it is earned, dated to the session that finished
    the week. They are derived, so `undoLast()` steps over them and the calendar
    gives them no Remove button — remove one of the week's sessions instead.
- Level curve: `xpForLevel(L) = 100(L-1) + 25(L-1)(L-2)`.
- Rendering: three views (`viewHome`, `viewCalendar`, `viewManage`) return HTML
  strings; `render()` replaces `#view`. All clicks go through one delegated
  listener keyed on `data-act` / `data-id`. Never use inline `onclick`.
- All user strings go through `esc()` before entering HTML.
- **Theme.** Every colour the app paints is a CSS custom property on `:root`;
  `:root[data-theme="dark"]` restates the values and nothing else. Never write a
  raw hex in a rule or an inline style — add a token. (The only deliberate
  exceptions are `#fff` inside `.hero` and on tick marks, which sit on a
  coloured fill in both themes, and the character SVG.) `state.theme` is
  `auto` (follows the phone), `light` or `dark`. The inline script in `<head>`
  settles `data-theme` before the first paint so a dark phone never flashes
  white; it duplicates the logic in `effectiveTheme()` and the two must agree.
- Character: `characterSVG(level)`, original design, tiers at levels 5/10/15/20.
- Badge: `updateBadge()` calls `navigator.setAppBadge` with the pending count.

## Testing

`python test_app.py` — ~100 Playwright checks in headless Chromium at iPhone
size, Europe/Rome timezone, with a fake clock (midnight rollover, the October
DST weekend, month wrap, v1 migration, corrupted storage, XSS in names).
Run it after every change. Add a check for every bug you fix.

Python is not installed on the owner's Windows machine, so the suite cannot be
run from there as things stand. `serve.ps1` (PowerShell, no dependencies) serves
the folder on `http://localhost:8765/` for eyeballing changes in a browser; it
is a dev convenience, not part of the app. Service workers do not register
against it — use the real host to check offline behaviour.

Real iOS Safari has NOT been tested from this environment. Things only a phone
can verify: Add to Home Screen, standalone mode, the share-sheet export, the
icon badge (iOS ties it to notification permission).

## Deploy

GitHub Pages from the repo root, or drag the folder onto app.netlify.com/drop.
The URL must never change after install: data is tied to the origin.

## Owner's wishlist (not built, in priority order)

1. Loss signals beyond the one that exists: weekly consistency %, days missed,
   streak freeze. (A weekly habit already turns amber and says "go today" once
   the days left in the week equal the sessions still owed — see `weeklyDue()`.)
2. Daily cap for repeatable habits.
3. Measurable objectives (current / target number).
4. Real push notifications would need a small server (e.g. Cloudflare Worker
   with VAPID + cron). Only if explicitly requested; it moves data off the phone.

`backupOverdue()` drives the Home nudge: 14 days since `lastBackup`, counted
from `start` when nothing has been exported yet, and only once there is
something in the log. `exportData()` is the only thing that sets `lastBackup`.
