# Technology Stack: v2.0 Live Game Interaction

**Project:** gdauto v2.0
**Researched:** 2026-03-29
**Scope:** New dependencies and technology decisions for the debugger bridge feature

## Recommended Stack (Additions to v1.0)

### Network and Async
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| asyncio (stdlib) | stdlib | TCP server, async I/O | The debugger bridge requires a TCP server that accepts game connections and handles bidirectional async communication. asyncio.start_server() and StreamReader/StreamWriter provide the exact abstraction needed. No external dependency. Part of Python since 3.4, mature and stable. | HIGH |
| struct (stdlib) | stdlib | Binary encoding/decoding | Godot's Variant binary format uses little-endian packed integers, floats, and strings. struct.pack/unpack with format strings like '<I' (uint32 LE) and '<f' (float32 LE) handle all encoding needs. No external dependency. | HIGH |

### Process Management
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| subprocess (stdlib) | stdlib | Non-blocking game launch | Need `subprocess.Popen` (not `subprocess.run`) to launch the game process without blocking. The existing `GodotBackend.run()` uses blocking `subprocess.run`; a new `launch_game()` method uses Popen for concurrent execution. | HIGH |
| asyncio.subprocess (stdlib) | stdlib | Async process management | Alternative to raw Popen for game process lifecycle management within the async context. Provides `create_subprocess_exec()` with async wait/communicate. | MEDIUM |

### Data Modeling
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| dataclasses (stdlib) | stdlib | Debugger models | SceneNode, NodeProperty, RemoteSceneTree, DebugSession config. Same rationale as v1.0: internal data, no need for Pydantic. | HIGH |

### No New External Dependencies

The debugger bridge adds ZERO new pip dependencies. Everything is built on Python stdlib:
- `asyncio` for TCP and async
- `struct` for binary encoding
- `subprocess` for game process management
- `dataclasses` for models
- `pathlib` for file operations (bridge script generation)
- `json` for session files and --json output
- `signal` and `atexit` for cleanup handlers

This is a deliberate design choice. The debugger protocol implementation is specialized enough that no general-purpose library covers it, and the components are simple enough that stdlib tools suffice.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Async framework | asyncio (stdlib) | trio | Adds a dependency. asyncio is sufficient for a single TCP server with one connection. trio's structured concurrency is overkill here. |
| Async framework | asyncio (stdlib) | anyio | Abstraction over asyncio/trio. We only need asyncio. Added dependency for no benefit. |
| CLI async | asyncio.run() wrapper | asyncclick 8.3.0.7 | Replaces all of Click with a fork. Risks breaking 28 existing synchronous commands. Requires re-testing rich-click compatibility. Adds an external dependency. |
| Variant codec | Custom (struct-based) | gdtype-python | Last updated Sept 2022. Targets Godot 4.0 beta. Unknown Python 3.12+ compat. Only 2 functions, no error handling. Same "build vs buy" logic as the .tscn parser. |
| Variant codec | Custom (struct-based) | godot-binary-serialization (JS/Rust) | Wrong language. Would need a full port regardless. |
| TCP framework | asyncio.start_server | twisted | Massive dependency (5MB+). asyncio provides everything needed for a single-connection TCP server. |
| TCP framework | asyncio.start_server | socketserver (stdlib) | Synchronous. Cannot handle bidirectional async communication needed for unsolicited game messages. |
| Session persistence | Session file + per-command connection | Redis/SQLite | Extreme overkill. A JSON file with PID and port is sufficient for session state. |
| IPC (daemon mode) | localhost TCP | Unix sockets | Not available on Windows. gdauto must work on Windows (developer's primary platform). |
| Bridge script | GDScript autoload | Modified Godot engine | PlayGodot's approach. Requires maintaining a Godot fork. Unacceptable for a tool that targets stock Godot. |
| Bridge script | GDScript autoload | GDExtension plugin | Requires compilation per platform. A .gd script is universal and human-readable. |

## Dependency Classification

### Core (always installed, v2.0 additions)
No new core dependencies. All debugger functionality uses stdlib.

### Development (v2.0 additions)
No new dev dependencies. Existing pytest, ruff, mypy cover the debugger package.

## Runtime Dependencies Summary (v2.0)

| Dependency | Size | Required For | Optional? |
|------------|------|-------------|-----------|
| click | ~100KB | All CLI commands | No (core) |
| rich-click | ~200KB | Formatted help output | No (core) |
| rich | ~2MB | Transitive via rich-click | No (core, transitive) |
| Pillow | ~10MB | sprite create-atlas, sprite split | Yes (image extra) |
| *asyncio* | *stdlib* | *debugger bridge* | *No (stdlib, zero-cost)* |
| *struct* | *stdlib* | *variant codec* | *No (stdlib, zero-cost)* |
| **Total (core)** | **~2.3MB** | | |
| **Total (all)** | **~12.3MB** | | |

**v2.0 adds zero bytes to the dependency footprint.**

## Key Design Decisions

### Why asyncio.run() over asyncclick
asyncclick replaces the entire Click import chain with a forked version. It makes ALL commands async, even the 28 existing sync commands that don't need it. The risk-to-benefit ratio is poor: we need async in exactly one command group (debug). `asyncio.run()` at the boundary of each debug command handler is simpler, safer, and adds no dependency.

### Why custom Variant codec over gdtype-python
Same reasoning as the custom .tscn/.tres parser: the format is well-specified, we only need ~10 of 29 types, we get full control over error handling, and we avoid depending on abandoned upstream. The codec is ~300-500 lines of struct.pack/unpack calls with thorough type mapping.

### Why GDScript bridge over engine modification
Stock Godot doesn't expose input injection via the debugger protocol. PlayGodot solves this with a Godot fork. We solve it with a GDScript autoload script that translates debugger messages into `Input.parse_input_event()` calls. This works with any stock Godot 4.5+ binary, which is a core gdauto constraint.

## Sources

- [asyncio streams docs](https://docs.python.org/3/library/asyncio-stream.html) - TCP server/client API
- [struct module docs](https://docs.python.org/3/library/struct.html) - Binary packing
- [asyncclick PyPI](https://pypi.org/project/asyncclick/) - v8.3.0.7, evaluated and rejected
- [Click async issue #2033](https://github.com/pallets/click/issues/2033) - asyncio.run() pattern discussion
- [gdtype-python GitHub](https://github.com/anetczuk/gdtype-python) - Evaluated and rejected
- [PlayGodot GitHub](https://github.com/Randroids-Dojo/PlayGodot) - Reference implementation (requires Godot fork)
