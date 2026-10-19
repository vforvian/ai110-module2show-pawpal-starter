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

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

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
2. **Automated tests:** 19 pytest tests in `tests/test_pawpal.py` cover each scheduling rule plus edge cases (a task longer than the whole budget, a task that runs past the end of the day, an owner with no tasks). All pass.
3. **Checking consistency:** after each change, the UML diagram, the README, and this reflection were updated so they describe the code that actually exists.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
