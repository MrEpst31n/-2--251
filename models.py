from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Habit:
    id: int
    title: str
    description: str
    schedule_type: str
    schedule_value: int
    total_target: int
    start_date: str


@dataclass(slots=True)
class HabitStats:
    period_completed: int
    total_completed: int
    total_target: int
    percent: float
    current_streak: int
    max_streak: int