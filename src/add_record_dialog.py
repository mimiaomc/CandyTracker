import gi
from gi.repository import Adw, Gtk, GLib
from datetime import datetime, timezone, date

from .candy_calendar import CandyCalendar

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/add_record_dialog.ui")
class AddRecordDialog(Adw.MessageDialog):
    __gtype_name__ = "AddRecordDialog"

    med_dropdown = Gtk.Template.Child()
    method_dropdown = Gtk.Template.Child()
    dose_spin = Gtk.Template.Child()
    unit_dropdown = Gtk.Template.Child()
    site_dropdown = Gtk.Template.Child()

    date_button = Gtk.Template.Child()
    calendar_popover = Gtk.Template.Child()
    calendar_container = Gtk.Template.Child()
    hour_dropdown = Gtk.Template.Child()
    min_dropdown = Gtk.Template.Child()

    def __init__(self, active_meds, meds_allowed_map, meds_pk_map, preset_units, transdermal_sites, **kwargs):
        super().__init__(**kwargs)

        self.active_meds = active_meds
        self.meds_allowed_map = meds_allowed_map
        self.meds_pk_map = meds_pk_map # 接收全局 PK 映射字典
        self.preset_units = preset_units
        self.transdermal_sites = transdermal_sites
        self.current_allowed_methods = ["Oral"]
        self.current_available_sites = []

        self.site_dropdown.set_model(Gtk.StringList.new([_(s) for s in self.transdermal_sites]))

        self.med_dropdown.set_model(Gtk.StringList.new(self.active_meds))
        self.unit_dropdown.set_model(Gtk.StringList.new(self.preset_units))

        hours = [f"{i:02d}" for i in range(24)]
        mins = [f"{i:02d}" for i in range(60)]
        self.hour_dropdown.set_model(Gtk.StringList.new(hours))
        self.min_dropdown.set_model(Gtk.StringList.new(mins))

        now_local = datetime.now()
        self.hour_dropdown.set_selected(now_local.hour)
        self.min_dropdown.set_selected(now_local.minute)

        self.candy_cal = CandyCalendar()
        self.candy_cal.connect("date-selected", self.on_custom_date_selected)
        self.calendar_container.append(self.candy_cal)
        self.update_date_button_label(now_local.date())

        # 监听药物和方式切换事件
        self.med_dropdown.connect("notify::selected", self.on_med_changed)
        self.method_dropdown.connect("notify::selected", self.on_method_changed)
        self.site_dropdown.connect("notify::selected", self.on_site_changed)

        self.on_med_changed(self.med_dropdown, None)

    def on_med_changed(self, dropdown, pspec):
        if not self.active_meds: return
        med_name = self.active_meds[dropdown.get_selected()]

        allowed = self.meds_allowed_map.get(med_name, ["Oral"])
        self.current_allowed_methods = allowed
        translated_methods = [_(m) for m in allowed]
        self.method_dropdown.set_model(Gtk.StringList.new(translated_methods))
        self.method_dropdown.set_selected(0)
        self.on_method_changed(self.method_dropdown, None) # 触发剂量的联动

    def on_method_changed(self, dropdown, pspec):
        if not self.active_meds or not self.current_allowed_methods: return
        med_name = self.active_meds[self.med_dropdown.get_selected()]

        idx = self.method_dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION: idx = 0

        if idx < len(self.current_allowed_methods):
            method = self.current_allowed_methods[idx]
            self.site_dropdown.set_visible(method == "Transdermal")
            
            route_pk = self.meds_pk_map.get(med_name, {}).get(method, {})
            
            if method == "Transdermal":
                if "half_life" in route_pk or not route_pk:
                    available_sites = self.transdermal_sites
                else:
                    available_sites = list(route_pk.keys())
                if not available_sites:
                    available_sites = self.transdermal_sites
                
                # Compare arrays exactly to avoid unnecessary rebuilds and signals
                if getattr(self, 'current_available_sites', None) != available_sites:
                    self.current_available_sites = available_sites
                    self.site_dropdown.set_model(Gtk.StringList.new([_(s) for s in available_sites]))
                    self.site_dropdown.set_selected(0)
            
            self.update_dose_from_current_selection()

    def on_site_changed(self, dropdown, pspec):
        self.update_dose_from_current_selection()
        
    def update_dose_from_current_selection(self):
        if not self.active_meds or not self.current_allowed_methods: return
        med_name = self.active_meds[self.med_dropdown.get_selected()]
        
        idx = self.method_dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION: return
        method = self.current_allowed_methods[idx]
        route_pk = self.meds_pk_map.get(med_name, {}).get(method, {})
        
        if method == "Transdermal":
            site_idx = self.site_dropdown.get_selected()
            if getattr(self, 'current_available_sites', None) and site_idx != Gtk.INVALID_LIST_POSITION and site_idx < len(self.current_available_sites):
                site_name = self.current_available_sites[site_idx]
                route_pk = route_pk.get(site_name, {}) if "half_life" not in route_pk else route_pk
                
        self.dose_spin.set_value(route_pk.get("default_dose", 2.0))
        try:
            self.unit_dropdown.set_selected(self.preset_units.index(route_pk.get("unit", "mg")))
        except ValueError:
            pass

    def update_date_button_label(self, selected_date):
        self.date_button.set_label(selected_date.strftime("%Y-%m-%d"))

    def on_custom_date_selected(self, calendar_widget, year, month, day):
        selected = date(year, month, day)
        self.update_date_button_label(selected)
        self.calendar_popover.popdown()

    def get_record_data(self):
        med_name = self.active_meds[self.med_dropdown.get_selected()]
        actual_method = self.current_allowed_methods[self.method_dropdown.get_selected()]
        
        actual_site = None
        if actual_method == "Transdermal":
            site_idx = self.site_dropdown.get_selected()
            if site_idx != Gtk.INVALID_LIST_POSITION and site_idx < len(self.current_available_sites):
                actual_site = self.current_available_sites[site_idx]

        dose = self.dose_spin.get_value()
        unit = self.preset_units[self.unit_dropdown.get_selected()]

        selected_date = self.candy_cal.get_date()
        hour = self.hour_dropdown.get_selected()
        minute = self.min_dropdown.get_selected()

        local_dt = datetime(selected_date.year, selected_date.month, selected_date.day, hour, minute, 0, 0)
        utc_dt = local_dt.astimezone(timezone.utc)
        utc_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")

        return med_name, actual_method, actual_site, dose, unit, utc_str
