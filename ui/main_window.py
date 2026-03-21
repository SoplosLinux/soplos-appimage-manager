import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, Gdk, Gio, GLib
from pathlib import Path

from core.appimage_manager import AppImageManager, AppImage
from config.constants import APP_ID, APP_NAME, APP_VERSION, APPIMAGES_DIR, DESKTOP_FILES_DIR


class AppImageRow(Gtk.ListBoxRow):
    def __init__(self, appimage: AppImage, on_run_callback, on_update_callback,
                 on_integrate_callback, on_delete_callback, _translate):
        super().__init__()
        self.appimage = appimage
        self._ = _translate

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        # Icon
        image = Gtk.Image()
        if appimage.icon_path and appimage.icon_path.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(appimage.icon_path), 48, 48, True)
                image.set_from_pixbuf(pixbuf)
            except Exception:
                image.set_from_icon_name('application-x-executable', Gtk.IconSize.DIALOG)
        else:
            image.set_from_icon_name('application-x-executable', Gtk.IconSize.DIALOG)
        box.pack_start(image, False, False, 0)

        # Text info
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        label_name = Gtk.Label(label=f'<b>{appimage.name}</b>')
        label_name.set_use_markup(True)
        label_name.set_halign(Gtk.Align.START)
        vbox.pack_start(label_name, False, False, 0)

        label_path = Gtk.Label(label=str(appimage.file_path))
        label_path.set_halign(Gtk.Align.START)
        label_path.get_style_context().add_class('dim-label')
        vbox.pack_start(label_path, False, False, 0)

        # Info line: type + size
        info_label = Gtk.Label(
            label=f"Type {appimage.appimage_type}  ·  {appimage.size / (1024*1024):.1f} MB"
                  + (f"  ·  v{appimage.version}" if appimage.version else ""))
        info_label.set_halign(Gtk.Align.START)
        info_label.get_style_context().add_class('dim-label')
        vbox.pack_start(info_label, False, False, 0)

        box.pack_start(vbox, True, True, 0)

        integrated = appimage.desktop_file_path is not None

        if integrated:
            # Update button
            btn_update = Gtk.Button()
            btn_update.set_image(Gtk.Image.new_from_icon_name('software-update-available', Gtk.IconSize.BUTTON))
            btn_update.set_tooltip_text(self._('Check for updates'))
            btn_update.set_valign(Gtk.Align.CENTER)
            btn_update.connect('clicked', lambda _w: on_update_callback(self.appimage))
            box.pack_start(btn_update, False, False, 0)

            # Run button
            btn_run = Gtk.Button()
            btn_run.set_image(Gtk.Image.new_from_icon_name('media-playback-start', Gtk.IconSize.BUTTON))
            btn_run.set_tooltip_text(self._('Run'))
            btn_run.set_valign(Gtk.Align.CENTER)
            btn_run.connect('clicked', lambda _w: on_run_callback(self.appimage))
            box.pack_start(btn_run, False, False, 0)
        else:
            # Integrate button (not yet in menu)
            btn_integrate = Gtk.Button(label=self._('Integrate'))
            btn_integrate.get_style_context().add_class('suggested-action')
            btn_integrate.set_valign(Gtk.Align.CENTER)
            btn_integrate.connect('clicked', lambda _w: on_integrate_callback(self.appimage))
            box.pack_start(btn_integrate, False, False, 0)

        # Delete button
        btn_delete = Gtk.Button()
        btn_delete.set_image(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON))
        btn_delete.set_tooltip_text(self._('Delete'))
        btn_delete.get_style_context().add_class('destructive-action')
        btn_delete.set_valign(Gtk.Align.CENTER)
        btn_delete.connect('clicked', lambda _w: on_delete_callback(self.appimage))
        box.pack_start(btn_delete, False, False, 10)

        self.add(box)


class MainWindow(Gtk.ApplicationWindow):
    """Main Application Window for Soplos AppImage Manager."""

    def __init__(self, app, appimage_manager: AppImageManager,
                 environment_detector, _translate, assets_dir):
        super().__init__(application=app, title=_translate(APP_NAME))
        self.appimage_manager = appimage_manager
        self._ = _translate
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.environment_detector = environment_detector

        self.set_default_size(650, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._setup_headerbar()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_file_monitor()
        self.connect('key-press-event', self._on_key_press)
        # Defer initial load so the window is fully shown first
        GLib.idle_add(self.load_appimages)

    def _setup_headerbar(self):
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.set_title(self._(APP_NAME))
        self.header.set_decoration_layout('menu:minimize,maximize,close')
        self.set_titlebar(self.header)

        btn_add = Gtk.Button()
        btn_add.set_image(Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.BUTTON))
        btn_add.set_tooltip_text(self._('Add AppImage'))
        btn_add.connect('clicked', self._on_add_clicked)
        self.header.pack_start(btn_add)

        btn_refresh = Gtk.Button()
        btn_refresh.set_image(Gtk.Image.new_from_icon_name('view-refresh', Gtk.IconSize.BUTTON))
        btn_refresh.set_tooltip_text(self._('Refresh'))
        btn_refresh.connect('clicked', lambda _w: self.load_appimages())
        self.header.pack_start(btn_refresh)

    def _setup_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # Drag and drop
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new('text/uri-list', 0, 0)],
            Gdk.DragAction.COPY
        )
        self.connect('drag-data-received', self._on_drag_data_received)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        vbox.pack_start(self.stack, True, True, 0)

        # Empty state
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name('application-x-executable', Gtk.IconSize.DIALOG)
        icon.set_pixel_size(128)
        icon.get_style_context().add_class('dim-label')
        empty_box.pack_start(icon, False, False, 0)

        label = Gtk.Label(label=self._("No AppImages installed.\nClick '+' to add one."))
        label.set_justify(Gtk.Justification.CENTER)
        label.get_style_context().add_class('dim-label')
        empty_box.pack_start(label, False, False, 0)

        self.stack.add_named(empty_box, 'empty')

        # List state
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(self.listbox)

        self.stack.add_named(scrolled, 'list')

        self._create_status_bar(vbox)

    def _create_status_bar(self, main_vbox):
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_box.set_margin_start(15)
        status_box.set_margin_end(15)
        status_box.set_margin_top(8)
        status_box.set_margin_bottom(8)

        env_info = self.environment_detector.detect_all()
        desktop_name = env_info['desktop_environment'].upper()
        protocol_name = env_info['display_protocol'].upper()

        status_label = Gtk.Label(
            label=self._('Ready - {desktop} on {protocol}').format(
                desktop=desktop_name, protocol=protocol_name))
        status_label.set_halign(Gtk.Align.START)
        status_label.get_style_context().add_class('dim-label')
        status_box.pack_start(status_label, False, False, 0)

        version_label = Gtk.Label(label=f'v{APP_VERSION}')
        version_label.set_halign(Gtk.Align.END)
        version_label.get_style_context().add_class('dim-label')
        status_box.pack_end(version_label, False, False, 0)

        main_vbox.pack_end(status_box, False, False, 0)

    def _setup_shortcuts(self):
        accel_group = Gtk.AccelGroup()
        self.add_accel_group(accel_group)
        key, mod = Gtk.accelerator_parse('<Primary>q')
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE,
                            lambda *_args: self.get_application().quit())

    def load_appimages(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        appimages = self.appimage_manager.list_installed()

        self.listbox.show_all()
        self.stack.show_all()

        if not appimages:
            self.stack.set_visible_child_name('empty')
        else:
            for appimage in appimages:
                row = AppImageRow(appimage, self._run_appimage,
                                  self._check_update, self._integrate_appimage,
                                  self._confirm_delete, self._)
                self.listbox.add(row)
            self.listbox.show_all()
            self.stack.set_visible_child_name('list')

    def _setup_file_monitor(self):
        self._reload_timeout_id = None
        self._file_monitors = []

        APPIMAGES_DIR.mkdir(parents=True, exist_ok=True)
        for watch_dir in [APPIMAGES_DIR, DESKTOP_FILES_DIR]:
            watch_dir.mkdir(parents=True, exist_ok=True)
            gfile = Gio.File.new_for_path(str(watch_dir))
            monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            monitor.connect('changed', self._on_dir_changed)
            self._file_monitors.append(monitor)

    def _on_dir_changed(self, _monitor, _file, _other, event_type):
        # Only react to file created/deleted/moved events
        relevant = {
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.DELETED,
            Gio.FileMonitorEvent.MOVED_IN,
            Gio.FileMonitorEvent.MOVED_OUT,
            Gio.FileMonitorEvent.RENAMED,
        }
        if event_type not in relevant:
            return
        # Debounce: wait 500 ms before reloading
        if self._reload_timeout_id is not None:
            GLib.source_remove(self._reload_timeout_id)
        self._reload_timeout_id = GLib.timeout_add(500, self._deferred_reload)

    def _deferred_reload(self):
        self._reload_timeout_id = None
        self.load_appimages()
        return GLib.SOURCE_REMOVE

    def _on_drag_data_received(self, _widget, _context, _x, _y, data, _info, _time):
        uris = data.get_uris()
        for uri in uris:
            path = Path(Gio.File.new_for_uri(uri).get_path() or '')
            if path.suffix.lower() == '.appimage' and path.is_file():
                self._do_add_appimage(path)
                break  # handle one at a time

    def _on_add_clicked(self, _widget):
        dialog = Gtk.FileChooserDialog(
            title=self._('Select an AppImage'),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        filt = Gtk.FileFilter()
        filt.set_name(self._('AppImage files'))
        filt.add_pattern('*.AppImage')
        filt.add_pattern('*.appimage')
        filt.add_mime_type('application/x-iso9660-appimage')
        filt.add_mime_type('application/vnd.appimage')
        dialog.add_filter(filt)

        if dialog.run() == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())
            dialog.destroy()
            self._do_add_appimage(path)
        else:
            dialog.destroy()

    def _do_add_appimage(self, path: Path):
        # Show a progress dialog while extracting metadata
        progress = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=self._('Adding AppImage…'),
        )
        progress.format_secondary_text(self._('Extracting metadata, please wait.'))
        progress.show_all()

        while Gtk.events_pending():
            Gtk.main_iteration()

        try:
            self.appimage_manager.add_appimage(path)
            progress.destroy()
            self.load_appimages()
        except Exception as e:
            progress.destroy()
            self._show_error(self._('Error adding AppImage'), str(e))

    def _integrate_appimage(self, appimage: AppImage):
        """Integrate an AppImage that was manually placed in ~/AppImages/."""
        progress = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=self._('Integrating AppImage…'),
        )
        progress.format_secondary_text(self._('Extracting metadata, please wait.'))
        progress.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()
        try:
            self.appimage_manager.integrate_existing(appimage)
            progress.destroy()
            self.load_appimages()
        except Exception as e:
            progress.destroy()
            self._show_error(self._('Error integrating AppImage'), str(e))

    def _check_update(self, appimage: AppImage):
        url = self.appimage_manager.get_update_url(appimage)
        if url:
            import webbrowser
            # GitHub/GitLab web URL → open in browser
            if url.startswith('https://') or url.startswith('http://'):
                webbrowser.open(url)
            else:
                # zsync or other format — show the raw info
                dialog = Gtk.MessageDialog(
                    transient_for=self, flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text=self._('Update information'),
                )
                dialog.format_secondary_text(url)
                dialog.run()
                dialog.destroy()
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=self._('No update information available'),
            )
            dialog.format_secondary_text(
                self._('This AppImage does not contain update information.'))
            dialog.run()
            dialog.destroy()

    def _run_appimage(self, appimage: AppImage):
        try:
            self.appimage_manager.run(appimage)
        except Exception as e:
            self._show_error(self._('Error running AppImage'), str(e))

    def _confirm_delete(self, appimage: AppImage):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=self._('Delete {}?').format(appimage.name),
        )
        dialog.format_secondary_text(
            self._('This will remove the AppImage file and its desktop entry.'))
        if dialog.run() == Gtk.ResponseType.YES:
            dialog.destroy()
            try:
                self.appimage_manager.delete(appimage)
                self.load_appimages()
            except Exception as e:
                self._show_error(self._('Error deleting AppImage'), str(e))
        else:
            dialog.destroy()

    def _show_error(self, title: str, message: str):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_F1:
            self._show_about()
            return True
        return False

    def _show_about(self, *_args):
        dialog = Gtk.AboutDialog()
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_program_name(APP_NAME)
        dialog.set_version(APP_VERSION)
        dialog.set_comments(self._('AppImage integration manager for Soplos Linux.'))
        dialog.set_website('https://soplos.org')
        dialog.set_website_label('soplos.org')
        dialog.set_authors(['Sergi Perich <info@soploslinux.com>'])
        dialog.set_license_type(Gtk.License.GPL_3_0)

        if self.assets_dir:
            icon_path = self.assets_dir / 'icons' / '64x64' / 'org.soplos.appimagemanager.png'
            if icon_path.exists():
                dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path), 48, 48, True))

        _about_css = Gtk.CssProvider()
        _about_css.load_from_data(b"""
            dialog, messagedialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            dialog .background, messagedialog .background {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            dialog > box, messagedialog > box {
                background-color: #2b2b2b;
            }
            dialog label, messagedialog label {
                color: #ffffff;
            }
            dialog button, messagedialog button {
                background-image: none;
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 14px;
                min-height: 0;
                box-shadow: none;
            }
            dialog button:hover, messagedialog button:hover {
                background-color: #444444;
                border-color: #ff8800;
            }
            dialog stackswitcher button {
                border-radius: 100px;
                background-color: #2b2b2b;
                background-image: none;
                border: 1px solid #3c3c3c;
                font-weight: normal;
                padding: 4px 16px;
                min-height: 0;
                box-shadow: none;
                color: #ffffff;
            }
            dialog stackswitcher button:hover {
                background-color: #444444;
                border-color: #ff8800;
            }
            dialog stackswitcher button:checked {
                background-color: #444444;
                color: #ffffff;
            }
            dialog scrolledwindow,
            dialog scrolledwindow viewport {
                background-color: #2b2b2b;
                border-radius: 0;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), _about_css,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        dialog.run()
        dialog.destroy()
