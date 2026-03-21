"""
AppImage Manager core logic for Soplos AppImage Manager.
Handles integration, listing, running and removal of AppImages.
"""

import os
import re
import shutil
import subprocess
import dataclasses
from pathlib import Path
from typing import Optional

from config.constants import APPIMAGES_DIR, ICONS_DIR, DESKTOP_FILES_DIR, TMP_DIR


@dataclasses.dataclass
class AppImage:
    """Represents a managed AppImage."""
    name: str
    file_path: Path
    icon_path: Optional[Path]
    desktop_file_path: Optional[Path]
    appimage_type: str
    size: int
    version: str = ''
    comment: str = ''
    categories: str = 'Utility;'


class AppImageManager:
    """Manages AppImage integration on Soplos Linux."""

    def __init__(self):
        APPIMAGES_DIR.mkdir(parents=True, exist_ok=True)
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        DESKTOP_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Public API ──────────────────────────────────────────────────────────

    def list_installed(self) -> list[AppImage]:
        """
        Scan ~/AppImages/ for AppImage files.
        Cross-reference with ANY .desktop file that points to ~/AppImages/.
        """
        result = []
        if not APPIMAGES_DIR.exists():
            return result

        # Build map: exec_path → (desktop_path, entry) from ALL .desktop files
        desktop_map: dict[str, tuple] = {}
        if DESKTOP_FILES_DIR.exists():
            for desktop_path in DESKTOP_FILES_DIR.glob('*.desktop'):
                try:
                    entry = self._parse_desktop_file(desktop_path)
                    exec_val = entry.get('TryExec') or entry.get('Exec', '').split()[0]
                    if exec_val and exec_val.startswith(str(APPIMAGES_DIR)):
                        desktop_map[exec_val] = (desktop_path, entry)
                except Exception:
                    pass

        # Scan ~/AppImages/ for AppImage files
        for appimage_path in sorted(APPIMAGES_DIR.iterdir()):
            if appimage_path.suffix.lower() not in ('.appimage',):
                continue
            if not appimage_path.is_file():
                continue

            try:
                match = desktop_map.get(str(appimage_path))
                desktop_path = None
                icon_path = None
                name = appimage_path.stem
                version = ''
                comment = ''
                categories = 'Utility;'

                if match:
                    desktop_path, entry = match
                    name = entry.get('Name', name)
                    version = entry.get('X-AppImage-Version', '')
                    comment = entry.get('Comment', '')
                    categories = entry.get('Categories', 'Utility;')
                    icon_raw = entry.get('Icon', '')
                    if icon_raw and os.path.isabs(icon_raw):
                        p = Path(icon_raw)
                        if p.exists():
                            icon_path = p

                appimage = AppImage(
                    name=name,
                    file_path=appimage_path,
                    icon_path=icon_path,
                    desktop_file_path=desktop_path,
                    appimage_type=self.get_appimage_type(appimage_path),
                    size=appimage_path.stat().st_size,
                    version=version,
                    comment=comment,
                    categories=categories,
                )
                result.append(appimage)
            except Exception:
                pass

        return result

    def add_appimage(self, source_path: Path) -> AppImage:
        """
        Move AppImage to ~/AppImages/, extract metadata and create .desktop file.
        Returns the new AppImage object.
        """
        source_path = Path(source_path)
        dest_path = APPIMAGES_DIR / source_path.name
        # Avoid overwriting
        if dest_path.exists() and dest_path != source_path:
            stem = source_path.stem
            suffix = source_path.suffix
            i = 1
            while dest_path.exists():
                dest_path = APPIMAGES_DIR / f'{stem}_{i}{suffix}'
                i += 1

        shutil.move(str(source_path), str(dest_path))
        dest_path.chmod(0o755)

        # Determine app_id from filename first (used for icon naming)
        app_id = self._safe_name(dest_path.stem)

        # Extract metadata — icon is copied to ~/AppImages/.icons/ inside this call
        meta = self._extract_metadata(dest_path, app_id)

        name = meta.get('name', dest_path.stem)
        app_id = self._safe_name(name)
        icon_dest = Path(meta['icon_path']) if meta.get('icon_path') else None
        desktop_path = DESKTOP_FILES_DIR / f'soplos-appimage-{app_id}.desktop'
        # Avoid collision
        i = 1
        while desktop_path.exists():
            desktop_path = DESKTOP_FILES_DIR / f'soplos-appimage-{app_id}_{i}.desktop'
            i += 1

        icon_value = str(icon_dest) if icon_dest else 'application-x-executable'

        self._write_desktop_file(
            desktop_path=desktop_path,
            name=name,
            exec_path=dest_path,
            icon=icon_value,
            comment=meta.get('comment', ''),
            categories=meta.get('categories', 'Utility;'),
            version=meta.get('version', ''),
        )

        self._update_desktop_db()

        return AppImage(
            name=name,
            file_path=dest_path,
            icon_path=icon_dest,
            desktop_file_path=desktop_path,
            appimage_type=self.get_appimage_type(dest_path),
            size=dest_path.stat().st_size,
            version=meta.get('version', ''),
            comment=meta.get('comment', ''),
            categories=meta.get('categories', 'Utility;'),
        )

    def integrate_existing(self, appimage: AppImage):
        """Create .desktop and extract icon for an AppImage already in ~/AppImages/."""
        appimage.file_path.chmod(0o755)
        app_id = self._safe_name(appimage.file_path.stem)
        meta = self._extract_metadata(appimage.file_path, app_id)
        name = meta.get('name', appimage.file_path.stem)
        app_id = self._safe_name(name)
        icon_dest = Path(meta['icon_path']) if meta.get('icon_path') else None

        desktop_path = DESKTOP_FILES_DIR / f'soplos-appimage-{app_id}.desktop'
        i = 1
        while desktop_path.exists():
            desktop_path = DESKTOP_FILES_DIR / f'soplos-appimage-{app_id}_{i}.desktop'
            i += 1

        self._write_desktop_file(
            desktop_path=desktop_path,
            name=name,
            exec_path=appimage.file_path,
            icon=str(icon_dest) if icon_dest else 'application-x-executable',
            comment=meta.get('comment', ''),
            categories=meta.get('categories', 'Utility;'),
            version=meta.get('version', ''),
        )
        self._update_desktop_db()

    def run(self, appimage: AppImage):
        """Launch an AppImage."""
        if appimage.desktop_file_path and appimage.desktop_file_path.exists():
            subprocess.Popen(
                ['gtk-launch', appimage.desktop_file_path.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            subprocess.Popen(
                [str(appimage.file_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    def delete(self, appimage: AppImage):
        """Remove .desktop, icon (if managed) and the AppImage file."""
        if appimage.desktop_file_path and appimage.desktop_file_path.exists():
            appimage.desktop_file_path.unlink()
        if (appimage.icon_path and appimage.icon_path.exists()
                and str(appimage.icon_path).startswith(str(ICONS_DIR))):
            appimage.icon_path.unlink()
        if appimage.file_path.exists():
            appimage.file_path.unlink()
        self._update_desktop_db()

    def get_appimage_type(self, path: Path) -> str:
        """Detect AppImage type from magic bytes."""
        try:
            with open(path, 'rb') as f:
                magic = f.read(11)[-3:]
            if magic == b'\x41\x49\x01':
                return '1'
            elif magic == b'\x41\x49\x02':
                return '2'
        except Exception:
            pass
        return '?'

    def get_update_url(self, appimage: AppImage) -> Optional[str]:
        """
        Read the update info embedded in the AppImage binary (.upd_info ELF section).
        Returns the raw update string or None.
        """
        # Primary: readelf -x .upd_info
        try:
            result = subprocess.run(
                ['readelf', '-x', '.upd_info', str(appimage.file_path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                raw_bytes = bytearray()
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line or not line.startswith('0x'):
                        continue
                    # Format: 0xOFFSET  HHHHHHHH HHHHHHHH HHHHHHHH HHHHHHHH  ASCII
                    # Split on whitespace, skip offset, take up to 4 hex groups
                    parts = line.split()
                    for chunk in parts[1:5]:
                        # Each chunk is 8 hex chars (4 bytes); skip ASCII column
                        if len(chunk) != 8:
                            break
                        try:
                            raw_bytes += bytes.fromhex(chunk)
                        except ValueError:
                            break
                text = raw_bytes.split(b'\x00', 1)[0].decode('utf-8', errors='ignore').strip()
                if self._is_valid_update_url(text):
                    return text
        except Exception:
            pass

        # Fallback: fixed offset (Type 2 standard)
        try:
            with open(appimage.file_path, 'rb') as f:
                f.seek(33651)
                raw = f.read(512)
            text = raw.split(b'\x00', 1)[0].decode('utf-8', errors='ignore').strip()
            if self._is_valid_update_url(text):
                return text
        except Exception:
            pass

        return None

    def _is_valid_update_url(self, text: str) -> bool:
        """Check that text looks like a known AppImage update URL format."""
        if not text or len(text) > 1024:
            return False
        valid_prefixes = (
            'zsync|', 'gh-releases-zsync|', 'bintray-zsync|',
            'pling-v1-zsync|', 'https://', 'http://',
        )
        return any(text.startswith(p) for p in valid_prefixes)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _extract_metadata(self, appimage_path: Path, app_id: str) -> dict:
        """
        Extract name, icon, comment, categories, version from an AppImage.
        Copies the icon directly to ~/AppImages/.icons/ before cleanup.
        Returns a dict with available keys.
        """
        tmp_dir = TMP_DIR / f'extract_{appimage_path.stem}'
        tmp_dir.mkdir(parents=True, exist_ok=True)

        try:
            extracted_root = self._extract_appimage(appimage_path, tmp_dir)
            if not extracted_root:
                return {}

            # Find .desktop file
            desktop_files = list(extracted_root.glob('*.desktop'))
            if not desktop_files:
                desktop_files = list(extracted_root.rglob('*.desktop'))
            if not desktop_files:
                return {}

            entry = self._parse_desktop_file(desktop_files[0])
            name = entry.get('Name', appimage_path.stem)
            icon_name = entry.get('Icon', '').strip()
            icon_name = re.sub(r'\.(png|svg)$', '', icon_name)
            version = entry.get('X-AppImage-Version', '')
            comment = entry.get('Comment', '')
            categories = entry.get('Categories', 'Utility;')

            # Find icon and copy to ~/AppImages/.icons/ BEFORE cleanup
            icon_src = self._find_icon(extracted_root, icon_name)
            icon_dest = None
            if icon_src and os.path.isfile(str(icon_src)):
                ICONS_DIR.mkdir(parents=True, exist_ok=True)
                icon_dest = ICONS_DIR / f'{app_id}{icon_src.suffix}'
                shutil.copy2(str(icon_src), str(icon_dest))

            return {
                'name': name,
                'icon_path': str(icon_dest) if icon_dest else None,
                'version': version,
                'comment': comment,
                'categories': categories,
            }
        except Exception:
            return {}
        finally:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)

    def _extract_appimage(self, appimage_path: Path, dest_dir: Path) -> Optional[Path]:
        """
        Extract AppImage content. Returns path to squashfs-root or None.
        Priority: 7zz → --appimage-extract
        """
        squashfs_root = dest_dir / 'squashfs-root'

        # Try 7zz first
        if shutil.which('7zz') or shutil.which('7z'):
            tool = '7zz' if shutil.which('7zz') else '7z'
            try:
                subprocess.run(
                    [tool, 'x', str(appimage_path), f'-o{squashfs_root}', '-y',
                     '-bso0', '-bsp0', '-ir!*.png', '-ir!*.svg', '-ir!*.desktop', '-ir0!.DirIcon'],
                    cwd=str(dest_dir), timeout=60,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False
                )
                if squashfs_root.exists():
                    return squashfs_root
            except Exception:
                pass

        # Fallback: --appimage-extract
        try:
            tmp_copy = dest_dir / 'app.appimage'
            shutil.copy2(str(appimage_path), str(tmp_copy))
            tmp_copy.chmod(0o755)
            subprocess.run(
                [str(tmp_copy), '--appimage-extract'],
                cwd=str(dest_dir), timeout=120,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False
            )
            if squashfs_root.exists():
                return squashfs_root
        except Exception:
            pass

        return None

    def _find_icon(self, root: Path, icon_name: str) -> Optional[Path]:
        """Find the best icon file in the extracted AppImage."""
        # 1. .DirIcon (resolve symlinks)
        diricon = root / '.DirIcon'
        if diricon.exists() or os.path.islink(str(diricon)):
            real = Path(os.path.realpath(str(diricon)))
            if real.exists() and os.path.isfile(str(real)):
                return real

        # 2. Root level {name}.svg / {name}.png
        for ext in ['.svg', '.png']:
            candidate = root / f'{icon_name}{ext}'
            if candidate.exists():
                return candidate

        # 3. hicolor icon dirs
        hicolor = root / 'usr' / 'share' / 'icons' / 'hicolor'
        for size in ['scalable/apps', '512x512/apps', '256x256/apps', '128x128/apps']:
            for ext in ['.svg', '.png']:
                candidate = hicolor / size / f'{icon_name}{ext}'
                if candidate.exists():
                    return candidate

        # 4. Any .png / .svg in root
        for ext in ['*.png', '*.svg']:
            found = list(root.glob(ext))
            if found:
                return found[0]

        return None

    def _parse_desktop_file(self, path: Path) -> dict:
        """Parse a .desktop file and return a dict of key=value pairs."""
        entry = {}
        try:
            in_desktop_entry = False
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line == '[Desktop Entry]':
                        in_desktop_entry = True
                        continue
                    if line.startswith('[') and line != '[Desktop Entry]':
                        if in_desktop_entry:
                            break
                        continue
                    if in_desktop_entry and '=' in line and not line.startswith('#'):
                        key, _, value = line.partition('=')
                        entry[key.strip()] = value.strip()
        except Exception:
            pass
        return entry

    def _write_desktop_file(self, desktop_path: Path, name: str, exec_path: Path,
                             icon: str, comment: str, categories: str, version: str):
        """Write a .desktop file for an AppImage."""
        lines = [
            '[Desktop Entry]',
            'Type=Application',
            f'Name={name}',
            f'Exec={exec_path}',
            f'TryExec={exec_path}',
            f'Icon={icon}',
            f'Categories={categories}',
        ]
        if comment:
            lines.append(f'Comment={comment}')
        if version:
            lines.append(f'X-AppImage-Version={version}')
        lines.append('X-AppImage-Integrate=true')
        lines.append('')

        with open(desktop_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        desktop_path.chmod(0o755)

    def _safe_name(self, name: str) -> str:
        """Convert a name to a filesystem-safe lowercase string."""
        return re.sub(r'[^a-z0-9_-]', '_', name.lower())

    def _update_desktop_db(self):
        """Update the desktop database."""
        try:
            subprocess.run(
                ['update-desktop-database', str(DESKTOP_FILES_DIR), '-q'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=False
            )
        except Exception:
            pass
