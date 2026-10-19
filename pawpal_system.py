"""PawPal+ core classes: the logic layer behind the Streamlit app.

Mirrors diagrams/uml.mmd.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date, time, timedelta
from enum import Enum


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Frequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


def to_minutes(t: time) -> int:
    """Convert a time of day to minutes since midnight."""
    return t.hour * 60 + t.minute


def from_minutes(m: int) -> time:
    """Convert minutes since midnight back to a time of day."""
    return time(m // 60, m % 60)


@dataclass
class Task:
    """A single pet care activity, e.g. a walk or a feeding."""

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    category: str = "general"
    frequency: Frequency = Frequency.DAILY
    # 0 = Monday ... 6 = Sunday; required for WEEKLY tasks
    due_weekday: int | None = None
    # If set, the task is pinned to this start time
    preferred_time: time | None = None
    # First day the task can be due; set on the next occurrence of a
    # recurring task so it does not come back on the day it was done
    due_date: date | None = None
    completed: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self) -> None:
        """Reject non-positive durations and weekly tasks with no weekday."""
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if self.frequency is Frequency.WEEKLY:
            if self.due_weekday is None or not 0 <= self.due_weekday <= 6:
                raise ValueError("weekly tasks need due_weekday 0-6")

    def is_due(self, day: date) -> bool:
        """Return True if this task should be done on `day`.

        A task is never due before its `due_date` (set when a recurring
        task is completed). After that, daily tasks are due every day and
        weekly tasks only on `due_weekday`.
        """
        if self.due_date is not None and day < self.due_date:
            return False
        if self.frequency is Frequency.WEEKLY:
            return day.weekday() == self.due_weekday
        return True

    def mark_complete(self) -> None:
        """Mark this task as done so the scheduler leaves it out."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Mark this task as not done so it is scheduled again."""
        self.completed = False

    def next_occurrence(self, completed_on: date) -> Task:
        """Return a fresh copy of this task for its next due day.

        Daily tasks come back the day after `completed_on`. Weekly tasks
        come back on the next `due_weekday` strictly after `completed_on`:
        `(due_weekday - weekday) % 7` days ahead, or 7 if that is 0. So a
        Sunday task done early on Friday is due again this Sunday, and one
        done on Sunday is due next Sunday.

        The copy keeps every setting but gets a new id, `completed=False`
        and `due_date` set to that day. This task is not changed.
        """
        if self.frequency is Frequency.WEEKLY:
            days_ahead = (self.due_weekday - completed_on.weekday()) % 7 or 7
        else:
            days_ahead = 1
        return replace(
            self,
            completed=False,
            due_date=completed_on + timedelta(days=days_ahead),
            id=uuid.uuid4().hex[:8],
        )


@dataclass
class Pet:
    name: str
    species: str
    age: int = 0
    special_needs: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet."""
        self.tasks.append(task)

    def get_task(self, task_id: str) -> Task:
        """Return the task with this id (titles may repeat, ids do not)."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"{self.name} has no task with id {task_id!r}")

    def remove_task(self, task_id: str) -> None:
        """Remove the task with this id."""
        self.tasks.remove(self.get_task(task_id))

    def complete_task(self, task_id: str, day: date) -> Task:
        """Mark a task done on `day` and add its next occurrence.

        The finished task stays in the list (completed) as history, and
        the copy from `Task.next_occurrence` is appended so the task
        returns on its next due day.

        Returns the new task. Raises KeyError if no task has `task_id`,
        and ValueError if it is already completed (completing twice would
        add a duplicate occurrence).
        """
        task = self.get_task(task_id)
        if task.completed:
            raise ValueError(f"{task.title!r} is already completed")
        task.mark_complete()
        upcoming = task.next_occurrence(day)
        self.add_task(upcoming)
        return upcoming


# A task together with the pet it belongs to
PetTask = tuple[Pet, Task]


@dataclass
class Owner:
    name: str
    # Total time budget for pet care in one day
    available_minutes: int
    # Tie-breaker when sorting, e.g. ["walk", "meds"]
    preferred_categories: list[str] = field(default_factory=list)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def get_all_tasks(self) -> list[PetTask]:
        """Return every (pet, task) pair across all of this owner's pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def filter_tasks(
        self, pet_name: str | None = None, completed: bool | None = None
    ) -> list[PetTask]:
        """Return (pet, task) pairs that match every filter given.

        `pet_name` keeps only that pet's tasks; `completed` keeps only
        done (True) or not-done (False) tasks. A filter left as None is
        ignored, so filter_tasks() returns every task. Order is the same
        as get_all_tasks(). Runs in one pass, O(number of tasks).
        """
        return [
            (pet, task)
            for pet, task in self.get_all_tasks()
            if (pet_name is None or pet.name == pet_name)
            and (completed is None or task.completed == completed)
        ]


@dataclass
class ScheduledTask:
    """A task placed at a specific time, with the reason it was chosen."""

    task: Task
    pet: Pet
    start: time
    end: time
    reason: str = ""


@dataclass
class SkippedTask:
    """A due task that did not make it into the plan, and why."""

    task: Task
    pet: Pet
    reason: str


@dataclass
class DailyPlan:
    day: date
    available_minutes: int
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)
    # Pinned tasks whose requested times overlap (see detect_conflicts)
    warnings: list[str] = field(default_factory=list)

    def total_minutes(self) -> int:
        """Return the total minutes of all scheduled tasks."""
        return sum(entry.task.duration_minutes for entry in self.scheduled)

    def explain(self) -> str:
        """Return a readable summary of the plan and its reasoning."""
        lines = [
            f"Plan for {self.day:%A, %B %d}: "
            f"{self.total_minutes()} of {self.available_minutes} minutes used."
        ]
        for warning in self.warnings:
            lines.append(f"  ⚠ {warning}")
        for entry in self.scheduled:
            lines.append(
                f"  {entry.start:%H:%M}-{entry.end:%H:%M}  "
                f"{entry.task.title} ({entry.pet.name}) — "
                f"{entry.task.priority.name.lower()} priority, {entry.reason}"
            )
        if self.skipped:
            lines.append("Skipped:")
            for item in self.skipped:
                lines.append(
                    f"  {item.task.title} ({item.pet.name}) — {item.reason}"
                )
        return "\n".join(lines)


class Scheduler:
    """Builds a DailyPlan for an owner.

    Rules:
    1. Only tasks that are due on the given day and not yet completed
       are considered.
    2. Pinned tasks (with a preferred_time) are placed first, at their
       requested time.
    3. Flexible tasks fill the remaining gaps in sorted order
       (see _sort_tasks).
    4. A pinned task that overlaps a task already placed is moved to
       the next free slot after its preferred time.
    5. A task is skipped if it would exceed the owner's time budget or
       cannot fit inside day_start..day_end.
    Greedy by priority: a long high-priority task may crowd out several
    shorter ones.
    """

    def __init__(
        self,
        owner: Owner,
        day_start: time = time(8, 0),
        day_end: time = time(20, 0),
    ):
        """Set up a scheduler for `owner` within day_start..day_end."""
        if day_end <= day_start:
            raise ValueError("day_end must be after day_start")
        self.owner = owner
        self.day_start = day_start
        self.day_end = day_end

    def generate_plan(self, day: date) -> DailyPlan:
        """Collect due tasks, place pinned ones, then fill gaps."""
        plan = DailyPlan(
            day=day, available_minutes=self.owner.available_minutes
        )
        plan.warnings = self.detect_conflicts(day)
        due = self._sort_tasks(self._collect_due_tasks(day))
        pinned = [(p, t) for p, t in due if t.preferred_time is not None]
        flexible = [(p, t) for p, t in due if t.preferred_time is None]

        for pet, task in pinned:
            self._place_pinned(plan, pet, task)
        for pet, task in flexible:
            self._place_flexible(plan, pet, task)

        plan.scheduled.sort(key=lambda entry: entry.start)
        return plan

    @staticmethod
    def sort_by_time(items: list[PetTask]) -> list[PetTask]:
        """Sort pinned tasks by start time; flexible tasks go last.

        The key is a tuple `(has no time, time)`. False sorts before
        True, so pinned tasks come first, ordered by `preferred_time`.
        Flexible tasks use `time.min` as a placeholder because None
        cannot be compared with a time. sorted() is stable, so tasks with
        the same time, and all flexible tasks, keep their input order.
        Returns a new list; `items` is not changed. O(n log n).
        """
        return sorted(items, key=lambda item: (
            item[1].preferred_time is None,
            item[1].preferred_time or time.min,
        ))

    def detect_conflicts(self, day: date) -> list[str]:
        """Return a warning for each pair of due pinned tasks that overlap.

        Lightweight on purpose: it only compares requested times and
        returns messages instead of raising, so a clash never stops the
        program. generate_plan still resolves the overlap by moving the
        lower-priority task.

        Pinned tasks are sorted by start time, then each one is compared
        with the tasks after it until one starts at or after its end;
        nothing later can overlap, so the inner loop stops there. Tasks
        that only touch (one ends at 08:30, the next starts at 08:30) do
        not conflict. Each warning says whether the clash is between the
        same pet or different pets. Returns [] when there is no conflict.
        """
        pinned = []
        for pet, task in self.sort_by_time(self._collect_due_tasks(day)):
            if task.preferred_time is None:
                break
            start = to_minutes(task.preferred_time)
            pinned.append((start, start + task.duration_minutes, pet, task))

        warnings = []
        for i, (start, end, pet, task) in enumerate(pinned):
            for other_start, _, other_pet, other in pinned[i + 1:]:
                if other_start >= end:
                    break
                who = "same pet" if other_pet is pet else "different pets"
                warnings.append(
                    f"{task.title} ({pet.name}) at "
                    f"{task.preferred_time:%H:%M} overlaps {other.title} "
                    f"({other_pet.name}) at {other.preferred_time:%H:%M} "
                    f"[{who}]"
                )
        return warnings

    def _collect_due_tasks(self, day: date) -> list[PetTask]:
        """Return the owner's tasks that are due on `day` and not done."""
        return [
            (pet, task)
            for pet, task in self.owner.get_all_tasks()
            if task.is_due(day) and not task.completed
        ]

    def _sort_tasks(self, items: list[PetTask]) -> list[PetTask]:
        """Sort by priority, then preferred category, then duration."""
        preferred = self.owner.preferred_categories

        def key(item: PetTask) -> tuple[int, int, int]:
            """Build the sort key for one (pet, task) pair."""
            task = item[1]
            if task.category in preferred:
                category_rank = preferred.index(task.category)
            else:
                category_rank = len(preferred)
            return (-task.priority.value, category_rank, task.duration_minutes)

        return sorted(items, key=key)

    def _find_conflicts(
        self, entries: list[ScheduledTask]
    ) -> list[tuple[ScheduledTask, ScheduledTask]]:
        """Return pairs of scheduled tasks whose time ranges overlap."""
        ordered = sorted(entries, key=lambda entry: entry.start)
        conflicts = []
        for i, first in enumerate(ordered):
            for second in ordered[i + 1:]:
                if second.start >= first.end:
                    break
                conflicts.append((first, second))
        return conflicts

    def _fits_budget(self, plan: DailyPlan, task: Task) -> bool:
        """Return True if `task` fits in the plan's remaining minutes."""
        return plan.total_minutes() + task.duration_minutes <= (
            plan.available_minutes
        )

    def _place_pinned(self, plan: DailyPlan, pet: Pet, task: Task) -> None:
        """Place a task at its preferred time, moving it if that is taken."""
        start = to_minutes(task.preferred_time)
        end = start + task.duration_minutes
        if (start < to_minutes(self.day_start)
                or end > to_minutes(self.day_end)):
            plan.skipped.append(SkippedTask(
                task, pet,
                # Not from_minutes(end): it may be past midnight
                f"{task.preferred_time:%H:%M} + {task.duration_minutes} min "
                f"does not fit inside "
                f"{self.day_start:%H:%M}-{self.day_end:%H:%M}",
            ))
            return
        if not self._fits_budget(plan, task):
            plan.skipped.append(SkippedTask(
                task, pet, "not enough time left in today's budget"
            ))
            return

        entry = ScheduledTask(
            task, pet, from_minutes(start), from_minutes(end),
            "pinned to its preferred time",
        )
        conflicts = self._find_conflicts(plan.scheduled + [entry])
        if conflicts:
            # Shift to the next free slot after the preferred time
            first, second = conflicts[0]
            other = second if first is entry else first
            moved = self._earliest_gap(
                plan, task.duration_minutes, not_before=start
            )
            if moved is None:
                plan.skipped.append(SkippedTask(
                    task, pet,
                    f"overlaps {other.task.title} ({other.pet.name}) and "
                    f"no later slot is free",
                ))
                return
            entry.start = from_minutes(moved)
            entry.end = from_minutes(moved + task.duration_minutes)
            entry.reason = (
                f"moved from {task.preferred_time:%H:%M} because it "
                f"overlapped "
                f"{other.task.title} ({other.pet.name})"
            )
        plan.scheduled.append(entry)

    def _place_flexible(self, plan: DailyPlan, pet: Pet, task: Task) -> None:
        """Place a task in the earliest free slot, or record why not."""
        if not self._fits_budget(plan, task):
            plan.skipped.append(SkippedTask(
                task, pet, "not enough time left in today's budget"
            ))
            return

        start = self._earliest_gap(plan, task.duration_minutes)
        if start is None:
            plan.skipped.append(SkippedTask(
                task, pet, "no free slot long enough before day end"
            ))
            return
        plan.scheduled.append(ScheduledTask(
            task, pet, from_minutes(start),
            from_minutes(start + task.duration_minutes),
            "placed in the earliest free slot",
        ))

    def _earliest_gap(
        self, plan: DailyPlan, duration: int, not_before: int | None = None
    ) -> int | None:
        """Return the first free start minute at or after `not_before`."""
        cursor = to_minutes(self.day_start)
        if not_before is not None:
            cursor = max(cursor, not_before)
        for entry in sorted(plan.scheduled, key=lambda e: e.start):
            if to_minutes(entry.end) <= cursor:
                continue
            if to_minutes(entry.start) - cursor >= duration:
                return cursor
            cursor = max(cursor, to_minutes(entry.end))
        if to_minutes(self.day_end) - cursor >= duration:
            return cursor
        return None
