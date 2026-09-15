# Level — setup

Seven app files, plus `CLAUDE.md` (project notes for Claude Code), `test_app.py`
(automated tests) and `serve.ps1` (previews the app locally on Windows: right
click > Run with PowerShell, then open `http://localhost:8765/`). Nothing to
install, nothing to pay for. The three extra files are harmless to upload and
the app ignores them; delete them from the repo if you would rather not.

## Put it online

Easiest route, no command line:

1. Create a free GitHub account.
2. New repository, any name, set to Public.
3. Upload every file in this folder to the root of the repo (`CLAUDE.md` and
   `test_app.py` are harmless to include; the app ignores them).
4. Settings > Pages > Source: "Deploy from a branch", branch `main`, folder `/ (root)`. Save.
5. Wait a minute. The app is at `https://<username>.github.io/<repo>/`.

Alternative: drag this folder onto app.netlify.com/drop. Instant, random URL.

Either way you get HTTPS, which the offline cache requires.

## First open

The app arrives empty - no example habits, no pre-filled anything. The first
time it opens it asks your name, your first section and its colour, your XP
target and deadline, and (optionally) a weight goal, then drops you straight
into building your first habit. Everything it asks for can be changed later
under Settings. You only ever see this once; restoring a backup skips it.

## Install on the iPhone

1. Open the URL in **Safari**. Only Safari can add to the home screen.
2. Share button, then "Add to Home Screen".
3. Open it from the icon, not from Safari. The icon and the Safari tab keep
   separate data, so always use the icon.

## Updating it

Edit `index.html`, push the change, then close and reopen the app. It fetches
from the network first, so you get the new version as soon as you have signal.
If a change refuses to appear, bump the version in `sw.js` (change
`CACHE = 'level-v7'` to `level-v8`, and so on).

## Your data

Stored in the browser's localStorage on that one device. Never leaves the phone.

- Deleting the app from the home screen deletes the data with it.
- iOS can evict storage from web apps left untouched for a long while.

Settings > Export backup produces a JSON file (on iPhone it opens the share
sheet, so save it to Files or iCloud). Settings > Restore backup reads it back.

If it has been a fortnight since the last export, Home shows a strip saying how
long it has been, with a button to export there and then. It goes away as soon
as you export and comes back a fortnight later. Settings > Your data always
shows the date of the last one.

## Reminders

The app cannot send notifications on its own. iPhone web apps only receive
notifications from a server, and this app has none, on purpose. Two things
do work:

- **Icon badge.** Settings > Reminders > "Show how many things are left on
  the app icon". iOS ties badges to notification permission, so the first
  time you turn it on the phone asks to allow notifications; the app never
  sends any, the permission only unlocks the badge. The number stays on the
  icon after you close the app.
- **Timed alerts via Shortcuts.** Settings > Reminders lists your times and
  the exact steps for the iPhone Shortcuts app. Each automation shows a
  notification at that time; when you then open Level, the home screen
  shows what's still pending.

## How it works

Seven tabs along the bottom, each with one job:

- **Home** — the daily loop. Tick habits, tick today's goals, log your weight,
  see what's still owed. Goals left unfinished from earlier days show here
  under "Unfinished tasks" with a button to move them to today.
- **Tasks** — where daily goals are written. Add one for today or pick a date
  to plan ahead; below the form sit Today, Unfinished tasks, and everything
  Planned, grouped by day.
- **Sections** — one box per section (Fitness, School, ...), with its habits
  and its objectives together inside it. Add and edit everything here; the
  form opens inside the box it belongs to.
- **Calendar** — the month at a glance, shaded against your own recent best
  rather than fixed numbers, so the map keeps contrast as your XP grows. Tap
  a day to see or fix it.
- **Progress** — the report card. Day, Week or Month: XP earned against the
  pace your target asks for, a verdict in plain words, a bar per day, what
  went well, and what slipped — named kindly, with counts.
- **Settings** — target, weight goal, appearance, reminders, your data.
- **Finances** — the monthly budget: allowance, categories, what's left, and
  a close-out that pays XP for discipline. Details further down.

- The app follows the phone's light or dark setting on its own. To pin it one
  way regardless, Settings > Appearance has Auto, Light and Dark.
- **Weight** lives at the bottom of Home and earns no XP on purpose. Weigh in
  each morning and log it (comma or dot decimals both work); logging again the
  same day just corrects the number. Daily readings bounce around with water
  and food, so the chart plots each Monday-Sunday week's **average** — one dot
  per week, joined by a line, with your goal as a dashed line to aim for. The
  current week's dot is hollow because its average can still move. Set or
  change the goal from the card itself or Settings > Weight goal; forgot a
  day? Fix it from that day in the calendar.
- Sections group habits and objectives and give them a colour.
- Habits are "once a day" (tap to log, tap again to undo), "repeatable"
  (each tap adds XP), or "times a week".
- **Times a week** is for things you do a few times a week rather than daily,
  like the gym. Set the count (say 3) and a bonus. Each session pays its own XP
  and fills one dot; the row counts down — "1 of 3 this week · 2 to go". Finish
  the third and the bonus is paid on top, once, that week. Extra sessions past
  the count still pay their XP, but the bonus is only ever paid once a week.
  Weeks run Monday to Sunday. On the day when the sessions you still owe equal
  the days left in the week, the row turns amber and says "go today"; that is
  also when it starts counting towards the number on the app icon. Come Monday
  the count starts again at zero and last week's XP stays where it is.
  Raising the count later never takes back a bonus an earlier week earned.
- Objectives are one-off. Tick when done; tick again to reopen. Each can
  carry an optional deadline: finish by it for the full XP, after it for
  half. The row says which applies before you tick.
- Anything ticked off can be tucked away: "Hide done" on Home or Tasks (and
  the "N done hidden" hints everywhere) fold completed habits, goals and
  objectives out of sight until you ask for them back.
- Daily goals are one-off things for a specific day (homework, an errand),
  each with its own XP. Add them in the Tasks tab (Home's "+ Add goal" takes
  you there), or plan ahead with the date field or by tapping a future day in
  the calendar. Unfinished ones show up the next day under "Unfinished tasks"
  with a "Move to today" button, on both Home and the Tasks tab.
- Calendar: tap any past day to see its entries, remove one, or log a habit
  you forgot to log that day.
- Level curve: reaching level L costs `100(L-1) + 25(L-1)(L-2)` XP.
  Level 2 at 100, 5 at 700, 10 at 2,700, 20 at 10,450.
- Pace is measured from "Counting from" in Settings (set to your first launch)
  to the deadline.
- Editing a habit's XP does not rewrite past entries; history stays as it was.
  Editing a completed objective's XP does update its one entry, so the total
  stays consistent.

## Measurable objectives

Give an objective a current number, a target and a unit (say 72.5 → 80 kg)
and its row grows a progress bar. Update the current number from Edit as you
go; reaching the target completes the objective by itself and pays the XP —
the deadline rule still applies. Downward targets work too (55 min → 50).

## Two quiet days cost a level

Go two consecutive days without logging anything and the app takes a level:
a red entry in the calendar drops your total to the start of the previous
level. Four quiet days cost two, and so on. It is never silent — you get a
toast, the calendar shows it, and Progress lists it. Honestly forgot to log
a day you actually did something? Backfill the habit from the calendar and
the penalty lifts itself. Only the last 30 days are ever judged, and logging
just your weight does not count — the rule is about the habits.

Exam week, holiday, illness? Settings > Level penalty has a switch. While it
is off, quiet days are not judged — and they never will be: switching it back
on starts counting from that day, with no back-charges. Penalties already on
the books stay, though; pausing is a shield, not a refund.

## Finances

The last tab is a monthly budget, kept apart from the daily XP loop the same
way weight is. Set your monthly allowance once, add categories with a monthly
figure — spending ones reward staying at or under, investing ones reward
meeting or exceeding — and fill in what you actually spent as the month goes.
The card shows what is budgeted, spent and left; green and red tell you where
you stand per category.

At the end of the month (or whenever you are ready), close it out: every
category you recorded gets judged, the winners pay their XP as one lump on
that month, and the figures lock. A category you never filled in is simply
skipped — but an explicit £0 is a real answer and gets judged, so an empty
investing month costs you its XP. Closed the month too soon? Reopen takes
the XP back and unlocks it. Money never counts as daily logging: it cannot
feed the streak and the quiet-days penalty cannot see it.
