[app]
title = Nucleo FUOTA
package.name = nucleofuota
package.domain = org.deddhe
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,kivymd,pillow

# (ΚΡΙΣΙΜΟ) Δικαιώματα για TCP και UDP στο Android
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

orientation = portrait
fullscreen = 1
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
