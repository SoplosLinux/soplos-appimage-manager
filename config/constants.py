"""
Configuration constants for Soplos AppImage Manager.
"""
import random
from pathlib import Path
from gi.repository import GLib

APP_ID = 'org.soplos.appimagemanager'
APP_NAME = 'Soplos AppImage Manager'
APP_VERSION = '1.0.0'

APPIMAGES_DIR = Path.home() / 'AppImages'
ICONS_DIR = APPIMAGES_DIR / '.icons'
DESKTOP_FILES_DIR = Path.home() / '.local' / 'share' / 'applications'

_RUN_ID = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8))
TMP_DIR = Path(GLib.get_tmp_dir()) / f'soplos-appimage-{_RUN_ID}'
