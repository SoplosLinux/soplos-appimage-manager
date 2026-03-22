# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/en/).

## [1.0.0-1] - 2026-03-22

### 🔧 Fixed
- **UI colors**: Fixed background color inconsistency — window, list and scrolled area now consistently use the correct Soplos dark theme color (#2b2b2b).

---

## [1.0.0] - 2026-03-22

### 🎉 Initial Release

#### Core
- Add AppImages via file chooser — file moved to `~/AppImages/` automatically
- Drag and drop AppImage files directly onto the window
- Automatic metadata extraction: icon, name, version and description from the AppImage itself
- Icons saved persistently to `~/AppImages/.icons/`
- Desktop entry creation in `~/.local/share/applications/`
- Supports AppImage Type 1 (ISO9660) and Type 2 (SquashFS)
- Extraction engine: `7zz` preferred, `--appimage-extract` fallback

#### Integration
- Universal detection: recognises AppImages from any source (Soplos Welcome, manual placement, third-party tools)
- One-click Integrate button for AppImages already present in `~/AppImages/`
- Auto-refresh via dual file monitor — watches `~/AppImages/` and `~/.local/share/applications/` with 500 ms debounce

#### Management
- Run AppImages directly from the manager
- Delete AppImage, icon and `.desktop` entry in one action
- Update URL detection via `readelf` parsing of the `.upd_info` ELF section
- Supports `zsync`, `gh-releases-zsync` and direct HTTP/HTTPS update formats

#### Interface
- About dialog (F1 shortcut + GNOME app menu entry)
- Status bar showing desktop environment and display protocol
- Internationalisation: 8 languages (es, en, fr, de, it, pt, ro, ru)
- Soplos Linux ecosystem UI style

---

## Author

Developed and maintained by Sergi Perich
Website: https://soplos.org
Contact: info@soploslinux.com

## Contributing

- **Issues**: https://github.com/SoplosLinux/soplos-appimage-manager/issues
- **Email**: info@soploslinux.com

## Support

- **Documentation**: https://soplos.org
- **Community**: https://soplos.org/forums/
