from setuptools import setup, find_packages

setup(
    name='soplos-appimage-manager',
    version='1.0.0',
    description='AppImage integration manager for Soplos Linux',
    author='Sergi Perich',
    author_email='info@soploslinux.com',
    url='https://soplos.org',
    license='GPL-3.0+',
    packages=find_packages(),
    python_requires='>=3.10',
    data_files=[
        ('share/applications', ['debian/org.soplos.appimagemanager.desktop']),
        ('share/metainfo', ['debian/org.soplos.appimagemanager.metainfo.xml']),
        ('share/man/man1', ['docs/soplos-appimage-manager.1']),
        ('share/icons/hicolor/48x48/apps', ['assets/icons/48x48/org.soplos.appimagemanager.png']),
        ('share/icons/hicolor/64x64/apps', ['assets/icons/64x64/org.soplos.appimagemanager.png']),
        ('share/icons/hicolor/128x128/apps', ['assets/icons/128x128/org.soplos.appimagemanager.png']),
        ('share/soplos-appimage-manager/assets/themes', [
            'assets/themes/base.css',
            'assets/themes/dark.css',
            'assets/themes/light.css',
        ]),
        ('share/locale/de/LC_MESSAGES', ['locale/de/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/en/LC_MESSAGES', ['locale/en/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/es/LC_MESSAGES', ['locale/es/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/fr/LC_MESSAGES', ['locale/fr/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/it/LC_MESSAGES', ['locale/it/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/pt/LC_MESSAGES', ['locale/pt/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/ro/LC_MESSAGES', ['locale/ro/LC_MESSAGES/soplos-appimage-manager.mo']),
        ('share/locale/ru/LC_MESSAGES', ['locale/ru/LC_MESSAGES/soplos-appimage-manager.mo']),
    ],
    entry_points={
        'console_scripts': [
            'soplos-appimage-manager=main:main',
        ],
    },
)
