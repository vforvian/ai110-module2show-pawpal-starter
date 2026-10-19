from datetime import date, time

import streamlit as st

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption(
    "Plan your pets' care for the day. Add your pets and their tasks, "
    "then generate a schedule that fits your available time."
)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]

# The Owner lives in session_state so it survives Streamlit's reruns
if "owner" not in st.session_state:
    st.session_state.owner = Owner("Jordan", available_minutes=120)
owner: Owner = st.session_state.owner

# --- Owner ------------------------------------------------------------------

st.subheader("👤 Owner")
col1, col2 = st.columns(2)
with col1:
    owner.name = st.text_input("Owner name", value=owner.name)
with col2:
    owner.available_minutes = int(st.number_input(
        "Time available today (minutes)", min_value=10, max_value=720,
        value=owner.available_minutes, step=10,
    ))

st.divider()

# --- Add a pet --------------------------------------------------------------

st.subheader("🐶 Add a pet")
with st.form("add_pet", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name = st.text_input("Pet name", value="Mochi")
    with col2:
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with col3:
        age = st.number_input("Age", min_value=0, max_value=40, value=1)
    if st.form_submit_button("Add pet"):
        if not pet_name.strip():
            st.error("Please enter a pet name.")
        elif any(p.name == pet_name.strip() for p in owner.pets):
            st.error(f"You already have a pet named {pet_name.strip()}.")
        else:
            owner.add_pet(Pet(pet_name.strip(), species, age=int(age)))
            st.success(f"Added {pet_name.strip()}!")

# --- Add a task -------------------------------------------------------------

st.subheader("📝 Add a task")
if not owner.pets:
    st.info("Add a pet first, then you can give it tasks.")
else:
    with st.form("add_task", clear_on_submit=True):
        # Select by name: the selectbox may hand back a copy of a Pet,
        # so look up the real one stored on the owner
        pet_name_choice = st.selectbox(
            "For which pet?", [p.name for p in owner.pets]
        )
        pet_choice = next(p for p in owner.pets if p.name == pet_name_choice)
        col1, col2, col3 = st.columns(3)
        with col1:
            title = st.text_input("Task title", value="Morning walk")
        with col2:
            duration = st.number_input(
                "Duration (minutes)", min_value=1, max_value=240, value=20
            )
        with col3:
            priority = st.selectbox("Priority", ["high", "medium", "low"])

        col1, col2, col3 = st.columns(3)
        with col1:
            category = st.selectbox(
                "Category",
                ["walk", "feeding", "meds", "enrichment", "grooming",
                 "cleaning", "general"],
            )
        with col2:
            frequency = st.selectbox("Repeats", ["daily", "weekly"])
        with col3:
            weekday = st.selectbox("Weekday (if weekly)", WEEKDAYS)

        pinned = st.checkbox("Must start at a specific time")
        start_at = st.time_input("Start time (if pinned)", value=time(8, 0))

        if st.form_submit_button("Add task"):
            try:
                task = Task(
                    title=title.strip() or "Untitled task",
                    duration_minutes=int(duration),
                    priority=Priority[priority.upper()],
                    category=category,
                    frequency=Frequency(frequency),
                    due_weekday=(WEEKDAYS.index(weekday)
                                 if frequency == "weekly" else None),
                    preferred_time=start_at if pinned else None,
                )
            except ValueError as error:
                st.error(str(error))
            else:
                pet_choice.add_task(task)
                st.success(f"Added '{task.title}' for {pet_choice.name}.")

# --- Current pets and tasks -------------------------------------------------

st.subheader("📋 Your pets and tasks")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))
if not owner.pets:
    st.info("No pets yet.")
else:
    st.caption(", ".join(f"{p.name} ({p.species}, age {p.age})"
                         for p in owner.pets))
    col1, col2 = st.columns(2)
    with col1:
        pet_filter = st.selectbox(
            "Show pet", ["All pets"] + [p.name for p in owner.pets]
        )
    with col2:
        status_filter = st.radio(
            "Status", ["To do", "Done", "All"], horizontal=True
        )
    shown = owner.filter_tasks(
        pet_name=None if pet_filter == "All pets" else pet_filter,
        completed={"To do": False, "Done": True, "All": None}[status_filter],
    )
    if not shown:
        st.caption("No tasks match these filters.")
    else:
        st.table([
            {
                "Time": t.preferred_time.strftime("%H:%M")
                if t.preferred_time else "flexible",
                "Task": t.title,
                "Pet": pet.name,
                "Minutes": t.duration_minutes,
                "Priority": t.priority.name.lower(),
                "Category": t.category,
                "Repeats": (f"weekly ({WEEKDAYS[t.due_weekday]})"
                            if t.frequency is Frequency.WEEKLY
                            else "daily"),
                "Due from": f"{t.due_date:%b %d}" if t.due_date else "",
                "Done": "✅" if t.completed else "",
            }
            for pet, t in Scheduler.sort_by_time(shown)
        ])

    # --- Mark a task complete ----------------------------------------------
    open_tasks = owner.filter_tasks(completed=False)
    if open_tasks:
        with st.form("complete_task"):
            labels = [f"{pet.name}: {t.title} ({t.id})"
                      for pet, t in open_tasks]
            choice = st.selectbox("Mark a task complete", labels)
            done_on = st.date_input("Completed on", value=date.today())
            if st.form_submit_button("Mark complete"):
                pet, task = open_tasks[labels.index(choice)]
                upcoming = pet.complete_task(task.id, done_on)
                # Rerun so the table above shows the new task; keep the
                # message so it survives the rerun
                st.session_state.flash = (
                    f"Done! Next '{upcoming.title}' for {pet.name} is due "
                    f"{upcoming.due_date:%A, %B %d}."
                )
                st.rerun()

st.divider()

# --- Build schedule ---------------------------------------------------------

st.subheader("📅 Build schedule")
col1, col2, col3 = st.columns(3)
with col1:
    plan_day = st.date_input("Day", value=date.today())
with col2:
    day_start = st.time_input("Day starts", value=time(8, 0))
with col3:
    day_end = st.time_input("Day ends", value=time(20, 0))

if st.button("Generate schedule", type="primary"):
    if not owner.get_all_tasks():
        st.warning("Add at least one task before generating a schedule.")
    elif day_end <= day_start:
        st.error("The day must end after it starts.")
    else:
        plan = Scheduler(owner, day_start, day_end).generate_plan(plan_day)
        st.markdown(
            f"**{plan_day:%A, %B %d}** — {plan.total_minutes()} of "
            f"{plan.available_minutes} minutes used"
        )
        for warning in plan.warnings:
            st.warning(f"⚠ Time conflict: {warning}. The lower-priority "
                       f"task was moved to the next free slot.")
        if plan.scheduled:
            st.table([
                {
                    "Time": f"{e.start:%H:%M}–{e.end:%H:%M}",
                    "Task": e.task.title,
                    "Pet": e.pet.name,
                    "Priority": e.task.priority.name.lower(),
                    "Why": e.reason,
                }
                for e in plan.scheduled
            ])
        else:
            st.info("Nothing is due on this day.")
        if plan.skipped:
            st.markdown("**Skipped**")
            for item in plan.skipped:
                st.warning(f"{item.task.title} ({item.pet.name}): "
                           f"{item.reason}")
