# UI fonts

Pick a face in config — bundled folder **or** a system-installed family:

```toml
# client/src/config.toml
[style.font]
family = "FiraCode Nerd Font"  # waybar default; or "Aldrich" / "Oxanium"
vertical_scale = 1.0           # >1 stretches bundled glyphs taller (ignored for system fonts)
```

## Bundled families

Folder name must match the font family Tk resolves:

```
assets/fonts/
  Aldrich/
    Aldrich-Regular.ttf
    OFL.txt
  Oxanium/
    Oxanium-Regular.ttf
    …
    OFL.txt
```

Drop TTFs (+ license) into `assets/fonts/<FamilyName>/`, set `family`, restart.

## System fonts

If `assets/fonts/<Family>/` is missing, the client uses the family from the OS
fontconfig (same as waybar). Example: `FiraCode Nerd Font`.

Linux still generates `client/data/fonts.conf` for bundled faces. Windows/macOS
register bundled TTFs at startup via FontManager / the user font directory.
