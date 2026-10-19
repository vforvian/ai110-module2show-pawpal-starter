"""Temporary testing ground: build a sample owner and print today's plan."""

from datetime import date, time

from pawpal_system import (
    DailyPlan,
    Frequency,
    Owner,
    Pet,
    PetTask,
    Priority,
    Scheduler,
    Task,
)


def build_owner() -> Owner:
    owner = Owner("Jordan", available_minutes=120,
                  preferred_categories=["meds", "walk"])

    mochi = Pet("Mochi", "dog", age=3)
    luna = Pet("Luna", "cat", age=5)
    owner.add_pet(mochi)
    owner.add_pet(luna)

    # Added out of time order on purpose so sort_by_time has work to do
    mochi.add_task(Task("Evening walk", 30, Priority.MEDIUM, "walk",
                        preferred_time=time(18, 0)))
    mochi.add_task(Task("Bath", 45, Priority.LOW, "grooming",
                        Frequency.WEEKLY, due_weekday=6))
    mochi.add_task(Task("Morning walk", 30, Priority.HIGH, "walk"))
    mochi.add_task(Task("Heartworm pill", 5, Priority.HIGH, "meds",
                        preferred_time=time(8, 0)))
    # Same pet, same time as the evening walk: should trigger a warning
    mochi.add_task(Task("Dinner", 10, Priority.MEDIUM, "feeding",
                        preferred_time=time(18, 0)))

    luna.add_task(Task("Brush coat", 15, Priority.LOW, "grooming"))
    luna.add_task(Task("Play session", 20, Priority.MEDIUM, "enrichment",
                       preferred_time=time(12, 30)))
    litter = Task("Clean litter box", 10, Priority.MEDIUM, "cleaning")
    litter.mark_complete()
    luna.add_task(litter)
    luna.add_task(Task("Breakfast", 10, Priority.HIGH, "feeding",
                       preferred_time=time(8, 0)))

    return owner


def print_schedule(owner: Owner, plan: DailyPlan) -> None:
    width = 72
    print("=" * width)
    print(f"🐾 Today's Schedule for {owner.name} — "
          f"{plan.day:%A, %B %d, %Y}")
    print("=" * width)
    print(f"{'Time':<13}{'Task':<18}{'Pet':<8}{'Priority':<10}Why")
    print("-" * width)
    for warning in plan.warnings:
        print(f"⚠ Conflict: {warning}")
    for entry in plan.scheduled:
        print(
            f"{entry.start:%H:%M}-{entry.end:%H:%M}  "
            f"{entry.task.title:<18}{entry.pet.name:<8}"
            f"{entry.task.priority.name.lower():<10}{entry.reason}"
        )
    print("-" * width)
    print(f"Time used: {plan.total_minutes()} of "
          f"{plan.available_minutes} minutes")

    if plan.skipped:
        print("\nSkipped:")
        for item in plan.skipped:
            print(f"  ✗ {item.task.title} ({item.pet.name}): {item.reason}")
    print("=" * width)


def print_tasks(heading: str, items: list[PetTask]) -> None:
    print(f"\n{heading}")
    for pet, task in items:
        when = f"{task.preferred_time:%H:%M}" if task.preferred_time \
            else "flexible"
        print(f"  {when:<9}{task.title:<18}{pet.name:<7}"
              f"{'done' if task.completed else 'to do'}")


if __name__ == "__main__":
    owner = build_owner()
    today = date.today()
    plan = Scheduler(owner).generate_plan(today)
    print_schedule(owner, plan)

    print_tasks("All tasks in the order they were added:",
                owner.get_all_tasks())
    print_tasks("All tasks sorted by time (flexible last):",
                Scheduler.sort_by_time(owner.get_all_tasks()))

    print_tasks("Filter: Mochi's tasks only:",
                owner.filter_tasks(pet_name="Mochi"))
    print_tasks("Filter: completed tasks only:",
                owner.filter_tasks(completed=True))
    print_tasks("Filter + sort: Luna's unfinished tasks by time:",
                Scheduler.sort_by_time(
                    owner.filter_tasks(pet_name="Luna", completed=False)))

    mochi = owner.pets[0]
    walk = next(t for t in mochi.tasks if t.title == "Morning walk")
    upcoming = mochi.complete_task(walk.id, today)
    print(f"\nCompleted '{walk.title}'; next one is due "
          f"{upcoming.due_date:%A, %B %d}.")
    print_tasks("Filter: Mochi's completed tasks after that:",
                owner.filter_tasks(pet_name="Mochi", completed=True))
