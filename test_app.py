"""
End-to-end tests for the Level app. Runs the real app in headless Chromium at
iPhone size, Rome timezone, with a controllable clock.

    pip install playwright && python -m playwright install chromium
    python test_app.py

Serves the current folder on localhost:8765 for the duration of the run and
writes screenshots to ./shots/. Exit code 1 on any failure.
"""
import json, datetime, sys, os, subprocess, time, pathlib
from zoneinfo import ZoneInfo
ROME = ZoneInfo("Europe/Rome")
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
os.chdir(HERE)
pathlib.Path("shots").mkdir(exist_ok=True)
server = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
URL = "http://localhost:8765/index.html"
IPHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2,
              is_mobile=True, has_touch=True, timezone_id="Europe/Rome", locale="en-GB")
fails = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("  -> " + str(extra)) if (extra and not cond) else ""))
    if not cond: fails.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---------- 1. fresh install, fixed clock: Mon 7 Sep 2026 23:30 Rome ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.clock.install(time=datetime.datetime(2026, 9, 7, 23, 30, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    page.goto(URL)
    page.wait_for_selector(".hero")
    check("no JS errors on load", not errors, errors)
    check("header shows local date", "Monday 7 September" in page.inner_text("#today"), page.inner_text("#today"))
    check("starts at level 1 / 0 XP", "Level 1" in page.inner_text(".lvl") and page.inner_text(".total").strip() == "0")
    check("three seeded sections on home", page.locator("h2 .dot").count() == 3)
    page.screenshot(path="shots/home_empty.png", full_page=True)

    # log the gym (multi) twice, steps (daily) once, then toggle steps off
    gym = page.locator(".row[data-act=log]", has_text="Gym session")
    gym.click(); page.wait_for_timeout(50)
    gym.click(); page.wait_for_timeout(50)
    steps = page.locator(".row[data-act=log]", has_text="8k steps")
    steps.click(); page.wait_for_timeout(50)
    check("multi habit logs twice, daily once", page.inner_text(".total").strip() == "120", page.inner_text(".total"))
    check("level 2 reached at 120 XP", "Level 2" in page.inner_text(".lvl"))
    check("gym row shows 2x today", "2× today" in page.locator(".row[data-act=log]", has_text="Gym session").inner_text())
    steps.click(); page.wait_for_timeout(50)
    check("daily habit toggles off", page.inner_text(".total").strip() == "100")
    check("fitness section shows today XP", "100 XP today" in page.locator("h2", has_text="Fitness").inner_text())
    check("streak is 1", "1 day streak" in page.inner_text(".streak"))

    # ---------- daily goals on home ----------
    badge_calls = []
    page.evaluate("""() => { window.__badge=[]; navigator.setAppBadge = n => { window.__badge.push(n); return Promise.resolve(); };
                            navigator.clearAppBadge = () => { window.__badge.push(0); return Promise.resolve(); }; }""")
    check("pending count shown (4 daily habits left)", "4 left" in page.inner_text(".pendline"), page.inner_text(".pendline"))
    check("21:00 reminder banner shows at 23:30 with pending items", "21:00 reminder" in page.inner_text("#view") and "4 still to do" in page.inner_text("#view"))
    page.locator("button[data-act=task-form]").click(); page.wait_for_timeout(50)
    check("quick-add form opens and focuses name", page.evaluate("document.activeElement && document.activeElement.id") == "f-t-name")
    page.locator("button[data-act=task-add]").click(); page.wait_for_timeout(50)
    check("empty goal rejected", page.locator(".row.task").count() == 0)
    page.fill("#f-t-name", "Finish marketing homework"); page.fill("#f-t-xp", "40")
    page.select_option("#f-t-cat", label="School")
    page.keyboard.press("Enter"); page.wait_for_timeout(50)
    check("Enter adds the goal and form stays open", page.locator(".row.task", has_text="Finish marketing homework").count() == 1 and page.locator("#f-t-name").count() == 1)
    check("name field cleared for the next goal", page.input_value("#f-t-name") == "")
    check("section remembered from last goal", page.evaluate("document.getElementById('f-t-cat').selectedOptions[0].text") == "School")
    page.fill("#f-t-name", "Email tutor"); page.fill("#f-t-xp", "15")
    page.locator("button[data-act=task-add]").click(); page.wait_for_timeout(50)
    check("two goals, 0/2 done, 6 left", "0/2 done" in page.locator(".goals-head").inner_text() and "6 left" in page.inner_text(".pendline"))
    page.locator(".row.task[data-act=task]", has_text="Email tutor").click(); page.wait_for_timeout(50)
    check("completing a goal adds its XP", page.inner_text(".total").strip() == "115" and "1/2 done" in page.locator(".goals-head").inner_text())
    check("School section counts goal XP today", "15 XP today" in page.locator("h2", has_text="School").inner_text())
    page.locator(".row.task", has_text="Email tutor").click(); page.wait_for_timeout(50)
    check("tap again reopens the goal", page.inner_text(".total").strip() == "100")
    page.locator(".row.task", has_text="Email tutor").click(); page.wait_for_timeout(50)
    page.locator(".row.task", has_text="Email tutor").locator("button[data-act=task-del]").click(); page.wait_for_timeout(80)
    check("deleting a done goal removes its XP", page.inner_text(".total").strip() == "100" and page.locator(".row.task", has_text="Email tutor").count() == 0)
    calls = page.evaluate("window.__badge")
    check("app badge updated with pending count", calls and calls[-1] == 5, calls)

    # complete an objective, then reopen it
    obj = page.locator(".row[data-act=goal]", has_text="Bench press")
    obj.click(); page.wait_for_timeout(50)
    check("objective adds XP", page.inner_text(".total").strip() == "400")
    check("objective moves out of open list", page.locator(".row[data-act=goal]", has_text="Bench press").count() == 0)
    check("section notes done count", "1 done" in page.locator("h3", has_text="Objectives").first.inner_text())
    page.locator("button[data-act=undo]").click(); page.wait_for_timeout(50)
    check("undo reopens objective and removes XP", page.inner_text(".total").strip() == "100"
          and page.locator(".row[data-act=goal]", has_text="Bench press").count() == 1)

    # ---------- persistence across reload ----------
    page.reload(); page.wait_for_selector(".hero")
    check("data survives reload", page.inner_text(".total").strip() == "100")
    raw = page.evaluate("localStorage.getItem('level.v2')")
    d = json.loads(raw)
    check("stored dates are local calendar days (23:30 Rome stays 7 Sep)", all(e["date"] == "2026-09-07" for e in d["log"]), [e["date"] for e in d["log"]])
    check("start date anchored to first launch", d["start"] == "2026-09-07")

    # ---------- midnight rollover while app open ----------
    page.clock.run_for(45 * 60 * 1000)   # 23:30 -> 00:15 Tue 8 Sep
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(100)
    check("header rolls over to Tuesday 8 September", "Tuesday 8 September" in page.inner_text("#today"), page.inner_text("#today"))
    check("gym resets to 0x today after midnight", "Tap each time" in page.locator(".row[data-act=log]", has_text="Gym session").inner_text())
    check("streak still 1 (yesterday counts)", "1 day streak" in page.inner_text(".streak"))
    check("total XP unchanged after rollover", page.inner_text(".total").strip() == "100")
    check("unfinished goal from yesterday shown as overdue", "Unfinished from earlier" in page.inner_text("#view") and "Set for 7 Sept" in page.locator(".row.task", has_text="Finish marketing homework").inner_text())
    page.locator("button[data-act=task-move]").click(); page.wait_for_timeout(50)
    check("move to today", "Unfinished from earlier" not in page.inner_text("#view") and "0/1 done" in page.locator(".goals-head").inner_text())
    check("no reminder banner at 00:15 before first time", "reminder." not in page.inner_text("#view"))

    # ---------- calendar ----------
    page.locator("button[data-act=tab][data-id=calendar]").click()
    page.wait_for_selector(".cal")
    check("calendar shows September 2026", "September 2026" in page.inner_text(".calhead"))
    first_cells = page.locator(".cal .day").all()
    # Sept 1 2026 is a Tuesday -> exactly 1 blank before it
    check("Monday-first alignment (1 blank before Tue 1 Sep)", "blank" in first_cells[0].get_attribute("class") and first_cells[1].inner_text().startswith("1"))
    check("7 Sep coloured with 100 XP", page.locator(".day[data-act=pick][data-id='2026-09-07']").get_attribute("data-l") == "3")
    check("8 Sep is today", "today" in page.locator(".day[data-id='2026-09-08']").get_attribute("class"))
    page.locator(".day[data-act=pick][data-id='2026-09-09']").click(); page.wait_for_timeout(50)
    check("future day opens a planning panel with no habit logging", page.locator("#f-t-name").count() == 1 and page.locator("#f-cal-habit").count() == 0 and "Nothing planned" in page.inner_text("#view"))
    page.fill("#f-t-name", "Submit essay draft"); page.fill("#f-t-xp", "60")
    page.locator("button[data-act=task-add]").click(); page.wait_for_timeout(50)
    check("goal planned on a future day", page.locator(".row.task", has_text="Submit essay draft").count() == 1)
    check("future planned goal is not tappable", page.locator(".row.task[data-act=task]", has_text="Submit essay draft").count() == 0)
    check("calendar cell shows planned count", "1 planned" in page.locator(".day[data-id='2026-09-09']").inner_text())
    check("month stats", "100" in page.locator(".stat").nth(0).inner_text() and "1" in page.locator(".stat").nth(1).inner_text())

    # backfill: pick yesterday, log Read 20 minutes
    page.locator(".day[data-act=pick][data-id='2026-09-07']").click()
    page.wait_for_selector("#f-cal-habit")
    check("day panel shows 7 Sep entries", page.locator(".entry").count() == 2)
    page.select_option("#f-cal-habit", label="Read 20 minutes (+10)")
    page.locator("button[data-act=log-day]").click(); page.wait_for_timeout(50)
    check("backfilled entry lands on 7 Sep", page.locator(".entry").count() == 3 and "110 XP" in page.locator("h2", has_text="Monday 7 September").inner_text())
    check("past day shows its goals list", "Goals for this day" in page.inner_text("#view"))
    # remove one gym entry from that day
    page.locator(".entry", has_text="Gym session").first.locator("button[data-act=rm-entry]").click(); page.wait_for_timeout(50)
    check("remove entry from a past day", page.locator(".entry").count() == 2)
    # navigate months
    page.locator("button[data-act=cal-prev]").click()
    check("prev month -> August 2026", "August 2026" in page.inner_text(".calhead"))
    for _ in range(6): page.locator("button[data-act=cal-prev]").click()
    check("wraps year backwards -> February 2026", "February 2026" in page.inner_text(".calhead"))
    check("Feb 2026 has 28 day cells", page.locator(".cal .day:not(.blank)").count() == 28)
    for _ in range(11): page.locator("button[data-act=cal-next]").click()
    check("wraps year forwards -> January 2027", "January 2027" in page.inner_text(".calhead"))
    for _ in range(4): page.locator("button[data-act=cal-prev]").click()
    page.screenshot(path="shots/calendar.png", full_page=True)

    # ---------- manage: sections ----------
    page.locator("button[data-act=tab][data-id=manage]").click()
    page.wait_for_selector(".seg")
    page.fill("#f-cat-name", "Career")
    page.locator(".sw[data-id='#F97316']").click()
    page.locator("button[data-act=save-cat]").click(); page.wait_for_timeout(50)
    check("add section", page.locator(".row", has_text="Career").count() == 1)
    page.locator(".row", has_text="Career").locator("button[data-act=edit-cat]").click()
    page.wait_for_timeout(50)
    check("edit form prefilled", page.input_value("#f-cat-name") == "Career" and page.locator(".sw[aria-pressed=true]").get_attribute("data-id") == "#F97316")
    page.fill("#f-cat-name", "Work")
    page.locator("button[data-act=save-cat]").click(); page.wait_for_timeout(50)
    check("rename section", page.locator(".row", has_text="Work").count() == 1 and page.locator(".row", has_text="Career").count() == 0)
    page.locator(".row", has_text="School").locator("button[data-act=del-cat]").click(); page.wait_for_timeout(80)
    check("delete section", page.locator(".row", has_text="School").count() == 0)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    orphan = [h for h in d["habits"] if h["cat"] not in {c["id"] for c in d["cats"]}]
    check("deleted section's items reassigned, no orphans", not orphan, orphan)

    # ---------- manage: habits ----------
    page.locator("button[data-act=seg][data-id=habits]").click()
    page.fill("#f-h-name", "Cold shower")
    page.fill("#f-h-xp", "12")
    page.select_option("#f-h-mode", "daily")
    page.select_option("#f-h-cat", label="Work")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("add habit", page.locator(".row", has_text="Cold shower").count() == 1)
    page.fill("#f-h-name", "Bad")
    page.fill("#f-h-xp", "0")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("rejects XP of 0", page.locator(".row", has_text="Bad").count() == 0)
    page.evaluate("document.getElementById('f-h-xp').value=''")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("rejects empty XP", page.locator(".row", has_text="Bad").count() == 0)
    page.fill("#f-h-xp", "-5")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("rejects negative XP", page.locator(".row", has_text="Bad").count() == 0)
    page.fill("#f-h-xp", "2.5")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("rejects decimal XP", page.locator(".row", has_text="Bad").count() == 0)
    # edit gym: multi -> daily should collapse the 7 Sep double-log to one
    page.locator(".row", has_text="Gym session").locator("button[data-act=edit-habit]").click(); page.wait_for_timeout(50)
    check("habit edit prefilled", page.input_value("#f-h-name") == "Gym session" and page.input_value("#f-h-xp") == "50")
    page.select_option("#f-h-mode", "daily")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    gymlogs = [e for e in d["log"] if e["name"] == "Gym session"]
    check("multi->daily collapses duplicate day entries", len(gymlogs) == 1, len(gymlogs))
    page.locator(".row", has_text="Cold shower").locator("button[data-act=del-habit]").click(); page.wait_for_timeout(80)
    check("delete habit", page.locator(".row", has_text="Cold shower").count() == 0)
    page.screenshot(path="shots/manage_habits.png", full_page=True)

    # ---------- manage: objectives ----------
    page.locator("button[data-act=seg][data-id=goals]").click()
    page.fill("#f-g-name", "Get Equita return offer")
    page.fill("#f-g-xp", "500")
    page.select_option("#f-g-cat", label="Work")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(50)
    check("add objective", page.locator(".row", has_text="Equita").count() == 1)
    page.locator(".row", has_text="Run 10k").locator(".tick").click(); page.wait_for_timeout(50)
    check("complete objective from manage", page.locator("h2", has_text="Completed").count() == 1)
    page.locator(".row", has_text="Run 10k").locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-xp", "400")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    run = [e for e in d["log"] if e["type"] == "goal"]
    check("editing a completed objective's XP updates its log entry", run and run[0]["xp"] == 400, run)
    page.locator(".row", has_text="Run 10k").locator("button[data-act=del-goal]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("deleting a completed objective removes its XP", not [e for e in d["log"] if e["type"] == "goal"])

    # ---------- target & data ----------
    page.locator("button[data-act=seg][data-id=target]").click()
    page.fill("#f-target", "5000")
    page.fill("#f-deadline", "2026-09-01")
    page.locator("button[data-act=save-target]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("rejects deadline before start", d["target"] == 10000)
    page.fill("#f-deadline", "2026-12-31")
    page.locator("button[data-act=save-target]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("saves valid target", d["target"] == 5000)
    check("persistence note shown (not preview warning)", page.locator(".note.warn").count() == 0)
    check("default reminder times listed", [c.inner_text().strip("×").strip() for c in page.locator(".timechip").all()] == ["15:00", "18:00", "21:00"])
    page.locator(".timechip", has_text="18:00").locator("button").click(); page.wait_for_timeout(50)
    check("remove a reminder time", page.locator(".timechip").count() == 2)
    page.fill("#f-rem-time", "12:30")
    page.locator("button[data-act=rem-add]").click(); page.wait_for_timeout(50)
    check("add a reminder time, kept sorted", [c.inner_text().strip("×").strip() for c in page.locator(".timechip").all()] == ["12:30", "15:00", "21:00"])
    page.fill("#f-rem-time", "15:00")
    page.locator("button[data-act=rem-add]").click(); page.wait_for_timeout(50)
    check("duplicate time rejected", page.locator(".timechip").count() == 3)
    check("shortcut steps use the first time", "12:30" in page.locator(".steps").inner_text())
    page.locator("#f-badge").uncheck(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("badge preference persisted off", d["reminders"]["badge"] is False and d["reminders"]["times"] == ["12:30", "15:00", "21:00"])
    page.locator("#f-badge").check(); page.wait_for_timeout(50)
    page.screenshot(path="shots/target.png", full_page=True)

    # home after edits
    page.locator("button[data-act=tab][data-id=home]").click()
    page.wait_for_selector(".hero")
    check("pace line mentions days left", "day" in page.inner_text(".pace") and "5,000" in page.inner_text(".yearhead"))
    page.screenshot(path="shots/home_after.png", full_page=True)
    check("no JS errors through whole flow", not errors, errors)
    ctx.close()

    # ---------- 2. corrupted storage + v1 migration + malformed import ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    errs2 = []
    page.on("pageerror", lambda e: errs2.append(str(e)))
    page.goto(URL); page.wait_for_selector(".hero")
    page.evaluate("localStorage.setItem('level.v2', '{not json')")
    page.reload(); page.wait_for_selector(".hero")
    check("corrupted storage falls back to seed without crashing", not errs2 and page.inner_text(".total").strip() == "0")
    check("corrupted blob preserved for recovery", page.evaluate("localStorage.getItem('level.broken')") == "{not json")
    v1 = {"habits":[{"id":"h1","name":"Gym","xp":50,"mode":"multi"}],
          "goals":[{"id":"g1","name":"Goal","xp":300,"done":True}],
          "log":[{"id":"a","habitId":"h1","name":"Gym","xp":50,"date":"2026-09-01","at":1},
                 {"id":"goal-g1","goalId":"g1","name":"Goal","xp":300,"date":"2026-09-02","at":2},
                 {"id":"bad","habitId":"h1","name":"Gym","xp":50,"date":"2026-02-31","at":3}],
          "target":10000,"deadline":"2026-12-31","start":"2026-09-01"}
    page.evaluate("localStorage.removeItem('level.v2')")
    page.evaluate("v => localStorage.setItem('level.v1', JSON.stringify(v))", v1)
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("v1 data migrates (habitId/goalId -> type/refId)", d["log"][0]["type"] == "habit" and d["log"][1]["type"] == "goal")
    check("invalid date 2026-02-31 dropped on migration", len(d["log"]) == 2)
    check("migrated habit assigned to a real section", d["habits"][0]["cat"] in {c["id"] for c in d["cats"]})
    check("migrated total is 350", page.inner_text(".total").strip() == "350")
    check("no errors during migration", not errs2, errs2)

    # goal.done inconsistent with log gets corrected
    page.evaluate("""() => { const s=JSON.parse(localStorage.getItem('level.v2'));
      s.goals.push({id:'gx',name:'Ghost',xp:999,cat:s.cats[0].id,done:true,doneDate:'2026-09-01'});
      localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    ghost = [g for g in d["goals"] if g["id"] == "gx"][0]
    check("done flag without a log entry is reset to open", ghost["done"] is False and ghost["doneDate"] is None)

    page.evaluate("""() => { const s=JSON.parse(localStorage.getItem('level.v2'));
      s.tasks=[{id:'t1',name:'ok',xp:5,cat:'nope',date:'2026-09-01',done:true},{id:'t2',name:'bad date',xp:5,date:'2026-13-01'},null];
      s.reminders={times:['25:00','9:00','15:00','15:00'],badge:'yes'};
      localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("bad tasks dropped, orphan section repaired, done-without-log reset", len(d["tasks"]) == 1 and d["tasks"][0]["cat"] in {c["id"] for c in d["cats"]} and d["tasks"][0]["done"] is False)
    check("invalid reminder times dropped and deduplicated", d["reminders"]["times"] == ["15:00"] and d["reminders"]["badge"] is True)

    # XSS-ish names render as text, not markup
    page.evaluate("""() => { const s=JSON.parse(localStorage.getItem('level.v2'));
      s.habits.push({id:'x',name:'<img src=x onerror=alert(1)> & "quotes"',xp:5,mode:'daily',cat:s.cats[0].id});
      localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    check("html in names is escaped", page.locator("img[src=x]").count() == 0 and '<img' in page.locator(".row", has_text="quotes").inner_text())
    ctx.close()

    # ---------- 3. DST boundary: Sun 25 Oct 2026, clocks go back in Rome ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 10, 24, 23, 55, 0, tzinfo=ROME))
    page.goto(URL); page.wait_for_selector(".hero")
    page.locator(".row[data-act=log]", has_text="Gym session").click(); page.wait_for_timeout(50)
    page.clock.run_for(10 * 60 * 1000)   # -> 00:05 on 25 Oct
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(80)
    page.locator(".row[data-act=log]", has_text="Gym session").click(); page.wait_for_timeout(50)
    page.clock.run_for(26 * 60 * 60 * 1000)  # through the DST change to 26 Oct ~01:05 (25h day)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(80)
    page.locator(".row[data-act=log]", has_text="Gym session").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    dates = sorted(e["date"] for e in d["log"])
    check("entries across the DST change land on 24, 25, 26 Oct", dates == ["2026-10-24", "2026-10-25", "2026-10-26"], dates)
    check("streak counts 3 across DST", "3 day streak" in page.inner_text(".streak"), page.inner_text(".streak"))
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    check("calendar moved to October after rollover", "October 2026" in page.inner_text(".calhead"))
    check("Oct 1 2026 is a Thursday -> 3 blanks", all("blank" in c.get_attribute("class") for c in page.locator(".cal .day").all()[:3]) and page.locator(".cal .day").all()[3].inner_text().startswith("1"))
    ctx.close()

    # ---------- 4. desktop width sanity + manifest/sw reachable ----------
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(URL); page.wait_for_selector(".hero")
    w = page.evaluate("document.querySelector('.app').getBoundingClientRect().width")
    check("content capped at 480px on desktop", 470 <= w <= 481, w)
    r = page.request.get("http://localhost:8765/manifest.json")
    check("manifest reachable and valid", r.ok and r.json()["display"] == "standalone")
    r = page.request.get("http://localhost:8765/sw.js")
    check("service worker file reachable", r.ok)
    page.wait_for_timeout(600)
    sw = page.evaluate("navigator.serviceWorker.getRegistrations().then(r => r.length)")
    check("service worker registers", sw >= 1, sw)
    ctx.close()
    browser.close()

server.terminate()
print("\n%d failures" % len(fails))
for f in fails: print(" -", f)
sys.exit(1 if fails else 0)
