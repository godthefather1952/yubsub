"""Native, signature-enforced Sparkle 2 updater for YUBSUB Desktop.

Sparkle owns downloading, verification, replacement, rollback/relaunch and its
standard Update Now / Later prompts. This module never downloads or executes
update files itself. Only load it inside an .app with an embedded public key.
"""

import os
from pathlib import Path

_controller = None

def start_updater():
    """Must be invoked on macOS's main thread before webview starts its loop."""
    global _controller
    if os.name != "posix" or not getattr(__import__("sys"), "frozen", False):
        return False
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle()
    key = bundle.objectForInfoDictionaryKey_("SUPublicEDKey")
    if not key:
        return False

    framework = Path(str(bundle.bundlePath())) / "Contents" / "Frameworks" / "Sparkle.framework"
    if not framework.is_dir():
        raise RuntimeError("Secure updater is configured but Sparkle.framework is missing.")

    import objc
    objc.loadBundle("Sparkle", {}, bundle_path=str(framework))
    controller_type = objc.lookUpClass("SPUStandardUpdaterController")
    _controller = controller_type.alloc().initWithUpdaterDelegate_userDriverDelegate_(None, None)
    if _controller is None:
        raise RuntimeError("Unable to initialize Sparkle updater.")
    return True


def updater_available():
    return _controller is not None


def check_for_updates():
    """Queue the native update check on the Cocoa UI thread."""
    if _controller is None:
        return False
    from PyObjCTools.AppHelper import callAfter
    callAfter(_controller.checkForUpdates_, None)
    return True
