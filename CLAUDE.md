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

- State: `{setup, name, cats, habits, goals, tasks, log, target, deadline,
  start, reminders, theme, hideDone, penaltyPaused, penaltyFrom, lastBackup,
  weight, finance, lastTaskCat}`.
  - **Fresh installs are empty.** `seed()` ships no habits, goals or entries -
    one placeholder section only (the code assumes at least one cat). With
    `setup:false`, `render()` shows the first-open welcome flow instead of the
    tabs: name, first section + colour, XP target/deadline, optional weight
    goal; finishing lands in Sections with the habit form open. Data without
    a `setup` field is treated as an established install and never sees the
    flow; "Reset everything" returns to it. `name` shows in the hero and is
    editable under Settings > You.
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
  - `finance`: `{income, categories, months}` - monthly GBP budgeting, sealed
    off like weight with ONE exception: closing out a month pays a lump of XP
    (a `finance` log entry, `refId` = `YYYY-MM`, dated inside that month).
    `categories` `{id,name,budget,xp,dir}` are shared across months
    (`dir:'under'` = spending, success is spent<=budget; `'over'` = investing,
    success is spent>=budget; equal always succeeds). `months[YYYY-MM]` =
    `{spent:{catId:number},closed,awarded}` - absence from `spent` means "not
    recorded, skip at close-out"; an explicit 0 is judged. No rollover, no
    per-purchase ledger, no link to habit sections. Categories may carry an
    optional `subs` array `{id,name}` (default empty = unchanged behaviour):
    a spending breakdown with NO own budget/direction/XP. With subs, the
    parent's spent is DERIVED via `finSpentOf()` - the sum of subs that have
    a value in the month's `spent` map (sub ids share that map) - and the
    parent counts as recorded only if at least one sub does; its own spent
    key is ignored (but preserved) while subs exist. Close-out judges the
    derived total exactly as before. Deleting a sub (staged in the form's
    DOM, applied at save) or its parent clears the sub's spends from every
    month. `finance` entries behave
    like bonus/penalty: `undoLast()` skips them, `streak()` and
    `reconcilePenalties()` ignore them (money is never "logging"), the
    calendar shows them ("close-out") with no Remove. Reopening a closed month
    removes its entry like a reopened objective. Money in/out via `moneyIn()`
    (comma or dot decimal) and `gbp()` (£1,234; decimals only when present).
  - `tasks`: daily goals tied to a `date`; overdue ones surface on Home.
  - `log`: XP entries `{type: habit|goal|task|bonus|penalty|finance, refId, name, xp, date, at}`. Total XP
    is always the sum of `log`. `done` flags are re-derived from the log in `normalise()`.
  - `bonus` entries are the weekly completion bonus: one per habit per week, XP
    snapshotted at the moment it is earned, dated to the session that finished
    the week. They are derived, so `undoLast()` steps over them and the calendar
    gives them no Remove button — remove one of the week's sessions instead.
- Level curve: `xpForLevel(L) = 100(L-1) + 25(L-1)(L-2)`.
- Rendering: seven tabs, one view function each (`viewHome`, `viewTasks`,
  `viewSections`, `viewCalendar`, `viewProgress`, `viewSettings`,
  `viewFinance`); each returns an HTML string
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
    The habit/objective/daily-goal forms carry two 1-5 Importance/Effort
    dials that only PRE-FILL the XP field: `suggestXP(ceil,imp,eff)` =
    max(5, round5(ceil*(0.25*imp/5 + 0.75*((eff-1)/4)^2))), CEIL 100 for
    habits, 500 for objectives, 30 for daily goals. The dials are
    input-only DOM state - nothing is stored on the item, the typed value
    always wins at save, and a dial touch overwrites the field in place
    (no render). Sections also shows the headroom advisory
    (`headroomEstimate()`): habit occurrences (daily/multi = inclusive day
    count of start..deadline; weekly = ceil(days/7) x perWeek, bonuses
    excluded) x XP x 0.75 plus objectives at half value, against the
    honest full-consistency maximum; warn-styled above 70% of
    `state.target`. Advisory only - it never blocks a save or scales a
    suggestion.
  - **Progress** reviews a day, week or month: XP earned against the daily
    pace `target / (start..deadline)` demands, a plain-words verdict, bars per
    day, then "Went well" and "Worth watching" lists. Everything derives from
    `todayISO()` at render time - nothing is cached - and the card names the
    exact date range it judges. Periods are calendar-aligned (Mon-Sun week,
    calendar month) to match the weekly-habit maths, not trailing windows. Encouraging in tone,
    but the misses are named with counts.
  - **Settings** holds target, weight goal, appearance, reminders, data.
  - **Finances** (last tab) is the monthly budget: month header with
    back/forward (never future), income card with budgeted/spent/left,
    category rows with in-place spent inputs (read-only once closed), an
    add/edit-in-place form, and the close-out / reopen controls. Good/over
    verdicts use the `--fin-good`/`--fin-bad` tokens.
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

`python test_app.py` — 304 Playwright checks in headless Chromium at iPhone
size, Europe/Rome timezone, with a fake clock (midnight rollover, the October
DST weekend, month wrap, v1 migration, corrupted storage, XSS in names).
Run it after every change. Add a check for every bug you fix.

The suite RUNS on the owner's machine: Python 3.12 with `pip install
playwright tzdata` (tzdata is required - Windows Python has no system zone
data) and `python -m playwright install chromium`. First full pass: 13 Sep
2026, 0 failures (246 checks as of the fresh-install rework). Feature tests
inject the classic demo fixture (see `DEMO` in the test file) because the app
itself now installs empty. `serve.ps1` (PowerShell, no dependencies)
serves the folder on `http://localhost:8765/` for eyeballing changes; service
workers do not register against it - use the real host for offline checks.

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
