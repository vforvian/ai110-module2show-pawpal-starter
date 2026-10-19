"""Temporary testing ground: build a sample owner and print today's plan."""

from datetime import date, time

from pawpal_system import (
    DailyPlan,
    Frequency,
    Owner,
    Pet,
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

    mochi.add_task(Task("Heartworm pill", 5, Priority.HIGH, "meds",
                        preferred_time=time(8, 0)))
    mochi.add_task(Task("Morning walk", 30, Priority.HIGH, "walk"))
    mochi.add_task(Task("Evening walk", 30, Priority.MEDIUM, "walk",
                        preferred_time=time(18, 0)))
    mochi.add_task(Task("Bath", 45, Priority.LOW, "grooming",
                        Frequency.WEEKLY, due_weekday=6))

    luna.add_task(Task("Breakfast", 10, Priority.HIGH, "feeding",
                       preferred_time=time(8, 0)))
    luna.add_task(Task("Play session", 20, Priority.MEDIUM, "enrichment"))
    luna.add_task(Task("Brush coat", 15, Priority.LOW, "grooming"))

    litter = Task("Clean litter box", 10, Priority.MEDIUM, "cleaning")
    litter.mark_complete()
    luna.add_task(litter)

    return owner


def print_schedule(owner: Owner, plan: DailyPlan) -> None:
    width = 72
    print("=" * width)
    print(f"🐾 Today's Schedule for {owner.name} — "
          f"{plan.day:%A, %B %d, %Y}")
    print("=" * width)
    print(f"{'Time':<13}{'Task':<18}{'Pet':<8}{'Priority':<10}Why")
    print("-" * width)
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


if __name__ == "__main__":
    owner = build_owner()
    plan = Scheduler(owner).generate_plan(date.today())
    print_schedule(owner, plan)
