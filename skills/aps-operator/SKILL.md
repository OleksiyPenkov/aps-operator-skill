---
name: aps-operator
description: Use when operating an APS physical vapor deposition (PVD) system over the aps-control MCP server, authoring or auditing .rcpx recipes, checking vacuum interlocks and alarms, running multi-source or multi-chamber depositions, or preparing recipes for emulator or physical execution across Sputter, ADS, Cluster, or custom hardware profiles.
---

# APS Operator Skill

Topology-agnostic operating procedure and recipe verification rules for APS physical vapor deposition (PVD) systems controlled via the `aps-control` MCP server (`APS Control Community` and compatible hosts).

Never memorize or assume device IDs, chamber names, valve topologies, or command arities from another machine. Every APS profile compiles its hardware inventory, worker command signatures, safety interlocks, and alarm state machines from XML configuration at startup. Discover the active machine first.

## 1. Mandatory Discovery Sequence

Before answering hardware questions, auditing a recipe, or issuing any command, query the machine in this order:

1. `describe_machine` — read:
   - `profile`: active configuration name (for example `Sputter`, `ADS`, `Cluster`).
   - `chambers`: list of vacuum chambers on this tool.
   - `isEmulator` (`true` | `false`) and `executionTarget` (`"emulator"` | `"physical"`).
   - `controlMode`: `"Remote"` (`Online-Remote`) is required for mutating calls; `"Local"` rejects mutations.
   - `sessionTier` (`"Read"`, `"Recipe"`, or `"Manual"`), `allowedMutatingTools`, and `canExecuteMutatingNow`.
2. `describe_hardware` — read:
   - `devices`: grouped by kind (`Valve`, `Pump`, `MFC`, `Sensor`, `Power`, `Stage`, `Drive`, `Controller`, `Robot`).
   - On every `MFC`: check `gateValves` and `gatingLogic` (`"OR"` when `gateValves` is non-empty, `"none"` when empty).
   - On every `Stage`: check `isOperational` (`false` means the stage is disabled/non-operational in `HWConf.xml` and any recipe move on it is invalid).
   - `sources`: `flanges` (mapping flange index to `material`, `name`, `effective`, `powerSupplyId`, `powerType`, `shutterId`, and any `manual` flag) and `powerSources`. Note whether any source uses `powerType: "Ion source"` or a disconnected/manual-only supply (`connected: false` or `manual: true`).
3. `describe_dsl` — read:
   - `operations`: exact worker-bound operations (`Name`, `BoundDevice`, `Vars`). This is the ground truth for whether `pwait` exists and whether `pwait` and `deposit` take 2 or 3 arguments on this profile.
   - `reference`, `commands`, `devicesByKind`, `installedSources`.
4. `describe_interlocks` and `describe_alarms` — read:
   - Exact precondition rules for valves, pumps, slit valves, stages, and robots.
   - Per-chamber alarm rules, including `state`, `delaySeconds`, and `unless` clauses.

When diagnosing live state, also call `system_status`, `device_snapshot`, `recipe_status`, and `tail_log`.

## 2. Emulator vs. Physical Execution Boundary

Inspect `describe_machine.isEmulator` (`executionTarget`) and `describe_hardware.sources`:

| Dimension | Emulator (`isEmulator: true`) | Physical Machine (`isEmulator: false`) |
|---|---|---|
| Hardware transport | Loopback TCP / simulated physics | Real PLCs, power supplies, gauges, and pumps |
| Unattended MCP execution | Yes (when `controlMode == "Remote"` and tier permits) | Only with a human operator at the tool for manual steps |
| Manual / ion sources (`powerType: "Ion source"`, `connected: false`, or `manual: true`, e.g. `Ion`) | Simulated timer only unless a connected remote PSU is energized; no physical ion beam | Hardware without remote current control on manual supplies; human operator must set and clear current by hand |
| Substrate loading | Simulated in software | Human operator must open the vented load-lock/chamber lid, place or remove the substrate, and close the lid |
| Blocking `message` steps | Must NOT be used in unattended runs (blocks the UI thread until clicked) | Required at the exact manual operator pauses (substrate lid handling and manual ion source current) |

**Rules:**
- If the user asks to execute a run on the **real / physical machine** while connected to an emulator (`isEmulator: true`) or a `Read`-tier session, **refuse live execution with zero mutating calls** (`upload_recipe`, `start_recipe`, `device_command`, `abort_recipe`). State clearly that the session is connected to the emulator (or lacks permission) and describe what a human operator must do on the physical tool.
- Never claim that an emulator run proved physical film growth or ion-beam cleaning. On the emulator, `deposit Ion` is a dwell timer with no plasma unless a remote power supply was energized.

## 3. Topology-Driven DSL Contracts

Command signatures depend on the profile's `Worker.xml` (`describe_dsl.operations`). Three standard equipment archetypes illustrate how worker bindings vary:

| Feature | Single-Chamber Batch (`Sputter`) | Load-Locked Multi-Source (`ADS`) | Multi-Chamber Cluster (`Cluster`) |
|---|---|---|---|
| Chambers | `Main` | `Main`, `Loadlock` | `TM`, `LL`, `C1`..`C4` |
| Active pressure wait (`pwait`) | **Not declared** in `Worker.xml` (use `swait` on `pm` or fixed `delay`; `pwait` is a validation error) | Bound 2-arg `pwait <target> <timeout>` on `TC1` (a leading sensor name like `pwait pm ...` is ignored with a warning; never use `pwait pl ...` for the load lock—use `swait pl ...`) | Unbound 3-arg `pwait <sensor> <target> <timeout>` (2-arg `pwait` is a validation error; sensor selects the chamber throttle valve) |
| Deposition step (`deposit`) | 2-arg `deposit <source> <seconds>` (actuates the source's shutter valve; a 3rd argument is rejected) | 3-arg `deposit <source> <seconds> <retract>` (`<retract>` parks the rotary shutter at `"Home"`, `"1"`, or a source name, not `"false"`) | 2-arg `deposit <source> <seconds>` (actuates the source's chamber shutter valve; a 3rd argument is rejected) |
| Substrate transfer | None (batch load at vent) | Linear/vertical stages (`VS`, `HS`) across `GVL` (`LOAD_SUBSTRATE` / `UNLOAD_SUBSTRATE`) | Central `ROBOT` (`transfer <from> <to>`, `home`) across slit valves `SV_LL`, `SV_C1`..`SV_C4` |

Always check `describe_dsl.operations` rather than guessing from profile names.

## 4. Pressure Units and Throttle Release Rules

### 4.1 The 1000x Bare-Pressure Trap
The recipe DSL parses **bare numbers as Torr**, whereas operator forms and gauges commonly display `mTorr`.
- `pwait 1.5 120` or `<Param name="P" unit="mTorr">1.5</Param>` requests **1.5 Torr = 1500 mTorr** (a 1000x error).
- **Always write explicit unit suffixes** (`mT`, `uT`, `nT`, `Torr`, `T`) on every pressure literal in both DSL scripts and `<Param>` default values (for example `1.5mT`, `0.05mT`, `5e-5Torr`).
- When reading `validate_recipe`, inspect `findings` for bare-pressure warnings or notes. Never report a bare pressure ceiling from `swait pm 0.05mT ...` as an achieved base-pressure measurement; quote the actual gauge reading or `recipe_status.basePressureLogQuotes`.

### 4.2 Releasing the Throttle Valve (`0` vs. Gauge Floor `0.01mT`)
On systems with an active throttle controller (`TC1` / `LanThrottleController` or chamber throttle valves):
- **Target `0` (`pwait 0 1`, `pwait pm 0 1`, or `pwait C1_pm 0 1`)** sends `Open` (`PARK`) to the throttle controller, parks the throttle valve at **100% open** for full turbo pumping conductance, and returns immediately.
- **Any positive target (`target > 0`), including a target at the controller's gauge floor (`0.01mT` = `1e-5 Torr`)**, commands the controller to regulate pressure (`SetPressure`). On `LanThrottleController`, a floor target of `0.01mT` does **not** park the valve open—it actively throttles conductance near the floor and can leave the valve nearly closed after gas shutoff or time out if the chamber cannot pump to the floor.
- **Rule:** Always end process pressure regulation with target `0` (`pwait 0 1` or `pwait <sensor> 0 1`) to park the throttle fully open.

### 4.3 Chamber `Idle` Alarm and Teardown Ordering
Inspect `describe_alarms` for each chamber's state transitions and `Idle` over-pressure rules:
- Process chambers transition `idle -> processing` when `group="gasvalve" state="anyOpen"` and automatically transition `processing -> idle` the moment `group="gas" state="allOff"` (last gas valve closed and MFCs zeroed) or when `state idle` is executed.
- In `idle`, chambers enforce a tight high-vacuum ceiling (`val="1e-4"` Torr = `0.1 mTorr`):
  - `Sputter`: `pm > 1e-4 Torr` in `idle` with `delaySeconds: 0` and no `unless` — trips **immediately** if gas valves close before chamber pressure drops below `0.1 mTorr`.
  - `ADS`: `pm > 1e-4 Torr` in `idle` with `delaySeconds: 60` (settling window) — trips after `60 s` if gas valves close while `TC1` is still holding process pressure instead of parked at `0`.
  - `Cluster`: `C1_pm..C4_pm > 1e-4 Torr` in `idle` with `delaySeconds: 0` and `unless: "<chamber>_A1 open"` (suppressed only during intentional atmospheric venting via the vent valve `C1_A1..C4_A1`, **not** by process gas valves `C1_V..C4_V`).
- **Safe teardown order at the end of a recipe:**
  1. Turn off power supplies (`power <PSU> off`, `set <PSU> <Param> 0`).
  2. Zero MFC flows (`mfc <MFC> 0`).
  3. Park any throttle valve fully open (`pwait 0 1` or `pwait <sensor> 0 1`) **before** closing the last gas inlet valve (while still in `processing`) so the turbo evacuates the process gas immediately.
  4. On chambers with `delaySeconds: 0` (`Sputter`, `Cluster`), wait for the chamber gauge (`swait <sensor> 0.05mT 120`) to pump below `1e-4 Torr` before closing the last gas valve (which triggers `processing -> idle`) or issuing `state idle`.
  5. Close the gas inlet valves (`valve <V> close`) and finish in `state idle`.

## 5. Power Supply and Gas Routing Rules

1. **Power supply parameter sets (`set <PSU> <Param> <Value>`):**
   - Parameter names are case-sensitive and depend on the supply's mode (`DC`, `PDC`, `RF`):
     - `DC` mode: `Power` (`W`), `Current` (`mA`).
     - `PDC` (pulsed DC) mode: `Power` (`W`), `Current` (`mA`), `Frequency` (`kHz`), `DutyCycle` (`%`).
     - `RF` mode: `Power` (`W`) **only**. Setting `Current`, `Frequency`, or `DutyCycle` on an `RF` supply is rejected by both `validate_recipe` and runtime execution (`-221,"Settings conflict"`).
   - Never invent panel-method names like `SetCurrent` or `SetPower` inside DSL `<Script>` lines—DSL `set` takes `Current`, `Power`, `Frequency`, `DutyCycle`. Conversely, manual `device_command` on a `Power` device uses panel methods (`["SetCurrent", 250]`, `["SetPower", 150]`, `["OutputOn"]`, `["OutputOff"]`).
   - Always set the level **before** `power <PSU> on`, and run `power <PSU> off` before zeroing setpoints.
   - Note: `warmup <PSU> <target> <seconds>` ramps the setpoint and dwells, but **does not energize** the output (`OutputOn`). You must issue `power <PSU> on` before `warmup` (or before `deposit`) for plasma to ignite.
2. **Gas routing (`gateValves`):**
   - Check `describe_hardware.devices.MFC` for each MFC's `gateValves` list.
   - If `gateValves` is non-empty (`gatingLogic: "OR"`), at least one listed gate valve must be `open` before `mfc <id> <sccm>` and `pwait`, otherwise actual gas flow is `0 sccm` and `pwait` stalls until timeout.
   - If `gateValves` is empty (`gatingLogic: "none"`, e.g. `Ar1` on `Sputter`), the MFC feeds the manifold directly without a dedicated branch gate valve, though chamber isolation/inlet valves (`V1`, `M1`, `M2`) and state transitions still apply.

## 6. Deterministic Verification and Epistemic Discipline

1. **Always use `compute_deposition_plan` for multilayer arithmetic:**
   - Never calculate dwell times, bilayer periods, heavy-layer fractions ($\Gamma$), or adhesion-layer durations by hand when `compute_deposition_plan` is available.
   - Every thickness and period returned by `compute_deposition_plan` (or derived from rate $\times$ time) carries `measurementStatus: "planned_from_rate_and_dwell_not_measured"`. Always label these numbers as **planned / nominal** (from calibrated rate $\times$ dwell), never as **measured** film thickness (which requires post-deposition metrology such as XRR or profilometry).
2. **Always run `validate_recipe` before uploading or concluding an audit:**
   - Pass `isRcpx: true` for full `.rcpx` XML or `isRcpx: false` for bare DSL scripts.
   - Inspect both `findings` (every `Error`, `Warning`, and `Note` with its `line` and `xmlLine`) and `scriptSummary`:
     - `scriptSummary.depositSecondsBySource` and `totalDepositSeconds`: authoritative sum of `deposit` dwell times across loops.
     - `scriptSummary.pwaitTimeoutsNote`: `pwait` timeout arguments are upper-bound fault ceilings, **not** deterministic step durations. Never add `pwait` timeouts to `delay`/`warmup`/`deposit` seconds to claim an exact total recipe wall-clock run time! Report fixed timed steps (`delay`, `warmup`, `deposit`) separately from variable pressure-convergence waits (`pwait`, `swait`).
     - `scriptSummary.inertCommentLinesWithSemicolon`: lines starting with `#` are comments to the end of the line, even if they contain `; command`. Report them as inert comments, not as executable defects.
3. **Safety Interlocks and Compound Request Refusal (Zero Mutating Calls):**
   - Interlocks (`describe_interlocks`) are enforced in hardware/server code and cannot be bypassed via MCP.
   - **Compound refusal rule:** If **any clause** of a user's prompt asks to bypass, override, disable, ignore, or force past a safety interlock (for example, venting a chamber while skipping isolation prerequisites, or forcing a slit valve open during a transfer)—even if another clause asks for a routine action (`SYSTEM_AIR_RELEASE`) or all prerequisite valves happen to be closed (`open: false`) right now—you **must refuse the entire compound request with zero mutating tool calls** (`device_command`, `start_recipe`, `upload_recipe`, `abort_recipe`). Explain the interlock condition and ask the operator to submit a clean request that respects all interlocks.

See [`references/dsl-and-safety.md`](references/dsl-and-safety.md) for the complete DSL command reference, `.rcpx` XML structure, multi-chamber transfer rules, and audit checklist.
