# medication_creator_page.py
import sqlite3
import json
import gi
from gi.repository import Adw, Gtk

from .pk_setup_page import PkSetupPage

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/medication_creator_page.ui")
class MedicationCreatorPage(Adw.NavigationPage):
    __gtype_name__ = "MedicationCreatorPage"

    craft_button = Gtk.Template.Child()
    creator_name_row = Gtk.Template.Child()
    creator_icon_row = Gtk.Template.Child()
    track_mode_row = Gtk.Template.Child()
    target_unit_row = Gtk.Template.Child()
    target_min_row = Gtk.Template.Child()
    target_max_row = Gtk.Template.Child()
    methods_list = Gtk.Template.Child()
    creator_substance_row = Gtk.Template.Child()

    def __init__(self, nav_view, preset_methods, preset_units, preset_icons, db_path, on_success_cb, prefill_data=None, **kwargs):
        super().__init__(**kwargs)
        self.nav_view = nav_view
        self.preset_methods = preset_methods
        self.preset_units = preset_units
        self.preset_icons = preset_icons
        self.db_path = db_path
        self.on_success_cb = on_success_cb
        self.prefill_data = prefill_data
        self.pk_data_dict = {}
        self.method_checks = {}

        self.craft_button.connect("clicked", self.on_craft_clicked)
        self.creator_icon_row.set_model(Gtk.StringList.new([_("{icon} Style").format(icon=i) for i in self.preset_icons]))
        self.track_modes = [_("Pharmacokinetics (PK)"), _("Pharmacodynamics (PD)")]
        self.track_mode_row.set_model(Gtk.StringList.new(self.track_modes))
        self.target_min_row.set_adjustment(Gtk.Adjustment(value=100.0, lower=0.0, upper=10000.0, step_increment=10.0))
        self.target_max_row.set_adjustment(Gtk.Adjustment(value=200.0, lower=0.0, upper=10000.0, step_increment=10.0))
        self.target_units = ["pg/mL", "pmol/L", "ng/mL", "mIU/mL"]
        self.target_unit_row.set_model(Gtk.StringList.new(self.target_units))

        def on_mode_changed(*args):
            is_pk = self.track_mode_row.get_selected() == 0
            self.target_unit_row.set_visible(is_pk)
            self.target_min_row.set_visible(is_pk)
            self.target_max_row.set_visible(is_pk)

        self.track_mode_row.connect("notify::selected", on_mode_changed)
        on_mode_changed()

        for m in self.preset_methods:
            self.pk_data_dict[m] = {"half_life": 12.0, "bio": 5.0, "peak": 2.0, "default_dose": 2.0, "unit": "mg"}

        for m in self.preset_methods:
            row = Adw.ActionRow(title=_(m))
            row.set_activatable(True)
            check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            chevron = Gtk.Image(icon_name="go-next-symbolic")
            row.add_suffix(chevron)
            self.methods_list.add(row)
            self.method_checks[m] = check
            row.connect("activated", lambda r, route=m: self.on_route_activated(route))

        if self.prefill_data:
            name, substance, default_method, unit, icon, allowed_str, pk_json, track_mode = self.prefill_data
            self.creator_name_row.set_text(name)
            self.creator_substance_row.set_text(substance if substance else "")
            for i, ic in enumerate(self.preset_icons):
                if ic in icon:
                    self.creator_icon_row.set_selected(i)
                    break
            mode_idx = 1 if track_mode == "dosage" else 0
            self.track_mode_row.set_selected(mode_idx)

            allowed_list = [m.strip() for m in allowed_str.split(",")] if allowed_str else []
            for m, chk in self.method_checks.items():
                chk.set_active(m in allowed_list)

            if pk_json:
                loaded_dict = json.loads(pk_json)
                g_min = loaded_dict.get("global_target_min", 100.0)
                g_max = loaded_dict.get("global_target_max", 200.0)
                g_unit = loaded_dict.get("global_target_unit", "pg/mL")
                self.target_min_row.set_value(float(g_min))
                self.target_max_row.set_value(float(g_max))
                if g_unit in self.target_units:
                    self.target_unit_row.set_selected(self.target_units.index(g_unit))

                for m, data in loaded_dict.items():
                    if m in ["global_target_min", "global_target_max", "global_target_unit"]:
                        continue
                    if isinstance(data, dict):
                        if "default_dose" not in data: data["default_dose"] = 2.0
                        if "unit" not in data: data["unit"] = unit if unit else "mg"
                        self.pk_data_dict[m] = data
        else:
            if self.preset_methods:
                self.method_checks[self.preset_methods[0]].set_active(True)

    def on_route_activated(self, route_name):
        current_mode = "dosage" if self.track_mode_row.get_selected() == 1 else "half_life"
        page = PkSetupPage(route_name, self.pk_data_dict[route_name], self.preset_units, current_mode)
        self.nav_view.push(page)

    def on_craft_clicked(self, button):
        name = self.creator_name_row.get_text().strip()
        if not name:
            self.on_success_cb(name, False, _("Please fill out the medication name!"))
            return

        substance = self.creator_substance_row.get_text().strip()
        if not substance: substance = "Unknown"

        allowed = [m for m, chk in self.method_checks.items() if chk.get_active()]
        if not allowed: allowed = ["Oral"]

        allowed_str = ", ".join(allowed)
        icon = self.preset_icons[self.creator_icon_row.get_selected()]
        track_mode = "dosage" if self.track_mode_row.get_selected() == 1 else "half_life"

        final_pk_data = {m: self.pk_data_dict[m] for m in allowed}

        if track_mode == "half_life":
            final_pk_data["global_target_min"] = self.target_min_row.get_value()
            final_pk_data["global_target_max"] = self.target_max_row.get_value()
            final_pk_data["global_target_unit"] = self.target_units[self.target_unit_row.get_selected()]

        global_fallback_unit = final_pk_data[allowed[0]]["unit"] if allowed[0] in final_pk_data else "mg"

        # 如果是 PK 模式，必须拦截检查体重
        if track_mode == "half_life":
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT value FROM preferences WHERE key = 'user_weight'")
            w_row = c.fetchone()
            conn.close()

            # 如果查不到，或者是个空字符串
            if not w_row or not w_row[0]:
                self.prompt_weight_and_save(name, substance, allowed, icon, allowed_str, final_pk_data, track_mode, global_fallback_unit)
                return

        # PD模式，或者已经有体重了，直接保存
        self._execute_db_insert(name, substance, allowed, icon, allowed_str, final_pk_data, track_mode, global_fallback_unit)

    def prompt_weight_and_save(self, name, substance, allowed, icon, allowed_str, final_pk_data, track_mode, global_fallback_unit):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=_("Personal Data Required"),
            body=_("To accurately predict the Pharmacokinetics (PK) curve for this medication, we need your body weight to dynamically calculate the Apparent Volume of Distribution (Vd).")
        )

        spin_row = Adw.SpinRow(title=_("Body Weight (kg)"), numeric=True, digits=1)
        spin_row.set_adjustment(Gtk.Adjustment(value=60.0, lower=30.0, upper=250.0, step_increment=0.5))

        list_box = Gtk.ListBox()
        list_box.add_css_class("boxed-list")
        list_box.append(spin_row)

        dialog.set_extra_child(list_box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save & Craft"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(d, response_id):
            if response_id == "save":
                weight = spin_row.get_value()
                conn = sqlite3.connect(self.db_path)
                conn.execute("UPDATE preferences SET value = ? WHERE key = 'user_weight'", (str(weight),))
                conn.commit()
                conn.close()
                self._execute_db_insert(name, substance, allowed, icon, allowed_str, final_pk_data, track_mode, global_fallback_unit)

        dialog.connect("response", on_response)
        dialog.present()

    def _execute_db_insert(self, name, substance, allowed, icon, allowed_str, final_pk_data, track_mode, global_fallback_unit):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO medications (name, substance, default_method, unit, icon, allowed_methods, pk_data, track_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, substance, allowed[0], global_fallback_unit, icon, allowed_str, json.dumps(final_pk_data), track_mode)
            )
            conn.commit()
            self.on_success_cb(name, True, _("Success"))
        except sqlite3.IntegrityError:
            self.on_success_cb(name, False, _("This name already exists inside your active box."))
        finally:
            conn.close()
