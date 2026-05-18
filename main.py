from __future__ import annotations

from pathlib import Path

from database import DatabaseManager
from services import HabitService
from ui import HabitTrackerApp


def main() -> None:
    db_path = Path(__file__).resolve().parent / "data" / "habittracker.db"
    db = DatabaseManager(db_path)
    service = HabitService(db)
    app = HabitTrackerApp(service)
    app.mainloop()


if __name__ == "__main__":
    main()
