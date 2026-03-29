# Phase 7: Variant Codec and TCP Connection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 07-variant-codec-and-tcp-connection
**Areas discussed:** CLI command design, Session model, Error experience, Variant type coverage

---

## CLI Command Design

| Option | Description | Selected |
|--------|-------------|----------|
| Subcommands with --project | gdauto debug connect --project ./my-game --port 6007 | ✓ |
| Top-level project context | gdauto --project ./my-game debug connect | |
| Auto-detect project | Auto-detect project.godot in cwd or parents | |

**User's choice:** Subcommands with --project
**Notes:** Each debug subcommand takes --project explicitly.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal status line | One-line connection status | |
| Detailed connection info | Show version, scene root, timing | |
| You decide | Claude picks format | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on connect output format.

---

| Option | Description | Selected |
|--------|-------------|----------|
| 6007 (Godot default) | Consistent with ecosystem | ✓ |
| 6008 (avoid conflict) | Avoids editor collision | |
| Auto-find free port | Scan from 6007 upward | |

**User's choice:** 6007 (Godot default)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Combined (Recommended) | debug connect does it all | ✓ |
| Separate commands | debug launch + debug connect | |
| Both | Combined + debug attach for existing games | |

**User's choice:** Combined (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Short verbs | debug connect, debug tree, debug get | |
| Verb-noun pattern | debug get-tree, debug get-property | |
| You decide | Claude picks what fits | ✓ |

**User's choice:** You decide
**Notes:** Claude decided short verbs; reasoning: debug commands are rapid-fire and already scoped under `debug`.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Foreground (block) | debug connect stays running | |
| Background (return) | Start session, write file, return | |
| You decide | Claude picks for agent workflows | ✓ |

**User's choice:** You decide

---

| Option | Description | Selected |
|--------|-------------|----------|
| YAML test file | Declarative steps | |
| JSON test file | Matches --json contract | |
| CLI args inline | Chain via flags | |
| You decide | Claude picks for agents | ✓ |

**User's choice:** You decide
**Notes:** Phase 10 concern, noted here for consistency.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, --scene flag | Launch specific scene | ✓ |
| No, always main scene | Use project default | |
| You decide | Claude picks | |

**User's choice:** Yes, --scene flag

---

## Session Model

| Option | Description | Selected |
|--------|-------------|----------|
| Single-command (self-contained) | Boot game per command | |
| Background server + session file | Spawned background process | |
| You decide | Claude picks for agent loop | ✓ |

**User's choice:** You decide

---

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-timeout (5 min) | Shutdown after inactivity | |
| No auto-timeout | Stay alive until disconnect | |
| You decide | Claude picks reasonable default | ✓ |

**User's choice:** You decide

---

| Option | Description | Selected |
|--------|-------------|----------|
| Single session only | One at a time | |
| Multiple sessions | Different projects, different ports | |
| You decide | Claude picks for v2.0 scope | ✓ |

**User's choice:** You decide

---

| Option | Description | Selected |
|--------|-------------|----------|
| In project directory | .gdauto-session.json next to project.godot | |
| In system temp directory | tempdir with project hash | |
| You decide | Claude balances visibility/cleanliness | ✓ |

**User's choice:** You decide

---

## Error Experience

| Option | Description | Selected |
|--------|-------------|----------|
| High-level only | Protocol details in --verbose | |
| Detailed by default | Show protocol-level details always | |
| You decide | Claude picks verbosity level | ✓ |

**User's choice:** You decide

---

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate error + cleanup | Detect crash, report, clean up | |
| Error + preserve state | Keep artifacts for debugging | |
| You decide | Claude picks crash behavior | ✓ |

**User's choice:** You decide

---

## Variant Type Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (10 types) | Only debugger-needed types | |
| Comprehensive (25+ types) | All common types, future-proof | ✓ |
| Minimal + graceful skip | 10 types + skip unknown | |

**User's choice:** Comprehensive (25+ types)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Golden byte tests (Recommended) | Compare against Godot's var_to_bytes() | ✓ |
| Round-trip only | Python encode/decode cycle | |
| Both | Golden + round-trip | |

**User's choice:** Golden byte tests (Recommended)

---

## Claude's Discretion

- Connect output format
- Debug command naming (decided: short verbs)
- Session model implementation
- Session timeout behavior
- Multi-session support
- Session file location
- Connect blocking behavior
- Test script format (Phase 10)
- Protocol error verbosity
- Game crash recovery behavior

## Deferred Ideas

None -- discussion stayed within phase scope.
