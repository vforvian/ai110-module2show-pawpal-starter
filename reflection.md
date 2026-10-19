# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial UML separates the system into three layers: the **data** being planned (owner, pets, tasks), the **logic** that does the planning (scheduler), and the **output** it produces (a daily plan). An owner has one or more pets, each pet has a list of care tasks, and the scheduler reads the owner's pets and tasks to build a plan for a given day.

Classes and responsibilities:

- **`Task`** (dataclass) — one care activity, such as a walk, feeding, or medication. It stores the title, duration in minutes, priority, category, how often it repeats, and an optional preferred time. It is responsible for answering `is_due(day)`, i.e. whether it should happen on a given date.
- **`Priority`** and **`Frequency`** (enums) — fixed choices for a task's importance (low/medium/high) and how often it repeats (daily/weekly). Using enums instead of plain strings prevents typos, and the numeric priority values make sorting simple.
- **`Pet`** (dataclass) — stores the pet's name, species, age, and special needs, and owns its list of tasks. It is responsible for adding and removing its tasks.
- **`Owner`** (dataclass) — stores the owner's name, how many minutes they have available per day, their preferences, and their pets. It is responsible for adding pets and gathering every task across all pets (`all_tasks()`).
- **`Scheduler`** (regular class) — the "brain" of the app. Given an owner, it builds the plan for a day: it collects the tasks that are due, sorts them by priority (then preferred time, then shortest duration), fits them into the owner's available time starting at `day_start`, and checks for overlapping time slots. I made this a regular class rather than a dataclass because it performs behavior instead of just holding data.
- **`ScheduledTask`** (dataclass) — a task placed on the timeline, with the pet it belongs to, a start and end time, and the reason it was chosen.
- **`DailyPlan`** (dataclass) — the result of scheduling. It holds the scheduled tasks plus the tasks that were skipped and why. It is responsible for reporting the total time used (`total_minutes()`) and explaining the plan in plain language (`explain()`).

Keeping the plan's output (`DailyPlan`, `ScheduledTask`) separate from the input data (`Task`, `Pet`, `Owner`) means the scheduler never modifies the original tasks, and the Streamlit UI can simply display whatever plan the scheduler returns.

**b. Design changes**

Yes. Before writing any logic, I reviewed the class skeleton for missing relationships and bottlenecks, and found several places where a method could not actually do its job with the data it had. I made these changes:

1. **Tasks now travel with their pet.** `Owner.all_tasks()` and `Scheduler._collect_due_tasks()` originally returned a flat `list[Task]`. But `Task` has no link back to its `Pet`, so once tasks were collected the scheduler could no longer tell whose walk it was, even though every `ScheduledTask` needs a `pet`. Both methods now return `(Pet, Task)` pairs. I chose pairs over adding a `pet` field to `Task` to avoid a circular reference between `Pet` and `Task`.
2. **Added a `SkippedTask` class.** `DailyPlan.skipped` was a `list[tuple[Task, str]]`, which had the same missing-pet problem and was hard to read. A small `SkippedTask(task, pet, reason)` dataclass mirrors `ScheduledTask` and makes the plan's explanation clearer.
3. **`DailyPlan` stores `available_minutes`.** Without it, `explain()` could not say how much of the owner's time budget was used (e.g. "95 of 120 minutes").
4. **Weekly tasks know which day they happen.** `Task` only had `frequency = WEEKLY`, so `is_due()` had no way to decide *which* day a weekly task falls on. I added `due_weekday` (0 = Monday … 6 = Sunday).
5. **Tasks have a unique `id`.** `Pet.remove_task(title)` was ambiguous if a pet had two tasks with the same title (morning and evening "Walk"), and dataclass equality treats two identical tasks as equal. Each task now gets a short random `id`, and `remove_task` takes the id.
6. **Owner preferences became something the code can use.** `preferences: list[str]` held free text like "walks in the morning" that the scheduler could not act on. I replaced it with `preferred_categories`, which `_sort_tasks` uses as a tie-breaker after priority.
7. **The scheduler has a day window.** It was unclear whether `available_minutes` was a total budget or a time window. I kept it as the total budget and added `day_end` to `Scheduler`, so tasks must fit both the budget and the `day_start`–`day_end` window.
8. **Scheduling rules are decided up front.** Mixing fixed-time tasks with back-to-back flexible tasks would have made conflict handling unpredictable. The `Scheduler` docstring now states the order: place pinned tasks (those with a `preferred_time`) first, then fill the gaps with flexible tasks in priority order, skipping anything that does not fit.

While implementing the logic, I made three more changes:

9. **Renamed `all_tasks()` to `get_all_tasks()` and made it the scheduler's only data source.** The `Scheduler` never reads a single pet's task list directly; it always asks the `Owner` for every pet's tasks, so plans automatically cover all of the owner's pets.
10. **Added a completion status to `Task`.** `completed`, `mark_complete()`, and `mark_incomplete()` let the owner check tasks off, and the scheduler leaves completed tasks out of the plan.
11. **Conflicting pinned tasks are moved instead of dropped.** My first version skipped a pinned task if its time was already taken. Testing with two pets showed this was too harsh: the cat's high-priority 08:00 feeding was dropped entirely because the dog's 5-minute pill was also at 08:00. Now the second task moves to the next free slot after its preferred time, and the plan explains why it moved.

I updated `diagrams/uml.mmd` to match these changes.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers six constraints:

1. **Is the task due today?** Daily tasks are always due; weekly tasks only on their weekday; a recurring task's next copy is not due before its `due_date`; completed tasks are left out.
2. **Fixed start times.** A task with a `preferred_time` is placed at that time if it is free.
3. **Priority.** High before medium before low.
4. **Owner preferences.** `preferred_categories` (e.g. meds before walks) break ties between tasks of the same priority, then shorter tasks go first.
5. **Time budget.** The total scheduled minutes can never exceed `available_minutes`.
6. **Day window.** Every task must start and end between `day_start` and `day_end` (08:00–20:00 by default).

I treated the budget and the day window as **hard** limits: a plan that needs more time than the owner has, or a walk at 23:00, is useless no matter how well it's ordered. Priority came next because it is the one thing the owner explicitly tells us about importance. A missed medication matters more than a missed brushing. Fixed times are respected when possible but are **soft**: if two clash, one moves rather than both being kept at overlapping times. Category preferences and duration are only tie-breakers, because they express taste, not necessity.

**b. Tradeoffs**

The scheduler is **greedy**: it places tasks one at a time in priority order and never goes back to rearrange them. That means one long high-priority task can use up the budget and crowd out several shorter, lower-priority tasks that together would have been more useful. For example, with 60 minutes, a 50-minute high-priority walk is scheduled and three 15-minute medium tasks are skipped.

This is reasonable here because:

- **It matches how owners think.** "Do the important things first" is easy to trust. A plan that drops a high-priority task so that more low-priority ones fit would feel wrong, even if it schedules more minutes.
- **It is explainable.** Every task's reason is simple ("placed in the earliest free slot", "not enough time left in today's budget"). An optimal search would be much harder to explain in one line.
- **The inputs are small.** One owner has maybe 5–20 tasks a day, so being slightly suboptimal costs little, and the greedy approach is fast and predictable.

I did soften the worst case: a task that is too long for the remaining budget is skipped, but the scheduler keeps going, so shorter tasks after it can still fit.

---

## 3. AI Collaboration

**a. How you used AI**

I used Claude Code (an AI coding agent in VS Code) at every stage of the project:

- **Setup and debugging:** my virtual environment wasn't working. The AI found that my `.venv` mixed an Intel-only Anaconda Python with the Apple Silicon python.org Python, so even `pip` crashed. It rebuilt the environment with the correct Python and explained why the README's plain `python -m venv .venv` caused the problem on my machine.
- **Design brainstorming:** it proposed the first set of classes (`Owner`, `Pet`, `Task`, `Scheduler`, `DailyPlan`) and the scheduling approach, then asked me questions only I could answer: one pet or several, fixed task times or not, and whether some tasks should never be skipped. I chose several pets, optional fixed times, and priority-only scheduling.
- **Turning the design into code:** it wrote the Mermaid UML, the dataclass skeleton, the implementation, `main.py`, the tests, and docstrings.
- **Design review:** I asked it to review its own skeleton for missing relationships and bottlenecks *before* writing any logic. That was the most useful prompt of the project; it found that tasks lost track of which pet they belonged to, that weekly tasks had no weekday, and that removing a task by title was ambiguous (see section 1b).

The most helpful prompts were specific and asked for critique rather than more code: "review the skeleton for missing relationships or logic bottlenecks," and pasting the exact assignment step so the AI worked to the real requirements (for example, naming the method `get_all_tasks()` and making the `Scheduler` read only from it, which the multi-pet requirement depends on).

**b. Judgment and verification**

Several AI outputs were changed rather than accepted as-is:

- **Conflicting fixed-time tasks.** The first version of the scheduler *skipped* any task whose fixed time was already taken. Running the two-pet demo showed the problem: the cat's high-priority 08:00 breakfast was dropped entirely because the dog's 5-minute pill was also at 08:00. A pet missing a meal over a five-minute overlap is the wrong outcome, so the rule was changed to move the second task to the next free slot (08:05) and explain why it moved.
- **Misleading explanations.** A task pinned at 19:50 was skipped with the reason "19:50 is outside 08:00–20:00", which is false: 19:50 is inside the day; the problem is that the 20-minute task would end at 20:10. The message was rewritten to show the full time range that doesn't fit.
- **Following the repo over the instructions.** The assignment suggested saving the diagram as `diagrams/uml_draft.mmd`, but the repo's git history showed it had been renamed to `uml.mmd` to match grading, so I kept `uml.mmd` instead of creating a duplicate.

I verified the AI's work in three ways:

1. **Running it:** `python main.py` with realistic data (two pets, a weekly task, a completed task, two tasks at the same time) and checking the printed schedule by hand: times don't overlap, the total stays within the budget, and the weekly bath only appears on its weekday.
2. **Automated tests:** 40 pytest tests in `tests/test_pawpal.py` cover each scheduling rule plus edge cases (a task longer than the whole budget, a task that runs past the end of the day, an owner with no tasks). All pass. The Streamlit app was also run headlessly with Streamlit's `AppTest` to confirm the conflict warnings render correctly.
3. **Checking consistency:** after each change, the UML diagram, the README, and this reflection were updated so they describe the code that actually exists.

**c. AI strategy**

*Most effective features.* The most useful thing was that the assistant could **run code, not just write it**. It ran `main.py` and the test suite after every change, wrote throwaway scripts to try edge cases (exact-fit budgets, three tasks at the same time, Dec 31 → Jan 1) before turning them into tests, and ran the Streamlit app headlessly to check what the warnings actually said. Second was **whole-project context**: because it read `pawpal_system.py`, the tests, the README and the git history together, it noticed things I would have missed, such as the README already having a testing section that described 29 tests, or the UML still saying an owner needs at least one pet. Third, it could **render the Mermaid diagram to a PNG and look at the image**, which caught two display bugs (nested generic types and `__init__` showing as bold "init") that the text source hid.

*A suggestion I rejected or modified.* When tasks lost track of their pet (section 1b), one option was to give every `Task` a `pet` field. I rejected that: `Pet` already holds a list of `Task`s, so a back-reference would create a circular link where the two could disagree (a task moved to another pet but still pointing at the old one). Instead, methods pass `(pet, task)` pairs, named `PetTask`, and `Task` stays a simple, self-contained record. A second example came from the Streamlit UI: the first conflict message always said "the lower-priority task was moved", but the scheduler sometimes *skips* it when the day is full. Rather than keep a message that was only usually true, the UI now reports what actually happened to each task, using the plan's own data.

*Separate chat sessions for each phase.* I used a different session for design, implementation, and testing. Each one started with just the files and the assignment step for that phase, so the assistant focused on the current goal instead of carrying old assumptions forward. The testing session in particular began by reading the finished code fresh and asking "what are the important edge cases?", which is closer to how an outside reviewer would look at it than continuing the session that wrote the code. It also kept each phase's decisions easy to find later, and each phase ended in its own git commit.

*Being the lead architect.* The AI can produce a lot of correct-looking code very quickly, so my job shifted from writing code to **deciding what the system should be and checking that it is**. The decisions that mattered most were mine to make: several pets or one, whether fixed times are hard or soft, whether a clash should drop a task or move it. The AI asked about these instead of guessing when I prompted it to. I learned to ask for **critique before code** ("review this skeleton for missing relationships"), to paste the exact requirement so it builds to the real goal, and to never accept "it works" without seeing it run. The AI's first answers were often reasonable but subtly off, like the "outside 08:00–20:00" message for a 19:50 task. Those are only caught by someone who knows what the system is supposed to do.

---

## 4. Testing and Verification

**a. What you tested**

The 40 tests in `tests/test_pawpal.py` cover five areas, each with happy paths and edge cases:

- **Sorting:** the plan comes out in time order even when tasks are added out of order; priority, then preferred category, then duration decides placement; `sort_by_time` puts fixed-time tasks first.
- **Recurrence:** completing a daily task creates a new one for the next day (and leaves it out of today's plan); weekly tasks return on their weekday, including when done early or the day before; Dec 31 rolls over to Jan 1; completing a task twice is rejected.
- **Conflicts:** two or three tasks at the same time produce warnings; tasks that only touch don't; the higher-priority task keeps its time and the other is moved, or skipped if there's no room.
- **Limits:** tasks that exactly use up the budget all fit; a zero budget skips everything; a task ending exactly at 20:00 fits; tasks past the end of the day or past midnight are skipped without crashing.
- **Data:** adding, removing and filtering tasks, a pet with no tasks, and rejecting invalid tasks.

These mattered because the scheduler's bugs are most likely at the **boundaries**: `<` vs `<=` for the budget and day end, clashes at exactly the same minute, and date math across weeks and years. Those are the cases that look fine in a normal demo and fail on a real owner's day. The tests also let me change the conflict rules (skip → move) without breaking anything else.

**b. Confidence**

**4 out of 5.** Every core behavior and boundary case passes, and the same cases gave matching results when checked by hand. It is not a 5 because the Streamlit UI is only checked manually and with a headless run, `DailyPlan.explain()`'s text isn't tested, and the greedy approach builds valid plans but not always the one that fits the most tasks.

With more time I would test:

- A pet with a `special_needs` entry, which the scheduler currently stores but ignores.
- Changing a task's time or duration after a plan is built, then rebuilding.
- Many tasks (100+) to check that sorting and conflict detection stay fast.
- A day window shorter than one task, and fixed times exactly at `day_start`.
- Completing a task on a date in the past or future, not today.

---

## 5. Reflection

**a. What went well**

I'm most satisfied that the scheduler **explains itself**. Every scheduled task says why it is there and every skipped task says why it isn't ("moved from 18:00 because it overlapped Evening walk", "not enough time left in today's budget"). That made the system easy to debug, easy to test, and easy to trust in the UI. I'm also happy with the decision to keep the input data (`Owner`, `Pet`, `Task`) separate from the output (`DailyPlan`): the scheduler never changes the owner's data, so the same owner can be planned for any day, and the UI just displays what it gets back.

**b. What you would improve**

- **Return conflicts as data, not strings.** `detect_conflicts` returns messages, so the Streamlit app has to check whether a reason starts with "moved from" to know what happened. A small `Conflict` dataclass (both tasks, both pets, the outcome) would be cleaner and wouldn't break if the wording changed.
- **Let the owner choose tasks that must never be skipped**, such as medication, instead of relying only on priority.
- **Expose preferred categories in the UI.** They work in the logic layer and `main.py` but the app has no control for them.
- **Save data between sessions.** The app keeps everything in `st.session_state`, so it is lost when the browser tab closes.

**c. Key takeaway**

Design decisions are cheap before the code exists and expensive after. The most valuable hour of the project was reviewing the class skeleton *before* any logic was written: it caught tasks losing track of their pet, weekly tasks with no weekday, and ambiguous removal by title. All of those would have spread through the scheduler, tests and UI if found later. Working with AI made this even more important: it can write the code for a flawed design just as fast as for a good one, so my value was in getting the design right and checking that the result matched it.
