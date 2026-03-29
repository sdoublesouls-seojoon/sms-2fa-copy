from setuptools import setup

APP = ['2fa.py']
DATA_FILES = []
OPTIONS = {
    'includes': ['site'],  # site 모듈 강제 포함
    'packages': ['sqlite3', 'pyperclip', 'watchdog'],  # 필요한 패키지
    'argv_emulation': False,
    'plist': {
        'CFBundleShortVersionString': '0.1.0',
        'LSUIElement': True,
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)