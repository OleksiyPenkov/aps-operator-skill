# APS Recipe DSL, Hardware Protocols, and Safety Reference

This reference accompanies [`SKILL.md`](../SKILL.md) and documents the `.rcpx` XML envelope, recipe DSL grammar, open hardware driver behaviors (`LanPowerSupply`, `LanThrottleController`, `LanRotaryDrive`, `LanTransferRobot`), and multi-chamber vacuum sequencing.

## 1. `.rcpx` XML Envelope and Parameter Substitution

User recipes are XML files (`.rcpx`) containing a `<Recipe>` root, a `<Description>` element, optional `<Parameters>` grouped under `<Group>`, and a plain newline-separated `<Script>` body (`<l>...</l>` line tags are used in `EmbedRecipes.xml` and `Interlocks*.xml`, never in `.rcpx`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<Recipe>
  <Description title="Mo single-layer example" type="Sputtering" author="LAB" notes="Example recipe"/>
  <Parameters>
    <Group name="Deposition Conditions">
      <Param name="Pbase" caption="Base vacuum" unit="mTorr" paramType="0">0.05mT</Param>
      <Param name="ArFlow" caption="Argon flow" unit="sccm" paramType="1">30</Param>
      <Param name="N" caption="Cycles" unit="N" paramType="1">5</Param>
    </Group>
  </Parameters>
  <Script>
swait pm Pbase 120
valve V1 open
valve M1 open
mfc Ar1 ArFlow
delay 10
loop N
  deposit Mo 25
endloop
  </Script>
</Recipe>
```

### Parameter and Line-Mapping Rules
- Parameters are referenced inside `<Script>` as **bare identifier tokens** (`mfc Ar1 ArFlow`, `loop N`), **not** `$ParamName`.
- `<Param ...>` stores its default value as element text (`<Param name="ArFlow" caption="Argon flow" unit="sccm" paramType="1">30</Param>`, where `paramType="0"` is string/suffixed literal and `paramType="1"` is numeric). Every parameter token used in `<Script>` must have a matching `<Param name="..." ...>` with non-empty text, or `validate_recipe` reports an unresolved variable (`scriptSummary.hasUnresolvedVariables: true`).
- Pressure parameters must include an explicit unit suffix in their text (`>0.05mT<` or `>2.50mT<` with `paramType="0"`, **never** bare `>2.5<`), because `unit="mTorr"` on `<Param>` is a UI display label only and does not scale bare numbers during DSL parsing.
- `validate_recipe` reports both `line` (1-based index inside `<Script>`) and `xmlLine` (1-based line number in the `.rcpx` XML document).

## 2. Core Recipe DSL Commands

Always verify profile-specific worker operations via `describe_dsl.operations`.

| Command | Syntax | Behavior & Constraints |
|---|---|---|
| `state` | `state startup \| idle \| processing` | Sets the chamber alarm state machine. Only `startup`, `idle`, and `processing` are valid DSL state keywords (never `vent`, `ready`, or `shutdown`). |
| `valve` | `valve <id> open \| close` | Opens or closes a valve defined in `describe_hardware.devices.Valve`. Subject to server-side interlocks. |
| `pump` | `pump <id> on \| off` | Starts or stops a backing or turbo pump defined in `describe_hardware.devices.Pump`. |
| `mfc` | `mfc <id> <sccm>` | Sets mass flow controller `<id>` setpoint in sccm. Requires at least one valve in `gateValves` to be `open` when `gatingLogic == "OR"`. |
| `set` | `set <psu> <param> <value>` | Sets a power-supply parameter (`Power`, `Current`, `Frequency`, `DutyCycle`). Parameter names are case-sensitive and mode-dependent. |
| `power` | `power <psu> on \| off` | Energizes or de-energizes power supply `<psu>`. Does not set the level; always `set` before `power <psu> on`. |
| `warmup` | `warmup <time> [<label>...]` | Interpreter timed stabilization dwell for `<time>` seconds (prefer `delay <time>`). **Does NOT set PSU Power/Current and does NOT turn output on**—always call `set <psu> <Param> <val>` and `power <psu> on` before dwelling/depositing. |
| `ramp` | `ramp <psu> <target>` | Immediately updates `<psu>` primary setpoint to `<target>` (no built-in dwell). |
| `swait` | `swait <sensor> <target> <timeout>` | Passive pressure wait: blocks until gauge `<sensor>` reads $\le$ `<target>` within `<timeout>` seconds. Does **not** move any throttle valve. |
| `pwait` | Profile-dependent (see §3) | Active pressure wait using a throttle controller or chamber throttle valve. |
| `holder` | `holder <source \| Home \| flange>` | Moves the rotary substrate holder (`LanRotaryDrive`) to face `<source>` or `"Home"`. |
| `shutter` | `shutter <source \| Home \| flange>` | Moves the rotary shutter (`LanRotaryDrive`) to expose `<source>` or park at `"Home"`. |
| `deposit` | Profile-dependent (see §3) | Timed deposition step for an installed source (`describe_dsl.installedSources`). |
| `stage` / `<stageId>` | `stage <id> <pos>` or `<id> <pos>` | Moves a linear, vertical, or rotary stage (`VS`, `HS`, `rotation`). Rejected if `isOperational == false`. |
| `transfer` | `transfer <from> <to>` | Multi-chamber robot transfer between faces (`LL`, `C1`..`C4`) via `TM`. Requires both slit valves (`SV_<from>`, `SV_<to>`) to be open at the relevant transfer phases and pressures equalized. |
| `home` | `home` | Homes the transfer robot (`ROBOT`). |
| `delay` / `wait` | `delay <time>` / `wait <time>` | Fixed dwell in seconds (or with `s`, `m`, `h` suffix, e.g. `30s`, `2m`). |
| `loop` / `endloop` | `loop <count>` ... `endloop` | Repeats the enclosed block `<count>` times (`<count>` may be an integer or a `<Param>` name). |
| `call` | `call <RECIPE_NAME>` | Invokes an embedded recipe (listed in `describe_recipes.embedded`). |
| `message` | `message <text>` | Pops a modal operator confirmation dialog on the Control UI. **Never use in unattended MCP runs**; use only for physical-machine manual pauses. |

### Comments and Semicolons
- `#` starts a comment that extends to the **end of the line**.
- `;` separates multiple statements on a single non-comment line (`valve V2 open; mfc Ar1 30`).
- **Decoy trap:** Inside a `#` comment line (e.g. `# legacy step; power PSU1 on`), a semicolon does **not** start a new executable command. The entire line is inert (`scriptSummary.inertCommentLinesWithSemicolon`).
- **Device ID trap:** Because `#` starts a comment, never write a raw token containing `#` in a DSL script.

## 3. Profile-Specific Worker Signatures (`pwait` and `deposit`)

Always inspect `describe_dsl.operations` to confirm how the active worker binds `pwait` and `deposit`:

1. **Single-Chamber Batch (`Sputter`):**
   - `pwait`: **Not present** in `describe_dsl.operations`. Calling `pwait` is a syntax/validation error. Use `swait pm <target> <timeout>` for pump-down verification and `delay <seconds>` for gas-flow stabilization.
   - `deposit`: 2 arguments `(source, time)` — opens the source's pneumatic shutter valve (`shutterId`: `Sh1` or `Sh2`), waits `<time>` seconds, and closes the shutter valve. Passing a 3rd argument (`deposit Mo 25 Home`) is a validation error.
2. **Load-Locked Multi-Source (`ADS`):**
   - `pwait`: Bound to `TC1` (`BoundDevice: "TC1"`), 2 arguments `(target, timeout)`.
     - Canonical call: `pwait 2.5mT 180` or `pwait 0 1` (park open).
     - Passing a leading sensor name (`pwait pm 2.5mT 180`) is accepted for legacy compatibility with a validator warning, but the sensor token is **ignored**—`TC1` always regulates `Main` chamber pressure (`pm`). Never write `pwait pl ...` expecting to wait on the load lock; use `swait pl ...`.
   - `deposit`: Bound to `Holder` (`BoundDevice: "Holder"`), 3 arguments `(source, time, retractPos)`.
     - Positions `Holder` at `<source>`, opens `Shutter` to `<source>` for `<time>` seconds, then parks `Shutter` at `<retractPos>` (`"Home"`, `"1"`, or a valid source/flange token). `Holder` remains over `<source>`, so issue `holder Home` during teardown so all drives return to `Home` (`0`). Passing `"false"` as `<retractPos>` is an error (`-222,"Invalid position"`).
3. **Multi-Chamber Cluster (`Cluster`):**
   - `pwait`: Unbound (`BoundDevice: ""`), 3 arguments `(sensor, target, timeout)`.
     - Canonical call: `pwait C1_pm 3mT 300` or `pwait C1_pm 0 1` (park chamber `C1` throttle open).
     - Calling 2-arg `pwait 3mT 300` is a validation error because the multi-chamber worker needs `<sensor>` (`C1_pm`, `C2_pm`, `C3_pm`, `C4_pm`) to select the target chamber's throttle valve.
   - `deposit`: Unbound (`BoundDevice: ""`), 2 arguments `(source, time)`.
     - Resolves the chamber and shutter valve (`shutterId`: `C1_Sh`, `C1_Sh_B`, `C2_Sh`, `C3_Sh`, `C3_Sh_B`, `C4_Sh`) from `Sources.xml` (`flanges`), opens the shutter for `<time>` seconds, and closes it. Passing a 3rd argument (`deposit W 60 Home`) is a validation error.

## 4. Open Hardware Drivers and Failure Modes

### 4.1 `LanPowerSupply` (`DC`, `PDC`, `RF`)
- Current unit is **milliamperes (`mA`)** in both DSL `set <psu> Current <mA>` and readbacks.
- Mode restrictions (enforced by `validate_recipe` and `ApplySetpoint`):
  - `DC`: `Power` (`W`), `Current` (`mA`).
  - `PDC`: `Power` (`W`), `Current` (`mA`), `Frequency` (`1..350 kHz`), `DutyCycle` (`5..95 %`).
  - `RF`: `Power` (`W`) only. Setting `Current`, `Frequency`, or `DutyCycle` on an `RF` supply raises a validation error and hardware `-221,"Settings conflict"`.
- Panel command names (`SetCurrent`, `SetPower`, `OutputOn`, `OutputOff`) are for `device_command` **only**. Using `set PSU_A SetCurrent 200` in a recipe script fails with unknown parameter `SetCurrent`.

### 4.2 `LanThrottleController` (`TC1`) and Chamber Throttle Valves
- Floor pressure: `0.01 mTorr` (`1e-5 Torr`).
- Target `0` (`pwait 0 1` or `pwait <sensor> 0 1`) parks the throttle valve **100% open** immediately without waiting on the gauge.
- Any positive target (`target > 0`, including `0.01mT`) puts the controller into closed-loop pressure regulation (`TARG <torr>`). If gas is turned off while the target is `0.01mT`, the controller throttles the valve nearly closed (`~0.1%`) to hold `1e-5 Torr` instead of opening the valve for base-vacuum pumping.

### 4.3 `LanRotaryDrive` (`Holder`, `Shutter`)
- Valid position tokens: `"Home"`, `"0"`, flange numbers (`"1"`..`"8"`), or installed source effective names from `describe_hardware.sources.flanges`.
- Invalid tokens such as `"false"` or uninstalled material names (`"Cr"`, `"BN"`, `"Gr"`) are rejected by `validate_recipe` and by the drive (`-222,"Invalid position"`).

### 4.4 `LanTransferRobot` (`ROBOT` on `Cluster`)
- Moves substrates between faces (`LL`, `C1`, `C2`, `C3`, `C4`) through the central transfer module (`TM`).
- **Slit-valve interlocks (`describe_interlocks`):**
  - Opening any slit valve `SV_<ch>` requires both the chamber gauge and `TM_pm` to be at high vacuum ($< 1\times 10^{-4}\text{ Torr}$ = `0.1mT`), the chamber vent valve closed, and `ROBOT` not currently in `transferring` state.
  - Before executing `transfer <from> <to>`, verify that the relevant slit valves are opened in the sequence required by the cluster transfer protocol and closed before starting plasma or process gas flow in the target chamber.
  - Never open two process-chamber slit valves simultaneously during deposition, and never flow process gas in a chamber while its slit valve to `TM` is open.

## 5. Recipe Audit Checklist

When asked to review or audit a `.rcpx` file or DSL script:
1. Call `describe_machine`, `describe_hardware`, `describe_dsl`, `describe_interlocks`, and `describe_alarms`.
2. Call `validate_recipe` on the exact file/script content (`isRcpx: true` for `.rcpx`, `false` for bare DSL).
3. Cross-check every finding and every line against:
   - **Command availability & arity:** Does `pwait` exist on this profile? Is `pwait` 2-arg (`ADS`) or 3-arg (`Cluster`)? Is `deposit` 2-arg (`Sputter`, `Cluster`) or 3-arg (`ADS`)?
   - **Installed sources & retract tokens:** Are all `deposit`/`holder`/`shutter` target names in `describe_dsl.installedSources`? Is any 3rd-arg retract token valid (`"Home"` / flange, not `"false"`)?
   - **PSU mode & parameter names:** Are `Current`/`Frequency`/`DutyCycle` only used on `DC`/`PDC` supplies and never on `RF` supplies? Are DSL parameter names (`Current`, `Power`) used instead of panel names (`SetCurrent`)? Is `power <psu> on` called before `warmup`/`deposit`?
   - **Gas gating & teardown ordering:** Are required `gateValves` opened before `mfc <id> <sccm>`? At teardown, is the throttle parked open (`pwait 0 1` or `pwait <sensor> 0 1`, **not** `0.01mT`) before closing gas inlet valves and entering `state idle` so the chamber `Idle` over-pressure alarm does not trip?
   - **Pressure units:** Are all pressure literals in `<Script>` and `<Param>` suffixed (`mT`, `uT`, `Torr`)?
   - **Stage operational status:** Does the script move a stage with `isOperational: false` (e.g. `rotate` on `Sputter`)?
   - **Unattended execution blockers:** Does the script contain a blocking `message` step or depend on a manual-only source (`Ion`) without human intervention?
   - **Inert comments:** Are lines starting with `#` containing `;` (`scriptSummary.inertCommentLinesWithSemicolon`) properly recognized as inert comments rather than executable commands?
