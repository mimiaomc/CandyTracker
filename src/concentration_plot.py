import math
import sqlite3
import json
import cairo
from datetime import datetime, timezone, timedelta
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
import gettext
_ = gettext.gettext

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/concentration_plot.ui")
class ConcentrationPlot(Gtk.Box):
    __gtype_name__ = "ConcentrationPlot"

    drawing_area = Gtk.Template.Child()
    pd_box = Gtk.Template.Child()
    pd_title = Gtk.Template.Child()
    pd_progress = Gtk.Template.Child()
    pd_current = Gtk.Template.Child()
    pd_target = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.target_min = 100.0
        self.target_max = 200.0
        self.target_unit = "pg/mL"
        self.status_msg = ""
        self.is_pd_mode = False
        self.pd_avg_dose = 0.0
        self.pd_target_dose = 12.5
        self.drawing_area.set_draw_func(self.on_draw)

    def update_data(self, db_path, target_substance=None):
        self.points.clear()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 先拿体重备用（兜底设为标准体重 65.0kg）
        cursor.execute("SELECT value FROM preferences WHERE key = 'user_weight'")
        w_row = cursor.fetchone()
        try:
            user_weight = float(w_row[0]) if w_row and w_row[0] else 65.0
        except ValueError:
            user_weight = 65.0

        cursor.execute("SELECT track_mode FROM medications WHERE substance = ? LIMIT 1", (target_substance,))
        mode_row = cursor.fetchone()

        if not mode_row:
            self.status_msg = _("Error loading substance data.")
            self.drawing_area.queue_draw()
            conn.close()
            return

        db_track_mode = mode_row[0]

        if db_track_mode == "dosage":
            self.is_pd_mode = True
            self.drawing_area.set_visible(False)
            self.pd_box.set_visible(True)
            self.set_size_request(-1, -1)

            now = datetime.now(timezone.utc)
            seven_days_ago_ts = (now - timedelta(days=7)).timestamp()
            total_dose = 0.0
            oldest_ts = now.timestamp()
            has_records = False

            cursor.execute("SELECT timestamp, dose_mg FROM records WHERE substance = ?", (target_substance,))
            for ts_str, d_mg in cursor.fetchall():
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                    if ts >= seven_days_ago_ts:
                        total_dose += d_mg
                        if ts < oldest_ts: oldest_ts = ts
                        has_records = True
                except: continue

            if has_records:
                now_date = now.date()
                oldest_date = datetime.fromtimestamp(oldest_ts, timezone.utc).date()
                days_span = (now_date - oldest_date).days + 1
                self.pd_avg_dose = total_dose / min(7.0, float(days_span))
            else:
                self.pd_avg_dose = 0.0

            cursor.execute("SELECT pk_data FROM medications WHERE substance = ?", (target_substance,))
            self.pd_target_dose = 12.5
            for pk_row in cursor.fetchall():
                try:
                    pk_dict = json.loads(pk_row[0])
                    for v in pk_dict.values():
                        if isinstance(v, dict) and "default_dose" in v:
                            self.pd_target_dose = v["default_dose"]
                            break
                except: continue

            self.pd_title.set_text(_("{substance} - 7-Day Average").format(substance=_(target_substance)))
            percentage = min(self.pd_avg_dose / max(self.pd_target_dose, 0.01), 1.0)
            self.pd_progress.set_fraction(percentage)

            self.pd_current.set_visible(False)
            self.pd_target.set_xalign(1.0)
            self.pd_target.set_text(_("Target: {dose:.1f} mg/day").format(dose=self.pd_target_dose))

            self.status_msg = ""
            conn.close()
            return

        self.is_pd_mode = False
        self.drawing_area.set_visible(True)
        self.pd_box.set_visible(False)
        self.set_size_request(-1, 180)

        cursor.execute("SELECT name, pk_data FROM medications WHERE substance = ?", (target_substance,))
        meds_pk = {}
        for r in cursor.fetchall():
            try:
                pk = json.loads(r[1])
                meds_pk[r[0]] = pk
                if "global_target_min" in pk:
                    self.target_min = pk["global_target_min"]
                    self.target_max = pk["global_target_max"]
                    self.target_unit = pk.get("global_target_unit", "pg/mL")
            except: meds_pk[r[0]] = {}

        now = datetime.now(timezone.utc)
        ten_days_ago = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("SELECT timestamp, med_name, dose_mg, method FROM records WHERE substance = ? AND timestamp >= ? ORDER BY timestamp ASC", (target_substance, ten_days_ago))
        records = cursor.fetchall()
        conn.close()

        now_ts = now.timestamp()
        start_sim = now_ts - 36 * 3600
        end_sim = now_ts + 12 * 3600
        step = 1800
        current_t = start_sim
        has_future_records = False

        # 容积动态计算 (19.0 L/kg 为 E2 的表观分布容积)
        dynamic_multiplier = 1000000.0 / (user_weight * 19.0)

        while current_t <= end_sim:
            total_conc = 0.0
            for rec_time_str, m_name, dose, method in records:
                try: rec_ts = datetime.strptime(rec_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                except: continue

                if rec_ts > current_t: continue
                has_future_records = True

                delta_hours = (current_t - rec_ts) / 3600.0
                route_pk = meds_pk.get(m_name, {}).get(method, {})
                half_life = route_pk.get("half_life", 12.0)
                bio = route_pk.get("bio", 5.0) / 100.0
                peak = route_pk.get("peak", 2.0)

                ke = 0.693 / max(half_life, 0.1)
                ka = 2.0 / max(peak, 0.1)
                for i in range(3):
                    if ka <= ke: ka = ke + 0.1
                    ka = math.log(ka / ke) / max(peak, 0.1) + ke

                # 🌟 第三步：彻底废弃魔法数字 800，装载千人千面的个体化乘数！
                amplitude = (dose * bio * dynamic_multiplier) * (ka / max(ka - ke, 0.01))
                conc_contribution = amplitude * (math.exp(-ke * delta_hours) - math.exp(-ka * delta_hours))
                total_conc += max(conc_contribution, 0.0)

            self.points.append((current_t, total_conc))
            current_t += step

        if not has_future_records:
            self.status_msg = _("No recent records for {substance}.").format(substance=_(target_substance))
            self.points.clear()

        self.drawing_area.queue_draw()

    def on_draw(self, drawing_area, cr, width, height):
        if self.status_msg:
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.8)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(14)
            extents = cr.text_extents(self.status_msg)
            cr.move_to((width - extents.width) / 2, height / 2)
            cr.show_text(self.status_msg)
            return

        pad_l, pad_r, pad_t, pad_b = 35, 15, 20, 30
        w_plot = width - pad_l - pad_r
        h_plot = height - pad_t - pad_b

        max_val = max([p[1] for p in self.points]) if self.points else 0
        y_max = max(max_val * 1.3, self.target_max * 1.5, 50.0)
        x_min, x_max = self.points[0][0], self.points[-1][0]

        def to_pixels(ts, val):
            x = pad_l + ((ts - x_min) / (x_max - x_min)) * w_plot
            y = pad_t + h_plot - (val / y_max) * h_plot
            return x, y

        _, y_t_max = to_pixels(x_min, self.target_max)
        _, y_t_min = to_pixels(x_min, self.target_min)
        cr.set_source_rgba(0.2, 0.8, 0.2, 0.12)
        cr.rectangle(pad_l, y_t_max, w_plot, y_t_min - y_t_max)
        cr.fill()

        cr.set_source_rgba(0.2, 0.6, 0.2, 0.4)
        cr.set_dash([4.0, 4.0], 0)
        cr.set_line_width(1)
        for y_val in [self.target_min, self.target_max]:
            _, py = to_pixels(x_min, y_val)
            cr.move_to(pad_l, py)
            cr.line_to(pad_l + w_plot, py)
            cr.stroke()
        cr.set_dash([], 0)

        now_x, _ = to_pixels(datetime.now(timezone.utc).timestamp(), 0)
        cr.set_source_rgba(0.8, 0.2, 0.2, 0.3)
        cr.set_line_width(1.5)
        cr.move_to(now_x, pad_t)
        cr.line_to(now_x, pad_t + h_plot)
        cr.stroke()

        cr.set_line_width(2.5)
        cr.set_source_rgba(0.1, 0.5, 0.8, 0.9)

        first = True
        for ts, val in self.points:
            px, py = to_pixels(ts, val)
            if first:
                cr.move_to(px, py)
                first = False
            else:
                cr.line_to(px, py)
        cr.stroke()

        cr.set_source_rgba(0.5, 0.5, 0.5, 0.6)
        cr.set_font_size(10)
        for y_lbl in [0, int(self.target_min), int(self.target_max), int(y_max * 0.8)]:
            _, py = to_pixels(x_min, y_lbl)
            cr.move_to(8, py + 4)
            cr.show_text(f"{y_lbl}")

        cr.move_to(pad_l, pad_t + h_plot + 18)
        cr.show_text("-36h")
        cr.move_to(now_x - 18, pad_t + h_plot + 18)
        cr.show_text("Now")
        cr.move_to(pad_l + w_plot - 25, pad_t + h_plot + 18)
        cr.show_text("+12h")

    def get_raw_points_data(self):
        from datetime import datetime
        readable_points = []
        if self.is_pd_mode:
            return [(_("7-Day Avg"), f"{self.pd_avg_dose:.2f} mg/day"), (_("Target"), f"{self.pd_target_dose:.1f} mg/day")], ""

        for ts, val in self.points:
            dt = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            readable_points.append((dt, f"{val:.2f} {self.target_unit}"))
        return readable_points, self.status_msg
