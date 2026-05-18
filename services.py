from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from database import DatabaseManager
from models import Habit, HabitStats


class HabitService:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create_habit(
        self,
        title: str,
        description: str,
        schedule_type: str,
        schedule_value: int,
        total_target: int,
        start_date: str,
    ) -> int:
        title = title.strip()
        description = description.strip()
        if not title:
            raise ValueError("Название привычки не может быть пустым.")
        if schedule_value < 1 or schedule_value > 7:
            raise ValueError("Количество дней в неделю должно быть от 1 до 7.")
        if total_target < 1:
            raise ValueError("Общая цель должна быть не меньше 1.")
        self._validate_date(start_date)
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO habits(title, description, schedule_type, schedule_value, total_target, start_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, description, schedule_type, schedule_value, total_target, start_date),
            )
            return int(cursor.lastrowid)

    def update_habit(
        self,
        habit_id: int,
        title: str,
        description: str,
        schedule_type: str,
        schedule_value: int,
        total_target: int,
        start_date: str,
    ) -> None:
        title = title.strip()
        if not title:
            raise ValueError("Название привычки не может быть пустым.")
        if total_target < 1:
            raise ValueError("Общая цель должна быть не меньше 1.")
        self._validate_date(start_date)
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE habits
                SET title = ?, description = ?, schedule_type = ?, schedule_value = ?,
                    total_target = ?, start_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, description.strip(), schedule_type, schedule_value, total_target, start_date, habit_id),
            )

    def delete_habit(self, habit_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))

    def list_habits(self) -> list[Habit]:
        query = "SELECT id, title, description, schedule_type, schedule_value, total_target, start_date FROM habits ORDER BY title COLLATE NOCASE ASC"
        with self.db.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [Habit(**dict(row)) for row in rows]

    def get_habit(self, habit_id: int) -> Habit | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, title, description, schedule_type, schedule_value, total_target, start_date FROM habits WHERE id = ?",
                (habit_id,),
            ).fetchone()
        return Habit(**dict(row)) if row else None

    def toggle_completion(self, habit_id: int, log_date: str, done: bool) -> None:
        self._validate_date(log_date)
        with self.db.connect() as conn:
            if done:
                conn.execute(
                    """
                    INSERT INTO habit_logs(habit_id, log_date, status)
                    VALUES (?, ?, 1)
                    ON CONFLICT(habit_id, log_date) DO UPDATE SET status = 1
                    """,
                    (habit_id, log_date),
                )
            else:
                conn.execute(
                    "DELETE FROM habit_logs WHERE habit_id = ? AND log_date = ?",
                    (habit_id, log_date),
                )

    def is_completed(self, habit_id: int, log_date: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM habit_logs WHERE habit_id = ? AND log_date = ? AND status = 1",
                (habit_id, log_date),
            ).fetchone()
        return row is not None

    def get_period_logs(self, habit_id: int, start: str, end: str) -> dict[str, int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT log_date, status FROM habit_logs
                WHERE habit_id = ? AND log_date BETWEEN ? AND ?
                ORDER BY log_date ASC
                """,
                (habit_id, start, end),
            ).fetchall()
        return {row["log_date"]: row["status"] for row in rows}

    def calculate_stats(self, habit_id: int, period_start: str, period_end: str, today: str | None = None) -> HabitStats:
        habit = self.get_habit(habit_id)
        if habit is None:
            raise ValueError("Привычка не найдена.")

        start_dt = self._validate_date(period_start)
        end_dt = self._validate_date(period_end)
        if end_dt < start_dt:
            raise ValueError("Дата окончания периода не может быть раньше даты начала.")
        today_dt = self._validate_date(today) if today else date.today()

        logs = self.get_period_logs(habit_id, start_dt.isoformat(), end_dt.isoformat())
        period_completed = sum(1 for value in logs.values() if value == 1)

        with self.db.connect() as conn:
            total_row = conn.execute("SELECT COUNT(*) as cnt FROM habit_logs WHERE habit_id = ? AND status = 1", (habit_id,)).fetchone()
            total_completed = total_row["cnt"] if total_row else 0

        percent = round((total_completed / habit.total_target) * 100, 2) if habit.total_target > 0 else 0.0
        current_streak, max_streak = self._calculate_streaks(habit, today_dt)

        return HabitStats(
            period_completed=period_completed,
            total_completed=total_completed,
            total_target=habit.total_target,
            percent=percent,
            current_streak=current_streak,
            max_streak=max_streak,
        )

    def build_activity_matrix(self, habit_id: int, days: int = 35) -> list[tuple[str, bool]]:
        today = date.today()
        start = today - timedelta(days=days - 1)
        logs = self.get_period_logs(habit_id, start.isoformat(), today.isoformat())
        result: list[tuple[str, bool]] = []
        cursor = start
        while cursor <= today:
            result.append((cursor.isoformat(), logs.get(cursor.isoformat(), 0) == 1))
            cursor += timedelta(days=1)
        return result

    def _calculate_streaks(self, habit: Habit, today_dt: date) -> tuple[int, int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT log_date FROM habit_logs WHERE habit_id = ? AND status = 1 ORDER BY log_date ASC",
                (habit.id,),
            ).fetchall()
        completed_dates = [datetime.strptime(row["log_date"], "%Y-%m-%d").date() for row in rows]
        if not completed_dates:
            return 0, 0

        completed_set = set(completed_dates)
        if habit.schedule_type == "weekly" or habit.schedule_value < 7:
            weekly_counts: dict[tuple[int, int], int] = defaultdict(int)
            for dt in completed_dates:
                weekly_counts[dt.isocalendar()[:2]] += 1
            sorted_weeks = sorted(weekly_counts)
            max_streak = 0
            current = 0
            prev_year_week: tuple[int, int] | None = None
            for year_week in sorted_weeks:
                if weekly_counts[year_week] < habit.schedule_value:
                    current = 0
                    prev_year_week = year_week
                    continue
                if prev_year_week and self._next_week(prev_year_week) == year_week:
                    current += 1
                else:
                    current = 1
                max_streak = max(max_streak, current)
                prev_year_week = year_week
            current_streak = 0
            this_week = today_dt.isocalendar()[:2]
            week_cursor = this_week
            while weekly_counts.get(week_cursor, 0) >= habit.schedule_value:
                current_streak += 1
                week_cursor = self._prev_week(week_cursor)
            return current_streak, max_streak

        max_streak = 0
        current = 0
        prev_date: date | None = None
        for dt in completed_dates:
            if prev_date and (dt - prev_date).days == 1:
                current += 1
            else:
                current = 1
            max_streak = max(max_streak, current)
            prev_date = dt

        current_streak = 0
        date_cursor = today_dt
        while date_cursor in completed_set:
            current_streak += 1
            date_cursor -= timedelta(days=1)
        return current_streak, max_streak

    @staticmethod
    def _next_week(year_week: tuple[int, int]) -> tuple[int, int]:
        year, week = year_week
        dt = datetime.fromisocalendar(year, week, 1).date() + timedelta(days=7)
        iso = dt.isocalendar()
        return iso[0], iso[1]

    @staticmethod
    def _prev_week(year_week: tuple[int, int]) -> tuple[int, int]:
        year, week = year_week
        dt = datetime.fromisocalendar(year, week, 1).date() - timedelta(days=7)
        iso = dt.isocalendar()
        return iso[0], iso[1]

    @staticmethod
    def _validate_date(value: str) -> date:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД.") from exc