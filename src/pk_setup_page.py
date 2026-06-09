import gi
from gi.repository import Adw, Gtk

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/pk_setup_page.ui")
class PkSetupPage(Adw.NavigationPage):
    __gtype_name__ = "PkSetupPage"

    unit_row = Gtk.Template.Child()
    default_dose_spin = Gtk.Template.Child()
    half_life_spin = Gtk.Template.Child()
    bio_spin = Gtk.Template.Child()
    peak_spin = Gtk.Template.Child()

    def __init__(self, route_name, pk_data_ref, preset_units, track_mode, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("{route} Setup").format(route=_(route_name)))
        self.pk_data_ref = pk_data_ref
        self.preset_units = preset_units

        self.unit_row.set_model(Gtk.StringList.new(self.preset_units))
        try:
            self.unit_row.set_selected(self.preset_units.index(pk_data_ref.get("unit", "mg")))
        except ValueError:
            pass

        self.default_dose_spin.set_adjustment(Gtk.Adjustment(value=pk_data_ref.get("default_dose", 2.0), lower=0.01, upper=5000.0, step_increment=0.5))
        self.half_life_spin.set_adjustment(Gtk.Adjustment(value=pk_data_ref.get("half_life", 12.0), lower=0.0, upper=500.0, step_increment=0.5))
        self.bio_spin.set_adjustment(Gtk.Adjustment(value=pk_data_ref.get("bio", 5.0), lower=0.0, upper=100.0, step_increment=1.0))
        self.peak_spin.set_adjustment(Gtk.Adjustment(value=pk_data_ref.get("peak", 2.0), lower=0.0, upper=72.0, step_increment=0.1))

        # 如果是 PD 模式，那就把底下三个框藏起来
        is_pk = (track_mode == "half_life")
        self.half_life_spin.set_visible(is_pk)
        self.bio_spin.set_visible(is_pk)
        self.peak_spin.set_visible(is_pk)

        self.unit_row.connect("notify::selected", self.on_value_changed)
        self.default_dose_spin.connect("notify::value", self.on_value_changed)
        self.half_life_spin.connect("notify::value", self.on_value_changed)
        self.bio_spin.connect("notify::value", self.on_value_changed)
        self.peak_spin.connect("notify::value", self.on_value_changed)

    def on_value_changed(self, widget, pspec):
        self.pk_data_ref["unit"] = self.preset_units[self.unit_row.get_selected()]
        self.pk_data_ref["default_dose"] = self.default_dose_spin.get_value()
        self.pk_data_ref["half_life"] = self.half_life_spin.get_value()
        self.pk_data_ref["bio"] = self.bio_spin.get_value()
        self.pk_data_ref["peak"] = self.peak_spin.get_value()
