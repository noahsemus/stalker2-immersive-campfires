Immersive Campfires v1.0.0 for S.T.A.L.K.E.R. 2: Heart of Chornobyl
Stay seated at the campfire: eat, drink, heal, open the PDA and backpack, play the guitar.
No UE4SS required.

WHAT IS IN THIS ZIP
  Six files, all required:
      zzz_ImmersiveCampfires_20_P.pak / .ucas / .utoc
      ImmersiveCampfiresStalker2-Windows-NewContent.pak / .ucas / .utoc

INSTALL (Vortex)
  Drop the zip into Vortex, install, deploy. Done.

INSTALL (manual)
  Copy the six files into
      <game>\Stalker2\Content\Paks\~mods\
  (create the ~mods folder if it does not exist). Don't rename them.

UNINSTALL
  Delete the six files. Safe to remove at any time; nothing is written to your save.

HOW TO USE
  Sit at any campfire as usual. While seated:
    - use food, drinks, medkits, bandages, injectors and other consumables
      (quick slots, the item wheel or the backpack), with their full animations
    - open the PDA and the backpack
    - play the guitar (G, as in vanilla); put it away and you are seated again
    - look around freely; the body and legs stay put
  To get up, press any movement key, jump, interact or Esc. Skif stands up,
  the view settles level and forward, and your weapon is back in your hands.
  All of this uses your own key bindings from Options > Controls.

SLEEPING BAG MOD
  With the Sleeping Bag Mod installed, using the sleeping bag while seated makes
  Skif stand up, unarmed, and opens its "how many hours" window; confirm to lie down and
  sleep by the fire.

MODDED ITEMS
  Items from other mods (Project Itemization Reborn and others) work seated too.

COMPATIBILITY
  Overrides two game assets: IMC_PlayerCA (the controls while seated) and
  HUDContextualLegend (the small key-hint line at the bottom of the screen; it is
  hidden, so the "Play the guitar" prompt no longer pops up while seated; the
  same line also carried the drop-body and dialogue-skip hints). Any other mod
  that replaces one of these two assets conflicts; the one loaded last wins.
  No config files are changed. Works alongside Immersive Dialogue.

Source and build instructions: https://github.com/noahsemus/stalker2-immersive-campfires
