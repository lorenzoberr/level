# Level — setup

Seven app files, plus `CLAUDE.md` (project notes for Claude Code) and
`test_app.py` (automated tests). Nothing to install, nothing to pay for.

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

## Install on the iPhone

1. Open the URL in **Safari**. Only Safari can add to the home screen.
2. Share button, then "Add to Home Screen".
3. Open it from the icon, not from Safari. The icon and the Safari tab keep
   separate data, so always use the icon.

## Updating it

Edit `index.html`, push the change, then close and reopen the app. It fetches
from the network first, so you get the new version as soon as you have signal.
If a change refuses to appear, change `CACHE = 'level-v3'` in `sw.js` to
`level-v4`.

## Your data

Stored in the browser's localStorage on that one device. Never leaves the phone.

- Deleting the app from the home screen deletes the data with it.
- iOS can evict storage from web apps left untouched for a long while.

Settings > Export backup produces a JSON file (on iPhone it opens the share
sheet, so save it to Files or iCloud). Settings > Restore backup reads it back.

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

- Sections group habits and objectives and give them a colour.
- Habits are "once a day" (tap to log, tap again to undo) or "repeatable"
  (each tap adds XP).
- Objectives are one-off. Tick when done; tick again to reopen.
- Daily goals are one-off things for a specific day (homework, an errand),
  each with its own XP. Add them from Home with "+ Add goal", or plan ahead
  by tapping a future day in the calendar. Unfinished ones show up the next
  day under "Unfinished from earlier" with a "Move to today" button.
- Calendar: tap any past day to see its entries, remove one, or log a habit
  you forgot to log that day.
- Level curve: reaching level L costs `100(L-1) + 25(L-1)(L-2)` XP.
  Level 2 at 100, 5 at 700, 10 at 2,700, 20 at 10,450.
- Pace is measured from "Counting from" in Settings (set to your first launch)
  to the deadline.
- Editing a habit's XP does not rewrite past entries; history stays as it was.
  Editing a completed objective's XP does update its one entry, so the total
  stays consistent.
