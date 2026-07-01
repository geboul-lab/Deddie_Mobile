[app]
title = Nucleo Mobile FUOTA
package.name = nucleofuota
package.domain = org.deddhe
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# (ΚΡΙΣΙΜΟ) Ορίζουμε ρητά την python3 για να μην τραβήξει παλιά έκδοση
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE
orientation = portrait
fullscreen = 1
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 0

