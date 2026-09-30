# Mod-specific tooling

Generic tools (cook / install / revert, `ue_exec.py`, editor helpers, T3D libraries, pak readers) live in
`harness/tools/` since the harness adoption on 2026-09-30; see `harness/README.md`. Python = the kit's embedded
interpreter. The generators import `bp_t3d` / `bp_graph` / `t3d_lift` from `harness/tools/t3d/`.

| Script | Runs | Does |
|---|---|---|
| `gen_actor_seated_mode.py <out.txt>` | shell | the whole `BP_ImmCampActor` event graph as paste text (current) |
| `gen_subsystem_spawn.py` | shell | `BP_ImmCampSubsystem` spawn graph |
| `make_sit_yaw.py` | open editor (`harness/tools/ue_exec.py`) | builds `AS_ImmCamp_SitRest` and `AS_ImmCamp_SitAdditive` (yaw / pitch tables) |
| `make_imc_playerca_override.py` | headless editor | the `IMC_PlayerCA` override (vanilla + exploration rows + canary) |
| `make_imc_override.py`, `add_mappable_to_imc.py` | templates | ImmersiveDialogue's IMC generators the override was derived from |
| `gen_actor_seat_test.py`, `gen_actor_seated_input.py`, `gen_abp_seated_legs.py`, `make_sit_additive.py` | history | earlier builds (seat test, input-only actor, post-process ABP, additive v2); kept for the log |
| `classifier/ImmersiveCampfires/` | cook | package lists (`harness/tools/cook_and_install.ps1` seeds / checks them) |
| `probe/ImmCampProbeCpp/` | dev box | UE4SS C++ probe (body / hands / move / per-frame burst logging) |
