pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'candytracker'
gnome = import('gnome')

gnome.compile_resources('candytracker',
  'candytracker.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'candytracker.in',
  output: 'candytracker',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

candytracker_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'add_record_dialog.py',
  'candy_calendar.py',
  'preferences_window.py',
  'medication_creator_page.py',
  'pk_setup_page.py',
  'concentration_plot.py',
  'chart_details_page.py',
]

install_data(candytracker_sources, install_dir: moduledir)
