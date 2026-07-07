# Soplos AppImage Manager

[![License: GPL-3.0+](https://img.shields.io/badge/License-GPL--3.0%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-1.0.1--1-green.svg)]()

AppImage integration manager for Soplos Linux.

## Description

Soplos AppImage Manager lets you easily integrate AppImage applications into your Soplos Linux desktop. Select any AppImage file, and the manager moves it to `~/AppImages/`, extracts its icon and metadata, and creates a `.desktop` entry so the app appears in your application menu — no manual steps needed.

## Screenshots

<div align="center">
  <img src="assets/screenshots/screenshot1.png" width="24%" alt="Empty state"/>
  <img src="assets/screenshots/screenshot2.png" width="24%" alt="AppImage detected"/>
  <img src="assets/screenshots/screenshot3.png" width="24%" alt="Mixed list"/>
  <img src="assets/screenshots/screenshot4.png" width="24%" alt="Integrated AppImages"/>
</div>
<div align="center">
  <img src="assets/screenshots/screenshot5.png" width="24%" alt="Properties dialog"/>
  <img src="assets/screenshots/screenshot6.png" width="24%" alt="Check for updates"/>
  <img src="assets/screenshots/screenshot7.png" width="24%" alt="Check All Updates"/>
  <img src="assets/screenshots/screenshot8.png" width="24%" alt="Update available"/>
</div>

## Features

- **Add AppImages**: File chooser or drag & drop → moved to `~/AppImages/` automatically
- **Metadata extraction**: icon, name, version and description extracted from the AppImage itself
- **Icon storage**: icons saved persistently to `~/AppImages/.icons/`
- **Desktop integration**: `.desktop` file created in `~/.local/share/applications/`
- **Type detection**: Supports AppImage Type 1 (ISO9660) and Type 2 (SquashFS)
- **Universal detection**: recognises AppImages installed by any source (Soplos Welcome, manual placement, etc.)
- **Integrate**: one-click integration for AppImages already in `~/AppImages/`
- **Auto-refresh**: file monitor watches `~/AppImages/` and `~/.local/share/applications/` — no manual refresh needed
- **Run**: launch any managed AppImage from the manager
- **Delete**: remove the AppImage, icon and desktop entry in one click
- **Properties**: edit name, version, description, categories and update URL for each AppImage
- **Run as root**: mark any AppImage to launch with `pkexec` — PolicyKit authentication dialog appears on launch
- **Automatic updates**: checks GitHub, GitLab and Codeberg release APIs, direct URL comparison, or embedded `appimageupdatetool` info
- **Check All Updates**: inspect all AppImages with a configured update source in one click; update them all from the same dialog
- **Internationalisation**: ships with 8 languages (de, en, es, fr, it, pt, ro, ru)
- **Soplos UI**: consistent dark theme matching the Soplos Linux ecosystem

## Requirements

- Python 3.10+
- GTK+ 3
- python3-gi
- `p7zip-full` (recommended, for faster metadata extraction)

## Installation

Usually shipped natively with Soplos Linux. To run locally:

```bash
git clone https://github.com/SoplosLinux/soplos-appimage-manager.git
cd soplos-appimage-manager
python3 main.py
```

## Structure

```
soplos-appimage-manager/
├── assets/           # Icons, themes and desktop file
├── config/           # Constants
├── core/             # AppImage logic (integration, extraction, management)
├── debian/           # Deb packaging data
├── ui/               # GTK3 interface
└── utils/            # Environment detection
```

## How it works

1. User selects an `.AppImage` file via the file chooser
2. The file is moved to `~/AppImages/`
3. Metadata is extracted using `7zz` or `--appimage-extract`
4. The icon is saved to `~/AppImages/.icons/`
5. A `.desktop` file is written to `~/.local/share/applications/`
6. The app appears in the application menu immediately

## 🆕 New in version 1.0.1-1 (July 7, 2026)

- **Build**: Build dependency `python3-all` replaced with `python3`.

## 🆕 New in version 1.0.1 (March 30, 2026)

- **Properties dialog**: view and edit name, version, description, categories and update URL per AppImage
- **Run as root**: toggle in Properties to launch any AppImage with `pkexec` (PolicyKit authentication)
- **Automatic updates**: GitHub, GitLab and Codeberg release APIs, direct URL (`Last-Modified`), or embedded `appimageupdatetool` info
- **Check All Updates**: header button replaces Refresh — checks all AppImages with a source at once and lets you update them all in one action
- **Improved icon extraction**: relative symlinks, case-insensitive search, pixmaps and additional hicolor sizes
- **Full translation coverage**: all visible UI strings translated across all 8 languages
- **Theme Support**: The application now seamlessly respects the system's light or dark theme preference, removing the forced dark mode

## 🆕 New in version 1.0.0-1 (March 22, 2026)

- **UI colors**: Fixed background color inconsistency — window, list and scrolled area now consistently use the correct Soplos dark theme color (#2b2b2b).

## New in version 1.0.0 (March 22, 2026)

- **Initial Release**: First stable release of the Soplos AppImage Manager.
- **Core Integration**: Add AppImages via file chooser or drag & drop. Automatic metadata and icon extraction.
- **Management**: Desktop entry creation in `~/.local/share/applications/` and icon storage in `~/AppImages/.icons/`.
- **Universal Detection**: Recognizes AppImages from any source and provides a one-click integration button.
- **Update Info**: Parses `.upd_info` ELF sections for AppImage update endpoints (zsync, HTTP).
- **Interface**: Full 8-language internationalization and Soplos ecosystem UI styling.

## License

This project is licensed under the GPL-3.0 License — see the `debian/copyright` file for details.
