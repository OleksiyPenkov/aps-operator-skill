# APS Operator Skill (`aps-operator`)

A portable, topology-agnostic operator skill for language-model agents driving physical vapor deposition (PVD) systems over the [`APS Control Community`](https://github.com/APS-Techno/Control-Community) Model Context Protocol (`aps-control`) server.

Instead of hardcoding device names, chamber topologies, or command arities from a single laboratory tool, `aps-operator` teaches an agent to discover the connected machine's hardware inventory, worker command signatures, safety interlocks, and alarm rules dynamically at runtime across arbitrary PVD architectures:

- **`Sputter` (Single-Chamber Batch Coater):** Two magnetrons (`DC`/`PDC` and `RF`), pneumatic source shutters (`2`-argument `deposit`), ungated argon mass flow controller, passive base-vacuum wait (`swait`), and immediate `Idle` over-pressure alarm protection.
- **`ADS` (Load-Locked Multi-Source Deposition System):** Main chamber with load lock, five sputter/ion sources, rotary substrate holder and shutter (`3`-argument `deposit`), active closed-loop throttle controller (`2`-argument `pwait`), OR-gated gas manifold valves, and `60 s` conditional `Idle` alarm delay.
- **`Cluster` (Multi-Chamber Radial Cluster Tool):** Central transfer module (`TM`) with a transfer robot (`ROBOT`), load lock (`LL`), and four process chambers (`C1`–`C4`) with per-chamber throttle valves (`3`-argument `pwait`), slit-valve pressure-equalization interlocks, and per-chamber alarm state machines.

## Repository Layout

```text
skills/
  aps-operator/
    SKILL.md                      # Primary topology-agnostic operator procedure
    references/
      dsl-and-safety.md           # Recipe XML/DSL grammar, driver contracts, and audit checklist
tools/
  check_portability.py            # Automated portability and vendor-denylist scanner
tests/
  test_portability.py             # pytest verification suite
```

## Installation

### Claude Code / Agent Skills Directory

Copy or symlink `skills/aps-operator` into your agent's skills directory (for example `~/.claude/skills/aps-operator` or `.agents/skills/aps-operator` in your workspace):

```bash
git clone https://github.com/OleksiyPenkov/aps-operator-skill.git
cp -r aps-operator-skill/skills/aps-operator ~/.claude/skills/
```

### With `ADS-Bench v2.0`

Point `ADS_BENCH_SKILL_DIR` at the `skills/aps-operator` directory when running [`OleksiyPenkov/ads-benchmark`](https://github.com/OleksiyPenkov/ads-benchmark):

```bash
export ADS_BENCH_SKILL_DIR="/path/to/aps-operator-skill/skills/aps-operator"
```

## Verification

Run the portability and hygiene test suite to verify that the skill contains zero machine-specific workstation paths or vendor-proprietary device identifiers:

```bash
pytest
python tools/check_portability.py
```

## Citation

If you use this skill in your research, please cite [`CITATION.cff`](CITATION.cff) and the accompanying preprint:

- O. V. Penkov, H. Fu, Y. Zhan, P. Wu, and J. Jin, *"Agent-authored deposition recipes for X-ray multilayer mirrors: schema-bound LLM control of a magnetron sputtering system with reflectivity-verified outcomes,"* arXiv:2609.12796 (2026). https://arxiv.org/abs/2609.12796

## License

Creative Commons Attribution 4.0 International ([`CC-BY-4.0`](LICENSE)) for the skill text and documentation; MIT for the verification scripts in `tools/` and `tests/`.
