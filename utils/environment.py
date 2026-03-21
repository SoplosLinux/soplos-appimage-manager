"""
Environment detection module for Soplos WebApp Manager.
Following the official Soplos standards.
"""

import os
import subprocess
from enum import Enum
from typing import Dict

class DesktopEnvironment(Enum):
    """Supported desktop environments."""
    GNOME = "gnome"
    KDE = "kde"
    XFCE = "xfce"
    UNKNOWN = "unknown"

class DisplayProtocol(Enum):
    """Display server protocols."""
    X11 = "x11"
    WAYLAND = "wayland"
    UNKNOWN = "unknown"

class EnvironmentDetector:
    """
    Detects and analyzes the current desktop environment and display protocol.
    """
    
    def __init__(self):
        self._desktop_env = None
        self._display_protocol = None
        
    def detect_all(self) -> Dict[str, str]:
        """Performs complete environment detection."""
        self._detect_desktop_environment()
        self._detect_display_protocol()
        
        return {
            'desktop_environment': self._desktop_env.value,
            'display_protocol': self._display_protocol.value
        }
    
    def _detect_desktop_environment(self) -> DesktopEnvironment:
        """Detects the current desktop environment."""
        current_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        
        if 'gnome' in current_desktop:
            self._desktop_env = DesktopEnvironment.GNOME
        elif 'kde' in current_desktop or 'plasma' in current_desktop:
            self._desktop_env = DesktopEnvironment.KDE
        elif 'xfce' in current_desktop:
            self._desktop_env = DesktopEnvironment.XFCE
        else:
            self._desktop_env = self._fallback_desktop_detection()
        
        return self._desktop_env
    
    def _fallback_desktop_detection(self) -> DesktopEnvironment:
        """Fallback method for desktop environment detection."""
        if os.environ.get('GNOME_DESKTOP_SESSION_ID'):
            return DesktopEnvironment.GNOME
        elif os.environ.get('KDE_SESSION_VERSION'):
            return DesktopEnvironment.KDE
        return DesktopEnvironment.UNKNOWN
    
    def _detect_display_protocol(self) -> DisplayProtocol:
        """Detects the display server protocol (X11 or Wayland)."""
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        
        if session_type == 'wayland':
            self._display_protocol = DisplayProtocol.WAYLAND
        elif session_type == 'x11' or os.environ.get('DISPLAY'):
            self._display_protocol = DisplayProtocol.X11
        else:
            self._display_protocol = DisplayProtocol.UNKNOWN
            
        return self._display_protocol

    @property
    def desktop_environment(self) -> DesktopEnvironment:
        if self._desktop_env is None:
            self._detect_desktop_environment()
        return self._desktop_env

    @property
    def display_protocol(self) -> DisplayProtocol:
        if self._display_protocol is None:
            self._detect_display_protocol()
        return self._display_protocol

_environment_detector = None

def get_environment_detector() -> EnvironmentDetector:
    global _environment_detector
    if _environment_detector is None:
        _environment_detector = EnvironmentDetector()
    return _environment_detector
