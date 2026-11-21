# Contributing codes

## A file

One file per brand and code set, in `library/<category>/<brand>[-<range>].ir`. Categories so far:
`displays`, `projectors`. Start with these headers:

```
Filetype: IR signals file
Version: 1
# Brand: LG
# Models: Which models or ranges use this code set
# Source: Where the codes came from (a manual, a published code table, a capture of model X's remote)
# Tested: no
# Notes: Optional. Quirks, such as "send Power twice to turn off".
```

When you have fired the codes at a real device, change `Tested` to `yes, <model>, <YYYY-MM-DD>`
and say which buttons worked in Notes.

## Button names

Use these names so files work with Flipper's universal remotes and with each other:

| Group | Names |
|---|---|
| Flipper standard | `Power` `Vol_up` `Vol_dn` `Mute` `Ch_next` `Ch_prev` |
| Discrete power | `Power_on` `Power_off` |
| Inputs | `Input` (cycles or opens the menu) `Input_next` `HDMI_1`–`HDMI_4` `DP` `VGA` `DVI` `USB_C` `HDBaseT` |
| Projector | `Freeze` `Blank` `Blank_on` `Blank_off` `Aspect` `Lamp` `Eco` |
| Menus | `Menu` `Exit` `Enter` `Up` `Down` `Left` `Right` `Info` |

Need another? Add it to `NAMES` in `tools/avir.py` in the same pull request.

## From a published code

Manuals and code tables usually print NEC-family codes as eight hex digits, such as `20DF10EF`.
Decode them rather than typing bytes by hand:

```bash
python3 tools/avir.py decode nec 20DF10EF
```

Use `necext` when the second byte isn't the inverse of the first (Epson, many projectors), and
`samsung32` for Samsung's `E0E0....` codes. Add the published code to `tests/test_avir.py` too,
so a later typo gets caught.

## From a capture

Learn the button on a Flipper (**Infrared → Learn New Remote**). If Flipper decodes it, copy
the parsed lines. If it saves `type: raw`, raw is fine, but say so in Notes.

## Before you push

```bash
python3 tools/avir.py validate
```

```bash
python3 tools/avir.py catalog
```

```bash
python3 tools/avir.py universal
```

```bash
python3 -m unittest discover tests
```
