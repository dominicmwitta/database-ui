"""
Runs once after installation (via .pth hook) to create the desktop shortcut.
The sentinel is only written when the shortcut is successfully created,
so failed attempts are retried on the next Python startup.
"""
from pathlib import Path

_sentinel = Path(__file__).parent / ".shortcut_created"

if not _sentinel.exists():
    try:
        from macro_database.run import create_shortcut
        created = create_shortcut()
        if created:  # True = just created, False = already existed
            _sentinel.touch()
        elif created is False:
            _sentinel.touch()  # shortcut already on desktop, no need to retry
    except Exception as e:
        print(f"Warning: Could not create desktop shortcut: {e}")
