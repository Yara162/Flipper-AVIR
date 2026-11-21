# Flipper AVIR

Infrared codes for commercial AV gear (displays, TVs and projectors) as Flipper Zero `.ir`
files, plus a tool that validates them. Made for commissioning: power a display on or off,
change its input or mute it from a Flipper, without hunting for the remote.

Every file names its source and says whether it has been fired at real hardware. **None has
yet.** The codes come from manufacturers' published code sets, and the tests check each one against
its published 32-bit form, but until a file says `Tested: yes`, treat it as a good first guess.

See [CATALOG.md](CATALOG.md) for every file and button.

| Folder | What's in it |
|---|---|
| [`library/`](library/) | One `.ir` file per brand and code set, in Flipper's saved-remote format |
| [`universal/`](universal/) | Every brand's Power, Volume, Mute and Input in one file each, in Flipper's universal-remote format, so one button tries every brand in turn |
| [`tools/avir.py`](tools/avir.py) | Validator, catalog and universal-file builder, and a decoder for published codes |

## Install

With qFlipper, copy the `.ir` files you want to `SD Card/infrared/`. They show up under
**Infrared → Saved Remotes**.

The universal files go to the same folder and open as saved remotes too. Each button sends
every brand's code for it one after another, which helps when you don't know the brand.

## Discrete codes

Most remotes have one Power button that toggles. For control systems and commissioning,
**discrete** codes are better: `Power_on` always turns the display on and `Power_off` always
turns it off, whatever state it's in. The Samsung, LG and Sony files include them.

## Adding codes

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

```bash
python3 tools/avir.py decode nec 20DF10EF
```

turns a published code into Flipper's `protocol` / `address` / `command` lines. Then:

```bash
python3 tools/avir.py validate
```

```bash
python3 tools/avir.py catalog
```

```bash
python3 tools/avir.py universal
```

CI runs all of these and the tests on every push.

## Related

[Flipper AV Tools](https://github.com/Yara162/flipper-av-tools) has a browser page that converts
these `.ir` files to Pronto hex and Global Caché `sendir` strings for control systems.

MIT License. The codes themselves are facts about how devices work, not anyone's creative work.
