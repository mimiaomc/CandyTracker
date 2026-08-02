import gi
from gi.repository import Adw, Gtk, GLib
from datetime import datetime, timezone
import gettext

from .concentration_plot import ConcentrationPlot

_ = gettext.gettext

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/chart_details_page.ui")
class ChartDetailsPage(Adw.NavigationPage):
    __gtype_name__ = "ChartDetailsPage"

    chart_group = Gtk.Template.Child()
    data_expander = Gtk.Template.Child()
    current_level_row = Gtk.Template.Child()
    current_level_label = Gtk.Template.Child()

    def __init__(self, substance_name, db_path, points_data, status_msg, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.substance_name = substance_name
        self.db_path = db_path
        self.set_title(_("{substance} Details").format(substance=_(substance_name)))

        # 图表
        self.plot = ConcentrationPlot()
        self.plot.set_size_request(-1, 240)
        self.chart_group.add(self.plot)

        # 塞入下拉框数据 (历史计算的切片）
        if status_msg:
            lbl = Gtk.Label(label=status_msg)
            lbl.add_css_class("dim-label")
            self.data_expander.add_row(lbl)
        else:
            for dt_str, val_str in reversed(points_data):
                row = Adw.ActionRow(title=dt_str)
                lbl = Gtk.Label(label=val_str)
                lbl.add_css_class("dim-label")
                row.add_suffix(lbl)

                row.set_activatable(True)
                copy_text = f"[{dt_str}] Level: {val_str}"
                row.connect("activated", lambda r, txt=copy_text: self.copy_to_clipboard(txt))

                self.data_expander.add_row(row)

        # 初始化时立刻主动拉取并渲染一次数据
        self.refresh_dynamic_data()

        # 每 60 秒触发一次刷新
        self._timer_id = GLib.timeout_add_seconds(60, self.refresh_dynamic_data)


    def copy_to_clipboard(self, text):
        from gi.repository import Gdk, GObject
        clipboard = Gdk.Display.get_default().get_clipboard()
        # GTK4 compatibility: some versions don't have set_text bound directly
        try:
            clipboard.set_text(text)
        except AttributeError:
            clipboard.set_content(Gdk.ContentProvider.new_for_value(text))
        self.main_window.toast_overlay.add_toast(Adw.Toast.new(_("Copied to clipboard.")))

    def refresh_dynamic_data(self):
        # 让图表重新从 SQLite 抓取数据并刷新画布
        self.plot.update_data(self.db_path, self.substance_name)

        # 重新计算并刷新上方的“当前浓度”数值面板
        if self.plot.is_pd_mode:
            self.current_level_row.set_title(_("7-Day Average"))
            self.current_level_label.set_label(f"{self.plot.pd_avg_dose:.2f} mg/day")
        else:
            self.current_level_row.set_title(_("Current Concentration (Est.)"))
            now_ts = datetime.now(timezone.utc).timestamp()
            curr_val = 0.0

            if self.plot.points:
                for ts, val in self.plot.points:
                    if ts >= now_ts:
                        curr_val = val
                        break

            self.current_level_label.set_label(f"{curr_val:.2f} {self.plot.target_unit}")

        # 返回 True 告诉系统

    def do_unroot(self):
        # 极其果断地杀掉后台心跳
        if hasattr(self, '_timer_id') and self._timer_id > 0:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        # 必须调用父类的 unroot，这是极其重要的生命周期惯例
        Adw.NavigationPage.do_unroot(self)
