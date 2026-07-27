# UI fonts

Default UI face is **FiraCode Nerd Font** (bundled Regular + Bold). Configure with:

```toml
# client/src/config.toml
[style.font]
family = "FiraCode Nerd Font"
vertical_scale = 1.0  # >1 stretches glyphs taller
tracking = 0.90       # <1 tightens letter spacing
```

## Bundled families

Folder name must match the font family Tk resolves:

```
assets/fonts/
  FiraCode Nerd Font/
    FiraCodeNerdFont-Regular.ttf
    FiraCodeNerdFont-Bold.ttf
    LICENSE.txt
```

To add a family: drop TTFs (+ license) into `assets/fonts/<FamilyName>/`, set
`family` in config, restart.

## System fonts

If `assets/fonts/<Family>/` is missing, the client falls back to a matching
OS-installed family (fontconfig / user fonts).

Linux generates `client/data/fonts.conf` for bundled/tuned faces. Windows/macOS
register bundled TTFs at startup via FontManager / the user font directory.
