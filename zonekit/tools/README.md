# Zone Kit tooling

Copied from `stalker2-immersive-dialogue/zonekit/tools/` on 2026-09-27. All
Python runs with the kit's embedded interpreter:
`G:\Epic Games\STALKER2ZoneKit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe`.
Replace `<SCRATCH>` with a writable output folder.

| Script | Where it runs | What it does |
|---|---|---|
| `cook_and_install.ps1 [-Mod X]` | shell | `GSCCookMod` cook (5-6 min), waits for the game to close, then `install_paktest.ps1` |
| `install_paktest.ps1 [-Mod X]` | shell, game closed | copies OverrideContent as `~mods\zzz_<Mod>_PakTest\zzz_<Mod>_30_P.*` (+ NewContent under its kit name) |
| `revert_paktest.ps1` | shell, game closed | removes `zzz_ImmersiveCampfires*_PakTest` |
| `dump_imc.py` | editor (headless or `ue_exec.py`) | mapping-context rows, modifiers, triggers, mappable names to JSON |
| `make_imc_override.py` | headless editor | **template** (ImmersiveDialogue's `IMC_Dialog` generator): duplicate + moved-objects technique; derive `make_imc_playerca_override.py` from it |
| `add_mappable_to_imc.py` | live editor via `ue_exec.py` | **template**: give override rows the game's mappable names in place |
| `duplicate_asset.py`, `move_asset.py`, `set_bp_default.py` | headless editor, editor closed | asset duplicate / rename with referencer fixup / class-default set; edit SRC/DST first |
| `ue_exec.py <file.py \| code>` | shell | runs Python in the open editor (remote execution is on in Project Settings) |
| `dump_names.py` | shell | FName table / strings of an uncooked `.uasset` |
| `zen_names.py <dir> [--imports]` | shell | names or imports of cooked packages (extract first: `UnrealPak <x>.utoc -Extract <dir>`) |
| `extract_from_pak.py` | shell | uncooked assets out of `FullEditor-WindowsModEditor.pak` by index offset (needs `pak_index_subset.txt` from `UnrealPak <pak> -List`) |

Headless editor command:
```
<kit>\Stalker2\Binaries\Win64\Stalker2ModEditor-Win64-Shipping-Cmd.exe "<kit>\Stalker2\Stalker2.uproject" -run=pythonscript -script=<file> -unattended -nosplash -stdout -NoShaderCompile
```
`classifier/ImmersiveCampfires/` holds the cook's package lists; copy them to
`<kit>\Stalker2\SavedMods\PackageClassifier\ImmersiveCampfires\`.
