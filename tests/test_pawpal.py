"""Tests for the most important PawPal+ behaviors."""

from datetime import date, time

import pytest

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

MONDAY = date(2026, 10, 19)
SUNDAY = date(2026, 10, 18)


def make_owner(minutes=120, pets=None, **kwargs):
    owner = Owner("Jordan", available_minutes=minutes, **kwargs)
    for pet in pets or []:
        owner.add_pet(pet)
    return owner


def titles(plan):
    return [entry.task.title for entry in plan.scheduled]


# --- Task ---------------------------------------------------------------

def test_mark_complete_changes_status():
    task = Task("Walk", 30)
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True
    task.mark_incomplete()
    assert task.completed is False


def test_daily_task_is_due_every_day():
    task = Task("Feeding", 10)
    assert task.is_due(MONDAY)
    assert task.is_due(SUNDAY)


def test_weekly_task_is_due_only_on_its_weekday():
    bath = Task("Bath", 45, frequency=Frequency.WEEKLY, due_weekday=6)
    assert bath.is_due(SUNDAY)
    assert not bath.is_due(MONDAY)


def test_invalid_tasks_are_rejected():
    with pytest.raises(ValueError):
        Task("Walk", 0)
    with pytest.raises(ValueError):
        Task("Bath", 45, frequency=Frequency.WEEKLY)  # no weekday


# --- Pet and Owner ------------------------------------------------------

def test_add_task_increases_task_count():
    pet = Pet("Mochi", "dog")
    assert len(pet.tasks) == 0
    pet.add_task(Task("Walk", 30))
    assert len(pet.tasks) == 1


def test_remove_task_by_id_keeps_other_task_with_same_title():
    pet = Pet("Mochi", "dog")
    morning = Task("Walk", 30)
    evening = Task("Walk", 30)
    pet.add_task(morning)
    pet.add_task(evening)

    pet.remove_task(morning.id)

    assert pet.tasks == [evening]
    with pytest.raises(KeyError):
        pet.remove_task(morning.id)


def test_get_all_tasks_covers_every_pet():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    walk, feed = Task("Walk", 30), Task("Feeding", 10)
    mochi.add_task(walk)
    luna.add_task(feed)
    owner = make_owner(pets=[mochi, luna])

    assert owner.get_all_tasks() == [(mochi, walk), (luna, feed)]


# --- Scheduler ----------------------------------------------------------

def test_plan_includes_tasks_from_multiple_pets():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    mochi.add_task(Task("Walk", 30))
    luna.add_task(Task("Feeding", 10))
    owner = make_owner(pets=[mochi, luna])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert {entry.pet.name for entry in plan.scheduled} == {"Mochi", "Luna"}


def test_flexible_tasks_ordered_by_priority_then_duration():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Brush", 15, Priority.LOW))
    pet.add_task(Task("Long walk", 40, Priority.HIGH))
    pet.add_task(Task("Feeding", 10, Priority.HIGH))
    pet.add_task(Task("Play", 20, Priority.MEDIUM))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Feeding", "Long walk", "Play", "Brush"]
    assert plan.scheduled[0].start == time(8, 0)


def test_preferred_category_breaks_priority_ties():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Feeding", 10, Priority.HIGH, "feeding"))
    pet.add_task(Task("Walk", 30, Priority.HIGH, "walk"))
    owner = make_owner(pets=[pet], preferred_categories=["walk"])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Walk", "Feeding"]


def test_completed_and_not_due_tasks_are_left_out():
    pet = Pet("Mochi", "dog")
    done = Task("Feeding", 10)
    done.mark_complete()
    pet.add_task(done)
    pet.add_task(Task("Bath", 45, frequency=Frequency.WEEKLY, due_weekday=6))
    pet.add_task(Task("Walk", 30))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Walk"]
    assert plan.skipped == []


def test_tasks_over_budget_are_skipped_with_reason():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Long walk", 50, Priority.HIGH))
    pet.add_task(Task("Grooming", 20, Priority.LOW))
    owner = make_owner(minutes=60, pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Long walk"]
    assert plan.total_minutes() <= 60
    assert [s.task.title for s in plan.skipped] == ["Grooming"]
    assert "budget" in plan.skipped[0].reason


def test_task_longer_than_budget_does_not_block_smaller_ones():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Hike", 90, Priority.HIGH))
    pet.add_task(Task("Feeding", 10, Priority.MEDIUM))
    owner = make_owner(minutes=60, pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Feeding"]
    assert [s.task.title for s in plan.skipped] == ["Hike"]


def test_pinned_task_starts_at_preferred_time():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Evening walk", 30, preferred_time=time(18, 0)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert plan.scheduled[0].start == time(18, 0)
    assert plan.scheduled[0].end == time(18, 30)


def test_conflicting_pinned_task_is_moved_not_dropped():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    mochi.add_task(Task("Pill", 5, Priority.HIGH,
                        preferred_time=time(8, 0)))
    luna.add_task(Task("Breakfast", 10, Priority.MEDIUM,
                       preferred_time=time(8, 0)))
    owner = make_owner(pets=[mochi, luna])

    plan = Scheduler(owner).generate_plan(MONDAY)

    pill, breakfast = plan.scheduled
    assert (pill.task.title, pill.start) == ("Pill", time(8, 0))
    assert (breakfast.task.title, breakfast.start) == ("Breakfast",
                                                      time(8, 5))
    assert "moved" in breakfast.reason


def test_flexible_tasks_fill_gaps_around_pinned_tasks():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Pill", 5, Priority.HIGH, preferred_time=time(8, 20)))
    pet.add_task(Task("Feeding", 15, Priority.HIGH))  # fits before 08:20
    pet.add_task(Task("Walk", 30, Priority.MEDIUM))   # must go after
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    starts = {e.task.title: e.start for e in plan.scheduled}
    assert starts == {"Feeding": time(8, 0), "Pill": time(8, 20),
                      "Walk": time(8, 25)}


def test_pinned_task_outside_day_window_is_skipped():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Late walk", 20, preferred_time=time(19, 50)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner, day_end=time(20, 0)).generate_plan(MONDAY)

    assert plan.scheduled == []
    assert "does not fit" in plan.skipped[0].reason


def test_plan_never_has_overlapping_tasks():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    for pet in (mochi, luna):
        pet.add_task(Task("Pinned", 15, preferred_time=time(9, 0)))
        pet.add_task(Task("Flexible A", 20))
        pet.add_task(Task("Flexible B", 25))
    owner = make_owner(minutes=240, pets=[mochi, luna])
    scheduler = Scheduler(owner)

    plan = scheduler.generate_plan(MONDAY)

    assert len(plan.scheduled) == 6
    assert scheduler._find_conflicts(plan.scheduled) == []


def test_owner_with_no_tasks_gets_empty_plan():
    owner = make_owner(pets=[Pet("Mochi", "dog")])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert plan.scheduled == []
    assert plan.skipped == []
    assert plan.total_minutes() == 0
