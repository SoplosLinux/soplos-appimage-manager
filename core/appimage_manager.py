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
    update_url: str = ''
    run_as_root: bool = False


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
                update_url = ''

                run_as_root = False
                if match:
                    desktop_path, entry = match
                    name = entry.get('Name', name)
                    version = entry.get('X-AppImage-Version', '')
                    comment = entry.get('Comment', '')
                    categories = entry.get('Categories', 'Utility;')
                    update_url = entry.get('X-AppImage-UpdateUrl', '')
                    run_as_root = entry.get('X-AppImage-RunAsRoot', '').lower() == 'true'
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
                    update_url=update_url,
                    run_as_root=run_as_root,
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
            update_url='',
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
            update_url='',
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
            update_url='',
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

    def update_info(self, appimage: AppImage, name: str, version: str,
                    comment: str, categories: str, update_url: str,
                    run_as_root: bool = False) -> AppImage:
        """Update metadata for an integrated AppImage (rewrites its .desktop file)."""
        if not appimage.desktop_file_path or not appimage.desktop_file_path.exists():
            raise ValueError('AppImage is not integrated')
        icon_value = str(appimage.icon_path) if appimage.icon_path else 'application-x-executable'
        self._write_desktop_file(
            desktop_path=appimage.desktop_file_path,
            name=name,
            exec_path=appimage.file_path,
            icon=icon_value,
            comment=comment,
            categories=categories,
            version=version,
            update_url=update_url,
            run_as_root=run_as_root,
        )
        self._update_desktop_db()
        appimage.name = name
        appimage.version = version
        appimage.comment = comment
        appimage.categories = categories
        appimage.update_url = update_url
        appimage.run_as_root = run_as_root
        return appimage

    # ── Update methods ───────────────────────────────────────────────────────

    def get_update_mode(self, appimage: AppImage) -> str:
        """
        Determine the best update method for this AppImage.
        Returns: 'api' | 'direct' | 'tool' | 'none'
          api    → GitHub, GitLab or Codeberg/Forgejo project URL
          direct → direct link to an .appimage file
          tool   → appimageupdatetool (reads embedded .upd_info)
          none   → no method available
        """
        if appimage.update_url:
            url = appimage.update_url
            if (self._parse_github_url(url)
                    or self._parse_gitlab_url(url)
                    or self._parse_forgejo_url(url)):
                return 'api'
            if url.lower().endswith('.appimage'):
                return 'direct'
        if shutil.which('appimageupdatetool') or shutil.which('AppImageUpdate'):
            return 'tool'
        return 'none'

    # ── API update (GitHub, GitLab, Codeberg/Forgejo) ────────────────────────

    def _parse_github_url(self, url: str) -> Optional[tuple]:
        """Extract (owner, repo) from a GitHub URL, or None."""
        m = re.match(r'https?://github\.com/([^/]+)/([^/?#\s]+)', url)
        if m:
            return m.group(1), m.group(2).rstrip('.git')
        return None

    def _parse_gitlab_url(self, url: str) -> Optional[tuple]:
        """Extract (owner, repo, is_packages) from a GitLab.com URL, or None."""
        m = re.match(r'https?://gitlab\.com/([^/]+)/([^/?#\s]+)', url)
        if m:
            is_packages = '/-/packages' in url
            return m.group(1), m.group(2).rstrip('.git'), is_packages
        return None

    def _parse_forgejo_url(self, url: str) -> Optional[tuple]:
        """
        Extract (host, owner, repo) from a Codeberg or generic Forgejo/Gitea URL.
        Matches codeberg.org and any host with /api/v1 style (Gitea/Forgejo).
        """
        m = re.match(r'https?://(codeberg\.org|[^/]+)/([^/]+)/([^/?#\s]+)', url)
        if m:
            host = m.group(1)
            # Only auto-detect codeberg; other hosts must be explicit Forgejo instances
            # (to avoid false positives with arbitrary URLs)
            if host == 'codeberg.org':
                return host, m.group(2), m.group(3).rstrip('.git')
        return None

    def check_for_update_api(self, appimage: AppImage) -> dict:
        """
        Query GitHub, GitLab or Codeberg/Forgejo releases API for a newer AppImage.
        Returns a dict: has_update (bool|None), message, latest_version,
                        download_url, asset_name, asset_size.
        """
        import urllib.request
        import json
        import platform

        url = appimage.update_url or ''
        gh = self._parse_github_url(url)
        gl = self._parse_gitlab_url(url)
        fj = self._parse_forgejo_url(url)

        headers = {'User-Agent': 'soplos-appimage-manager/1.0'}
        if gh:
            owner, repo = gh
            api_url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'
            headers['Accept'] = 'application/vnd.github+json'
        elif fj:
            host, owner, repo = fj
            api_url = f'https://{host}/api/v1/repos/{owner}/{repo}/releases?limit=1'
        elif gl:
            owner, repo, is_pkg = gl
            encoded_path = f"{owner}%2F{repo}"
            if is_pkg:
                api_url = f'https://gitlab.com/api/v4/projects/{encoded_path}/packages?sort=desc&order_by=created_at&per_page=10'
            else:
                api_url = f'https://gitlab.com/api/v4/projects/{encoded_path}/releases'
        else:
            return {'has_update': None, 'message': 'Not a valid GitHub, GitLab or Codeberg URL'}

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            return {'has_update': None, 'message': str(e)}

        assets = []
        latest_version_str = ''

        if fj:
            # Forgejo/Gitea API returns a list; take first (latest)
            releases = data if isinstance(data, list) else [data]
            if not releases:
                return {'has_update': None, 'message': 'No releases found'}
            latest_release = releases[0]
            latest_version_str = latest_release.get('tag_name', '').lstrip('v')
            for asset in latest_release.get('assets', []):
                if asset.get('name', '').lower().endswith('.appimage'):
                    assets.append({
                        'name': asset['name'],
                        'browser_download_url': asset.get('browser_download_url', ''),
                        'size': asset.get('size', 0),
                    })
        elif gl:
            owner, repo, is_pkg = gl
            encoded_path = f"{owner}%2F{repo}"
            
            if is_pkg:
                if not isinstance(data, list):
                    data = [data]
                for pkg in data:
                    pkg_id = pkg.get('id')
                    try:
                        files_req = urllib.request.Request(f'https://gitlab.com/api/v4/projects/{encoded_path}/packages/{pkg_id}/package_files', headers=headers)
                        with urllib.request.urlopen(files_req, timeout=10) as files_resp:
                            pkg_files = json.loads(files_resp.read())
                    except Exception:
                        continue
                    
                    for f in pkg_files:
                        fname = f.get('file_name', '')
                        if fname.lower().endswith('.appimage'):
                            assets.append({
                                'name': fname,
                                'browser_download_url': f"https://gitlab.com/api/v4/projects/{encoded_path}/packages/generic/{pkg.get('name')}/{pkg.get('version')}/{fname}",
                                'size': f.get('size', 0)
                            })
                    if assets:
                        latest_version_str = pkg.get('version', '')
                        break
                
                if not assets:
                    return {'has_update': None, 'message': 'No AppImage generic packages found on GitLab'}
                    
            else:
                if not isinstance(data, list) or len(data) == 0:
                    return {'has_update': None, 'message': 'No releases found on GitLab'}
                latest_release = data[0]
                latest_version_str = latest_release.get('tag_name', '').lstrip('v')
                if 'assets' in latest_release and 'links' in latest_release['assets']:
                    for link in latest_release['assets']['links']:
                        link_name = link.get('name', '')
                        link_url = link.get('url', '')
                        if '.appimage' in link_name.lower() or '.appimage' in link_url.lower():
                            assets.append({
                                'name': link_name,
                                'browser_download_url': link_url,
                                'size': 0
                            })
        else:
            latest_release = data
            latest_version_str = latest_release.get('tag_name', '').lstrip('v')
            assets = [a for a in latest_release.get('assets', []) if a['name'].lower().endswith('.appimage')]

        if not assets:
            return {'has_update': None, 'message': 'No AppImage assets found in the latest release'}

        # Version fallback parsing
        current_version = (appimage.version or '').lstrip('v')
        if not current_version:
            import re
            match = re.search(r'[-_]v?(\d+\.\d+(?:\.\d+)?)', appimage.file_path.stem)
            if match:
                current_version = match.group(1)

        if not current_version:
            return {
                'has_update': None,
                'message': f'Cannot determine current version to compare against v{latest_version_str}. Please set version in Properties.',
                'latest_version': latest_version_str
            }

        def _parse_ver(v_str):
            import re
            return [int(x) for x in re.sub(r'[^\d]+', '.', v_str).split('.') if x]

        try:
            has_update = _parse_ver(latest_version_str) > _parse_ver(current_version)
        except Exception:
            has_update = (latest_version_str != current_version)
            
        message = f'v{latest_version_str}'
        message += f'  (current: v{current_version})'

        # Prefer asset matching current architecture
        machine = platform.machine().lower()
        arch_aliases = {
            'x86_64': ['x86_64', 'amd64'],
            'aarch64': ['aarch64', 'arm64'],
        }
        preferred = arch_aliases.get(machine, [machine])
        best = next(
            (a for a in assets if any(p in a['name'].lower() for p in preferred)),
            assets[0]
        )

        return {
            'has_update': has_update,
            'message': message,
            'latest_version': latest_version_str,
            'download_url': best['browser_download_url'],
            'asset_name': best['name'],
            'asset_size': best.get('size', 0),
        }

    def check_for_update_direct(self, appimage: AppImage) -> dict:
        """
        Check a direct .appimage URL for updates by comparing the remote
        Last-Modified header against the local file's mtime.
        If the server doesn't provide Last-Modified, always offers the download.
        """
        import urllib.request
        from urllib.parse import urlparse
        from email.utils import parsedate_to_datetime

        url = appimage.update_url or ''
        asset_name = Path(urlparse(url).path).name or appimage.file_path.name
        if not asset_name.lower().endswith('.appimage'):
            asset_name += '.AppImage'

        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'soplos-appimage-manager/1.0'},
                method='HEAD',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                last_modified = resp.headers.get('Last-Modified')
                content_length = int(resp.headers.get('Content-Length', 0))
        except Exception as e:
            return {'has_update': None, 'message': str(e)}

        if last_modified:
            try:
                import datetime
                remote_dt = parsedate_to_datetime(last_modified)
                file_mtime = appimage.file_path.stat().st_mtime
                file_dt = datetime.datetime.fromtimestamp(
                    file_mtime, tz=datetime.timezone.utc)
                has_update = remote_dt > file_dt
                message = (remote_dt.strftime('%Y-%m-%d')
                           if has_update else 'File appears to be up to date')
            except Exception:
                has_update = True
                message = 'Cannot compare dates, offering download'
        else:
            has_update = True
            message = 'Server does not provide version info'

        return {
            'has_update': has_update,
            'message': message,
            'latest_version': '',
            'download_url': url,
            'asset_name': asset_name,
            'asset_size': content_length,
        }

    def download_and_install_new(self, appimage: AppImage, download_url: str,
                                 new_asset_name: str, progress_callback=None) -> Path:
        """
        Download a new AppImage to a new filename, atomically move it over,
        delete the old file and return the new Path. Raises on any error.
        """
        import urllib.request
        from config.constants import APPIMAGES_DIR

        if not new_asset_name.lower().endswith('.appimage'):
            new_asset_name += '.AppImage'

        new_path = APPIMAGES_DIR / new_asset_name
        
        # Avoid overwriting perfectly fine existing files if name matches
        if new_path.exists() and new_path != appimage.file_path:
            stem = new_path.stem
            suffix = new_path.suffix
            i = 1
            while new_path.exists() and new_path != appimage.file_path:
                new_path = APPIMAGES_DIR / f'{stem}_{i}{suffix}'
                i += 1

        tmp_path = new_path.with_suffix('.part')

        try:
            req = urllib.request.Request(
                download_url,
                headers={'User-Agent': 'soplos-appimage-manager/1.0'}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                with open(tmp_path, 'wb') as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)
            tmp_path.chmod(0o755)

            # Delete old file safely
            if appimage.file_path.exists() and appimage.file_path != new_path:
                appimage.file_path.unlink()

            tmp_path.replace(new_path)
            appimage.file_path = new_path
            return new_path
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    # ── appimageupdatetool fallback ───────────────────────────────────────────

    def check_for_update_tool(self, appimage: AppImage) -> tuple:
        """
        Check via appimageupdatetool --check-for-update.
        Returns (has_update: bool|None, message: str).
        """
        tool = shutil.which('appimageupdatetool') or shutil.which('AppImageUpdate')
        if not tool:
            return None, 'appimageupdatetool is not installed'
        try:
            result = subprocess.run(
                [tool, '--check-for-update', str(appimage.file_path)],
                capture_output=True, text=True, timeout=30
            )
            output = (result.stdout + result.stderr).strip()
            if result.returncode == 1:
                return True, output
            elif result.returncode == 0:
                return False, output
            else:
                return None, output or 'No update information found in binary'
        except subprocess.TimeoutExpired:
            return None, 'Timeout while checking for updates'
        except Exception as e:
            return None, str(e)

    def start_update_tool(self, appimage: AppImage) -> subprocess.Popen:
        """Start appimageupdatetool --overwrite. Returns Popen for streaming output."""
        tool = shutil.which('appimageupdatetool') or shutil.which('AppImageUpdate')
        if not tool:
            raise RuntimeError('appimageupdatetool is not installed')
        return subprocess.Popen(
            [tool, '--overwrite', str(appimage.file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def write_update_info_to_binary(self, appimage: AppImage, url: str) -> bool:
        """
        Write a zsync update URL to the .upd_info section of a Type 2 AppImage.
        The section is 512 bytes at offset 33651 per the AppImage Type 2 spec.
        Returns True on success.
        """
        if appimage.appimage_type != '2':
            return False
        try:
            encoded = url.encode('utf-8')
            if len(encoded) > 512:
                return False
            padded = encoded + b'\x00' * (512 - len(encoded))
            with open(appimage.file_path, 'r+b') as f:
                f.seek(33651)
                f.write(padded)
            return True
        except Exception:
            return False

    def get_update_url(self, appimage: AppImage) -> Optional[str]:
        """
        Return the update URL for an AppImage.
        Prefers the manually saved URL in the .desktop file; falls back to
        the embedded .upd_info ELF section in the binary.
        """
        # Prefer saved URL from .desktop
        if appimage.update_url:
            return appimage.update_url

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
        # 1. .DirIcon — handle both real files and symlinks (including relative)
        diricon = root / '.DirIcon'
        if os.path.islink(str(diricon)):
            link_target = os.readlink(str(diricon))
            if os.path.isabs(link_target):
                real = Path(link_target)
            else:
                real = (diricon.parent / link_target).resolve()
            if real.exists() and real.is_file():
                return real
        elif diricon.exists() and diricon.is_file():
            return diricon

        # 2. Root level {name}.svg / {name}.png (exact and case-insensitive)
        for ext in ['.svg', '.png']:
            candidate = root / f'{icon_name}{ext}'
            if candidate.exists():
                return candidate
        # case-insensitive fallback at root
        name_lower = icon_name.lower()
        for f in root.iterdir():
            if f.suffix.lower() in ('.svg', '.png') and f.stem.lower() == name_lower:
                return f

        # 3. hicolor icon dirs (largest to smallest, prefer PNG over SVG)
        hicolor = root / 'usr' / 'share' / 'icons' / 'hicolor'
        for size in ['scalable/apps', '512x512/apps', '256x256/apps',
                     '128x128/apps', '64x64/apps', '48x48/apps']:
            for ext in ['.png', '.svg']:
                candidate = hicolor / size / f'{icon_name}{ext}'
                if candidate.exists():
                    return candidate
                # case-insensitive
                size_dir = hicolor / size
                if size_dir.exists():
                    for f in size_dir.iterdir():
                        if f.suffix.lower() == ext and f.stem.lower() == name_lower:
                            return f

        # 4. usr/share/pixmaps/
        pixmaps = root / 'usr' / 'share' / 'pixmaps'
        if pixmaps.exists():
            for ext in ['.png', '.svg']:
                candidate = pixmaps / f'{icon_name}{ext}'
                if candidate.exists():
                    return candidate
            for f in pixmaps.iterdir():
                if f.suffix.lower() in ('.png', '.svg') and f.stem.lower() == name_lower:
                    return f

        # 5. Any .png then .svg anywhere under root (prefer larger name match)
        for ext in ['*.png', '*.svg']:
            candidates = list(root.rglob(ext))
            if candidates:
                # prefer files whose stem matches icon_name
                for c in candidates:
                    if c.stem.lower() == name_lower:
                        return c
                return candidates[0]

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
                             icon: str, comment: str, categories: str, version: str,
                             update_url: str = '', run_as_root: bool = False):
        """Write a .desktop file for an AppImage."""
        exec_value = f'pkexec {exec_path}' if run_as_root else str(exec_path)
        lines = [
            '[Desktop Entry]',
            'Type=Application',
            f'Name={name}',
            f'Exec={exec_value}',
            f'TryExec={exec_path}',
            f'Icon={icon}',
            f'Categories={categories}',
        ]
        if comment:
            lines.append(f'Comment={comment}')
        if version:
            lines.append(f'X-AppImage-Version={version}')
        if update_url:
            lines.append(f'X-AppImage-UpdateUrl={update_url}')
        if run_as_root:
            lines.append('X-AppImage-RunAsRoot=true')
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
