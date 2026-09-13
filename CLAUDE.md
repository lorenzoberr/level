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
  theme, hideDone, penaltyPaused, penaltyFrom, lastBackup, weight, lastTaskCat}`.
  - `weight`: `{goal, entries:[{date, kg}]}` — deliberately outside the XP
    system: no `log` entries, no badge, no pending count. One entry per day
    (logging again the same day corrects it), 20-300 kg, one decimal; `kgIn()`
    accepts a comma decimal because the Italian iOS keypad types one. Home
    shows the card and chart; the chart plots each Monday-Sunday week's
    average, spaced by real time, the running week hollow/dashed. Past days
    are fixed from the calendar's day panel, like forgotten habits.
  - `habits`: `mode` is `daily` (toggle, once per day), `multi` (repeatable), or
    `weekly` (N sessions per Monday–Sunday week). Weekly habits also carry
    `perWeek` (1–14) and `bonus` (0 = no bonus); both fields are present on every
    habit so the shape is stable, and are ignored outside `weekly`.
  - `goals`: one-off objectives; `done` + `doneDate`, plus an optional
    `deadline`. Completing by the deadline pays full XP; after it, half
    (`goalAward()`), snapshotted into the single log entry. Editing a
    completed objective re-judges its entry against the current deadline
    using the day it was actually completed.
  - Measurable objectives: `mStart`/`mCur`/`mTarget`/`mUnit` (`mTarget` null =
    not measurable). `mStart` anchors the progress bar and is set when the
    objective first becomes measurable, never on later edits. Works in both
    directions (82→90 kg up, 55→50 min down); `goalReached()` decides by
    which side of `mStart` the target sits. Updating `mCur` past the target
    in `saveGoal()` auto-completes through the normal `completeGoal()` path,
    so the deadline half-XP rule still applies.
  - `penalty` log entries: two consecutive days with nothing logged cost a
    level. `reconcilePenalties()` (called at boot, on day rollover, and after
    any past-day log mutation) derives expected penalty days — the 2nd, 4th,
    … day of each unlogged run — inside a 30-day window, drops penalties whose
    days were since backfilled, and adds missing ones with the amount that
    lands the total exactly on the previous level's floor, snapshotted and
    never recomputed. Penalties are derived like bonuses: `undoLast()` skips
    them, the calendar shows them (red, "level down") with no Remove button,
    and `streak()` ignores them. Weight entries do not count as logging.
    Settings can pause it: `penaltyPaused` stops all judging (existing
    penalties stay - a shield, not a refund), and unpausing stamps
    `penaltyFrom` with today so days that passed while paused are never
    judged retroactively. Jurisdiction is `max(window, penaltyFrom)`.
  - `tasks`: daily goals tied to a `date`; overdue ones surface on Home.
  - `log`: XP entries `{type: habit|goal|task|bonus, refId, name, xp, date, at}`. Total XP
    is always the sum of `log`. `done` flags are re-derived from the log in `normalise()`.
  - `bonus` entries are the weekly completion bonus: one per habit per week, XP
    snapshotted at the moment it is earned, dated to the session that finished
    the week. They are derived, so `undoLast()` steps over them and the calendar
    gives them no Remove button — remove one of the week's sessions instead.
- Level curve: `xpForLevel(L) = 100(L-1) + 25(L-1)(L-2)`.
- Rendering: six tabs, one view function each (`viewHome`, `viewTasks`,
  `viewSections`, `viewCalendar`, `viewProgress`, `viewSettings`); each
  returns an HTML string
  and `render()` replaces `#view`. All clicks go through one delegated listener
  keyed on `data-act` / `data-id`. Never use inline `onclick`.
  - **Home** is the daily loop only: tick habits, tick today's goals, log the
    weight, see what is owed. Nothing is added or edited here.
  - **Tasks** is where daily goals are added (with a date field for planning
    ahead) and lists Today, "Unfinished tasks" carried over from earlier days,
    and Planned (future, grouped by date). Overdue goals also stay visible on
    Home, because that is where they get acted on.
  - **Sections** shows one `.secbox` per section with its habits and
    objectives inside it. Add/edit forms open in place inside the box they
    belong to: UI state `editing` ({type,id}) for existing items, `adding`
    ({type,cat}) for new ones; a successful save or Cancel clears both.
  - **Progress** reviews a day, week or month: XP earned against the daily
    pace `target / (start..deadline)` demands, a plain-words verdict, bars per
    day, then "Went well" and "Worth watching" lists. Everything derives from
    `todayISO()` at render time - nothing is cached - and the card names the
    exact date range it judges. Periods are calendar-aligned (Mon-Sun week,
    calendar month) to match the weekly-habit maths, not trailing windows. Encouraging in tone,
    but the misses are named with counts.
  - **Settings** holds target, weight goal, appearance, reminders, data.
  - `state.hideDone` (persisted) tucks away ticked daily habits, met weekly
    habits, done daily goals and done objectives across Home, Tasks and
    Sections; every hidden list leaves a tappable "N done hidden" hint.

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

1. Streak freeze (the other loss signals now live in the Progress tab and
   `weeklyDue()`).
2. Daily cap for repeatable habits.
3. Real push notifications would need a small server (e.g. Cloudflare Worker
   with VAPID + cron). Only if explicitly requested; it moves data off the phone.

`backupOverdue()` drives the Home nudge: 14 days since `lastBackup`, counted
from `start` when nothing has been exported yet, and only once there is
something in the log. `exportData()` is the only thing that sets `lastBackup`.
