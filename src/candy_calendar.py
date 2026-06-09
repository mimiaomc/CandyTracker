# candy_calendar.py
import calendar
from datetime import date
from gi.repository import Gtk, GObject

class CandyCalendar(Gtk.Box):
    __gtype_name__ = "CandyCalendar"

    __gsignals__ = {
        'date-selected': (GObject.SignalFlags.RUN_FIRST, None, (int, int, int,))
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        self.today = date.today()
        self.view_year = self.today.year
        self.view_month = self.today.month
        self.selected_date = self.today

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.prev_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.prev_btn.add_css_class("flat")
        self.prev_btn.add_css_class("circular")
        self.prev_btn.connect("clicked", self.on_prev_month)

        self.next_btn = Gtk.Button(icon_name="go-next-symbolic")
        self.next_btn.add_css_class("flat")
        self.next_btn.add_css_class("circular")
        self.next_btn.connect("clicked", self.on_next_month)

        self.month_label = Gtk.Label(hexpand=True)
        self.month_label.add_css_class("heading")

        header.append(self.prev_btn)
        header.append(self.month_label)
        header.append(self.next_btn)
        self.append(header)

        self.grid = Gtk.Grid(row_spacing=4, column_spacing=4)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.append(self.grid)

        weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for col, day_name in enumerate(weekdays):
            lbl = Gtk.Label(label=day_name)
            lbl.add_css_class("dim-label")
            lbl.set_margin_bottom(8)
            self.grid.attach(lbl, col, 0, 1, 1)

    def refresh(self):
        month_name = calendar.month_name[self.view_month]
        self.month_label.set_label(f"{month_name} {self.view_year}")

        child = self.grid.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            if type(child) is Gtk.Button:
                self.grid.remove(child)
            child = next_child

        first_weekday, days_in_month = calendar.monthrange(self.view_year, self.view_month)

        row = 1
        col = first_weekday

        for day in range(1, days_in_month + 1):
            btn = Gtk.Button(label=str(day))
            btn.add_css_class("flat")
            btn.add_css_class("circular")
            btn.set_size_request(36, 36)

            current_iter_date = date(self.view_year, self.view_month, day)
            if current_iter_date == self.selected_date:
                btn.add_css_class("suggested-action")
                btn.remove_css_class("flat")
            elif current_iter_date == self.today:
                btn.add_css_class("error")

            btn.connect("clicked", self.on_day_clicked, day)
            self.grid.attach(btn, col, row, 1, 1)

            col += 1
            if col > 6:
                col = 0
                row += 1

    def on_prev_month(self, btn):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self.refresh()

    def on_next_month(self, btn):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self.refresh()

    def on_day_clicked(self, btn, day):
        self.selected_date = date(self.view_year, self.view_month, day)
        self.refresh()
        self.emit("date-selected", self.selected_date.year, self.selected_date.month, self.selected_date.day)

    def get_date(self):
        return self.selected_date
