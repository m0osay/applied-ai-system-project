import logging

import streamlit as st

from gemini_agent import AgentInsight, PawPalAgent
from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")


def build_task_table(task_pairs: list[tuple[str, Task]]) -> list[dict[str, str | int]]:
    """Convert pet-task pairs into rows for Streamlit tables."""
    return [
        {
            "Pet": pet_name,
            "Time": task.time,
            "Task": task.description,
            "Frequency": task.frequency,
            "Priority": task.priority.title(),
            "Duration": task.duration_minutes,
            "Due Date": task.due_date.isoformat(),
            "Status": "Done" if task.completed else "Pending",
        }
        for pet_name, task in task_pairs
    ]


def build_schedule_table(plan) -> list[dict[str, str]]:
    """Convert scheduled items into rows for the generated schedule table."""
    return [
        {
            "Start": item.start_time,
            "End": item.end_time,
            "Pet": item.pet_name,
            "Task": item.task.description,
            "Priority": item.task.priority.title(),
            "Requested": item.task.time,
        }
        for item in plan.items
    ]


if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_minutes_per_day=45)
if "agent_insight" not in st.session_state:
    st.session_state.agent_insight = None

owner = st.session_state.owner

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, #fff6e8 0%, transparent 28%),
            radial-gradient(circle at top right, #e3f2ef 0%, transparent 24%),
            linear-gradient(180deg, #fffdf8 0%, #f6fbfa 100%);
    }
    .hero {
        padding: 1.25rem 1.4rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #183a37 0%, #25544c 55%, #356d60 100%);
        color: #fff8ef;
        box-shadow: 0 18px 50px rgba(24, 58, 55, 0.18);
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0 0 0.35rem 0;
        font-size: 2.3rem;
    }
    .hero p {
        margin: 0;
        font-size: 1rem;
        max-width: 48rem;
        line-height: 1.5;
    }
    .section-card {
        background: rgba(255, 255, 255, 0.75);
        border: 1px solid rgba(24, 58, 55, 0.08);
        border-radius: 18px;
        padding: 1rem 1rem 0.4rem 1rem;
        box-shadow: 0 10px 30px rgba(24, 58, 55, 0.06);
        margin-bottom: 1rem;
    }
    .small-note {
        color: #4f635f;
        font-size: 0.95rem;
    }
    </style>
    <div class="hero">
        <h1>PawPal+</h1>
        <p>Plan pet care with a cleaner daily schedule, smarter task sorting, recurring task support, and gentle conflict warnings before your day gets crowded.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Today at a Glance")
    st.caption("Your scheduling inputs update the planner immediately.")

    owner_name = st.text_input("Owner name", value=owner.name)
    available_minutes = st.number_input(
        "Available minutes today",
        min_value=1,
        max_value=720,
        value=owner.available_minutes_per_day,
    )

    owner.name = owner_name
    owner.available_minutes_per_day = int(available_minutes)

    total_tasks = len(owner.get_all_tasks())
    pending_tasks = len(owner.get_all_tasks(include_completed=False))
    st.metric("Pets", len(owner.pets))
    st.metric("All tasks", total_tasks)
    st.metric("Pending tasks", pending_tasks)
    st.metric("Available time", f"{owner.available_minutes_per_day} min")

scheduler = Scheduler(owner)
all_tasks = scheduler.get_all_tasks(include_completed=True)
pending_tasks = scheduler.filter_tasks_by(include_completed=False)
sorted_pending_tasks = scheduler.sort_tasks(pending_tasks)

overview_col, builder_col = st.columns([1.1, 1], gap="large")

with overview_col:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Household Overview")
    st.markdown(
        '<p class="small-note">Track your pets, scan pending work, and catch conflicts early.</p>',
        unsafe_allow_html=True,
    )

    if owner.pets:
        st.table(
            [
                {"Name": pet.name, "Species": pet.species.title(), "Age": pet.age}
                for pet in owner.pets
            ]
        )
    else:
        st.info("No pets added yet. Add your first pet in the planner panel.")

    if sorted_pending_tasks:
        st.markdown("#### Sorted pending tasks")
        st.table(build_task_table(sorted_pending_tasks))

        conflict_warnings = scheduler.detect_conflicts(sorted_pending_tasks)
        for warning in conflict_warnings:
            st.warning(
                f"Conflict detected: {warning} This should be shown prominently so a pet owner can adjust one of the times before following the plan."
            )
    elif owner.pets:
        st.info("Your pets are set up, but there are no pending tasks yet.")

    st.markdown("</div>", unsafe_allow_html=True)

with builder_col:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Add a Pet")
    add_pet_col1, add_pet_col2, add_pet_col3 = st.columns([1.4, 1, 1])
    with add_pet_col1:
        pet_name = st.text_input("Pet name", value="Mochi")
    with add_pet_col2:
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with add_pet_col3:
        pet_age = st.number_input("Pet age", min_value=0, max_value=40, value=3)

    if st.button("Add pet", use_container_width=True):
        existing_pet = owner.get_pet(pet_name)
        if existing_pet is None:
            owner.add_pet(Pet(name=pet_name, species=species, age=int(pet_age)))
            st.success(f"Added {pet_name} to {owner.name}'s household.")
        else:
            st.info(f"{pet_name} is already in the profile.")

    st.markdown("#### Add a task")
    if owner.pets:
        selected_pet_name = st.selectbox(
            "Assign task to",
            [pet.name for pet in owner.pets],
        )
        task_col1, task_col2 = st.columns(2)
        with task_col1:
            task_description = st.text_input("Task description", value="Morning walk")
            task_time = st.text_input("Preferred time", value="08:00")
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly", "as needed"],
                index=0,
            )
        with task_col2:
            duration = st.number_input(
                "Duration (minutes)",
                min_value=1,
                max_value=240,
                value=20,
            )
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

        if st.button("Add task", use_container_width=True):
            pet = owner.get_pet(selected_pet_name)
            if pet is not None:
                pet.add_task(
                    Task(
                        description=task_description,
                        time=task_time,
                        frequency=frequency,
                        duration_minutes=int(duration),
                        priority=priority,
                    )
                )
                st.success(f"Added '{task_description}' for {selected_pet_name}.")

        selected_pet_tasks = scheduler.filter_tasks_by(
            pet_name=selected_pet_name,
            include_completed=False,
        )
        if selected_pet_tasks:
            st.markdown(f"#### Pending tasks for {selected_pet_name}")
            st.table(build_task_table(selected_pet_tasks))
        else:
            st.info(f"{selected_pet_name} has no pending tasks.")
    else:
        st.info("Add a pet first so tasks have somewhere to go.")

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Generate Today’s Schedule")
st.caption("Build a daily plan using the current pets, pending tasks, and available time.")

generate_col, summary_col = st.columns([1, 1.3], gap="large")
with generate_col:
    if st.button("Generate schedule", type="primary", use_container_width=True):
        if not owner.pets or not owner.get_all_tasks(include_completed=False):
            st.warning("Add at least one pet and one pending task before generating a schedule.")
        else:
            st.session_state.latest_plan = scheduler.build_plan()
            try:
                agent = PawPalAgent()
                st.session_state.agent_insight = agent.analyze(
                    owner, st.session_state.latest_plan
                )
            except Exception as exc:
                logging.error("Unexpected agent error: %s", exc)
                st.session_state.agent_insight = None

with summary_col:
    st.markdown(
        f"Planner ready for **{owner.name}** with **{len(owner.pets)}** pet(s) and **{len(pending_tasks)}** pending task(s)."
    )

plan = st.session_state.get("latest_plan")
if plan is not None:
    if plan.items:
        top_metrics = st.columns(3)
        top_metrics[0].metric("Scheduled items", len(plan.items))
        top_metrics[1].metric("Minutes used", plan.total_minutes_used)
        top_metrics[2].metric("Warnings", len(plan.warnings))

        st.table(build_schedule_table(plan))
    else:
        st.info("No tasks fit into the available time today.")

    if plan.warnings:
        st.markdown("#### Scheduling warnings")
        for warning in plan.warnings:
            st.warning(warning)

    if plan.skipped_tasks:
        st.markdown("#### Skipped tasks")
        st.table(
            [
                {
                    "Pet": pet_name,
                    "Task": task.description,
                    "Requested": task.time,
                    "Duration": task.duration_minutes,
                }
                for pet_name, task in plan.skipped_tasks
            ]
        )

    st.markdown("#### Why this plan was chosen")
    st.success(plan.summary)

    insight: AgentInsight | None = st.session_state.get("agent_insight")
    if insight is not None:
        with st.expander("AI Care Gap Analysis (Gemini Flash)", expanded=True):
            if insight.error:
                st.warning(f"AI analysis unavailable: {insight.error}")
            else:
                if insight.overall_note:
                    st.info(insight.overall_note)

                validated = insight.validated or []
                if validated:
                    actionable = [v for v in validated if v.get("status") == "actionable"]
                    deferred = [v for v in validated if v.get("status") == "deferred"]

                    if actionable:
                        st.markdown("**Actionable today:**")
                        for item in actionable:
                            st.success(
                                f"**{item.get('pet_name')}** — {item.get('suggestion')} "
                                f"({item.get('suggested_duration_minutes')} min)  \n"
                                f"_{item.get('confidence_note', '')}_"
                            )
                    if deferred:
                        st.markdown("**Suggested for tomorrow:**")
                        for item in deferred:
                            st.info(
                                f"**{item.get('pet_name')}** — {item.get('suggestion')}  \n"
                                f"_{item.get('confidence_note', '')}_"
                            )
                elif insight.gaps:
                    st.markdown("**Identified care gaps:**")
                    for gap in insight.gaps:
                        st.info(
                            f"**{gap.get('pet_name')}** ({gap.get('gap_type')}): "
                            f"{gap.get('suggestion')} — {gap.get('reason')}"
                        )
else:
    st.info("Generate a schedule to see your full daily plan here.")

st.markdown("</div>", unsafe_allow_html=True)
