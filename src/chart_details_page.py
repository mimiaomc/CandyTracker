import gi
from gi.repository import Adw, Gtk
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
        self.set_title(_("{substance} Details").format(substance=_(substance_name)))

        # 🌟 极其优雅地复刻图表
        self.plot = ConcentrationPlot()
        self.plot.update_data(db_path, substance_name)
        self.plot.set_size_request(-1, 240)
        self.chart_group.add(self.plot)

        # ==========================================
        # 🌟 极其聪明的“抓取当前数值”逻辑
        # ==========================================
        if self.plot.is_pd_mode:
            # 如果是打卡进度条模式，直接读取 pd_avg_dose
            self.current_level_row.set_title(_("7-Day Average"))
            self.current_level_label.set_label(f"{self.plot.pd_avg_dose:.2f} mg/day")
        else:
            # 如果是 PK 曲线模式，从时间轴里“拦截”出当前的瞬时浓度
            self.current_level_row.set_title(_("Current Concentration (Est.)"))
            now_ts = datetime.now(timezone.utc).timestamp()
            curr_val = 0.0

            # 因为 points 数组是按时间严格排序的，抓到第一个大于等于现在的点即可
            if self.plot.points:
                for ts, val in self.plot.points:
                    if ts >= now_ts:
                        curr_val = val
                        break

            self.current_level_label.set_label(f"{curr_val:.2f} {self.plot.target_unit}")
        # ==========================================

        # 🌟 塞入下拉框数据
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

                # 保留点击复制的极客功能
                row.set_activatable(True)
                copy_text = f"[{dt_str}] Level: {val_str}"
                row.connect("activated", lambda r, txt=copy_text: self.copy_to_clipboard(txt))

                self.data_expander.add_row(row)

    def copy_to_clipboard(self, text):
        from gi.repository import Gdk
        self.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(text))
        toast = Adw.Toast.new(_("Copied: {text}").format(text=text))
        toast.set_timeout(2)
        # 借用主窗口的 Toast 发送极其原生的通知
        self.main_window.toast_overlay.add_toast(toast)
