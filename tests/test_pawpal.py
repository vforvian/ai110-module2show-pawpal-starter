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


# --- Sorting by time ----------------------------------------------------

def test_sort_by_time_orders_pinned_tasks_and_puts_flexible_last():
    pet = Pet("Mochi", "dog")
    play = Task("Play", 20)
    evening = Task("Evening walk", 30, preferred_time=time(18, 0))
    pill = Task("Pill", 5, preferred_time=time(8, 0))
    brush = Task("Brush", 15)
    for task in (play, evening, pill, brush):
        pet.add_task(task)
    owner = make_owner(pets=[pet])

    ordered = Scheduler.sort_by_time(owner.get_all_tasks())

    # Flexible tasks keep their original order after the pinned ones
    assert [t.title for _, t in ordered] == [
        "Pill", "Evening walk", "Play", "Brush"
    ]


# --- Filtering ----------------------------------------------------------

def test_filter_tasks_by_pet_and_status():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    walk, feed, brush = Task("Walk", 30), Task("Feeding", 10), Task("Brush", 5)
    feed.mark_complete()
    mochi.add_task(walk)
    luna.add_task(feed)
    luna.add_task(brush)
    owner = make_owner(pets=[mochi, luna])

    assert owner.filter_tasks() == owner.get_all_tasks()
    assert owner.filter_tasks(pet_name="Luna") == [(luna, feed), (luna, brush)]
    assert owner.filter_tasks(completed=True) == [(luna, feed)]
    assert owner.filter_tasks(pet_name="Luna", completed=False) == [
        (luna, brush)
    ]
    assert owner.filter_tasks(pet_name="Nobody") == []


# --- Recurring tasks ----------------------------------------------------

def test_completing_daily_task_schedules_it_for_tomorrow():
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH)
    pet.add_task(walk)
    owner = make_owner(pets=[pet])
    scheduler = Scheduler(owner)

    upcoming = pet.complete_task(walk.id, MONDAY)

    assert walk.completed
    assert upcoming.id != walk.id
    assert (upcoming.title, upcoming.priority) == ("Walk", Priority.HIGH)
    assert upcoming.due_date == date(2026, 10, 20)
    assert not upcoming.completed
    # Done for today, back tomorrow
    assert titles(scheduler.generate_plan(MONDAY)) == []
    assert titles(scheduler.generate_plan(date(2026, 10, 20))) == ["Walk"]


def test_completing_weekly_task_schedules_it_for_next_week():
    pet = Pet("Mochi", "dog")
    bath = Task("Bath", 45, frequency=Frequency.WEEKLY, due_weekday=6)
    pet.add_task(bath)

    upcoming = pet.complete_task(bath.id, SUNDAY)

    assert upcoming.due_date == date(2026, 10, 25)
    assert not upcoming.is_due(SUNDAY)
    assert upcoming.is_due(date(2026, 10, 25))


def test_weekly_task_done_early_still_comes_back_on_its_weekday():
    pet = Pet("Mochi", "dog")
    bath = Task("Bath", 45, frequency=Frequency.WEEKLY, due_weekday=6)
    pet.add_task(bath)

    # Done on Friday instead of Sunday: next one is the coming Sunday
    upcoming = pet.complete_task(bath.id, date(2026, 10, 16))

    assert upcoming.due_date == SUNDAY


def test_completing_a_task_twice_is_rejected():
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30)
    pet.add_task(walk)
    pet.complete_task(walk.id, MONDAY)

    with pytest.raises(ValueError):
        pet.complete_task(walk.id, MONDAY)
    assert len(pet.tasks) == 2


# --- Conflict detection -------------------------------------------------

def test_detect_conflicts_warns_about_overlapping_pinned_tasks():
    mochi, luna = Pet("Mochi", "dog"), Pet("Luna", "cat")
    mochi.add_task(Task("Walk", 30, preferred_time=time(8, 0)))
    luna.add_task(Task("Breakfast", 10, preferred_time=time(8, 15)))
    luna.add_task(Task("Play", 20, preferred_time=time(8, 30)))  # touches
    owner = make_owner(pets=[mochi, luna])
    scheduler = Scheduler(owner)

    warnings = scheduler.detect_conflicts(MONDAY)

    assert warnings == [
        "Walk (Mochi) at 08:00 overlaps Breakfast (Luna) at 08:15 "
        "[different pets]"
    ]
    plan = scheduler.generate_plan(MONDAY)
    assert plan.warnings == warnings
    assert "⚠" in plan.explain()


def test_detect_conflicts_ignores_tasks_not_due_or_done():
    pet = Pet("Mochi", "dog")
    done = Task("Pill", 5, preferred_time=time(8, 0))
    done.mark_complete()
    pet.add_task(done)
    pet.add_task(Task("Bath", 45, frequency=Frequency.WEEKLY,
                      due_weekday=6, preferred_time=time(8, 0)))
    pet.add_task(Task("Walk", 30, preferred_time=time(8, 0)))
    owner = make_owner(pets=[pet])

    assert Scheduler(owner).detect_conflicts(MONDAY) == []


def test_detect_conflicts_flags_same_pet_at_the_same_time():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Evening walk", 30, preferred_time=time(18, 0)))
    pet.add_task(Task("Dinner", 10, preferred_time=time(18, 0)))
    owner = make_owner(pets=[pet])

    assert Scheduler(owner).detect_conflicts(MONDAY) == [
        "Evening walk (Mochi) at 18:00 overlaps Dinner (Mochi) at 18:00 "
        "[same pet]"
    ]


def test_pinned_task_running_past_midnight_is_skipped_not_crashing():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Late walk", 20, preferred_time=time(23, 50)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner, day_end=time(23, 59)).generate_plan(MONDAY)

    assert plan.scheduled == []
    assert "does not fit" in plan.skipped[0].reason


# --- Edge cases ---------------------------------------------------------

def test_tasks_that_exactly_use_the_budget_are_all_scheduled():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30))
    pet.add_task(Task("Feeding", 10))
    owner = make_owner(minutes=40, pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert sorted(titles(plan)) == ["Feeding", "Walk"]
    assert plan.total_minutes() == 40
    assert plan.skipped == []


def test_pinned_task_ending_exactly_at_day_end_is_scheduled():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Last walk", 30, preferred_time=time(19, 30)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert plan.scheduled[0].start == time(19, 30)
    assert plan.scheduled[0].end == time(20, 0)
    assert plan.skipped == []


def test_three_tasks_at_the_same_time_are_warned_and_spread_out():
    pet = Pet("Mochi", "dog")
    for title in ("Pill", "Breakfast", "Water"):
        pet.add_task(Task(title, 10, preferred_time=time(9, 0)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert len(plan.warnings) == 3  # every pair overlaps
    assert [entry.start for entry in plan.scheduled] == [
        time(9, 0), time(9, 10), time(9, 20)
    ]


def test_higher_priority_pinned_task_keeps_its_time_over_an_earlier_one():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Brush", 30, Priority.LOW, preferred_time=time(8, 0)))
    pet.add_task(Task("Meds", 30, Priority.HIGH, preferred_time=time(8, 10)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    meds, brush = plan.scheduled
    assert (meds.task.title, meds.start) == ("Meds", time(8, 10))
    assert (brush.task.title, brush.start) == ("Brush", time(8, 40))
    assert "moved from 08:00" in brush.reason


def test_conflicting_pinned_task_with_no_later_slot_is_skipped():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, Priority.HIGH, preferred_time=time(19, 30)))
    pet.add_task(Task("Play", 30, preferred_time=time(19, 30)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert titles(plan) == ["Walk"]
    assert [s.task.title for s in plan.skipped] == ["Play"]
    assert "no later slot is free" in plan.skipped[0].reason


def test_daily_task_completed_on_new_years_eve_returns_jan_1():
    task = Task("Feeding", 10)

    upcoming = task.next_occurrence(date(2026, 12, 31))

    assert upcoming.due_date == date(2027, 1, 1)


def test_weekly_task_done_the_day_before_returns_the_next_day():
    bath = Task("Bath", 45, frequency=Frequency.WEEKLY, due_weekday=6)
    saturday = date(2026, 10, 17)

    upcoming = bath.next_occurrence(saturday)

    assert upcoming.due_date == SUNDAY
    assert upcoming.is_due(SUNDAY)


def test_next_occurrence_keeps_settings_but_gets_new_id():
    task = Task("Pill", 5, Priority.HIGH, "meds", preferred_time=time(8, 0))

    upcoming = task.next_occurrence(MONDAY)

    assert upcoming.priority is Priority.HIGH
    assert upcoming.category == "meds"
    assert upcoming.preferred_time == time(8, 0)
    assert upcoming.completed is False
    assert upcoming.id != task.id


def test_zero_budget_skips_everything():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30))
    pet.add_task(Task("Pill", 5, preferred_time=time(8, 0)))
    owner = make_owner(minutes=0, pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert plan.scheduled == []
    assert len(plan.skipped) == 2
    assert all("budget" in s.reason for s in plan.skipped)


def test_pet_with_no_tasks_does_not_affect_other_pets():
    empty, mochi = Pet("Luna", "cat"), Pet("Mochi", "dog")
    mochi.add_task(Task("Walk", 30))
    owner = make_owner(pets=[empty, mochi])

    plan = Scheduler(owner).generate_plan(MONDAY)

    assert [entry.pet.name for entry in plan.scheduled] == ["Mochi"]
    assert owner.filter_tasks(pet_name="Luna") == []


def test_plan_is_returned_in_chronological_order():
    pet = Pet("Mochi", "dog")
    # Added out of order, and the HIGH task is the latest one
    pet.add_task(Task("Dinner", 10, Priority.HIGH,
                      preferred_time=time(18, 0)))
    pet.add_task(Task("Lunch", 10, preferred_time=time(12, 0)))
    pet.add_task(Task("Play", 20, Priority.LOW))
    pet.add_task(Task("Breakfast", 10, preferred_time=time(8, 0)))
    owner = make_owner(pets=[pet])

    plan = Scheduler(owner).generate_plan(MONDAY)

    starts = [entry.start for entry in plan.scheduled]
    assert starts == sorted(starts)
    assert titles(plan) == ["Breakfast", "Play", "Lunch", "Dinner"]
