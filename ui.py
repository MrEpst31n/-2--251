from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta, datetime
from tkinter import messagebox, ttk

from models import Habit
from services import HabitService

MONTHS_RU_GEN = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября",
                 "Ноября", "Декабря"]


def iso_to_ru(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        d = datetime.strptime(iso_str, "%Y-%m-%d")
        return f"{d.day:02d} {MONTHS_RU_GEN[d.month - 1]} {d.year}"
    except Exception:
        return iso_str


def ru_to_iso(ru_str: str) -> str:
    try:
        parts = ru_str.strip().split()
        day = int(parts[0])
        month = MONTHS_RU_GEN.index(parts[1]) + 1
        year = int(parts[2])
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return ru_str


class AutoScrollbar(ttk.Scrollbar):
    def set(self, lo: str | float, hi: str | float) -> None:
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(lo, hi)


class HabitDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, service: HabitService, habit: Habit | None = None) -> None:
        super().__init__(master)
        self.service = service
        self.habit = habit
        self.result = False
        self.title("Добавление привычки" if habit is None else "Редактирование привычки")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(bg="#FFFFFF")

        self.columnconfigure(1, weight=1)

        self.title_var = tk.StringVar(value=habit.title if habit else "")
        self.desc_var = tk.StringVar(value=habit.description if habit else "")
        self.days_per_week_var = tk.StringVar(value=str(habit.schedule_value) if habit else "7")
        self.total_target_var = tk.StringVar(value=str(habit.total_target) if habit else "100")

        initial_date = habit.start_date if habit else date.today().isoformat()
        self.start_var = tk.StringVar(value=iso_to_ru(initial_date))

        main_frame = ttk.Frame(self, style="Card.TFrame", padding=20)
        main_frame.pack(fill="both", expand=True)

        fields = [
            ("Название:", ttk.Entry(main_frame, textvariable=self.title_var, width=40, font=("Segoe UI", 10))),
            ("Описание:", ttk.Entry(main_frame, textvariable=self.desc_var, width=40, font=("Segoe UI", 10))),
        ]
        for row_idx, (label, widget) in enumerate(fields):
            ttk.Label(main_frame, text=label, style="Form.TLabel").grid(row=row_idx, column=0, padx=(0, 10), pady=10,
                                                                        sticky="w")
            widget.grid(row=row_idx, column=1, pady=10, sticky="ew")

        ttk.Label(main_frame, text="Дней в неделю:", style="Form.TLabel").grid(row=2, column=0, padx=(0, 10), pady=10,
                                                                               sticky="w")
        ttk.Spinbox(
            main_frame, textvariable=self.days_per_week_var, from_=1, to=7, width=13, font=("Segoe UI", 10)
        ).grid(row=2, column=1, pady=10, sticky="w")

        ttk.Label(main_frame, text="Цель (всего раз):", style="Form.TLabel").grid(row=3, column=0, padx=(0, 10),
                                                                                  pady=10, sticky="w")
        ttk.Entry(main_frame, textvariable=self.total_target_var, width=15, font=("Segoe UI", 10)).grid(row=3, column=1,
                                                                                                        pady=10,
                                                                                                        sticky="w")

        ttk.Label(main_frame, text="Дата начала:", style="Form.TLabel").grid(row=4, column=0, padx=(0, 10), pady=10,
                                                                             sticky="w")
        ttk.Entry(main_frame, textvariable=self.start_var, width=15, font=("Segoe UI", 10)).grid(row=4, column=1,
                                                                                                 pady=10, sticky="w")
        ttk.Label(main_frame, text="(например: 16 Мая 2026)", style="Muted.TLabel").grid(row=4, column=1, padx=(120, 0),
                                                                                         pady=10, sticky="w")

        button_row = ttk.Frame(main_frame, style="Card.TFrame")
        button_row.grid(row=5, column=0, columnspan=2, pady=(20, 0), sticky="e")
        ttk.Button(button_row, text="Отмена", command=self.destroy).pack(side="left", padx=(0, 10))
        ttk.Button(button_row, text="Сохранить", style="Accent.TButton", command=self.on_save).pack(side="left")

    def on_save(self) -> None:
        try:
            start_date_iso = ru_to_iso(self.start_var.get())
            datetime.strptime(start_date_iso, "%Y-%m-%d")
        except Exception:
            messagebox.showerror("Ошибка", "Неверный формат даты. Пример: 16 Мая 2026", parent=self)
            return

        try:
            days_val = int(self.days_per_week_var.get())
            total_val = int(self.total_target_var.get())
            calc_type = "daily" if days_val == 7 else "weekly"

            if self.habit is None:
                self.service.create_habit(
                    self.title_var.get(), self.desc_var.get(), calc_type, days_val, total_val, start_date_iso
                )
            else:
                self.service.update_habit(
                    self.habit.id, self.title_var.get(), self.desc_var.get(), calc_type, days_val, total_val,
                    start_date_iso
                )
            self.result = True
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)


class HabitTrackerApp(tk.Tk):
    def __init__(self, service: HabitService) -> None:
        super().__init__()
        self.service = service
        self.selected_habit_id: int | None = None

        self.title("HabitTracker")
        self.geometry("1280x800")
        self.minsize(1100, 720)
        self.configure(bg="#EFF6FF")

        self._apply_styles()

        self.date_map: dict[str, str] = {}
        past_dates_display = []
        for i in range(31):
            d = date.today() - timedelta(days=i)
            iso = d.isoformat()
            display = iso_to_ru(iso)
            self.date_map[display] = iso
            past_dates_display.append(display)

        self.past_dates_display = past_dates_display
        self.display_date_var = tk.StringVar(value=past_dates_display[0])
        self.period_var = tk.StringVar(value="неделя")
        self.display_date_var.trace_add("write", lambda *_: self.refresh_completion_status())

        self._build_layout()
        self.refresh_habits()

    def _apply_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", background="#EFF6FF", font=("Segoe UI", 10))
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(10, 6), borderwidth=0)
        style.map("TButton", background=[("active", "#E0E7FF")], foreground=[("active", "#312E81")])
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8), background="#6366F1",
                        foreground="white")
        style.map("Accent.TButton", background=[("active", "#4F46E5")])
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"), foreground="#1E1B4B", background="#EFF6FF")
        style.configure("CardTitle.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1E293B", background="#FFFFFF")
        style.configure("Form.TLabel", font=("Segoe UI", 10, "bold"), foreground="#475569", background="#FFFFFF")
        style.configure("Muted.TLabel", font=("Segoe UI", 9, "bold"), foreground="#94A3B8", background="#FFFFFF")
        style.configure("StatValue.TLabel", font=("Segoe UI", 28, "bold"), foreground="#6366F1", background="#FFFFFF")
        style.configure("TCombobox", padding=5)
        style.configure("TEntry", padding=5)

        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("Treeview", rowheight=36, font=("Segoe UI", 10), borderwidth=0, background="#FFFFFF",
                        fieldbackground="#FFFFFF")
        style.map("Treeview", background=[("selected", "#EEF2FF")], foreground=[("selected", "#3730A3")])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(0, 8), background="#F8FAFC",
                        foreground="#475569", borderwidth=0)

        style.configure("TNotebook", background="#EFF6FF", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 6), background="#E0E7FF",
                        foreground="#6366F1", borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", "#FFFFFF")],
                  foreground=[("selected", "#312E81")],
                  padding=[("selected", (22, 12))])

    def _bind_mousewheel(self, widget: tk.Widget, target: tk.Widget) -> None:
        def on_mousewheel(event: tk.Event) -> None:
            delta = getattr(event, "delta", 0)
            num = getattr(event, "num", 0)

            if num == 5 or delta < 0:
                target.yview_scroll(1, "units")
            elif num == 4 or delta > 0:
                target.yview_scroll(-1, "units")

        widget.bind("<MouseWheel>", on_mousewheel)
        widget.bind("<Button-4>", on_mousewheel)
        widget.bind("<Button-5>", on_mousewheel)

    def _bind_mousewheel_recursive(self, parent: tk.Widget, target: tk.Widget) -> None:
        self._bind_mousewheel(parent, target)
        for child in parent.winfo_children():
            self._bind_mousewheel_recursive(child, target)

    @staticmethod
    def _pluralize(n: int, form1: str, form2: str, form5: str) -> str:
        n = abs(n) % 100
        n1 = n % 10
        if 10 < n < 20:
            return form5
        if 1 < n1 < 5:
            return form2
        if n1 == 1:
            return form1
        return form5

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=24)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=4)
        container.columnconfigure(1, weight=5)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 24))
        header.columnconfigure(0, weight=1)

        title_box = ttk.Frame(header)
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(title_box, text="HabitTracker", style="Title.TLabel").pack(anchor="w")

        ttk.Button(header, text="+ Добавить привычку", style="Accent.TButton", command=self.open_create).grid(row=0,
                                                                                                              column=1,
                                                                                                              sticky="e")

        left_card = ttk.Frame(container, style="Card.TFrame", padding=20)
        left_card.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        left_card.rowconfigure(1, weight=1)
        left_card.columnconfigure(0, weight=1)

        controls = ttk.Frame(left_card, style="Card.TFrame")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Список привычек", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        tree_frame = ttk.Frame(left_card)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("title", "schedule", "start")
        self.habit_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.habit_tree.heading("title", text="Название")
        self.habit_tree.heading("schedule", text="Частота")
        self.habit_tree.heading("start", text="Старт")
        self.habit_tree.column("title", width=250, minwidth=200)
        self.habit_tree.column("schedule", width=110, anchor="center")
        self.habit_tree.column("start", width=100, anchor="center")
        self.habit_tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll_y = AutoScrollbar(tree_frame, orient="vertical", command=self.habit_tree.yview)
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x = AutoScrollbar(tree_frame, orient="horizontal", command=self.habit_tree.xview)
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        self.habit_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        self.habit_tree.bind("<<TreeviewSelect>>", self.on_habit_selected)

        self._bind_mousewheel(self.habit_tree, self.habit_tree)

        actions = ttk.Frame(left_card, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        for text, command in [
            ("Обновить", self.refresh_habits),
            ("Редактировать", self.open_edit),
            ("Удалить", self.delete_selected),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 8))

        right_area = ttk.Frame(container)
        right_area.grid(row=1, column=1, sticky="nsew")
        right_area.rowconfigure(1, weight=1)
        right_area.columnconfigure(0, weight=1)

        top_stats = ttk.Frame(right_area)
        top_stats.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        top_stats.columnconfigure((0, 1, 2, 3), weight=1)

        self.summary_labels: dict[str, ttk.Label] = {}
        for idx, key in enumerate(["За период", "Всего", "Осталось", "Прогресс"]):
            card = ttk.Frame(top_stats, style="Card.TFrame", padding=20)
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 12, 0))
            ttk.Label(card, text=key.upper(), style="Muted.TLabel").pack(anchor="w")
            lbl = ttk.Label(card, text="-", style="StatValue.TLabel")
            lbl.pack(anchor="w", pady=(8, 0))
            self.summary_labels[key] = lbl

        notebook = ttk.Notebook(right_area)
        notebook.grid(row=1, column=0, sticky="nsew")

        self.tab_completion = ttk.Frame(notebook, padding=20, style="Card.TFrame")
        self.tab_completion.columnconfigure(0, weight=1)
        # Увеличиваем вес правой колонки, чтобы ей доставалось больше места
        self.tab_completion.columnconfigure(1, weight=1)
        notebook.add(self.tab_completion, text="Отметка и описание")

        self.tab_stats = ttk.Frame(notebook, padding=20, style="Card.TFrame")
        self.tab_stats.columnconfigure(0, weight=1)
        self.tab_stats.rowconfigure(3, weight=1)
        notebook.add(self.tab_stats, text="Детальная статистика")

        ttk.Label(self.tab_completion, text="Детали привычки", style="CardTitle.TLabel").grid(row=0, column=0,
                                                                                              sticky="w", pady=(0, 12))

        self.details_text = tk.Text(
            self.tab_completion, height=10, wrap="word", relief="flat",
            bg="#F8FAFC", fg="#334155", font=("Segoe UI", 11), padx=16, pady=16, highlightthickness=0
        )
        self.details_text.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        self.details_text.configure(state="disabled")

        action_card = ttk.Frame(self.tab_completion, style="Card.TFrame")
        action_card.grid(row=1, column=1, sticky="nsew")

        ttk.Label(action_card, text="Фиксация выполнения", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(action_card, text="Выберите дату:", style="Form.TLabel").pack(anchor="w", pady=(0, 4))

        ttk.Combobox(
            action_card, textvariable=self.display_date_var, values=self.past_dates_display, state="readonly", width=20,
            font=("Segoe UI", 11)
        ).pack(anchor="w", fill="x")  # Заполняем ширину

        self.done_var = tk.BooleanVar(value=False)
        # Динамическая метка: justify="left" и anchor="w" помогают ей прижиматься влево даже при переносе строк
        self.chk_lbl = tk.Label(
            action_card, text="☐ Привычка не выполнена", bg="#FFFFFF", fg="#64748B",
            font=("Segoe UI", 10, "bold"), cursor="hand2", justify="left", anchor="w"
        )
        self.chk_lbl.pack(anchor="w", fill="x", pady=16)

        # Функция для динамического переноса слов (wrap) при сужении окна
        def on_action_card_resize(event):
            # Устанавливаем максимальную ширину текста равной ширине карточки минус небольшие отступы
            self.chk_lbl.configure(wraplength=event.width - 10)

        action_card.bind("<Configure>", on_action_card_resize)

        def toggle_done(event=None):
            self.done_var.set(not self.done_var.get())

        def update_chk_lbl(*args):
            if self.done_var.get():
                self.chk_lbl.config(text="☑ Привычка выполнена", fg="#10B981")
            else:
                self.chk_lbl.config(text="☐ Привычка не выполнена", fg="#64748B")

        self.chk_lbl.bind("<Button-1>", toggle_done)
        self.done_var.trace_add("write", update_chk_lbl)

        ttk.Button(action_card, text="Сохранить отметку", style="Accent.TButton", command=self.save_mark).pack(
            anchor="w", fill="x", pady=(0, 8))
        ttk.Button(action_card, text="Установить сегодня",
                   command=lambda: self.display_date_var.set(self.past_dates_display[0])).pack(anchor="w", fill="x")

        stat_controls = ttk.Frame(self.tab_stats, style="Card.TFrame")
        stat_controls.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ttk.Label(stat_controls, text="Период отображения:", style="Form.TLabel").pack(side="left", padx=(0, 10))
        ttk.Combobox(stat_controls, textvariable=self.period_var, values=["неделя", "месяц"], state="readonly",
                     width=12, font=("Segoe UI", 10)).pack(side="left", padx=(0, 10))
        ttk.Button(stat_controls, text="Показать", command=self.refresh_stats).pack(side="left")

        metric_frame = ttk.Frame(self.tab_stats, style="Card.TFrame")
        metric_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.metric_label = ttk.Label(metric_frame, text="Выберите привычку", style="CardTitle.TLabel")
        self.metric_label.pack(anchor="w")
        self.streak_label = ttk.Label(metric_frame, text="", font=("Segoe UI", 11), foreground="#64748B",
                                      background="#FFFFFF")
        self.streak_label.pack(anchor="w", pady=(8, 0))

        self.calendar_title_label = ttk.Label(self.tab_stats, text="Календарь активности", style="CardTitle.TLabel")
        self.calendar_title_label.grid(row=2, column=0, sticky="w", pady=(0, 12))

        cal_container = ttk.Frame(self.tab_stats)
        cal_container.grid(row=3, column=0, sticky="nsew")
        cal_container.rowconfigure(0, weight=1)
        cal_container.columnconfigure(0, weight=1)

        self.cal_canvas = tk.Canvas(cal_container, bg="#FFFFFF", highlightthickness=0)
        self.cal_canvas.grid(row=0, column=0, sticky="nsew")

        cal_scroll = AutoScrollbar(cal_container, orient="vertical", command=self.cal_canvas.yview)
        cal_scroll.grid(row=0, column=1, sticky="ns")
        self.cal_canvas.configure(yscrollcommand=cal_scroll.set)

        self.calendar_frame = tk.Frame(self.cal_canvas, bg="#FFFFFF")
        self.cal_canvas.create_window((0, 0), window=self.calendar_frame, anchor="nw")

        def update_scrollregion(event):
            self.cal_canvas.configure(scrollregion=self.cal_canvas.bbox("all"))

        self.calendar_frame.bind("<Configure>", update_scrollregion)

    def open_create(self) -> None:
        dialog = HabitDialog(self, self.service)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_habits()

    def open_edit(self) -> None:
        habit = self._require_selection()
        if not habit:
            return
        dialog = HabitDialog(self, self.service, habit)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_habits()
            self.show_habit_details(habit.id)

    def delete_selected(self) -> None:
        habit = self._require_selection()
        if not habit:
            return
        if messagebox.askyesno("Подтверждение", f"Удалить привычку '{habit.title}'?"):
            self.service.delete_habit(habit.id)
            self.selected_habit_id = None
            self.refresh_habits()
            self.clear_details()

    def refresh_habits(self) -> None:
        for item in self.habit_tree.get_children():
            self.habit_tree.delete(item)
        habits = self.service.list_habits()
        for habit in habits:
            schedule = "Ежедневно" if habit.schedule_type == "daily" and habit.schedule_value == 7 else f"{habit.schedule_value} дн/нед."
            self.habit_tree.insert("", "end", iid=str(habit.id),
                                   values=(habit.title, schedule, iso_to_ru(habit.start_date)))
        self.refresh_stats()

    def on_habit_selected(self, _event: object) -> None:
        selection = self.habit_tree.selection()
        if not selection:
            return
        habit_id = int(selection[0])
        self.selected_habit_id = habit_id
        self.show_habit_details(habit_id)
        self.refresh_stats()

    def show_habit_details(self, habit_id: int) -> None:
        habit = self.service.get_habit(habit_id)
        if not habit:
            return
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        schedule = "ежедневно" if habit.schedule_type == "daily" and habit.schedule_value == 7 else f"{habit.schedule_value} раз(а) в неделю"
        text = (
            f"Название:\n  {habit.title}\n\n"
            f"Описание:\n  {habit.description or '—'}\n\n"
            f"Режим:\n  {schedule}\n\n"
            f"Общая цель:\n  {habit.total_target} раз\n\n"
            f"Дата начала:\n  {iso_to_ru(habit.start_date)}\n"
        )
        self.details_text.insert("1.0", text)
        self.details_text.configure(state="disabled")
        self.refresh_completion_status()

    def refresh_completion_status(self) -> None:
        iso_date = self.date_map.get(self.display_date_var.get())
        if not iso_date:
            return
        if self.selected_habit_id is not None:
            self.done_var.set(self.service.is_completed(self.selected_habit_id, iso_date))
        else:
            self.done_var.set(False)

    def save_mark(self) -> None:
        habit = self._require_selection()
        if not habit:
            return
        iso_date = self.date_map.get(self.display_date_var.get())
        if not iso_date:
            return

        try:
            self.service.toggle_completion(habit.id, iso_date, self.done_var.get())
            messagebox.showinfo("Готово", "Отметка сохранена.")
            self.refresh_stats()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def refresh_stats(self) -> None:
        habit = self._get_selected_habit()
        if not habit:
            self.clear_stats()
            return

        today = date.today()
        period = self.period_var.get()
        days = 7 if period == "неделя" else 30

        start = today - timedelta(days=days - 1)
        end = today

        stats = self.service.calculate_stats(habit.id, start.isoformat(), end.isoformat())

        self.summary_labels["За период"].configure(text=str(stats.period_completed))
        self.summary_labels["Всего"].configure(text=str(stats.total_completed))

        remaining = max(0, stats.total_target - stats.total_completed)
        self.summary_labels["Осталось"].configure(text=str(remaining))

        self.summary_labels["Прогресс"].configure(text=f"{stats.percent:.0f}%")

        self.metric_label.configure(text=f"Статистика по привычке: {habit.title}")

        if habit.schedule_value == 7:
            cur_unit = self._pluralize(stats.current_streak, "день", "дня", "дней")
            max_unit = self._pluralize(stats.max_streak, "день", "дня", "дней")
        else:
            cur_unit = self._pluralize(stats.current_streak, "неделя", "недели", "недель")
            max_unit = self._pluralize(stats.max_streak, "неделя", "недели", "недель")

        self.streak_label.configure(
            text=f"Текущая серия: {stats.current_streak} {cur_unit}  |  Максимальная серия: {stats.max_streak} {max_unit}"
        )

        self._render_activity(habit.id)

    def _render_activity(self, habit_id: int) -> None:
        habit = self.service.get_habit(habit_id)
        if not habit:
            return

        period = self.period_var.get()
        days = 7 if period == "неделя" else 30
        target_days = habit.schedule_value

        self.calendar_title_label.configure(text=f"Календарь активности (последние {days} дней)")
        matrix = self.service.build_activity_matrix(habit_id, days=days)

        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        if not matrix:
            return

        weekdays_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        months_ru_short = ["Янв", "Фев", "Мар", "Апр", "Мая", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

        if days == 7:
            completed_count = 0
            for col, (date_str, is_done) in enumerate(matrix):
                if is_done:
                    completed_count += 1
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = weekdays_names[dt.weekday()]

                lbl = tk.Label(self.calendar_frame, text=day_name, bg="#FFFFFF", fg="#94A3B8",
                               font=("Segoe UI", 9, "bold"))
                lbl.grid(row=0, column=col, pady=(0, 4))

                bg_color = "#10B981" if is_done else "#F8FAFC"
                fg_color = "#FFFFFF" if is_done else "#475569"
                border_color = "#059669" if is_done else "#E2E8F0"

                card_border = tk.Frame(self.calendar_frame, bg=border_color, padx=1, pady=1)
                card_border.grid(row=1, column=col, padx=4, pady=4)

                card = tk.Frame(card_border, bg=bg_color, width=80, height=80)
                card.pack(expand=True, fill="both")
                card.grid_propagate(False)

                formatted_date = f"{dt.day} {months_ru_short[dt.month - 1]}"

                lbl_date = tk.Label(card, text=formatted_date, bg=bg_color, fg=fg_color, font=("Segoe UI", 11, "bold"))
                lbl_date.place(relx=0.5, rely=0.5 if not is_done else 0.35, anchor="center")

                if is_done:
                    icon_lbl = tk.Label(card, text="✓", bg=bg_color, fg="#FFFFFF", font=("Segoe UI", 16, "bold"))
                    icon_lbl.place(relx=0.5, rely=0.75, anchor="center")

            if habit.schedule_value == 7:
                today_done = matrix[-1][1] if matrix else False
                if today_done:
                    goal_lbl = tk.Label(self.calendar_frame, text="🔥 Отличная работа! Сегодня привычка выполнена!",
                                        bg="#FFFFFF", fg="#F59E0B", font=("Segoe UI", 11, "bold"))
                else:
                    goal_lbl = tk.Label(self.calendar_frame, text="🔥 Не дай огню погаснуть! Выполни привычку сегодня.",
                                        bg="#FFFFFF", fg="#94A3B8", font=("Segoe UI", 11, "bold"))
            else:
                if completed_count >= target_days:
                    goal_lbl = tk.Label(self.calendar_frame, text="⭐ Цель на неделю выполнена!", bg="#FFFFFF",
                                        fg="#F59E0B", font=("Segoe UI", 11, "bold"))
                else:
                    goal_lbl = tk.Label(self.calendar_frame, text="⏳ Цель пока не выполнена, нужно поднажать!",
                                        bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 11, "bold"))
            goal_lbl.grid(row=2, column=0, columnspan=7, pady=(12, 0), sticky="w")

        else:
            for col, day_name in enumerate(weekdays_names):
                lbl = tk.Label(self.calendar_frame, text=day_name, bg="#FFFFFF", fg="#94A3B8",
                               font=("Segoe UI", 9, "bold"))
                lbl.grid(row=0, column=col, pady=(0, 4))

            weeks = []
            current_week = []
            for date_str, is_done in matrix:
                dt = datetime.strptime(date_str, "%Y-%m-%d")

                if dt.weekday() == 0 and current_week:
                    weeks.append(current_week)
                    current_week = []

                current_week.append((date_str, is_done, dt))

            if current_week:
                weeks.append(current_week)

            weeks.reverse()

            today_iso = date.today().isocalendar()[:2]
            current_row = 1
            for week in weeks:
                week_completed = sum(1 for _, is_done, _ in week if is_done)
                week_iso = week[0][2].isocalendar()[:2]

                for date_str, is_done, dt in week:
                    col = dt.weekday()

                    bg_color = "#10B981" if is_done else "#F8FAFC"
                    fg_color = "#FFFFFF" if is_done else "#475569"
                    border_color = "#059669" if is_done else "#E2E8F0"

                    card_border = tk.Frame(self.calendar_frame, bg=border_color, padx=1, pady=1)
                    card_border.grid(row=current_row, column=col, padx=4, pady=4)

                    card = tk.Frame(card_border, bg=bg_color, width=48, height=48)
                    card.pack(expand=True, fill="both")
                    card.grid_propagate(False)

                    formatted_date = f"{dt.day} {months_ru_short[dt.month - 1]}"

                    lbl_date = tk.Label(card, text=formatted_date, bg=bg_color, fg=fg_color,
                                        font=("Segoe UI", 9, "bold"))
                    lbl_date.place(relx=0.5, rely=0.5 if not is_done else 0.35, anchor="center")

                    if is_done:
                        icon_lbl = tk.Label(card, text="✓", bg=bg_color, fg="#FFFFFF", font=("Segoe UI", 12, "bold"))
                        icon_lbl.place(relx=0.5, rely=0.75, anchor="center")

                if habit.schedule_value == 7:
                    if week_completed >= 7:
                        star_lbl = tk.Label(self.calendar_frame, text="🔥", bg="#FFFFFF", fg="#F59E0B",
                                            font=("Segoe UI", 14))
                    else:
                        star_lbl = tk.Label(self.calendar_frame, text="🔥", bg="#FFFFFF", fg="#94A3B8",
                                            font=("Segoe UI", 14))
                else:
                    if week_completed >= target_days:
                        star_lbl = tk.Label(self.calendar_frame, text="⭐", bg="#FFFFFF", fg="#F59E0B",
                                            font=("Segoe UI", 14))
                    else:
                        if week_iso == today_iso:
                            star_lbl = tk.Label(self.calendar_frame, text="⏳", bg="#FFFFFF", fg="#94A3B8",
                                                font=("Segoe UI", 14))
                        else:
                            star_lbl = tk.Label(self.calendar_frame, text="❌", bg="#FFFFFF", fg="#EF4444",
                                                font=("Segoe UI", 12))

                star_lbl.grid(row=current_row, column=7, padx=(8, 0))

                current_row += 1

        self._bind_mousewheel_recursive(self.cal_canvas, self.cal_canvas)

    def clear_details(self) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.configure(state="disabled")

    def clear_stats(self) -> None:
        for label in self.summary_labels.values():
            label.configure(text="-")
        self.metric_label.configure(text="Выберите привычку")
        self.streak_label.configure(text="")

        self.calendar_title_label.configure(text="Календарь активности")
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

    def _get_selected_habit(self) -> Habit | None:
        if self.selected_habit_id is None:
            return None
        return self.service.get_habit(self.selected_habit_id)

    def _require_selection(self) -> Habit | None:
        habit = self._get_selected_habit()
        if habit is None:
            messagebox.showwarning("Внимание", "Сначала выберите привычку из списка.")
            return None
        return habit