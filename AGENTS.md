# Omibang

Omibang is a third-party clone of Omarchy's built-in `omarchy.menu`. It must stay in
parity with the **stable** Omarchy branch while keeping Helium iBang search.

## Stable source

- Repo: `https://github.com/omacom/omarchy.git`
- Branch: `quattro` (Omarchy default / stable; `origin/HEAD`)
- Paths:
  - `shell/plugins/menu/Menu.qml`
  - `shell/plugins/menu/MenuModel.js`
  - `shell/plugins/menu/BarWidget.qml`

Do not track `dev`. Menu JSONC lives in Omarchy (`$OMARCHY_PATH/default/omarchy/omarchy-menu.jsonc`)
and is read at runtime — never copy it into this repo.

## What must match quattro

- `MenuModel.js` — identical to quattro.
- `BarWidget.qml` — identical to quattro (`moduleName: "omarchy.menu"` is required for clone routing).
- Shared `Menu.qml` behavior — same as quattro except the iBang overlay listed below.

## Omibang-only (never drop on a sync)

- `scripts/bangs.py`, `scripts/default_bang.py`, `tests/`
- iBang functions in `Menu.qml`, `!` / `!!` / `!?` rows, Tab to accept a bang
- Search-header hint and right-edge shorthand labels
- `textFormat: Text.PlainText` on every `Text` (including bang extras)
- Registry parse limits in `bangs.py` (label / template / collection size)
- `manifest.json` `clonedFrom: omarchy.menu` and this plugin's id/version/description

Shared `Menu.qml` functions may differ from quattro only in:

- `setFilter` — also `scheduleBangSearch`
- `rebuildDisplay` — prepend bang rows
- `activateIndex` — bang-choice / status short-circuits
- `Keys.onPressed` — Tab → `requestBangInMenu()`

## Sync workflow

1. Fetch `origin/quattro` from omacom/omarchy.
2. Diff the three menu files against this repo.
3. Replay quattro onto `MenuModel.js` and `BarWidget.qml` wholesale.
4. Replay quattro onto `Menu.qml`, then re-apply the iBang overlay and PlainText.
5. `python3 -m unittest discover -s tests -v`
6. `omarchy plugin validate .`
7. Smoke: open the menu, `!yt`, Tab, `!!y`, Esc. Confirm Install rows still dim when installed.
