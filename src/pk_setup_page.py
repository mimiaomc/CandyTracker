import gi
from gi.repository import Adw, Gtk

@Gtk.Template(resource_path="/com/github/mimiaomc/candytracker/pk_setup_page.ui")
class PkSetupPage(Adw.NavigationPage):
    __gtype_name__ = "PkSetupPage"

    model_selection_group = Gtk.Template.Child() # Group 引用
    advanced_model_switch = Gtk.Template.Child()
    standard_pk_group = Gtk.Template.Child()
    advanced_pk_group = Gtk.Template.Child()
    patch_pk_group = Gtk.Template.Child()

    # 单室参数
    spin_half_life = Gtk.Template.Child()
    spin_peak = Gtk.Template.Child()
    spin_bio = Gtk.Template.Child()

    # 三室参数
    spin_k_absorb = Gtk.Template.Child()
    spin_k_elim = Gtk.Template.Child()
    spin_k_cf = Gtk.Template.Child()
    spin_k_fc = Gtk.Template.Child()
    spin_vd = Gtk.Template.Child()

    # 贴片参数
    spin_patch_wear = Gtk.Template.Child()
    spin_patch_rate = Gtk.Template.Child()
    spin_patch_scale = Gtk.Template.Child()

    # 通用参数
    spin_dose = Gtk.Template.Child()
    unit_row = Gtk.Template.Child()

    def __init__(self, route_name, pk_data_ref, preset_units, track_mode, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_(route_name) + _(" Setup"))

        self.pk_data_ref = pk_data_ref
        self.preset_units = preset_units
        self.unit_row.set_model(Gtk.StringList.new(self.preset_units))

        # Adjustment 范围锁
        self.spin_half_life.set_adjustment(Gtk.Adjustment(value=12.0, lower=0.1, upper=1000.0, step_increment=0.5))
        self.spin_peak.set_adjustment(Gtk.Adjustment(value=2.0, lower=0.1, upper=200.0, step_increment=0.5))
        self.spin_bio.set_adjustment(Gtk.Adjustment(value=5.0, lower=0.1, upper=100.0, step_increment=1.0))

        self.spin_k_absorb.set_adjustment(Gtk.Adjustment(value=0.02, lower=0.001, upper=10.0, step_increment=0.001))
        self.spin_k_elim.set_adjustment(Gtk.Adjustment(value=0.15, lower=0.001, upper=10.0, step_increment=0.001))
        self.spin_k_cf.set_adjustment(Gtk.Adjustment(value=0.08, lower=0.001, upper=10.0, step_increment=0.001))
        self.spin_k_fc.set_adjustment(Gtk.Adjustment(value=0.01, lower=0.001, upper=10.0, step_increment=0.001))
        self.spin_vd.set_adjustment(Gtk.Adjustment(value=1.5, lower=1.0, upper=500.0, step_increment=1.0))

        self.spin_patch_wear.set_adjustment(Gtk.Adjustment(value=84.0, lower=1.0, upper=500.0, step_increment=1.0))
        self.spin_patch_rate.set_adjustment(Gtk.Adjustment(value=50.0, lower=1.0, upper=5000.0, step_increment=5.0))
        self.spin_patch_scale.set_adjustment(Gtk.Adjustment(value=1.0, lower=0.1, upper=10.0, step_increment=0.1))

        self.spin_dose.set_adjustment(Gtk.Adjustment(value=2.0, lower=0.01, upper=10000.0, step_increment=0.5))

        # 路由拦截与预填数据
        self.is_patch = route_name == "Transdermal Patch"
        is_advanced = self.pk_data_ref.get("model") == "3_compartment"

        # 如果不是针剂 (Injection / Implant)，那就不显示这个计算模型
        if route_name not in ["Injection", "Implant"]:
            self.model_selection_group.set_visible(False)
            is_advanced = False
            if not self.is_patch:
                self.pk_data_ref["model"] = "1_comp"
            else:
                self.pk_data_ref["model"] = "patch_zero_order"

        self.advanced_model_switch.set_active(is_advanced)
        
        if self.is_patch:
            self.standard_pk_group.set_visible(False)
            self.advanced_pk_group.set_visible(False)
            self.patch_pk_group.set_visible(True)
        else:
            self.patch_pk_group.set_visible(False)
            self.standard_pk_group.set_visible(not is_advanced)
            self.advanced_pk_group.set_visible(is_advanced)

        # 填入单室数据
        self.spin_half_life.set_value(float(self.pk_data_ref.get("half_life", 12.0)))
        self.spin_peak.set_value(float(self.pk_data_ref.get("peak", 2.0)))
        self.spin_bio.set_value(float(self.pk_data_ref.get("bio", 5.0)))

        # 填入三室数据
        self.spin_k_absorb.set_value(float(self.pk_data_ref.get("k_absorb", 0.025)))
        self.spin_k_elim.set_value(float(self.pk_data_ref.get("k_elim", 0.15)))
        self.spin_k_cf.set_value(float(self.pk_data_ref.get("k_cf", 0.08)))
        self.spin_k_fc.set_value(float(self.pk_data_ref.get("k_fc", 0.015)))
        self.spin_vd.set_value(float(self.pk_data_ref.get("vd", 1.5)))
        
        # 填入贴片数据
        self.spin_patch_wear.set_value(float(self.pk_data_ref.get("wear_hours", 84.0)))
        self.spin_patch_rate.set_value(float(self.pk_data_ref.get("release_rate", 50.0)))
        self.spin_patch_scale.set_value(float(self.pk_data_ref.get("patch_scale", 1.0)))

        # 填入通用数据
        self.spin_dose.set_value(float(self.pk_data_ref.get("default_dose", 2.0)))
        current_unit = self.pk_data_ref.get("unit", "mg")
        if current_unit in self.preset_units:
            self.unit_row.set_selected(self.preset_units.index(current_unit))

        # 信号绑定
        self.advanced_model_switch.connect("notify::active", self.on_model_switched)

        self.spin_half_life.connect("notify::value", self.auto_save)
        self.spin_peak.connect("notify::value", self.auto_save)
        self.spin_bio.connect("notify::value", self.auto_save)

        self.spin_k_absorb.connect("notify::value", self.auto_save)
        self.spin_k_elim.connect("notify::value", self.auto_save)
        self.spin_k_cf.connect("notify::value", self.auto_save)
        self.spin_k_fc.connect("notify::value", self.auto_save)
        self.spin_vd.connect("notify::value", self.auto_save)

        self.spin_patch_wear.connect("notify::value", self.auto_save)
        self.spin_patch_rate.connect("notify::value", self.auto_save)
        self.spin_patch_scale.connect("notify::value", self.auto_save)

        self.spin_dose.connect("notify::value", self.auto_save)
        self.unit_row.connect("notify::selected", self.auto_save)

    def on_model_switched(self, switch, pspec):
        if self.is_patch: return
        is_advanced = switch.get_active()
        self.standard_pk_group.set_visible(not is_advanced)
        self.advanced_pk_group.set_visible(is_advanced)
        self.auto_save()

    def auto_save(self, *args):
        """每次数值变动时，实时更新传入的字典引用"""
        is_advanced = self.advanced_model_switch.get_active()

        # 无论哪个模型，基础的剂量和单位都得存
        self.pk_data_ref["default_dose"] = self.spin_dose.get_value()
        self.pk_data_ref["unit"] = self.preset_units[self.unit_row.get_selected()]

        if self.is_patch:
            self.pk_data_ref["model"] = "patch_zero_order"
            self.pk_data_ref["wear_hours"] = self.spin_patch_wear.get_value()
            self.pk_data_ref["release_rate"] = self.spin_patch_rate.get_value()
            self.pk_data_ref["patch_scale"] = self.spin_patch_scale.get_value()
        elif is_advanced:
            self.pk_data_ref["model"] = "3_compartment"
            self.pk_data_ref["k_absorb"] = self.spin_k_absorb.get_value()
            self.pk_data_ref["k_elim"] = self.spin_k_elim.get_value()
            self.pk_data_ref["k_cf"] = self.spin_k_cf.get_value()
            self.pk_data_ref["k_fc"] = self.spin_k_fc.get_value()
            self.pk_data_ref["vd"] = self.spin_vd.get_value()
        else:
            self.pk_data_ref["model"] = "1_comp"
            self.pk_data_ref["half_life"] = self.spin_half_life.get_value()
            self.pk_data_ref["peak"] = self.spin_peak.get_value()
            self.pk_data_ref["bio"] = self.spin_bio.get_value()
