# preferences_window.py
import sqlite3
import json
import gi
from gi.repository import Adw, Gtk

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/preferences_window.ui")
class PreferencesWindow(Adw.PreferencesWindow):
    __gtype_name__ = "PreferencesWindow"

    clear_records_btn = Gtk.Template.Child()
    jump_switch = Gtk.Template.Child()
    sites_entry_row = Gtk.Template.Child()

    def __init__(self, main_window, db_path, **kwargs):
        super().__init__(**kwargs)
        # 把主窗口的实例传进来，方便我们删完记录后指挥主窗口刷新 UI
        self.main_window = main_window
        self.db_path = db_path
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM preferences WHERE key = 'auto_jump_history'")
        val = cursor.fetchone()
        
        cursor.execute("SELECT value FROM preferences WHERE key = 'transdermal_sites'")
        val_sites = cursor.fetchone()
        conn.close()

        if val_sites and val_sites[0]:
            try:
                sites_list = json.loads(val_sites[0])
                self.sites_entry_row.set_text(", ".join(sites_list))
            except Exception:
                pass

        self.jump_switch.set_active(val is not None and val[0] == '1')

        def on_switch_changed(switch, gparam):
            new_val = '1' if switch.get_active() else '0'
            c = sqlite3.connect(self.db_path)
            c.execute("UPDATE preferences SET value = ? WHERE key = 'auto_jump_history'", (new_val,))
            c.commit()
            c.close()

        self.jump_switch.connect("notify::active", on_switch_changed)

    @Gtk.Template.Callback()
    def on_sites_applied(self, entry_row):
        text = entry_row.get_text()
        sites_list = [s.strip() for s in text.split(",") if s.strip()]
        if not sites_list:
            sites_list = ["Arm", "Inner Thigh", "Scrotal"] # Fallback
            
        json_str = json.dumps(sites_list)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE preferences SET value = ? WHERE key = 'transdermal_sites'", (json_str,))
        conn.commit()
        conn.close()
        
        self.main_window.toast_overlay.add_toast(Adw.Toast.new(_("Transdermal sites updated.")))

    @Gtk.Template.Callback()
    def on_clear_records_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Clear All Records?",
            body="This will permanently delete all your intake history.\n\nYour active medication library will NOT be affected. This action CANNOT be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete All")
        # 把删除按钮变成红色
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(dialog_win, response_id):
            if response_id == "delete":
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM records")
                conn.commit()
                conn.close()

                # 通知主窗口刷新列表并弹出 Toast
                self.main_window.load_history()
                # 在这里顺手让主窗口的图表刷新重绘
                self.main_window.load_dashboard()

                self.main_window.toast_overlay.add_toast(Adw.Toast.new("All records have been cleared."))
                self.close()

        dialog.connect("response", handle_response)
        dialog.present()
