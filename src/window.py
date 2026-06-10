# window.py
#
# Copyright 2026 MM 喵了个
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sqlite3
import json
import sys
from datetime import datetime, timezone, timedelta
from gi.repository import Adw, GLib, Gtk, Gio

from .add_record_dialog import AddRecordDialog
from .preferences_window import PreferencesWindow
from .medication_creator_page import MedicationCreatorPage
from .concentration_plot import ConcentrationPlot

# ==============================================================================
__TRANSLATION_ANCHORS = [
    _("Estrogel"), _("Progynova"), _("Androcur"),
    _("Estradiol"), _("Cyproterone Acetate"),
    _("Estradiol Valerate"),
    _("Oral"), _("Sublingual"), _("Transdermal"), _("Injection")
]
# ==============================================================================

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/window.ui")
class CandytrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = "CandytrackerWindow"

    split_view = Gtk.Template.Child()
    sidebar_list = Gtk.Template.Child()
    content_stack = Gtk.Template.Child()
    history_empty_clamp = Gtk.Template.Child()
    history_scrolled = Gtk.Template.Child()
    history_list = Gtk.Template.Child()
    view_more_button = Gtk.Template.Child()
    meds_nav_view = Gtk.Template.Child()
    meds_empty_clamp = Gtk.Template.Child()
    meds_scrolled = Gtk.Template.Child()
    meds_list = Gtk.Template.Child()
    library_list = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    dashboard_box = Gtk.Template.Child()
    personal_weight_row = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        data_dir = GLib.get_user_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "candytracker_v4.db")

        self.my_active_meds = []
        self.meds_allowed_map = {}

        self.preset_methods = ["Oral", "Sublingual", "Transdermal", "Injection"]
        self.preset_units = ["mg", "g", "ml", "patch", "drop"]
        self.preset_icons = ["💊", "🧴", "💉", "🧪", "🩹", "🍬", "📦"]

        self.init_database()
        self.load_medications()
        self.load_history()
        self.load_dashboard()

        self.sidebar_list.connect("row-selected", self.on_sidebar_row_selected)
        self.content_stack.connect("notify::visible-child", self.on_page_changed)
        self.on_page_changed(self.content_stack, None)

        first_row = self.sidebar_list.get_row_at_index(0)
        if first_row:
            self.sidebar_list.select_row(first_row)

        self.setup_actions()
        GLib.timeout_add_seconds(60, self.refresh_active_charts)

        # 配置体重输入框的范围 (30kg - 250kg)
        self.personal_weight_row.set_adjustment(Gtk.Adjustment(value=65.0, lower=30.0, upper=250.0, step_increment=0.5))

        # 尝试从数据库加载已有体重
        c = sqlite3.connect(self.db_path).cursor()
        c.execute("SELECT value FROM preferences WHERE key = 'user_weight'")
        w_row = c.fetchone()
        if w_row and w_row[0]:
            self.personal_weight_row.set_value(float(w_row[0]))
        c.connection.close()

        # 监听数值改变信号，自动保存
        self.personal_weight_row.connect("notify::value", self.on_personal_weight_changed)

        # 延迟一帧触发免责声明检查，保证主界面已经画出来了
        GLib.idle_add(self.check_eula)

    def check_eula(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM preferences WHERE key = 'eula_agreed'")
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] != '1':
            self.show_eula_dialog()

    def show_eula_dialog(self):
        eula_text = _(
            "Welcome to CandyTracker! 💊\n\n"
            "This software utilizes a simplified one-compartment pharmacokinetic model for simulation purposes. Please read and agree to the following before use:\n\n"
            "1. Not Medical Advice: This application is strictly for informational and educational purposes. It does not provide medical advice, diagnosis, or treatment.\n"
            "2. Theoretical Simulations: The charts and calculated levels are mathematical approximations. They do not represent your actual blood serum concentrations.\n"
            "3. Consult Professionals: Always consult a licensed healthcare provider before altering any medication or dosage. Rely on actual clinical blood tests for medical decisions.\n"
            "4. No Liability: The developer assumes no responsibility or liability for any health consequences or errors arising from the use of this software.\n\n"
            "Please manage your health safely and responsibly under professional guidance!"
        )

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Disclaimer & EULA"),
            # body 只留极其简短的一句话引导
            body=_("Please read the following terms carefully before using CandyTracker.")
        )

        # 给长文套上一个最高只能有 250px 的滚动容器
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(150)
        scrolled.set_max_content_height(250)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_top(12)

        # 把 EULA 文本装进一个可以自动换行的标签里
        label = Gtk.Label(label=eula_text)
        label.set_wrap(True)
        label.set_justify(Gtk.Justification.LEFT)
        label.set_xalign(0.0)
        label.add_css_class("dim-label") # 让免责声明的字色稍微变灰一点

        scrolled.set_child(label)

        # 把滚动容器塞进对话框的额外区域
        dialog.set_extra_child(scrolled)

        dialog.add_response("cancel", _("Decline & Exit"))
        dialog.add_response("agree", _("I Understand and Agree"))
        dialog.set_response_appearance("agree", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")

        def on_response(d, response_id):
            if response_id == "agree":
                conn = sqlite3.connect(self.db_path)
                conn.execute("UPDATE preferences SET value = '1' WHERE key = 'eula_agreed'")
                conn.commit()
                conn.close()
            else:
                import sys
                sys.exit(0)

        dialog.connect("response", on_response)
        dialog.present()

    def on_page_changed(self, stack, param):
        page_name = stack.get_visible_child_name()
        page_titles = {
            "home": _("Dashboard"),
            "history": _("History"),
            "medications": _("Medications"),
            "library": _("App Library"),
            "personal": _("Personal")
        }
        self.set_title(_("CandyTracker"))

    def setup_actions(self):
        pref_action = Gio.SimpleAction.new("preferences", None)
        pref_action.connect("activate", self.on_preferences_action)
        self.add_action(pref_action)

    def on_preferences_action(self, action, param):
        pref_win = PreferencesWindow(main_window=self, db_path=self.db_path, transient_for=self)
        pref_win.present()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, med_name TEXT, substance TEXT DEFAULT 'Unknown', dose_mg REAL, unit TEXT, method TEXT)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, substance TEXT DEFAULT 'Unknown', default_method TEXT,
                unit TEXT, icon TEXT, allowed_methods TEXT, pk_data TEXT, track_mode TEXT DEFAULT 'half_life', sort_order INTEGER DEFAULT 0
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT)")

        # 写入三条预设配置
        cursor.execute("INSERT OR IGNORE INTO preferences (key, value) VALUES ('auto_jump_history', '0')")
        cursor.execute("INSERT OR IGNORE INTO preferences (key, value) VALUES ('eula_agreed', '0')")
        cursor.execute("INSERT OR IGNORE INTO preferences (key, value) VALUES ('user_weight', '')")

        conn.commit()
        conn.close()

    def load_medications(self):
        while self.meds_list.get_first_child() is not None:
            self.meds_list.remove(self.meds_list.get_first_child())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, substance, default_method, unit, icon, allowed_methods, pk_data FROM medications ORDER BY sort_order ASC, id ASC")
        rows = cursor.fetchall()
        conn.close()

        self.my_active_meds = [row[1] for row in rows]
        self.meds_allowed_map = {}
        self.meds_pk_map = {}

        for row in rows:
            # raw_methods 现在是 row[6]
            raw_methods = row[6] if row[6] else row[3]
            self.meds_allowed_map[row[1]] = [m.strip() for m in raw_methods.split(",")]

            # pk_json 现在是 row[7]
            pk_json = row[7] if row[7] else "{}"
            try:
                self.meds_pk_map[row[1]] = json.loads(pk_json)
            except json.JSONDecodeError:
                self.meds_pk_map[row[1]] = {}

        if not rows:
            self.meds_empty_clamp.set_visible(True)
            self.meds_scrolled.set_visible(False)
            self.load_dashboard()
            return

        self.meds_empty_clamp.set_visible(False)
        self.meds_scrolled.set_visible(True)

        for row in rows:
            action_row = Adw.ActionRow()
            action_row.set_title(row[1])

            # “方法 | 单位 | 物质”
            all_methods = self.meds_allowed_map.get(row[1], [row[3]])
            display_methods = " / ".join([_(m) for m in all_methods])

            # 给物质名称也套上翻译，这样以后可以支持多语言物质名
            display_substance = _(row[2])

            action_row.set_subtitle(_("{methods}  |  Unit: {unit}  |  Sub: {substance}").format(
                methods=display_methods,
                unit=row[4],
                substance=display_substance
            ))

            action_row.add_prefix(Gtk.Label(label=row[5])) # icon 现在是 row[5]

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, valign=Gtk.Align.CENTER)
            up_btn = Gtk.Button(icon_name="go-up-symbolic")
            up_btn.add_css_class("flat")
            up_btn.connect("clicked", lambda b, mid=row[0]: self.move_med(mid, -1))

            down_btn = Gtk.Button(icon_name="go-down-symbolic")
            down_btn.add_css_class("flat")
            down_btn.connect("clicked", lambda b, mid=row[0]: self.move_med(mid, 1))

            btn_box.append(up_btn)
            btn_box.append(down_btn)
            action_row.add_suffix(btn_box)

            action_row.set_activatable(True)
            action_row.connect("activated", lambda r, rid=row[0], mname=row[1]: self.trigger_med_delete(rid, mname))

            self.meds_list.append(action_row)

        self.load_dashboard()

    def load_library_shop(self):
        while self.library_list.get_first_child() is not None:
            self.library_list.remove(self.library_list.get_first_child())

        # JSON 资源直读
        try:
            resource_path = "/com/github/mimiaomc/candytracker/presets.json"
            bytes_variant = Gio.resources_lookup_data(resource_path, Gio.ResourceLookupFlags.NONE)
            json_str = bytes_variant.get_data().decode('utf-8')
            presets = json.loads(json_str)
        except Exception as e:
            print(f"JSON Load Error: {e}")
            presets = []

        for item in presets:
            shop_row = Adw.ActionRow()

            # 按系统语言挂上翻译
            translated_name = _(item["name"])
            translated_substance = _(item["substance"])

            shop_row.set_title(translated_name)

            raw_allowed = item.get("allowed_methods", item["default_method"])
            methods = [m.strip() for m in raw_allowed.split(",")]
            methods_tr = " / ".join([_(m) for m in methods])

            shop_row.set_subtitle(_("Substance: {substance}  |  Routes: {routes}").format(
                substance=translated_substance,
                routes=methods_tr
            ))
            shop_row.add_prefix(Gtk.Label(label=item["icon"]))

            # 列表结构
            modified_payload = [
                translated_name,            # 0: name (固化为中文)
                translated_substance,       # 1: substance (固化为中文，消除图表悬浮不更新的 bug)
                item["default_method"],     # 2: default_method
                item["unit"],               # 3: unit
                item["icon"],               # 4: icon
                raw_allowed,                # 5: allowed_methods
                json.dumps(item["pk_data"]),# 6: pk_data_json (依然需要转成字符串传给下一页)
                item["track_mode"]          # 7: track_mode
            ]

            shop_row.set_activatable(True)
            shop_row.connect("activated", lambda r, p=modified_payload: self.on_library_shop_row_activated(p))

            self.library_list.append(shop_row)

    def on_library_shop_row_activated(self, payload):
        def on_crafted(med_name, success, msg):
            if success:
                self.sync_weight_from_db()
                self.load_medications()
                self.meds_nav_view.pop()
                self.meds_nav_view.pop()
                self.toast_overlay.add_toast(Adw.Toast.new(_("Medication '{med_name}' imported!").format(med_name=med_name)))
            else:
                self.toast_overlay.add_toast(Adw.Toast.new(msg))

        creator_page = MedicationCreatorPage(
            nav_view=self.meds_nav_view,
            preset_methods=self.preset_methods,
            preset_units=self.preset_units,
            preset_icons=self.preset_icons,
            db_path=self.db_path,
            on_success_cb=on_crafted,
            prefill_data=payload
        )
        self.meds_nav_view.push(creator_page)

    @Gtk.Template.Callback()
    def on_add_med_button_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Add Medication"),
            body=_("Where would you like to add the medication from?")
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("library", _("App Library"))
        dialog.add_response("custom", _("Custom Medication"))
        dialog.set_response_appearance("library", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("custom", Adw.ResponseAppearance.SUGGESTED)

        def handle_choice(dialog_win, response_id):
            if response_id == "library":
                self.load_library_shop()
                self.meds_nav_view.push_by_tag("meds_library")
            elif response_id == "custom":
                def on_crafted(med_name, success, msg):
                    if success:
                        self.sync_weight_from_db()
                        self.load_medications()
                        self.meds_nav_view.pop()
                        self.toast_overlay.add_toast(Adw.Toast.new(_("Medication '{med_name}' crafted successfully!").format(med_name=med_name)))
                    else:
                        self.toast_overlay.add_toast(Adw.Toast.new(msg))

                creator_page = MedicationCreatorPage(
                    nav_view=self.meds_nav_view,
                    preset_methods=self.preset_methods,
                    preset_units=self.preset_units,
                    preset_icons=self.preset_icons,
                    db_path=self.db_path,
                    on_success_cb=on_crafted
                )
                self.meds_nav_view.push(creator_page)

        dialog.connect("response", handle_choice)
        dialog.present()

    def create_action_row_from_db(self, row, on_click_cb=None):
        record_id, utc_time_str, med_name, dose_mg, unit, med_icon, method = row[0], row[1], row[2], row[3], row[4], (row[5] if row[5] else "💊"), row[6]

        display_method = _(method if method else "Oral")

        try:
            utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            local_dt = utc_dt.astimezone()
            display_time = local_dt.strftime("%m-%d %H:%M")
        except ValueError:
            display_time = utc_time_str

        action_row = Adw.ActionRow()
        action_row.set_title(med_name)
        action_row.set_subtitle(f"{display_time}  •  {display_method}")
        action_row.add_prefix(Gtk.Label(label=med_icon))

        dose_label = Gtk.Label(label=f"{dose_mg} {unit}")
        dose_label.add_css_class("dim-label")
        action_row.add_suffix(dose_label)

        action_row.set_activatable(True)
        if on_click_cb:
            action_row.connect("activated", lambda r, rid=record_id: on_click_cb(rid))
        else:
            action_row.connect("activated", lambda r, rid=record_id: self.show_delete_confirm_dialog(rid))

        return action_row

    def load_history(self):
        while self.history_list.get_first_child() is not None:
            self.history_list.remove(self.history_list.get_first_child())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT r.id, r.timestamp, r.med_name, r.dose_mg, r.unit, m.icon, r.method FROM records r LEFT JOIN medications m ON r.med_name = m.name ORDER BY datetime(r.timestamp) DESC, r.id DESC LIMIT 11")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self.history_empty_clamp.set_visible(True)
            self.history_scrolled.set_visible(False)
            return

        self.history_empty_clamp.set_visible(False)
        self.history_scrolled.set_visible(True)

        if len(rows) > 10:
            self.view_more_button.set_visible(True)
            display_rows = rows[:10]
        else:
            self.view_more_button.set_visible(False)
            display_rows = rows

        for row in display_rows:
            self.history_list.append(self.create_action_row_from_db(row))

    def on_sidebar_row_selected(self, listbox, row):
        if row is None: return
        idx = row.get_index()

        if idx == 0:
            self.content_stack.set_visible_child_name("home")
        elif idx == 1:
            self.content_stack.set_visible_child_name("history")
        elif idx == 2:
            self.content_stack.set_visible_child_name("medications")
        elif idx == 3:
            self.content_stack.set_visible_child_name("personal")

        if self.split_view.get_collapsed():
            self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def on_view_more_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("All History Records"),
            body=_("Below is the full historical log of your candy intake:")
        )
        dialog.add_response("close", _("Close"))
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(350)
        scrolled.set_max_content_height(500)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        all_history_list = Gtk.ListBox()
        all_history_list.add_css_class("boxed-list")
        all_history_list.set_selection_mode(Gtk.SelectionMode.NONE)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT r.id, r.timestamp, r.med_name, r.dose_mg, r.unit, m.icon, r.method FROM records r LEFT JOIN medications m ON r.med_name = m.name ORDER BY datetime(r.timestamp) DESC, r.id DESC")
        rows = cursor.fetchall()
        conn.close()

        def handle_view_more_click(rid):
            dialog.destroy()
            self.show_delete_confirm_dialog(rid)

        for row in rows:
            all_history_list.append(self.create_action_row_from_db(row, handle_view_more_click))

        scrolled.set_child(all_history_list)
        dialog.set_extra_child(scrolled)
        dialog.present()

    def trigger_med_delete(self, target_id, med_name):
        confirm_dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Remove '{med_name}'?").format(med_name=med_name),
            body=_("Do you want to keep its intake history logs, or completely wipe all past records associated with this medication name?")
        )
        confirm_dialog.add_response("cancel", _("Cancel"))
        confirm_dialog.add_response("keep", _("Keep History (Archive)"))
        confirm_dialog.add_response("delete_all", _("Delete Med & History"))
        confirm_dialog.set_response_appearance("delete_all", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_med_delete_response(dialog_window, response_id):
            if response_id not in ("keep", "delete_all"):
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if response_id == "delete_all":
                cursor.execute("DELETE FROM records WHERE med_name = ?", (med_name,))

            cursor.execute("DELETE FROM medications WHERE id = ?", (target_id,))

            conn.commit()
            conn.close()

            self.load_history()
            self.load_medications()
            self.load_dashboard()

            self.toast_overlay.add_toast(Adw.Toast.new(_("'{med_name}' removed.").format(med_name=med_name)))

        confirm_dialog.connect("response", handle_med_delete_response)
        confirm_dialog.present()

    @Gtk.Template.Callback()
    def on_add_record_clicked(self, button):
        if not self.my_active_meds:
            error_dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Your Active Box is Empty"),
                body=_("You don't have any active medications to log records.\nPlease switch to the 'Medications' tab on the left sidebar and import or create one first.")
            )
            error_dialog.add_response("ok", _("I see"))
            error_dialog.present()
            return

        dialog = AddRecordDialog(
            active_meds=self.my_active_meds,
            meds_allowed_map=self.meds_allowed_map,
            meds_pk_map=self.meds_pk_map,
            preset_units=self.preset_units,
            transient_for=self
        )

        def on_response(dialog_window, response_id):
            if response_id == "save":
                med_name, actual_method, dose, unit, utc_str = dialog_window.get_record_data()

                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute("SELECT substance FROM medications WHERE name = ?", (med_name,))
                sub_row = cursor.fetchone()
                substance = sub_row[0] if sub_row else "Unknown"

                cursor.execute(
                    "INSERT INTO records (timestamp, med_name, substance, dose_mg, unit, method) VALUES (?, ?, ?, ?, ?, ?)",
                    (utc_str, med_name, substance, dose, unit, actual_method)
                )
                conn.commit()
                conn.close()

                self.load_history()
                self.load_dashboard()

                c = sqlite3.connect(self.db_path)
                cur = c.cursor()
                cur.execute("SELECT value FROM preferences WHERE key = 'auto_jump_history'")
                jump_val = cur.fetchone()
                c.close()

                if jump_val and jump_val[0] == '1':
                    history_row = self.sidebar_list.get_row_at_index(1)
                    if history_row:
                        self.sidebar_list.select_row(history_row)

                self.toast_overlay.add_toast(Adw.Toast.new(_("Added {med_name} successfully!").format(med_name=med_name)))

        dialog.connect("response", on_response)
        dialog.present()

    def show_delete_confirm_dialog(self, target_id):
        confirm_dialog = Adw.MessageDialog(transient_for=self, heading=_("Delete this record?"), body=_("This action cannot be undone."))
        confirm_dialog.add_response("cancel", _("Cancel"))
        confirm_dialog.add_response("delete", _("Delete"))
        confirm_dialog.set_close_response("cancel")
        confirm_dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_delete_response(dialog_window, response_id):
            if response_id == "delete":
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM records WHERE id = ?", (target_id,))
                conn.commit()
                conn.close()
                self.load_history()
                self.load_dashboard()
                self.toast_overlay.add_toast(Adw.Toast.new(_("Record deleted.")))

        confirm_dialog.connect("response", handle_delete_response)
        confirm_dialog.present()

    def load_dashboard(self):
        while child := self.dashboard_box.get_first_child():
            self.dashboard_box.remove(child)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT substance FROM medications GROUP BY substance ORDER BY MIN(sort_order) ASC")
        subs = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not subs:
            lbl = Gtk.Label(label=_("No active medications. Add one from the Library!"))
            lbl.add_css_class("dim-label")
            self.dashboard_box.append(lbl)
            return

        from .concentration_plot import ConcentrationPlot
        self.active_plots = []

        for sub_name in subs:
            group = Adw.PreferencesGroup()
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_bottom=8)

            title_lbl = Gtk.Label(label=f"<b>{_(sub_name)}</b>", use_markup=True, xalign=0, hexpand=True)
            title_lbl.add_css_class("heading")

            up_btn = Gtk.Button(icon_name="go-up-symbolic", valign=Gtk.Align.CENTER)
            up_btn.add_css_class("flat")
            up_btn.connect("clicked", lambda b, s=sub_name: self.move_substance(s, -1))

            down_btn = Gtk.Button(icon_name="go-down-symbolic", valign=Gtk.Align.CENTER)
            down_btn.add_css_class("flat")
            down_btn.connect("clicked", lambda b, s=sub_name: self.move_substance(s, 1))

            header_box.append(title_lbl)
            header_box.append(up_btn)
            header_box.append(down_btn)

            list_box = Gtk.ListBox()
            list_box.add_css_class("boxed-list")
            list_box.set_selection_mode(Gtk.SelectionMode.NONE)

            plot = ConcentrationPlot()
            plot.update_data(self.db_path, target_substance=sub_name)

            list_box.connect("row-activated", lambda box, row, p=plot: self.show_chart_details(p))

            row = Gtk.ListBoxRow()
            row.set_child(plot)
            list_box.append(row)

            group.add(header_box)
            group.add(list_box)
            self.dashboard_box.append(group)
            self.active_plots.append((plot, sub_name))

    def move_substance(self, substance, direction):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT substance FROM medications GROUP BY substance ORDER BY MIN(sort_order) ASC")
        subs = [row[0] for row in cursor.fetchall()]

        idx = subs.index(substance)
        new_idx = idx + direction

        if 0 <= new_idx < len(subs):
            subs[idx], subs[new_idx] = subs[new_idx], subs[idx]
            new_sort_order = 0
            for sub in subs:
                cursor.execute("SELECT id FROM medications WHERE substance = ? ORDER BY sort_order ASC, id ASC", (sub,))
                for (m_id,) in cursor.fetchall():
                    cursor.execute("UPDATE medications SET sort_order = ? WHERE id = ?", (new_sort_order, m_id))
                    new_sort_order += 1
            conn.commit()
        conn.close()

        self.load_dashboard()
        self.load_medications()

    def refresh_active_charts(self):
        if hasattr(self, 'active_plots'):
            for plot, m_name in self.active_plots:
                plot.update_data(self.db_path, m_name)
        return True

    def move_med(self, med_id, direction):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM medications ORDER BY sort_order ASC, id ASC")
        ids = [row[0] for row in cursor.fetchall()]

        idx = ids.index(med_id)
        new_idx = idx + direction
        if 0 <= new_idx < len(ids):
            ids[idx], ids[new_idx] = ids[new_idx], ids[idx]
            for i, i_id in enumerate(ids):
                cursor.execute("UPDATE medications SET sort_order = ? WHERE id = ?", (i, i_id))
            conn.commit()
        conn.close()

        self.load_medications()

    def show_chart_details(self, plot):
        points_data, status_msg = plot.get_raw_points_data()

        dialog = Adw.MessageDialog(transient_for=self, heading=_("PK/PD Data"), body=_("Tap a row to copy:"))
        dialog.add_response("close", _("Close"))

        if status_msg:
            dialog.set_body(status_msg)
        else:
            scrolled = Gtk.ScrolledWindow(height_request=350, propagate_natural_width=True)
            list_box = Gtk.ListBox()
            list_box.add_css_class("boxed-list")

            for dt_str, val_str in reversed(points_data):
                item_row = Adw.ActionRow(title=dt_str)
                lbl = Gtk.Label(label=val_str)
                lbl.add_css_class("dim-label")
                item_row.add_suffix(lbl)
                item_row.set_activatable(True)

                copy_text = f"[{dt_str}] Level: {val_str}"
                item_row.connect("activated", lambda r, txt=copy_text: self.copy_to_clipboard(txt))

                list_box.append(item_row)

            scrolled.set_child(list_box)
            dialog.set_extra_child(scrolled)

        dialog.present()

    def copy_to_clipboard(self, text):
        from gi.repository import Gdk
        self.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(text))
        toast = Adw.Toast.new(_("Copied: {text}").format(text=text))
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)

    def on_personal_weight_changed(self, *args):
        # 拿到新体重
        new_weight = self.personal_weight_row.get_value()

        # 存入数据库
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE preferences SET value = ? WHERE key = 'user_weight'", (str(new_weight),))
        conn.commit()
        conn.close()

        # 通知仪表盘里的图表重新渲染
        self.refresh_active_charts()

    def sync_weight_from_db(self):
        """强制让个人页面的输入框从数据库同步最新的体重数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT value FROM preferences WHERE key = 'user_weight'")
            w_row = c.fetchone()
            conn.close()
            if w_row and w_row[0]:
                # 这一步会自动触发数值改变信号，连带着把主页的图表也一起刷新了
                self.personal_weight_row.set_value(float(w_row[0]))
        except Exception as e:
            print(f"Sync weight error: {e}")
