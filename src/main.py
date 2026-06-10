# main.py
#
# Copyright 2026 MM 喵了个
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import os
import locale
import gettext
import builtins  # 用来把 _() 变成所有文件都能用的全局函数……？

# 多语言

# os.environ["LANGUAGE"] = "zh_CN.UTF-8"
# 这里主要是为了在测试的时候更方便改语言，没让你打包的时候写进去啊

APP_ID = 'com.github.mimiaomc.candytracker'
GETTEXT_DOMAIN = 'candytracker'  # 去看一眼 po/meson.build

LOCALE_DIR = '/app/share/locale'
if not os.path.exists(LOCALE_DIR):
    LOCALE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')

try:
    locale.bindtextdomain(GETTEXT_DOMAIN, LOCALE_DIR)
    locale.textdomain(GETTEXT_DOMAIN)
    gettext.bindtextdomain(GETTEXT_DOMAIN, LOCALE_DIR)
    gettext.textdomain(GETTEXT_DOMAIN)
except AttributeError:
    pass

import builtins
builtins._ = gettext.gettext

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw
from .window import CandytrackerWindow



class CandytrackerApplication(Adw.Application):
    """Main application class"""

    def __init__(self):
        # 在这里抢在 super().__init__ 之前宣告名字……虽然但是，这一步是 AI 教的，猫猫并不知道是什么意思
        from gi.repository import GLib
        GLib.set_application_name(_('CandyTracker'))
        GLib.set_prgname('com.github.mimiaomc.candytracker')

        super().__init__(application_id='com.github.mimiaomc.candytracker',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/com/github/mimiaomc/candytracker')
        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)

    def do_activate(self):
        """Activate the app and show the main window"""
        win = self.props.active_window
        if not win:
            win = CandytrackerWindow(application=self)
        win.present()

    def on_about_action(self, *args):
        """Libadwaita 原生关于窗口"""
        about = Adw.AboutDialog(
            application_name=_('CandyTracker'),
            application_icon='com.github.mimiaomc.candytracker',
            developer_name='MM 喵了个',
            version='0.9.8',
            translator_credits=_('translator-credits'),
            developers=['MM 喵了个'],
            copyright='© 2026 MM 喵了个',
            issue_url='https://github.com/mimiaomc/candytracker/issues',
            website='https://github.com/mimiaomc/candytracker'
        )

        about.add_credit_section("Special Thanks", ["Icon from streamline-emojis", "家猫姐姐"])

        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        """激活高级首选项面板"""
        win = self.props.active_window
        if win:
            # 动态导入设置窗口
            from .preferences_window import PreferencesWindow

            # 把主窗口和数据库路径传过去
            pref_win = PreferencesWindow(main_window=win, db_path=win.db_path)
            pref_win.present(win)

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = CandytrackerApplication()
    return app.run(sys.argv)
