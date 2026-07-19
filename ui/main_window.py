import os
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, Gdk, Gio, GLib
from pathlib import Path
from typing import Optional

from core.appimage_manager import AppImageManager, AppImage
from config.constants import APP_ID, APP_NAME, APP_VERSION, APPIMAGES_DIR, DESKTOP_FILES_DIR


class AppImagePropertiesDialog(Gtk.Dialog):
    """Dialog for viewing and editing AppImage metadata."""

    def __init__(self, parent, appimage: AppImage, _translate):
        super().__init__(
            title=_translate('Properties'),
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        self._ = _translate
        self.appimage = appimage
        self.set_default_size(480, -1)
        self.set_resizable(False)

        self.add_button(_translate('Cancel'), Gtk.ResponseType.CANCEL)
        save_btn = self.add_button(_translate('Save'), Gtk.ResponseType.OK)
        save_btn.get_style_context().add_class('suggested-action')
        self.set_default_response(Gtk.ResponseType.OK)

        content = self.get_content_area()
        content.set_spacing(0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        content.add(main_box)

        # Header: icon + read-only info
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        main_box.pack_start(header_box, False, False, 0)

        icon_image = Gtk.Image()
        if appimage.icon_path and appimage.icon_path.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(appimage.icon_path), 64, 64, True)
                icon_image.set_from_pixbuf(pixbuf)
            except Exception:
                icon_image.set_from_icon_name('application-x-executable', Gtk.IconSize.DIALOG)
                icon_image.set_pixel_size(64)
        else:
            icon_image.set_from_icon_name('application-x-executable', Gtk.IconSize.DIALOG)
            icon_image.set_pixel_size(64)
        header_box.pack_start(icon_image, False, False, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_valign(Gtk.Align.CENTER)
        header_box.pack_start(info_box, True, True, 0)

        size_mb = appimage.size / (1024 * 1024)
        ro_label = Gtk.Label(
            label=f'<span size="small">'
                  f'{_translate("File")}: {appimage.file_path.name}\n'
                  f'{_translate("Size")}: {size_mb:.1f} MB  ·  '
                  f'{_translate("Type")}: AppImage {appimage.appimage_type}'
                  f'</span>')
        ro_label.set_use_markup(True)
        ro_label.set_halign(Gtk.Align.START)
        ro_label.get_style_context().add_class('dim-label')
        ro_label.set_line_wrap(True)
        info_box.pack_start(ro_label, False, False, 0)

        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Editable fields grid
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(12)
        main_box.pack_start(grid, False, False, 0)

        def make_label(text):
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.END)
            lbl.set_valign(Gtk.Align.CENTER)
            lbl.get_style_context().add_class('dim-label')
            return lbl

        # Name
        grid.attach(make_label(_translate('Name')), 0, 0, 1, 1)
        self.entry_name = Gtk.Entry()
        self.entry_name.set_text(appimage.name)
        self.entry_name.set_hexpand(True)
        grid.attach(self.entry_name, 1, 0, 1, 1)

        # Version
        grid.attach(make_label(_translate('Version')), 0, 1, 1, 1)
        self.entry_version = Gtk.Entry()
        self.entry_version.set_text(appimage.version)
        self.entry_version.set_placeholder_text(_translate('e.g. 1.2.3'))
        grid.attach(self.entry_version, 1, 1, 1, 1)

        # Description
        grid.attach(make_label(_translate('Description')), 0, 2, 1, 1)
        self.entry_comment = Gtk.Entry()
        self.entry_comment.set_text(appimage.comment)
        self.entry_comment.set_placeholder_text(_translate('Short description'))
        grid.attach(self.entry_comment, 1, 2, 1, 1)

        # Categories
        grid.attach(make_label(_translate('Categories')), 0, 3, 1, 1)
        self.entry_categories = Gtk.Entry()
        self.entry_categories.set_text(appimage.categories)
        self.entry_categories.set_placeholder_text('Utility;')
        grid.attach(self.entry_categories, 1, 3, 1, 1)

        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Run as root toggle
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        root_label_box.set_hexpand(True)
        root_title = Gtk.Label(label=_translate('Run as root'))
        root_title.set_halign(Gtk.Align.START)
        root_hint = Gtk.Label(label=_translate('Launch with pkexec (requires authentication)'))
        root_hint.set_halign(Gtk.Align.START)
        root_hint.get_style_context().add_class('dim-label')
        root_hint.set_line_wrap(True)
        root_label_box.pack_start(root_title, False, False, 0)
        root_label_box.pack_start(root_hint, False, False, 0)
        root_box.pack_start(root_label_box, True, True, 0)
        self.switch_run_as_root = Gtk.Switch()
        self.switch_run_as_root.set_active(appimage.run_as_root)
        self.switch_run_as_root.set_valign(Gtk.Align.CENTER)
        root_box.pack_start(self.switch_run_as_root, False, False, 0)
        main_box.pack_start(root_box, False, False, 0)

        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Update URL section
        url_title = Gtk.Label(label=f'<b>{_translate("Update URL")}</b>')
        url_title.set_use_markup(True)
        url_title.set_halign(Gtk.Align.START)
        main_box.pack_start(url_title, False, False, 0)

        url_hint = Gtk.Label()
        url_hint.set_markup(
            _translate('Supported sources for automatic updates:') + '\n'
            '<span foreground="#888888" size="small">'
            + _translate('● GitHub / GitLab / Codeberg → paste the project URL') + '\n'
            + _translate('● Any server → paste a direct link ending in .appimage')
            + '</span>'
        )
        url_hint.set_halign(Gtk.Align.START)
        url_hint.get_style_context().add_class('dim-label')
        url_hint.set_line_wrap(True)
        url_hint.set_xalign(0)
        main_box.pack_start(url_hint, False, False, 0)

        self.entry_update_url = Gtk.Entry()
        self.entry_update_url.set_text(appimage.update_url)
        self.entry_update_url.set_placeholder_text(
            _translate('https://github.com/user/repo  or  https://example.com/latest/App.AppImage'))
        main_box.pack_start(self.entry_update_url, False, False, 0)

        self.show_all()

    def get_values(self) -> dict:
        return {
            'name': self.entry_name.get_text().strip() or self.appimage.name,
            'version': self.entry_version.get_text().strip(),
            'comment': self.entry_comment.get_text().strip(),
            'categories': self.entry_categories.get_text().strip() or 'Utility;',
            'update_url': self.entry_update_url.get_text().strip(),
            'run_as_root': self.switch_run_as_root.get_active(),
        }


class AppImageUpdateDialog(Gtk.Dialog):
    """
    Checks for updates and performs them.
    - GitHub/GitLab/Codeberg URL → API + direct download
    - Direct .appimage URL → HEAD request + direct download
    - No URL but appimageupdatetool installed → uses embedded .upd_info
    """

    def __init__(self, parent, appimage: AppImage, manager: AppImageManager, _translate):
        super().__init__(
            title=_translate('Update'),
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        self._ = _translate
        self.appimage = appimage
        self.manager = manager
        self.set_default_size(520, -1)
        self._update_done = False
        self._api_result = None
        self._mode = manager.get_update_mode(appimage)  # 'api' | 'direct' | 'tool' | 'none'

        content = self.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        content.add(main_box)

        # App name
        title_lbl = Gtk.Label(label=f'<b>{GLib.markup_escape_text(appimage.name)}</b>')
        title_lbl.set_use_markup(True)
        title_lbl.set_halign(Gtk.Align.START)
        main_box.pack_start(title_lbl, False, False, 0)

        # Spinner + status
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main_box.pack_start(status_box, False, False, 0)
        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(20, 20)
        status_box.pack_start(self._spinner, False, False, 0)
        self._status_lbl = Gtk.Label(label=_translate('Checking for updates…'))
        self._status_lbl.set_halign(Gtk.Align.START)
        self._status_lbl.set_line_wrap(True)
        status_box.pack_start(self._status_lbl, True, True, 0)

        # Progress bar — shown during API download
        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(True)
        self._progress.set_no_show_all(True)
        main_box.pack_start(self._progress, False, False, 0)

        # Text output — shown during appimageupdatetool run
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_min_content_height(120)
        self._scrolled.set_no_show_all(True)
        self._textview = Gtk.TextView()
        self._textview.set_editable(False)
        self._textview.set_cursor_visible(False)
        self._textview.set_monospace(True)
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._buf = self._textview.get_buffer()
        self._scrolled.add(self._textview)
        main_box.pack_start(self._scrolled, True, True, 0)

        self._btn_close = self.add_button(_translate('Close'), Gtk.ResponseType.CLOSE)
        self._btn_update = self.add_button(_translate('Update Now'), Gtk.ResponseType.APPLY)
        self._btn_update.get_style_context().add_class('suggested-action')
        self._btn_update.set_sensitive(False)
        self._btn_update.connect('clicked', self._on_update_clicked)
        self.connect('response', self._on_response)
        self.show_all()

        if self._mode == 'none':
            self._spinner.stop()
            self._status_lbl.set_markup(
                f'<span foreground="#ff8800">●</span>  '
                + _translate('No update source configured.\n'
                             'Add a GitHub, GitLab, Codeberg URL or a direct .appimage link in Properties.'))
        else:
            self._spinner.start()
            threading.Thread(target=self._do_check, daemon=True).start()

    # ── Check phase ───────────────────────────────────────────────────────────

    def _do_check(self):
        if self._mode == 'api':
            result = self.manager.check_for_update_api(self.appimage)
            GLib.idle_add(self._on_check_done_api, result)
        elif self._mode == 'direct':
            result = self.manager.check_for_update_direct(self.appimage)
            GLib.idle_add(self._on_check_done_api, result)
        else:
            has_update, message = self.manager.check_for_update_tool(self.appimage)
            GLib.idle_add(self._on_check_done, has_update, message)

    def _on_check_done_api(self, result):
        self._spinner.stop()
        self._api_result = result
        has_update = result.get('has_update')
        message = GLib.markup_escape_text(result.get('message', ''))
        if has_update is True:
            self._status_lbl.set_markup(
                f'<span foreground="#4ec94e">●</span>  '
                f'<b>{self._("Update available!")}</b>  '
                f'<span foreground="#888888">{message}</span>')
            asset = GLib.markup_escape_text(result.get('asset_name', ''))
            size_mb = result.get('asset_size', 0) / (1024 * 1024)
            self._status_lbl.set_markup(
                self._status_lbl.get_label() +
                f'\n<span foreground="#888888" size="small">{asset}  ({size_mb:.1f} MB)</span>')
            self._btn_update.set_sensitive(True)
        elif has_update is False:
            self._status_lbl.set_markup(
                f'<span foreground="#888888">●</span>  '
                f'{self._("Already up to date.")}  '
                f'<span foreground="#666666">{message}</span>')
        else:
            self._status_lbl.set_markup(
                f'<span foreground="#ff8800">●</span>  '
                f'{self._("Could not check:")} {message}')

    def _on_check_done(self, has_update, message):
        self._spinner.stop()
        message = GLib.markup_escape_text(message or '')
        if has_update is True:
            self._status_lbl.set_markup(
                f'<span foreground="#4ec94e">●</span>  '
                f'<b>{self._("Update available!")}</b>')
            self._btn_update.set_sensitive(True)
        elif has_update is False:
            self._status_lbl.set_markup(
                f'<span foreground="#888888">●</span>  {self._("Already up to date.")}')
        else:
            self._status_lbl.set_markup(
                f'<span foreground="#ff8800">●</span>  '
                f'{self._("Could not check:")} {message}')

    # ── Update phase ──────────────────────────────────────────────────────────

    def _on_update_clicked(self, _button):
        self._btn_update.set_sensitive(False)
        self._btn_close.set_sensitive(False)
        self._spinner.start()
        self._status_lbl.set_markup(
            f'<span foreground="#4ec9b0">●</span>  {self._("Downloading update…")}')
        if self._mode in ('api', 'direct'):
            self._progress.show()
            self._progress.set_fraction(0)
            threading.Thread(target=self._do_update_api, daemon=True).start()
        else:
            self._scrolled.show()
            threading.Thread(target=self._do_update_tool, daemon=True).start()

    def _do_update_api(self):
        download_url = self._api_result.get('download_url', '')
        asset_name = self._api_result.get('asset_name', self.appimage.file_path.name)
        try:
            def on_progress(downloaded, total):
                if total > 0:
                    frac = downloaded / total
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    GLib.idle_add(self._progress.set_fraction, frac)
                    GLib.idle_add(self._progress.set_text,
                                  f'{mb_done:.1f} / {mb_total:.1f} MB')
            self.manager.download_and_install_new(
                self.appimage, download_url, asset_name, on_progress)
            # Update stored version from API result
            new_ver = self._api_result.get('latest_version', '')
            if new_ver:
                self.appimage.version = new_ver
            GLib.idle_add(self._on_update_done, True, '')
        except Exception as e:
            GLib.idle_add(self._on_update_done, False, str(e))

    def _do_update_tool(self):
        try:
            proc = self.manager.start_update_tool(self.appimage)
            for line in proc.stdout:
                GLib.idle_add(self._append_output, line)
            proc.wait()
            GLib.idle_add(self._on_update_done, proc.returncode == 0, '')
        except Exception as e:
            GLib.idle_add(self._on_update_done, False, str(e))

    def _append_output(self, line: str):
        end = self._buf.get_end_iter()
        self._buf.insert(end, line)
        adj = self._scrolled.get_vadjustment()
        adj.set_value(adj.get_upper())

    def _on_update_done(self, success: bool, error_msg: str):
        self._spinner.stop()
        self._btn_close.set_sensitive(True)
        self._update_done = success
        if success:
            # Persistir la versión nueva en el archivo .desktop
            if self.appimage.desktop_file_path and self.appimage.desktop_file_path.exists():
                try:
                    self.manager.update_info(
                        self.appimage,
                        name=self.appimage.name,
                        version=self.appimage.version,
                        comment=self.appimage.comment,
                        categories=self.appimage.categories,
                        update_url=self.appimage.update_url,
                    )
                except Exception:
                    pass
            self._status_lbl.set_markup(
                f'<span foreground="#4ec94e">●</span>  '
                f'<b>{self._("Update completed successfully!")}</b>')
        else:
            self._status_lbl.set_markup(
                f'<span foreground="#ff4444">●</span>  '
                f'{self._("Update failed.")} '
                f'{GLib.markup_escape_text(error_msg)}')

    def _on_response(self, _dialog, response):
        if response == Gtk.ResponseType.APPLY:
            # No cerrar el diálogo mientras se descarga la actualización
            self.stop_emission_by_name('response')
            return
        self.destroy()


class AppImageCheckAllDialog(Gtk.Dialog):
    """Check all installed AppImages for updates and optionally update them all."""

    def __init__(self, parent, appimages: list, manager: AppImageManager, _translate):
        super().__init__(
            title=_translate('Check All Updates'),
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        self._ = _translate
        self.manager = manager
        self.set_default_size(540, 420)
        self._update_done = False
        self._updates_available = []   # list of (appimage, mode, result)
        self._rows = {}                # str(file_path) → (spinner, status_lbl)
        self._checked = 0

        self._checkable = [
            (a, manager.get_update_mode(a))
            for a in appimages
            if manager.get_update_mode(a) != 'none'
        ]

        content = self.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        content.add(main_box)

        # Header row: spinner + summary label
        hbox = Gtk.Box(spacing=8)
        main_box.pack_start(hbox, False, False, 0)
        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(18, 18)
        hbox.pack_start(self._spinner, False, False, 0)
        self._header_lbl = Gtk.Label()
        self._header_lbl.set_halign(Gtk.Align.START)
        self._header_lbl.set_line_wrap(True)
        hbox.pack_start(self._header_lbl, True, True, 0)

        # Scrolled list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(220)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(self._listbox)
        main_box.pack_start(scrolled, True, True, 0)

        self._btn_close = self.add_button(_translate('Close'), Gtk.ResponseType.CLOSE)
        self._btn_update_all = self.add_button(
            _translate('Update All'), Gtk.ResponseType.APPLY)
        self._btn_update_all.get_style_context().add_class('suggested-action')
        self._btn_update_all.set_sensitive(False)
        self._btn_update_all.connect('clicked', self._on_update_all_clicked)
        self.connect('response', self._on_response)
        self.show_all()

        if not self._checkable:
            self._spinner.hide()
            self._header_lbl.set_markup(
                f'<span foreground="#888888">'
                + _translate('No AppImages have update sources configured.\n'
                             'Add GitHub, GitLab, Codeberg URLs or direct links in Properties.')
                + '</span>')
        else:
            self._build_rows()
            self._header_lbl.set_text(
                _translate('Checking {n} AppImage(s) for updates…').format(
                    n=len(self._checkable)))
            self._spinner.start()
            threading.Thread(target=self._do_check_all, daemon=True).start()

    # ── Build list rows ───────────────────────────────────────────────────────

    def _build_rows(self):
        for appimage, _mode in self._checkable:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(spacing=10)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_top(7)
            box.set_margin_bottom(7)

            img = Gtk.Image()
            if appimage.icon_path and appimage.icon_path.exists():
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(appimage.icon_path), 32, 32, True)
                    img.set_from_pixbuf(pb)
                except Exception:
                    img.set_from_icon_name('application-x-executable',
                                           Gtk.IconSize.LARGE_TOOLBAR)
            else:
                img.set_from_icon_name('application-x-executable',
                                       Gtk.IconSize.LARGE_TOOLBAR)
            box.pack_start(img, False, False, 0)

            name_lbl = Gtk.Label(label=appimage.name)
            name_lbl.set_halign(Gtk.Align.START)
            box.pack_start(name_lbl, True, True, 0)

            row_spinner = Gtk.Spinner()
            row_spinner.set_size_request(16, 16)
            row_spinner.start()
            box.pack_start(row_spinner, False, False, 0)

            status_lbl = Gtk.Label()
            status_lbl.set_halign(Gtk.Align.END)
            status_lbl.set_no_show_all(True)
            box.pack_start(status_lbl, False, False, 0)

            row.add(box)
            self._listbox.add(row)
            self._listbox.show_all()
            self._rows[str(appimage.file_path)] = (row_spinner, status_lbl)

    # ── Check phase ───────────────────────────────────────────────────────────

    def _do_check_all(self):
        for appimage, mode in self._checkable:
            if mode == 'api':
                result = self.manager.check_for_update_api(appimage)
            elif mode == 'direct':
                result = self.manager.check_for_update_direct(appimage)
            else:
                has_update, msg = self.manager.check_for_update_tool(appimage)
                result = {'has_update': has_update, 'message': msg}
            result['_mode'] = mode
            GLib.idle_add(self._on_row_checked, appimage, mode, result)
        GLib.idle_add(self._on_all_checked)

    def _on_row_checked(self, appimage, mode, result):
        self._checked += 1
        key = str(appimage.file_path)
        if key not in self._rows:
            return
        row_spinner, status_lbl = self._rows[key]
        row_spinner.stop()
        row_spinner.hide()

        has_update = result.get('has_update')
        if has_update is True:
            status_lbl.set_markup(
                f'<span foreground="#4ec94e">● {self._("Update available")}</span>')
            self._updates_available.append((appimage, mode, result))
        elif has_update is False:
            status_lbl.set_markup(
                f'<span foreground="#888888">{self._("Up to date")}</span>')
        else:
            msg = (result.get('message') or self._('Error'))[:50]
            status_lbl.set_markup(
                f'<span foreground="#ff8800">⚠ {GLib.markup_escape_text(msg)}</span>')
        status_lbl.show()

    def _on_all_checked(self):
        self._spinner.stop()
        count = len(self._updates_available)
        total = len(self._checkable)
        if count > 0:
            self._header_lbl.set_markup(
                f'<b>{count}</b> / {total}  {self._("update(s) available")}')
            self._btn_update_all.set_sensitive(True)
        else:
            self._header_lbl.set_markup(
                f'<span foreground="#888888">'
                + self._('All AppImages are up to date.')
                + '</span>')

    # ── Update-all phase ──────────────────────────────────────────────────────

    def _on_update_all_clicked(self, button):
        button.set_sensitive(False)
        self._btn_close.set_sensitive(False)
        self._spinner.start()
        self._header_lbl.set_text(self._('Updating…'))
        threading.Thread(target=self._do_update_all, daemon=True).start()

    def _do_update_all(self):
        for appimage, mode, result in self._updates_available:
            GLib.idle_add(self._set_row_status, appimage,
                          f'<span foreground="#4ec9b0">{self._("Updating…")}</span>')
            try:
                if mode in ('api', 'direct'):
                    download_url = result.get('download_url', '')
                    asset_name = result.get('asset_name', appimage.file_path.name)
                    self.manager.download_and_install_new(
                        appimage, download_url, asset_name)
                    new_ver = result.get('latest_version', '')
                    if new_ver:
                        appimage.version = new_ver
                    if (appimage.desktop_file_path
                            and appimage.desktop_file_path.exists()):
                        try:
                            self.manager.update_info(
                                appimage, appimage.name, appimage.version,
                                appimage.comment, appimage.categories,
                                appimage.update_url)
                        except Exception:
                            pass
                else:
                    proc = self.manager.start_update_tool(appimage)
                    proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError('appimageupdatetool exited with error')
                GLib.idle_add(self._set_row_status, appimage,
                              f'<span foreground="#4ec94e">✓ {self._("Updated")}</span>')
            except Exception as e:
                msg = str(e)[:50]
                GLib.idle_add(self._set_row_status, appimage,
                              f'<span foreground="#ff4444">'
                              f'✗ {GLib.markup_escape_text(msg)}</span>')
        GLib.idle_add(self._on_update_all_done)

    def _set_row_status(self, appimage, markup: str):
        key = str(appimage.file_path)
        if key in self._rows:
            _, status_lbl = self._rows[key]
            status_lbl.set_markup(markup)

    def _on_update_all_done(self):
        self._spinner.stop()
        self._btn_close.set_sensitive(True)
        self._update_done = True
        self._header_lbl.set_markup(
            f'<b>{self._("Update complete!")}</b>')

    def _on_response(self, _dialog, response):
        if response == Gtk.ResponseType.APPLY:
            return  # no cerrar mientras actualiza
        self.destroy()


class AppImageRow(Gtk.ListBoxRow):
    def __init__(self, appimage: AppImage, on_run_callback, on_update_callback,
                 on_integrate_callback, on_delete_callback, on_properties_callback,
                 _translate):
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
            label=f"{self._('Type')} {appimage.appimage_type}  ·  {appimage.size / (1024*1024):.1f} MB"
                  + (f"  ·  v{appimage.version}" if appimage.version else ""))
        info_label.set_halign(Gtk.Align.START)
        info_label.get_style_context().add_class('dim-label')
        vbox.pack_start(info_label, False, False, 0)

        box.pack_start(vbox, True, True, 0)

        integrated = appimage.desktop_file_path is not None

        if integrated:
            # Properties button
            btn_props = Gtk.Button()
            btn_props.set_image(Gtk.Image.new_from_icon_name('document-properties', Gtk.IconSize.BUTTON))
            btn_props.set_tooltip_text(self._('Properties'))
            btn_props.set_valign(Gtk.Align.CENTER)
            btn_props.connect('clicked', lambda _w: on_properties_callback(self.appimage))
            box.pack_start(btn_props, False, False, 0)

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

        _env = environment_detector.detect_all()
        _is_light = _env.get('theme_type', 'dark') == 'light'
        self._is_light = _is_light

        if not _is_light:
            _css = Gtk.CssProvider()
            _css.load_from_data(b"""
                window { background-color: #2b2b2b; color: #ffffff; }
                list { background-color: #2b2b2b; color: #ffffff; }
                list row { background-color: #2b2b2b; color: #ffffff; border-bottom: 1px solid #3c3c3c; }
                list row:hover { background-color: #333333; }
                scrolledwindow, scrolledwindow viewport { background-color: #2b2b2b; }
                label { color: #ffffff; }
                label.dim-label { color: #888888; }
            """)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), _css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

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

        btn_check_all = Gtk.Button()
        btn_check_all.set_image(Gtk.Image.new_from_icon_name(
            'software-update-available', Gtk.IconSize.BUTTON))
        btn_check_all.set_tooltip_text(self._('Check all updates'))
        btn_check_all.connect('clicked', self._on_check_all_clicked)
        self.header.pack_start(btn_check_all)

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

        status_label = Gtk.Label(label=f"{desktop_name}  ·  {protocol_name}")
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
                                  self._confirm_delete, self._show_properties, self._)
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
        # Use getattr for MOVED_IN/MOVED_OUT — not available on all GLib versions
        relevant = {
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.DELETED,
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
        }
        for name in ('MOVED_IN', 'MOVED_OUT', 'RENAMED'):
            ev = getattr(Gio.FileMonitorEvent, name, None)
            if ev is not None:
                relevant.add(ev)
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
                copy = self._ask_move_or_copy(path)
                if copy is not None:
                    self._do_add_appimage(path, copy=copy)
                break  # handle one at a time

    def _ask_move_or_copy(self, path: Path) -> Optional[bool]:
        """Ask the user whether to move or copy the dropped AppImage.
        Returns True for copy, False for move, None if cancelled."""
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=self._('Add {name}?').format(name=path.name),
        )
        dialog.format_secondary_text(
            self._('Move it into ~/AppImages/, or keep the original file '
                    'and copy it instead?'))
        dialog.add_buttons(
            self._('Cancel'), Gtk.ResponseType.CANCEL,
            self._('Keep Original (Copy)'), Gtk.ResponseType.APPLY,
            self._('Move'), Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            return False
        if response == Gtk.ResponseType.APPLY:
            return True
        return None

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

        keep_original_check = Gtk.CheckButton(
            label=self._('Keep the original file (copy instead of move)'))
        dialog.set_extra_widget(keep_original_check)

        if dialog.run() == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())
            copy = keep_original_check.get_active()
            dialog.destroy()
            self._do_add_appimage(path, copy=copy)
        else:
            dialog.destroy()

    def _do_add_appimage(self, path: Path, copy: bool = False):
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
            self.appimage_manager.add_appimage(path, copy=copy)
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

    def _show_properties(self, appimage: AppImage):
        dialog = AppImagePropertiesDialog(self, appimage, self._)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            values = dialog.get_values()
            dialog.destroy()
            try:
                self.appimage_manager.update_info(
                    appimage,
                    name=values['name'],
                    version=values['version'],
                    comment=values['comment'],
                    categories=values['categories'],
                    update_url=values['update_url'],
                    run_as_root=values['run_as_root'],
                )
                self.load_appimages()
            except Exception as e:
                self._show_error(self._('Error saving properties'), str(e))
        else:
            dialog.destroy()

    def _on_check_all_clicked(self, _widget):
        appimages = self.appimage_manager.list_installed()
        dialog = AppImageCheckAllDialog(
            self, appimages, self.appimage_manager, self._)
        dialog.run()
        if dialog._update_done:
            self.load_appimages()

    def _check_update(self, appimage: AppImage):
        import webbrowser

        mode = self.appimage_manager.get_update_mode(appimage)

        if mode == 'none':
            # No GitHub/GitLab URL and no appimageupdatetool
            self._show_error(
                self._('No update source configured'),
                self._('Open Properties and add an update URL:\n\n'
                       '● GitHub/GitLab/Codeberg project URL\n'
                       '● Direct link to the .appimage file\n\n'
                       'Or install appimageupdatetool if the AppImage\n'
                       'has update info embedded.'))
            return

        # 'github' or 'tool' → open the update dialog
        dialog = AppImageUpdateDialog(self, appimage, self.appimage_manager, self._)
        dialog.run()
        if dialog._update_done:
            self.load_appimages()

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

        if not getattr(self, '_is_light', False):
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
