# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## 🛠️ Implementation Summary

PawPal+ plans a pet owner's day across **all of their pets**. The logic lives in `pawpal_system.py`; `main.py` is a terminal demo and `tests/test_pawpal.py` holds the tests.

**How the classes work together:**

1. **`Owner` → `Pet` → `Task`** hold the input data. An owner has a daily time budget, optional preferred categories, and one or more pets. Each pet keeps its own list of tasks. A `Task` has a title, duration, priority (`Priority` enum), category, frequency (`Frequency` enum: daily or weekly), an optional fixed start time, and a completion status.
2. **`Owner.get_all_tasks()`** returns every pet's tasks together as `(pet, task)` pairs, so each task keeps track of whose it is.
3. **`Scheduler.generate_plan(day)`** is the "brain." It reads only from `get_all_tasks()`, then:
   - keeps tasks that are due that day (`Task.is_due`) and not completed,
   - sorts them by priority, then the owner's preferred categories, then shortest duration,
   - places tasks with a fixed time first; if two want the same slot, the later one moves to the next free time,
   - fills the remaining gaps with flexible tasks in sorted order,
   - skips anything that would exceed the time budget or run past the end of the day.
4. **`DailyPlan`** is the result: a list of `ScheduledTask`s (task, pet, start, end, reason) and `SkippedTask`s (task, pet, reason). `total_minutes()` reports time used, and `explain()` describes the plan in plain language.

The scheduler never changes the owner's data, so the same owner can be planned for any day, and the UI only needs to display the `DailyPlan` it gets back. The class diagram is in `diagrams/uml.mmd`.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Output of `python main.py` (two pets, a 120-minute budget, run on a Sunday so the weekly bath is due):

```
========================================================================
🐾 Today's Schedule for Jordan — Sunday, October 18, 2026
========================================================================
Time         Task              Pet     Priority  Why
------------------------------------------------------------------------
08:00-08:05  Heartworm pill    Mochi   high      pinned to its preferred time
08:05-08:15  Breakfast         Luna    high      moved from 08:00 because it overlapped Heartworm pill (Mochi)
08:15-08:45  Morning walk      Mochi   high      placed in the earliest free slot
08:45-09:05  Play session      Luna    medium    placed in the earliest free slot
09:05-09:20  Brush coat        Luna    low       placed in the earliest free slot
18:00-18:30  Evening walk      Mochi   medium    pinned to its preferred time
------------------------------------------------------------------------
Time used: 110 of 120 minutes

Skipped:
  ✗ Bath (Mochi): not enough time left in today's budget
========================================================================
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.14, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/vians/AI110/ai110-module2show-pawpal-starter
configfile: pytest.ini
testpaths: tests
collected 19 items

tests/test_pawpal.py ...................                                 [100%]

============================== 19 passed in 0.01s ==============================
```

The tests in `tests/test_pawpal.py` cover task completion, adding/removing tasks, daily vs. weekly recurrence, gathering tasks across multiple pets, priority ordering, the time budget, pinned times and conflict handling, the day window, and the empty-plan edge case.

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
