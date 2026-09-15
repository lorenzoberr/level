"""
End-to-end tests for the Level app. Runs the real app in headless Chromium at
iPhone size, Rome timezone, with a controllable clock.

    pip install playwright tzdata && python -m playwright install chromium
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

# The app installs empty behind a first-open setup screen. Tests that exercise
# features inject this classic fixture (setup already completed), mirroring an
# install that is actually in use; normalise() fills every field not listed.
DEMO = """() => localStorage.setItem('level.v2', JSON.stringify({
  setup: true,
  cats: [{id:'c-fit',name:'Fitness',color:'#22C55E'},
         {id:'c-school',name:'School',color:'#3B82F6'},
         {id:'c-personal',name:'Personal',color:'#8B5CF6'}],
  habits: [{id:'h1',name:'Gym session',xp:50,mode:'multi',cat:'c-fit'},
           {id:'h2',name:'8k steps',xp:20,mode:'daily',cat:'c-fit'},
           {id:'h3',name:'Study 2 hours',xp:30,mode:'daily',cat:'c-school'},
           {id:'h4',name:'Read 20 minutes',xp:10,mode:'daily',cat:'c-personal'},
           {id:'h5',name:'Sleep before midnight',xp:15,mode:'daily',cat:'c-personal'}],
  goals: [{id:'g1',name:'Bench press bodyweight',xp:300,cat:'c-fit'},
          {id:'g2',name:'Run 10k under 50 min',xp:250,cat:'c-fit'},
          {id:'g3',name:'Finish coursework draft',xp:200,cat:'c-school'}],
  target: 10000, deadline: '2026-12-31', lastTaskCat: 'c-school'
}))"""
# The classic fixture plus a working budget: an allowance and three categories
# (two spending, one investing). Months start empty; tests enter the spends.
FIN_DEMO = DEMO.replace("lastTaskCat: 'c-school'", """lastTaskCat: 'c-school',
  finance: { income: 1200.5, months: {},
    categories: [{id:'f1',name:'Groceries',budget:250,xp:80,dir:'under'},
                 {id:'f2',name:'Investing',budget:100,xp:60,dir:'over'},
                 {id:'f3',name:'Eating out',budget:120,xp:40,dir:'under'}] }""")
def fin_boot(page):
    page.goto(URL)
    page.evaluate(FIN_DEMO)
    page.reload()
    page.wait_for_selector(".hero")

def demo_boot(page):
    page.goto(URL)
    page.evaluate(DEMO)
    page.reload()
    page.wait_for_selector(".hero")

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
    demo_boot(page)
    check("no JS errors on load", not errors, errors)
    check("header shows local date", "Monday 7 September" in page.inner_text("#today"), page.inner_text("#today"))
    check("starts at level 1 / 0 XP", "Level 1" in page.inner_text(".lvl") and page.inner_text(".total").strip() == "0")
    check("three seeded sections plus the weight section on home", page.locator("h2 .dot").count() == 4)
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
    page.locator("button[data-act=go-tasks]").click(); page.wait_for_timeout(50)
    check("+ Add goal opens the Tasks tab with the form focused",
          page.evaluate("document.activeElement && document.activeElement.id") == "f-t-name"
          and page.locator("#f-t-date").count() == 1)
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
    check("two goals today, 0/2 done on the Tasks tab", "0/2 done" in page.locator(".goals-head", has_text="Today").inner_text())
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(50)
    check("home shows the same two goals, 6 left", page.locator(".row.task").count() == 2 and "6 left" in page.inner_text(".pendline"))
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

    # complete an objective from its section box, undo it from home
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_timeout(80)
    check("each section is a box holding its habits and objectives",
          page.locator(".secbox").count() == 3
          and page.locator(".secbox", has_text="Fitness").locator(".row", has_text="Gym session").count() == 1
          and page.locator(".secbox", has_text="Fitness").locator(".row", has_text="Bench press").count() == 1)
    page.locator(".secbox .row", has_text="Bench press").locator(".tick").click(); page.wait_for_timeout(80)
    check("objective ticked inside its box", "1 done" in page.locator(".secbox", has_text="Fitness").inner_text()
          and "done" in (page.locator(".secbox .row", has_text="Bench press").get_attribute("class") or ""))
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(50)
    check("objective adds XP", page.inner_text(".total").strip() == "400")
    check("home lists habits only, no objective rows", page.locator(".row[data-act=goal]").count() == 0)
    page.locator("button[data-act=undo]").click(); page.wait_for_timeout(50)
    check("undo reopens objective and removes XP", page.inner_text(".total").strip() == "100")

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
    check("unfinished goal from yesterday shown under Unfinished tasks", "Unfinished tasks" in page.inner_text("#view") and "Set for 7 Sept" in page.locator(".row.task", has_text="Finish marketing homework").inner_text())
    page.locator("button[data-act=task-move]").click(); page.wait_for_timeout(50)
    check("move to today", "Unfinished tasks" not in page.inner_text("#view") and "0/1 done" in page.locator(".goals-head").inner_text())
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

    # ---------- sections tab: section boxes ----------
    page.locator("button[data-act=tab][data-id=sections]").click()
    page.wait_for_selector(".secbox")
    check("no forms open until asked", page.locator("#view .form").count() == 0)
    page.locator("button[data-act=add-cat]").click(); page.wait_for_timeout(50)
    page.fill("#f-cat-name", "Career")
    page.locator(".sw[data-id='#F97316']").click()
    page.locator("button[data-act=save-cat]").click(); page.wait_for_timeout(50)
    check("add section makes a new box", page.locator(".secbox", has_text="Career").count() == 1)
    page.locator(".secbox", has_text="Career").locator("button[data-act=edit-cat]").click()
    page.wait_for_timeout(50)
    check("edit form prefilled, inside its own box",
          page.input_value("#f-cat-name") == "Career"
          and page.locator(".sw[aria-pressed=true]").get_attribute("data-id") == "#F97316"
          and page.locator(".secbox", has_text="Career").locator("#f-cat-name").count() == 1)
    page.fill("#f-cat-name", "Work")
    page.locator("button[data-act=save-cat]").click(); page.wait_for_timeout(50)
    check("rename section", page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).count() == 1 and page.locator(".secbox", has_text="Career").count() == 0)
    page.locator(".secbox", has_text="School").locator("button[data-act=del-cat]").click(); page.wait_for_timeout(80)
    check("delete section", page.locator(".secbox", has_text="School").count() == 0)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    orphan = [h for h in d["habits"] if h["cat"] not in {c["id"] for c in d["cats"]}]
    check("deleted section's items reassigned, no orphans", not orphan, orphan)

    # ---------- sections tab: habits ----------
    page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator("button[data-act=add-habit]").click(); page.wait_for_timeout(50)
    check("add-habit form opens inside that box with its section preset",
          page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator("#f-h-name").count() == 1
          and page.evaluate("document.getElementById('f-h-cat').selectedOptions[0].text") == "Work")
    page.fill("#f-h-name", "Cold shower")
    page.fill("#f-h-xp", "12")
    page.select_option("#f-h-mode", "daily")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(50)
    check("add habit", page.locator(".row", has_text="Cold shower").count() == 1)
    check("form closes after a successful save", page.locator("#f-h-name").count() == 0)
    page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator("button[data-act=add-habit]").click(); page.wait_for_timeout(50)
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

    # ---------- sections tab: objectives ----------
    page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator("button[data-act=add-objective]").click(); page.wait_for_timeout(50)
    check("add-objective form opens inside that box with its section preset",
          page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator("#f-g-name").count() == 1
          and page.evaluate("document.getElementById('f-g-cat').selectedOptions[0].text") == "Work")
    page.fill("#f-g-name", "Get Equita return offer")
    page.fill("#f-g-xp", "500")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(50)
    check("add objective", page.locator(".secbox").filter(has=page.locator(".sechead b", has_text="Work")).locator(".row", has_text="Equita").count() == 1)
    page.locator(".row", has_text="Run 10k").locator(".tick").click(); page.wait_for_timeout(50)
    check("complete objective from its box", "done" in (page.locator(".row", has_text="Run 10k").get_attribute("class") or "")
          and "1 done" in page.locator(".secbox", has_text="Fitness").inner_text())
    page.locator(".row", has_text="Run 10k").locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-xp", "400")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    run = [e for e in d["log"] if e["type"] == "goal"]
    check("editing a completed objective's XP updates its log entry", run and run[0]["xp"] == 400, run)
    page.locator(".row", has_text="Run 10k").locator("button[data-act=del-goal]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("deleting a completed objective removes its XP", not [e for e in d["log"] if e["type"] == "goal"])

    # ---------- settings tab: target & data ----------
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(50)
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
    # pinned near the fixture dates, or the missed-days penalty (correctly)
    # fines the gap between the v1 entries and the real today
    page.clock.install(time=datetime.datetime(2026, 9, 3, 9, 0, 0, tzinfo=ROME))
    demo_boot(page)
    page.evaluate("localStorage.setItem('level.v2', '{not json')")
    page.reload(); page.wait_for_selector("#f-su-name")
    check("corrupted storage falls back to a brand-new install without crashing",
          not errs2 and "Welcome to Level" in page.inner_text("#view"))
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
    demo_boot(page)
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

    # ---------- 3b. weekly habits: Sat 12 Sep 2026, mid-week pressure ----------
    # Sat 12 Sep 2026 sits in the week starting Mon 7 Sep. Two days are left,
    # so a fresh "3x a week" habit is already unmissable.
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    werr = []
    page.on("pageerror", lambda e: werr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 12, 10, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)

    page.locator("button[data-act=tab][data-id=sections]").click()
    page.locator(".secbox", has_text="Fitness").locator("button[data-act=add-habit]").click(); page.wait_for_timeout(50)
    check("weekly fields hidden until 'Times a week' is picked",
          "hidden" in page.locator("#f-h-weekly").get_attribute("class"))
    page.fill("#f-h-name", "Weekly gym")
    page.fill("#f-h-xp", "50")
    page.select_option("#f-h-mode", "weekly")
    check("picking 'Times a week' reveals the count and bonus fields",
          "hidden" not in page.locator("#f-h-weekly").get_attribute("class"))
    check("switching mode keeps what was already typed", page.input_value("#f-h-name") == "Weekly gym")
    page.fill("#f-h-per", "3")
    page.fill("#f-h-bonus", "60")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(60)
    check("weekly habit listed with its count and bonus",
          "3× a week, +60 bonus" in page.locator(".row", has_text="Weekly gym").inner_text(),
          page.locator(".row", has_text="Weekly gym").inner_text())

    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)
    gym = lambda: page.locator(".row[data-act=log]", has_text="Weekly gym")
    check("starts at 0 of 3", "0 of 3 this week" in gym().inner_text(), gym().inner_text())
    check("3 pips, none filled", gym().locator(".pips i").count() == 3
          and not any(i.get_attribute("style") for i in gym().locator(".pips i").all()))
    check("Saturday with 3 still to go says go today", "go today" in gym().inner_text(), gym().inner_text())

    gym().click(); page.wait_for_timeout(60)
    check("one session logged: 2 to go", "1 of 3 this week" in gym().inner_text() and "2 left, go today" in gym().inner_text(), gym().inner_text())
    check("first pip filled", sum(1 for i in gym().locator(".pips i").all() if i.get_attribute("style")) == 1)
    gym().click(); page.wait_for_timeout(60)
    check("two sessions logged: 1 to go", "2 of 3 this week" in gym().inner_text(), gym().inner_text())
    check("XP is the sessions only, no bonus yet", page.inner_text(".total").strip() == "100", page.inner_text(".total"))
    gym().click(); page.wait_for_timeout(60)
    check("third session completes the week", "3 of 3 this week" in gym().inner_text() and "done, +60 bonus" in gym().inner_text(), gym().inner_text())
    check("bonus paid on top of the three sessions", page.inner_text(".total").strip() == "210", page.inner_text(".total"))
    check("bonus toast shown", "bonus +60 XP" in page.inner_text("#toast"), page.inner_text("#toast"))
    page.screenshot(path="shots/weekly_done.png", full_page=True)

    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    bonuses = [e for e in d["log"] if e["type"] == "bonus"]
    check("exactly one bonus entry, dated to the session that finished the week",
          len(bonuses) == 1 and bonuses[0]["date"] == "2026-09-12" and bonuses[0]["xp"] == 60, bonuses)
    check("total XP is still just the sum of the log", sum(e["xp"] for e in d["log"]) == 210)

    # a fourth session in the same week pays its XP but not a second bonus
    gym().click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("extra session pays no second bonus",
          len([e for e in d["log"] if e["type"] == "bonus"]) == 1 and page.inner_text(".total").strip() == "260")
    check("row counts the extra session", "4 this week" in gym().inner_text(), gym().inner_text())

    # the calendar shows the bonus as its own entry, and will not let you remove it
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    bonus_entry = page.locator(".entry", has_text="in a week")
    check("bonus appears in the day's entries, tagged", bonus_entry.count() == 1 and "weekly bonus" in bonus_entry.inner_text())
    check("bonus has no Remove button of its own", bonus_entry.locator("button[data-act=rm-entry]").count() == 0)
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)

    # undo steps over the bonus; dropping under the count takes the bonus back
    page.locator("button[data-act=undo]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("undo removes a session, not the bonus",
          len([e for e in d["log"] if e["type"] == "bonus"]) == 1 and page.inner_text(".total").strip() == "210")
    page.locator("button[data-act=undo]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("falling under the count takes the bonus back",
          not [e for e in d["log"] if e["type"] == "bonus"] and page.inner_text(".total").strip() == "100", page.inner_text(".total"))
    check("row reverts to 2 of 3", "2 of 3 this week" in gym().inner_text(), gym().inner_text())
    gym().click(); page.wait_for_timeout(60)
    check("re-earning pays the bonus exactly once again", page.inner_text(".total").strip() == "210")

    # ---------- the week rolls over on Monday ----------
    page.clock.run_for(2 * 24 * 60 * 60 * 1000)   # Sat 12 -> Mon 14 Sep
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(120)
    check("header moved to Monday 14 September", "Monday 14 September" in page.inner_text("#today"), page.inner_text("#today"))
    check("weekly counter resets on Monday", "0 of 3 this week" in gym().inner_text(), gym().inner_text())
    check("Monday with a full week ahead does not nag", "go today" not in gym().inner_text(), gym().inner_text())
    check("last week's XP and bonus are untouched", page.inner_text(".total").strip() == "210")

    # raising the count must not strip a bonus already earned in an earlier week
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_timeout(60)
    page.locator(".row", has_text="Weekly gym").locator("button[data-act=edit-habit]").click(); page.wait_for_timeout(60)
    check("edit form prefilled with the weekly settings",
          page.input_value("#f-h-per") == "3" and page.input_value("#f-h-bonus") == "60")
    page.fill("#f-h-per", "4")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("raising 3x to 4x leaves last week's bonus alone",
          len([e for e in d["log"] if e["type"] == "bonus"]) == 1 and sum(e["xp"] for e in d["log"]) == 210, d["log"])
    check("weekly settings survive a save", d["habits"][-1]["perWeek"] == 4 and d["habits"][-1]["bonus"] == 60)

    # switching a weekly habit to once-a-day collapses that day and drops the live bonus
    page.locator(".row", has_text="Weekly gym").locator("button[data-act=edit-habit]").click(); page.wait_for_timeout(60)
    page.select_option("#f-h-mode", "daily")
    page.locator("button[data-act=save-habit]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    sess = [e for e in d["log"] if e["type"] == "habit" and e["name"] == "Weekly gym"]
    check("weekly -> once a day collapses the repeated day to one entry", len(sess) == 1, sess)
    check("no JS errors anywhere in the weekly flow", not werr, werr)
    ctx.close()

    # ---------- 3c. fixes: section delete, badge count, reset wording ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 8, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)
    # a daily goal in School, then delete the School section
    page.locator("button[data-act=tab][data-id=tasks]").click(); page.wait_for_timeout(50)
    page.fill("#f-t-name", "Homework"); page.fill("#f-t-xp", "40")
    page.select_option("#f-t-cat", label="School")
    page.locator("button[data-act=task-add]").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_selector(".secbox")
    page.locator(".secbox", has_text="School").locator("button[data-act=del-cat]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    cat_ids = {c["id"] for c in d["cats"]}
    check("deleting a section moves its daily goals too, no orphans",
          all(t["cat"] in cat_ids for t in d["tasks"]), [t["cat"] for t in d["tasks"]])
    check("lastTaskCat is not left pointing at the deleted section", d["lastTaskCat"] in cat_ids)

    # badge counts goals carried over from earlier days, not just today's
    page.evaluate("""() => { window.__badge=[]; navigator.setAppBadge = n => { window.__badge.push(n); return Promise.resolve(); };
                            navigator.clearAppBadge = () => { window.__badge.push(0); return Promise.resolve(); }; }""")
    page.clock.run_for(24 * 60 * 60 * 1000)   # -> 9 Sep, yesterday's goal is now overdue
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(120)
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(80)
    overdue = page.locator(".row.task", has_text="Homework").count()
    calls = page.evaluate("window.__badge")
    check("badge and 'left' count include unfinished goals from earlier days",
          overdue == 1 and calls and calls[-1] == 5, (overdue, calls, page.inner_text(".pendline")))
    ctx.close()

    # ---------- 3d. dark mode ----------
    ctx = browser.new_context(color_scheme="dark", **IPHONE)
    page = ctx.new_page()
    derr = []
    page.on("pageerror", lambda e: derr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 8, 22, 0, 0, tzinfo=ROME))
    demo_boot(page)
    check("a dark phone gets the dark theme", page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark")
    check("page background is the dark token",
          page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(11, 18, 32)",
          page.evaluate("getComputedStyle(document.body).backgroundColor"))
    check("status bar colour follows the theme", page.get_attribute("#tc", "content") == "#0B1220")
    check("color-scheme is set so native controls follow",
          page.evaluate("getComputedStyle(document.documentElement).colorScheme") == "dark")

    # every painted surface must come from a token: nothing may stay pure white
    whites = []
    for t in ("home", "tasks", "sections", "calendar", "progress", "settings", "finances"):
        page.locator("button[data-act=tab][data-id=%s]" % t).click(); page.wait_for_timeout(80)
        whites += page.evaluate("""() => [...document.querySelectorAll('#view *, .tabs, .tabs *, .toast')]
            .filter(e => !e.closest('.hero'))   // the hero bar is white on its blue gradient, by design
            .filter(e => getComputedStyle(e).backgroundColor === 'rgb(255, 255, 255)')
            .map(e => e.tagName + '.' + (e.className || '')).slice(0, 8)""")
    check("no surface is left hardcoded white in dark mode", not whites, whites)
    page.screenshot(path="shots/dark_settings.png", full_page=True)

    # forcing a theme overrides the phone, and survives a reload without flashing
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)   # the sweep ends on Finances
    page.locator("button[data-act=theme][data-id=light]").click(); page.wait_for_timeout(60)
    check("forcing light overrides a dark phone",
          page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
          and page.get_attribute("#tc", "content") == "#F3F5F9")
    page.reload(); page.wait_for_selector(".hero")
    check("the head script applies the forced theme before the first paint",
          page.evaluate("document.documentElement.getAttribute('data-theme')") == "light")
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=theme][data-id=auto]").click(); page.wait_for_timeout(60)
    check("back on auto it follows the phone again",
          page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark")
    check("no JS errors in dark mode", not derr, derr)
    ctx.close()

    # a light phone is unaffected
    ctx = browser.new_context(color_scheme="light", **IPHONE)
    page = ctx.new_page()
    demo_boot(page)
    check("a light phone still gets the light theme",
          page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
          and page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(243, 245, 249)")
    ctx.close()

    # ---------- 3e. backup nudge ----------
    ctx = browser.new_context(accept_downloads=True, **IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 8, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)
    check("a fresh install does not nag about backups", page.locator(".remind.backup").count() == 0)
    page.locator(".row[data-act=log]", has_text="8k steps").click(); page.wait_for_timeout(60)
    check("nor does it after one day of use", page.locator(".remind.backup").count() == 0)

    # wind the clock back by moving `start`, which is what the nudge counts from
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.start = '2026-08-19'; s.lastBackup = null;
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    check("after 20 days with no backup, Home says so",
          page.locator(".remind.backup").count() == 1
          and "20 days of entries" in page.locator(".remind.backup").inner_text(),
          page.locator(".remind.backup").inner_text() if page.locator(".remind.backup").count() else "no nudge")
    page.screenshot(path="shots/backup_nudge.png", full_page=True)

    with page.expect_download() as dl:
        page.locator(".remind.backup button[data-act=export]").click()
    check("the nudge's button exports a dated backup file",
          dl.value.suggested_filename == "level-backup-2026-09-08.json", dl.value.suggested_filename)
    page.wait_for_timeout(120)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("exporting records the backup date", d["lastBackup"] == "2026-09-08", d.get("lastBackup"))
    check("the nudge goes away once backed up", page.locator(".remind.backup").count() == 0)
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    check("settings shows when the last backup was", "Last backup 8 Sept 2026" in page.inner_text("#view"), page.inner_text("#view")[:200])

    # it comes back when the backup goes stale
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.lastBackup = '2026-08-20';
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    check("a stale backup brings the nudge back",
          page.locator(".remind.backup").count() == 1
          and "Last backup 19 days ago" in page.locator(".remind.backup").inner_text(),
          page.locator(".remind.backup").inner_text() if page.locator(".remind.backup").count() else "no nudge")
    ctx.close()

    # ---------- 3f. weight tracking ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    werr2 = []
    page.on("pageerror", lambda e: werr2.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 10, 8, 0, 0, tzinfo=ROME))  # Thursday
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)

    check("weight card on home with a log field", page.locator(".wcard #f-wt").count() == 1)
    # goal set inline on first use, with a comma decimal like the Italian keypad types
    page.fill("#f-w-goal-h", "70")
    page.locator("button[data-act=wt-goal-home]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("inline goal saved and its row gone", d["weight"]["goal"] == 70 and page.locator("#f-w-goal-h").count() == 0)

    page.fill("#f-wt", "72,6")
    page.locator("button[data-act=wt-log]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("comma decimal logged as 72.6", d["weight"]["entries"] == [{"date": "2026-09-10", "kg": 72.6}], d["weight"]["entries"])
    check("button flips to Update", "Update" in page.locator("button[data-act=wt-log]").inner_text())
    page.fill("#f-wt", "72.4")
    page.locator("button[data-act=wt-log]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("logging the same day again corrects it, one entry only",
          d["weight"]["entries"] == [{"date": "2026-09-10", "kg": 72.4}], d["weight"]["entries"])
    check("weight never touches XP", page.inner_text(".total").strip() == "0" and d["log"] == [])
    for bad in ("7,2", "500", "abc"):
        page.fill("#f-wt", bad)
        page.locator("button[data-act=wt-log]").click(); page.wait_for_timeout(50)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("nonsense weights rejected", len(d["weight"]["entries"]) == 1 and d["weight"]["entries"][0]["kg"] == 72.4)

    # two settled weeks of history + this week: averages, line, goal line, hollow point
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.weight.entries = [
          {date:'2026-08-24',kg:73.4},{date:'2026-08-26',kg:73.0},{date:'2026-08-28',kg:73.2}, // avg 73.2
          {date:'2026-08-31',kg:73.0},{date:'2026-09-02',kg:72.6},{date:'2026-09-04',kg:72.8}, // avg 72.8
          {date:'2026-09-07',kg:72.2},{date:'2026-09-08',kg:72.6},{date:'2026-09-10',kg:72.1}  // this week: avg 72.3
        ];
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    meta = page.locator(".wmeta").inner_text()
    check("weekly average shown for the running week", "72.3 kg" in meta and "3 mornings so far" in meta, meta)
    check("change against last week's average", "0.5 kg vs last week" in meta, meta)
    check("distance to goal", "2.3 kg above goal" in meta, meta)
    svg = page.locator(".wchart svg")
    check("one point per week", svg.locator("circle").count() == 3)
    check("running week's point is hollow", svg.locator("circle[stroke-width='2']").count() == 1)
    check("weekly points joined by a line", svg.locator("polyline").count() == 1)
    check("goal drawn as a labelled dashed line",
          svg.locator("line[stroke-dasharray='5 4']").count() == 1 and "Goal 70.0" in svg.text_content())
    check("segment into the running week is dashed", svg.locator("line[stroke-dasharray='4 4']").count() == 1)
    page.screenshot(path="shots/weight_chart.png", full_page=True)

    # calendar: fix yesterday, remove it, and no weight form on a future day
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    page.locator(".cal .day", has_text="9").first.click(); page.wait_for_timeout(60)
    page.fill("#f-wt-day", "71.9")
    page.locator("button[data-act=wt-log-day]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("a past day's weight can be added from the calendar",
          {"date": "2026-09-09", "kg": 71.9} in d["weight"]["entries"], d["weight"]["entries"])
    page.locator("button[data-act=wt-del-day]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("and removed again", not [e for e in d["weight"]["entries"] if e["date"] == "2026-09-09"])
    page.locator(".cal .day", has_text="25").first.click(); page.wait_for_timeout(60)
    check("no weight form on a future day", page.locator("#f-wt-day").count() == 0)

    # a corrupted backup keeps the sane entries and drops the junk
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.weight.goal = 'seventy';
        s.weight.entries.push({date:'2026-09-01',kg:9999},{date:'not-a-date',kg:72},{date:'2026-09-03'},
                              {date:'2026-09-02',kg:72.0},{date:'2026-09-02',kg:71.0});
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    days = [e["date"] for e in d["weight"]["entries"]]
    check("normalise drops junk weights, keeps one entry per day",
          d["weight"]["goal"] is None and len(days) == len(set(days))
          and all(20 <= e["kg"] <= 300 for e in d["weight"]["entries"]), d["weight"])
    check("no JS errors in the weight flow", not werr2, werr2)
    ctx.close()

    # ---------- 3g. objective deadlines: full XP on time, half after ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    gerr = []
    page.on("pageerror", lambda e: gerr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 10, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_selector(".secbox")
    page.locator(".secbox", has_text="Fitness").locator("button[data-act=add-objective]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-name", "Bench press 80 kg")
    page.fill("#f-g-xp", "300")
    page.fill("#f-g-deadline", "2026-11-30")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    row = lambda: page.locator(".secbox .row", has_text="80 kg")
    check("objective shows its deadline", "by 30 Nov 2026" in row().inner_text(), row().inner_text())
    row().locator(".tick").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("completed before the deadline pays the full XP",
          [e for e in d["log"] if e["type"] == "goal"][0]["xp"] == 300)
    row().locator(".tick").click(); page.wait_for_timeout(60)   # reopen
    # move the deadline into the past
    row().locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    check("deadline prefilled in the edit form", page.input_value("#f-g-deadline") == "2026-11-30")
    page.fill("#f-g-deadline", "2026-09-01")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    check("an overdue objective says so and shows the halved amount",
          "was due 1 Sept 2026, half XP now" in row().inner_text()
          and row().locator(".xp").inner_text().strip() == "150", row().inner_text())
    row().locator(".tick").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("completed after the deadline pays half",
          [e for e in d["log"] if e["type"] == "goal"][0]["xp"] == 150)
    check("done row explains the halving", "Half XP, after the deadline." in row().inner_text(), row().inner_text())
    # editing the done objective re-judges its entry against the deadline
    row().locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-xp", "400")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("raising the XP of a late completion keeps it halved",
          [e for e in d["log"] if e["type"] == "goal"][0]["xp"] == 200)
    row().locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-deadline", "")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("removing the deadline restores the full amount",
          [e for e in d["log"] if e["type"] == "goal"][0]["xp"] == 400
          and sum(e["xp"] for e in d["log"]) == 400)
    # a nonsense deadline in a backup is dropped
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.goals[0].deadline = 'someday';
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("junk deadline repaired to none", d["goals"][0]["deadline"] is None)
    check("no JS errors in the deadline flow", not gerr, gerr)
    ctx.close()

    # ---------- 3h. progress tab ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    perr = []
    page.on("pageerror", lambda e: perr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 12, 10, 0, 0, tzinfo=ROME))  # Saturday
    demo_boot(page)
    # deterministic history: target 10000 from 13 Aug to 31 Dec = 140 days, ~71.4/day
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.target = 10000; s.start = '2026-08-13'; s.deadline = '2026-12-31';
        s.habits.find(h => h.id === 'h1').mode = 'weekly';
        s.habits.find(h => h.id === 'h1').perWeek = 3;
        s.habits.find(h => h.id === 'h1').bonus = 60;
        let n = 0; const put = (type, refId, name, xp, date) =>
          s.log.push({id: 'p' + (n++), type, refId, name, xp, date, at: n});
        // this week (Mon 7 - Sat 12): 470 XP, pace needs round(71.43*6)=429
        for (const d of ['2026-09-07', '2026-09-09', '2026-09-11']) put('habit', 'h1', 'Gym session', 50, d);
        put('bonus', 'h1', 'Gym session — 3× in a week', 60, '2026-09-11');
        for (const d of ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11']) put('habit', 'h3', 'Study 2 hours', 30, d);
        for (const d of ['2026-09-08', '2026-09-10', '2026-09-12']) put('habit', 'h2', '8k steps', 20, d);
        for (const d of ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-11', '2026-09-12']) put('habit', 'h4', 'Read 20 minutes', 10, d);
        put('habit', 'h3', 'Study 2 hours', 500, '2026-09-02');   // last week: 500 + 4x10 filler
        // no unlogged gaps, or the missed-days penalty (correctly) rewrites the arithmetic
        for (const d of ['2026-09-03', '2026-09-04', '2026-09-05', '2026-09-06'])
          put('habit', 'h4', 'Read 20 minutes', 10, d);
        s.tasks.push({id: 'tx', name: 'Email the tutor', xp: 15, cat: s.cats[1].id, date: '2026-09-10', done: false});
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    page.locator("button[data-act=tab][data-id=progress]").click(); page.wait_for_timeout(80)
    check("week is the default period", page.locator("button[data-act=prog][data-id=week]").get_attribute("aria-pressed") == "true")
    check("weekly XP against the pace the target asks for",
          "470" in page.inner_text(".prognum") and "asks for about 429" in page.inner_text(".proglab"), page.inner_text(".proglab"))
    check("last week comparison shown", "Last week: 540 XP" in page.inner_text(".proglab"), page.inner_text(".proglab"))
    check("evaluative verdict: ahead of pace", "41 XP ahead" in page.inner_text(".progsay"), page.inner_text(".progsay"))
    svg = page.locator(".wchart svg")
    check("seven bars with the pace line drawn across", svg.locator("rect").count() == 7 and "pace 71/day" in svg.text_content())
    wins = page.locator(".pitem.win").all_inner_texts()
    check("wins: weekly bonus and best day celebrated",
          any("Weekly target hit" in w for w in wins) and any("Best day" in w for w in wins), wins)
    watch = page.locator(".pitem.watch").all_inner_texts()
    check("watch: missed daily habits called out with counts",
          any("8k steps" in w and "missed 3 days" in w for w in watch)
          and any("Read 20 minutes" in w and "missed 1 day" in w for w in watch), watch)
    check("watch: unfinished daily goal pointed back to Tasks",
          any("unfinished" in w and "Email the tutor" in w for w in watch), watch)
    page.screenshot(path="shots/progress_week.png", full_page=True)
    page.locator("button[data-act=prog][data-id=day]").click(); page.wait_for_timeout(60)
    check("day view compares against yesterday", "XP today" in page.inner_text(".prognum") and "Yesterday:" in page.inner_text(".proglab"))
    check("day view lists what is still open", any("Still open today" in w for w in page.locator(".pitem.watch").all_inner_texts()))
    page.locator("button[data-act=prog][data-id=month]").click(); page.wait_for_timeout(60)
    check("month view draws a bar per day of September", page.locator(".wchart rect").count() == 30)

    # the report is visibly dated, and follows the clock when left open
    page.locator("button[data-act=prog][data-id=week]").click(); page.wait_for_timeout(60)
    check("week card names the exact days it judges",
          "7 Sept 2026" in page.inner_text(".wcard") and "13 Sept 2026" in page.inner_text(".wcard"),
          page.inner_text(".wcard")[:120])
    page.clock.run_for(2 * 24 * 60 * 60 * 1000)   # Sat 12 -> Mon 14, Progress left open
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(150)
    check("a new week resets the open report by itself",
          "0" in page.inner_text(".prognum") and "14 Sept 2026" in page.inner_text(".wcard")
          and "20 Sept 2026" in page.inner_text(".wcard"), page.inner_text(".wcard")[:160])
    page.locator("button[data-act=prog][data-id=day]").click(); page.wait_for_timeout(60)
    check("day view moved to the actual day", "Monday 14 September" in page.inner_text(".wcard")
          and "Yesterday: 0 XP" in page.inner_text(".proglab"), page.inner_text(".wcard")[:160])
    # and it tracks the same day live: tick a habit, the number follows
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)
    page.locator(".row[data-act=log]", has_text="8k steps").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=tab][data-id=progress]").click(); page.wait_for_timeout(60)
    check("today's XP updates the moment something is logged",
          "20" in page.inner_text(".prognum"), page.inner_text(".prognum"))
    check("no JS errors in the progress tab", not perr, perr)
    ctx.close()

    # ---------- 3i. hide done ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 10, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)
    check("no hide toggle while nothing is done yet",
          page.locator(".goals-head button[data-act=toggle-done]").count() == 0)
    page.locator(".row[data-act=log]", has_text="8k steps").click(); page.wait_for_timeout(50)
    check("ticking a habit alone is enough to surface the hide toggle",
          page.locator(".goals-head button[data-act=toggle-done]").count() == 1)
    page.locator("button[data-act=go-tasks]").click(); page.wait_for_timeout(50)
    page.fill("#f-t-name", "Water the plants"); page.fill("#f-t-xp", "5")
    page.locator("button[data-act=task-add]").click(); page.wait_for_timeout(50)
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(50)
    page.locator(".row.task", has_text="Water the plants").click(); page.wait_for_timeout(50)
    before = page.locator(".row[data-act=log]").count()
    page.locator(".goals-head button[data-act=toggle-done]").click(); page.wait_for_timeout(60)
    check("hide done tucks away the ticked habit and the done goal",
          page.locator(".row[data-act=log]").count() == before - 1
          and page.locator(".row.task").count() == 0
          and "done hidden" in page.locator(".mini.dim").inner_text())
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("the preference is saved", d["hideDone"] is True)
    # sections tab tucks done objectives away the same way, with its own toggle
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_selector(".secbox")
    check("sections has its own hide toggle in the header",
          page.locator(".goals-head button[data-act=toggle-done]").count() == 1)
    page.locator(".secbox .row", has_text="Bench press").locator(".tick").click(); page.wait_for_timeout(60)
    check("done objective hidden in its box, with a count",
          page.locator(".secbox .row.done").count() == 0
          and "1 done hidden" in page.locator(".secbox", has_text="Fitness").inner_text())
    page.locator(".secbox .mini.dim").click(); page.wait_for_timeout(60)
    check("the hidden hint brings them back everywhere",
          page.locator(".secbox .row.done").count() == 1
          and json.loads(page.evaluate("localStorage.getItem('level.v2')"))["hideDone"] is False)
    ctx.close()

    # ---------- 3j. measurable objectives ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    merr = []
    page.on("pageerror", lambda e: merr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 13, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    demo_boot(page)
    page.locator("button[data-act=tab][data-id=sections]").click(); page.wait_for_selector(".secbox")
    page.locator(".secbox", has_text="Fitness").locator("button[data-act=add-objective]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-name", "Bench 80 kg")
    page.fill("#f-g-xp", "300")
    page.fill("#f-g-mcur", "72,5")     # comma decimal, like the Italian keypad
    page.fill("#f-g-mtarget", "80")
    page.fill("#f-g-munit", "kg")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    gj = [g for g in d["goals"] if g["name"] == "Bench 80 kg"][0]
    check("measurable objective stored with its anchor",
          gj["mStart"] == 72.5 and gj["mCur"] == 72.5 and gj["mTarget"] == 80 and gj["mUnit"] == "kg", gj)
    mrow = lambda: page.locator(".secbox .row", has_text="Bench 80 kg")
    check("row shows numbers and a progress bar",
          "72.5 / 80 kg" in mrow().inner_text() and mrow().locator(".gbar").count() == 1, mrow().inner_text())
    mrow().locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-mcur", "76")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    check("progress bar moves with the current number (76 of 72.5->80 = 47%)",
          page.evaluate("document.querySelector('.gbar i').style.width") == "47%",
          page.evaluate("document.querySelector('.gbar i').style.width"))
    mrow().locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-mcur", "80")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    gj = [g for g in d["goals"] if g["name"] == "Bench 80 kg"][0]
    check("reaching the target completes the objective by itself, full XP",
          gj["done"] is True and [e for e in d["log"] if e["type"] == "goal"][0]["xp"] == 300)
    # a downward objective (time under 50 min) works from the other side
    page.locator(".secbox", has_text="Fitness").locator("button[data-act=add-objective]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-name", "Ten-k time")
    page.fill("#f-g-xp", "250")
    page.fill("#f-g-mcur", "55"); page.fill("#f-g-mtarget", "50"); page.fill("#f-g-munit", "min")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    page.locator(".secbox .row", has_text="Ten-k time").locator("button[data-act=edit-goal]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-mcur", "49,5")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("downward target auto-completes when the number gets under it",
          [g for g in d["goals"] if g["name"] == "Ten-k time"][0]["done"] is True)
    # one number without the other is refused
    page.locator(".secbox", has_text="School").locator("button[data-act=add-objective]").click(); page.wait_for_timeout(50)
    page.fill("#f-g-name", "Broken"); page.fill("#f-g-mtarget", "10")
    page.locator("button[data-act=save-goal]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("a target without a current number is refused", not [g for g in d["goals"] if g["name"] == "Broken"])
    check("no JS errors in the measurable flow", not merr, merr)
    ctx.close()

    # ---------- 3k. missed-days level penalty ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 13, 9, 0, 0, tzinfo=ROME))
    demo_boot(page)
    # 730 XP: level 5 (700) plus a 30-XP day three days ago. Empty: 6-9 Sep and 11-12 Sep.
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.log.push({id:'a',type:'habit',refId:'h3',name:'Study 2 hours',xp:700,date:'2026-09-05',at:1});
        s.log.push({id:'b',type:'habit',refId:'h3',name:'Study 2 hours',xp:30,date:'2026-09-10',at:2});
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    pens = sorted([e for e in d["log"] if e["type"] == "penalty"], key=lambda e: e["date"])
    check("each pair of quiet days costs a level, on the 2nd and 4th day of a run",
          [p["date"] for p in pens] == ["2026-09-07", "2026-09-09", "2026-09-12"], [p["date"] for p in pens])
    check("each drop lands exactly on the previous level's floor (730->450->250->100)",
          [p["xp"] for p in pens] == [-280, -200, -150] and sum(e["xp"] for e in d["log"]) == 100, pens)
    check("hero shows the demoted level", "Level 2" in page.inner_text(".lvl"))
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("reconciling again adds nothing (idempotent)",
          len([e for e in d["log"] if e["type"] == "penalty"]) == 3)
    # backfilling a habit onto a punished day takes that penalty back
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    page.locator(".day[data-act=pick][data-id='2026-09-07']").click(); page.wait_for_timeout(60)
    check("penalty visible on its day, not removable",
          "level down" in page.inner_text("#view")
          and page.locator(".entry", has_text="without logging").locator("button[data-act=rm-entry]").count() == 0)
    page.select_option("#f-cal-habit", label="Read 20 minutes (+10)")
    page.locator("button[data-act=log-day]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("backfilling the quiet day lifts its penalty",
          [e["date"] for e in d["log"] if e["type"] == "penalty"] == ["2026-09-09", "2026-09-12"])
    # yesterday holds only a penalty entry, which must not count as an active day
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)
    check("streak ignores penalty entries", "No streak yet" in page.inner_text(".streak"), page.inner_text(".streak"))
    ctx.close()

    # ---------- 3k2. pausing the penalty ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 13, 9, 0, 0, tzinfo=ROME))
    demo_boot(page)
    # nine quiet days on the books, but the penalty is paused
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.log.push({id:'a',type:'habit',refId:'h3',name:'Study 2 hours',xp:700,date:'2026-09-04',at:1});
        s.penaltyPaused = true;
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("paused: quiet days are not judged", not [e for e in d["log"] if e["type"] == "penalty"])
    check("hero keeps the level while paused", "Level 5" in page.inner_text(".lvl"))
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    check("settings shows the toggle unchecked with the paused note",
          not page.is_checked("#f-penalty") and "Paused." in page.inner_text("#view"))
    page.locator("#f-penalty").check(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("switching back on charges nothing for the paused stretch",
          d["penaltyPaused"] is False and d["penaltyFrom"] == "2026-09-13"
          and not [e for e in d["log"] if e["type"] == "penalty"])
    # a boundary in the past: only quiet days on or after it are judged
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.penaltyFrom = '2026-09-08';
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("after the boundary, quiet days count again - never before it",
          [e["date"] for e in d["log"] if e["type"] == "penalty"] == ["2026-09-09", "2026-09-11"],
          [e["date"] for e in d["log"] if e["type"] == "penalty"])
    # pausing again is a shield, not a refund
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    page.locator("#f-penalty").uncheck(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("pausing keeps the penalties already on the books",
          d["penaltyPaused"] is True and len([e for e in d["log"] if e["type"] == "penalty"]) == 2)
    ctx.close()

    # ---------- 3l. live reminder banner + personal heatmap scale ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    page.clock.install(time=datetime.datetime(2026, 9, 8, 14, 59, 30, tzinfo=ROME))
    demo_boot(page)
    check("no banner just before the reminder time", "reminder." not in page.inner_text("#view"))
    page.clock.run_for(2 * 60 * 1000)   # cross 15:00 with the app open, no taps
    page.wait_for_timeout(150)
    check("banner appears on its own when the time passes",
          "15:00 reminder" in page.inner_text("#view"), page.inner_text("#view")[:300])
    # heatmap scales to your own recent best instead of fixed thresholds
    page.evaluate("""() => { const s = JSON.parse(localStorage.getItem('level.v2'));
        s.log.push({id:'x1',type:'habit',refId:'h3',name:'Study 2 hours',xp:700,date:'2026-09-05',at:1});
        s.log.push({id:'x2',type:'habit',refId:'h4',name:'Read 20 minutes',xp:30,date:'2026-09-06',at:2});
        localStorage.setItem('level.v2', JSON.stringify(s)); }""")
    page.reload(); page.wait_for_selector(".hero")
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    check("a 700-XP day is full intensity, a 30-XP day stays light against it",
          page.locator(".day[data-id='2026-09-05']").get_attribute("data-l") == "3"
          and page.locator(".day[data-id='2026-09-06']").get_attribute("data-l") == "1",
          (page.locator(".day[data-id='2026-09-05']").get_attribute("data-l"),
           page.locator(".day[data-id='2026-09-06']").get_attribute("data-l")))
    ctx.close()

    # ---------- 3m. first-open setup ----------
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    oerr = []
    page.on("pageerror", lambda e: oerr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 14, 9, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    page.goto(URL); page.wait_for_selector("#f-su-name")
    check("a fresh install opens on the welcome flow with the tabs hidden",
          "Welcome to Level" in page.inner_text("#view") and not page.locator(".tabs").is_visible())
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("and the app itself is genuinely empty",
          d["habits"] == [] and d["goals"] == [] and d["log"] == [] and d["tasks"] == []
          and d["weight"]["entries"] == [] and d["setup"] is False and len(d["cats"]) == 1)
    page.locator("button[data-act=finish-setup]").click(); page.wait_for_timeout(60)
    check("it will not start without a name", page.locator("#f-su-name").count() == 1
          and json.loads(page.evaluate("localStorage.getItem('level.v2')"))["setup"] is False)
    page.fill("#f-su-name", "Lorenzo")
    page.fill("#f-su-cat", "Fitness")
    page.locator(".sw[data-id='#22C55E']").click()
    page.fill("#f-su-target", "8000")
    page.fill("#f-su-deadline", "2026-12-31")
    page.fill("#f-su-weight", "71")
    page.locator("button[data-act=finish-setup]").click(); page.wait_for_timeout(100)
    check("setup lands in Sections with the first habit form already open",
          page.locator(".tabs").is_visible() and page.locator("#f-h-name").count() == 1
          and page.locator(".secbox .sechead b", has_text="Fitness").count() == 1)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("everything from the form landed in state",
          d["setup"] is True and d["name"] == "Lorenzo" and d["target"] == 8000
          and d["deadline"] == "2026-12-31" and d["start"] == "2026-09-14"
          and d["weight"]["goal"] == 71 and len(d["cats"]) == 1
          and d["cats"][0]["name"] == "Fitness" and d["cats"][0]["color"] == "#22C55E", d)
    page.reload(); page.wait_for_selector(".hero")
    check("the welcome flow never returns, and the hero greets by name",
          page.locator("#f-su-name").count() == 0 and "Lorenzo" in page.inner_text(".hero"))
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    page.fill("#f-name", "Enzo")
    page.locator("button[data-act=save-name]").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)
    check("the name can be changed later under Settings", "Enzo" in page.inner_text(".hero"))
    page.locator("button[data-act=tab][data-id=settings]").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=reset]").click(); page.wait_for_selector("#f-su-name")
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("Reset everything returns the app to brand new, welcome flow included",
          d["setup"] is False and d["habits"] == [] and d["log"] == [])
    check("no JS errors through the welcome flow", not oerr, oerr)
    ctx.close()

    # ---------- 3m. finances ----------
    # a pre-finance install (the DEMO fixture has no finance key) gets the empty default
    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    demo_boot(page)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("pre-finance install gets the empty finance default",
          d["finance"] == {"income": None, "categories": [], "months": {}}, d.get("finance"))
    ctx.close()

    ctx = browser.new_context(**IPHONE)
    page = ctx.new_page()
    ferr = []
    page.on("pageerror", lambda e: ferr.append(str(e)))
    page.clock.install(time=datetime.datetime(2026, 9, 15, 10, 0, 0, tzinfo=ROME))
    page.on("dialog", lambda dlg: dlg.accept())
    fin_boot(page)
    page.locator("button[data-act=tab][data-id=finances]").click(); page.wait_for_timeout(80)
    check("finances opens on the current month", "September 2026" in page.inner_text(".calhead")
          and "Current month" in page.inner_text(".progdate"))
    check("income and budgets from the fixture", "£1,200.50 left" in page.inner_text(".wmeta")
          and "£470 budgeted" in page.inner_text(".wmeta") and "£0 spent" in page.inner_text(".wmeta"))

    # add a category through the form, edit it, delete it
    page.locator("button[data-act=fin-add]").click(); page.wait_for_timeout(50)
    page.fill("#f-fc-name", "Coffee"); page.fill("#f-fc-budget", "30"); page.fill("#f-fc-xp", "10")
    page.locator("button[data-act=fin-save]").click(); page.wait_for_timeout(60)
    check("category added", page.locator(".finrow", has_text="Coffee").count() == 1
          and "£30 budget" in page.locator(".finrow", has_text="Coffee").inner_text())
    page.locator(".finrow", has_text="Coffee").locator("button[data-act=fin-edit]").click(); page.wait_for_timeout(50)
    check("edit form prefilled", page.input_value("#f-fc-name") == "Coffee" and page.input_value("#f-fc-budget") == "30")
    page.fill("#f-fc-budget", "35,50")
    page.locator("button[data-act=fin-save]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("comma-decimal budget saved", [c for c in d["finance"]["categories"] if c["name"] == "Coffee"][0]["budget"] == 35.5)
    page.locator(".finrow", has_text="Coffee").locator("button[data-act=fin-del]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("category deleted", page.locator(".finrow", has_text="Coffee").count() == 0
          and len(d["finance"]["categories"]) == 3)

    # spends: under-budget success, equal-boundary success, third left blank
    spend = lambda name, v: (page.locator(".finrow", has_text=name).locator("input.finspent").fill(v),
                             page.locator(".finrow", has_text=name).locator("input.finspent").press("Enter"),
                             page.wait_for_timeout(60))
    spend("Groceries", "230")
    spend("Investing", "100")
    check("difference and left update", "£20 under" in page.locator(".finrow", has_text="Groceries").inner_text()
          and "target met" in page.locator(".finrow", has_text="Investing").inner_text()
          and "£330 spent" in page.inner_text(".wmeta") and "£870.50 left" in page.inner_text(".wmeta"))
    check("good verdicts use the good token class",
          page.locator(".finrow", has_text="Groceries").locator(".fin-good").count() == 1)
    check("blank category counts as unrecorded in the close preview",
          "2 of 3 categories recorded" in page.inner_text("#view") and "140 XP" in page.inner_text("#view"))

    # close out: equal boundary succeeds, blank spending category is skipped, not rewarded
    page.locator("button[data-act=fin-close]").click(); page.wait_for_timeout(100)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    fe = [e for e in d["log"] if e["type"] == "finance"]
    check("close-out pays exactly the successful categories' XP (80+60, blank skipped)",
          len(fe) == 1 and fe[0]["xp"] == 140 and d["finance"]["months"]["2026-09"]["awarded"] == 140
          and d["finance"]["months"]["2026-09"]["closed"] is True, fe)
    check("finance entry shape: refId month, dated today when closing mid-month",
          fe[0]["refId"] == "2026-09" and fe[0]["name"] == "September budget" and fe[0]["date"] == "2026-09-15")
    check("spent inputs lock once closed", page.locator("input.finspent").count() == 0
          and page.locator(".spentro").count() == 3)

    # the entry is background history: undo steps over it, streak ignores it, calendar cannot remove it
    page.locator("button[data-act=tab][data-id=home]").click(); page.wait_for_timeout(60)
    check("hero total includes finance XP", page.inner_text(".total").strip() == "140")
    page.locator("button[data-act=undo]").click(); page.wait_for_timeout(60)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("undoLast skips the finance entry", len([e for e in d["log"] if e["type"] == "finance"]) == 1
          and page.inner_text(".total").strip() == "140")
    check("streak ignores finance entries", "No streak yet" in page.inner_text(".streak"))
    page.locator("button[data-act=tab][data-id=calendar]").click(); page.wait_for_selector(".cal")
    fentry = page.locator(".entry", has_text="September budget")
    check("calendar shows it tagged with no Remove button",
          "close-out" in fentry.inner_text() and fentry.locator("button[data-act=rm-entry]").count() == 0)

    # reopen removes the XP and unlocks the month
    page.locator("button[data-act=tab][data-id=finances]").click(); page.wait_for_timeout(60)
    page.locator("button[data-act=fin-reopen]").click(); page.wait_for_timeout(80)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("reopen removes the entry and unlocks",
          not [e for e in d["log"] if e["type"] == "finance"]
          and d["finance"]["months"]["2026-09"]["closed"] is False
          and d["finance"]["months"]["2026-09"]["awarded"] == 0
          and page.locator("input.finspent").count() == 3
          and sum(e["xp"] for e in d["log"]) == 0)

    # explicit 0 is judged: success for spending, failure for investing
    spend("Eating out", "0")
    spend("Investing", "0")
    check("zero investing is judged a failure, shown as short",
          "£100 short" in page.locator(".finrow", has_text="Investing").inner_text()
          and page.locator(".finrow", has_text="Investing").locator(".fin-bad").count() == 1)
    check("all three now count as recorded, paying only the winners",
          "3 of 3 categories recorded" in page.inner_text("#view") and "120 XP" in page.inner_text("#view"))
    page.locator("button[data-act=fin-close]").click(); page.wait_for_timeout(100)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    check("zero-spend close: 80 (under) + 40 (zero spending succeeds), investing failed",
          d["finance"]["months"]["2026-09"]["awarded"] == 120
          and [e for e in d["log"] if e["type"] == "finance"][0]["xp"] == 120)

    # past months: reachable, independent, closable with the last-day entry date
    page.locator("button[data-act=fin-prev]").click(); page.wait_for_timeout(60)
    check("previous month viewable, its spends independent",
          "August 2026" in page.inner_text(".calhead") and "Past month" in page.inner_text(".progdate")
          and "£0 spent" in page.inner_text(".wmeta"))
    spend("Groceries", "10")
    page.locator("button[data-act=fin-close]").click(); page.wait_for_timeout(100)
    d = json.loads(page.evaluate("localStorage.getItem('level.v2')"))
    aug = [e for e in d["log"] if e["type"] == "finance" and e["refId"] == "2026-08"]
    check("closing a past month dates its entry to that month's last day",
          len(aug) == 1 and aug[0]["date"] == "2026-08-31" and aug[0]["name"] == "August budget" and aug[0]["xp"] == 80)
    # forward stops at the current month
    page.locator("button[data-act=fin-next]").click(); page.wait_for_timeout(60)
    check("back to the current month", "September 2026" in page.inner_text(".calhead"))
    check("the future is not reachable", page.locator("button[data-act=fin-next]").is_disabled())
    # (no level cap exists in the app today; when one ships, finance close-out
    # must be added to its enforcement tests)
    check("no JS errors in the finance flow", not ferr, ferr)
    ctx.close()

    # ---------- 4. desktop width sanity + manifest/sw reachable ----------
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    demo_boot(page)
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
