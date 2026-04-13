"""Basic tests for the PawPal+ logic layer and AI agent reliability."""

import os
from datetime import date
from unittest.mock import MagicMock, patch

from pawpal_system import Owner, Pet, Scheduler, Task


def test_mark_complete_changes_task_status() -> None:
    task = Task(description="Evening walk", time="18:00", frequency="daily")

    task.mark_complete()

    assert task.completed is True


def test_add_task_increases_pet_task_count() -> None:
    pet = Pet(name="Luna", species="Dog", age=4)
    task = Task(description="Breakfast", time="08:00", frequency="daily")

    pet.add_task(task)

    assert len(pet.tasks) == 1


def test_mark_task_complete_creates_next_daily_occurrence() -> None:
    pet = Pet(name="Mochi", species="Cat", age=2)
    task = Task(
        description="Give medication",
        time="09:00",
        frequency="daily",
        due_date=date(2026, 3, 15),
    )
    pet.add_task(task)

    next_task = pet.mark_task_complete("Give medication")

    assert task.completed is True
    assert next_task is not None
    assert next_task.completed is False
    assert next_task.due_date == date(2026, 3, 16)
    assert len(pet.tasks) == 2


def test_mark_task_complete_creates_next_weekly_occurrence() -> None:
    pet = Pet(name="Luna", species="Dog", age=4)
    task = Task(
        description="Bath",
        time="10:00",
        frequency="weekly",
        due_date=date(2026, 3, 15),
    )
    pet.add_task(task)

    next_task = pet.mark_task_complete("Bath")

    assert next_task is not None
    assert next_task.due_date == date(2026, 3, 22)


def test_sort_by_time_returns_tasks_in_chronological_order() -> None:
    owner = Owner(name="Jordan", available_minutes_per_day=60)
    scheduler = Scheduler(owner)
    tasks = [
        Task(description="Lunch", time="12:00", frequency="daily"),
        Task(description="Morning walk", time="08:00", frequency="daily"),
        Task(description="Medication", time="09:30", frequency="daily"),
    ]

    sorted_tasks = scheduler.sort_by_time(tasks)

    assert [task.time for task in sorted_tasks] == ["08:00", "09:30", "12:00"]


def test_detect_conflicts_flags_duplicate_task_times() -> None:
    owner = Owner(name="Jordan", available_minutes_per_day=60)
    luna = Pet(name="Luna", species="Dog", age=4)
    mochi = Pet(name="Mochi", species="Cat", age=2)

    luna.add_task(Task(description="Breakfast", time="08:30", frequency="daily"))
    mochi.add_task(Task(description="Play session", time="08:30", frequency="daily"))
    owner.add_pet(luna)
    owner.add_pet(mochi)

    scheduler = Scheduler(owner)
    conflicts = scheduler.detect_conflicts(scheduler.get_all_tasks())

    assert len(conflicts) == 1
    assert "08:30" in conflicts[0]
    assert "Luna: Breakfast" in conflicts[0]
    assert "Mochi: Play session" in conflicts[0]


# ---------------------------------------------------------------------------
# Phase 4: AI agent reliability tests (offline — no API key or network needed)
# ---------------------------------------------------------------------------

def test_agent_returns_fallback_when_api_key_missing() -> None:
    """PawPalAgent.analyze() returns an error-flagged insight when no key is set."""
    from gemini_agent import AgentInsight, PawPalAgent

    owner = Owner(name="Test", available_minutes_per_day=60)
    pet = Pet(name="Rex", species="dog", age=2)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)
    plan = scheduler.build_plan()

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("GEMINI_API_KEY", None)
        agent = PawPalAgent()
        insight = agent.analyze(owner, plan)

    assert isinstance(insight, AgentInsight)
    assert insight.error is not None
    assert insight.gaps == []


def test_agent_degrades_gracefully_on_api_error() -> None:
    """analyze() returns a usable AgentInsight even when the Gemini call raises."""
    from gemini_agent import AgentInsight, PawPalAgent

    owner = Owner(name="Test", available_minutes_per_day=60)
    pet = Pet(name="Bella", species="cat", age=5)
    pet.add_task(Task(description="Feeding", time="08:00", frequency="daily"))
    owner.add_pet(pet)
    scheduler = Scheduler(owner)
    plan = scheduler.build_plan()

    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
        agent = PawPalAgent()
        # Simulate a network failure on every Gemini call
        agent._client = MagicMock()
        agent._client.models.generate_content.side_effect = Exception("API timeout")

        insight = agent.analyze(owner, plan)

    assert isinstance(insight, AgentInsight)
    assert insight.error is not None
