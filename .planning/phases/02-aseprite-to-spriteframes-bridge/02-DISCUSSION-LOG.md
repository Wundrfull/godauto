# Phase 2: Aseprite-to-SpriteFrames Bridge - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-28
**Phase:** 02-aseprite-to-spriteframes-bridge
**Areas discussed:** Aseprite JSON handling, Animation conversion strategy, Atlas and sprite split behavior, Validation and error recovery

---

## Aseprite JSON Handling

### JSON Export Format
| Option | Description | Selected |
|--------|-------------|----------|
| Both hash and array | Support both --format json-hash and --format json-array | ✓ |
| Hash only | Only support json-hash (Aseprite default) | |
| Array only | Only support json-array | |

**User's choice:** Both hash and array
**Notes:** Auto-detect format from JSON structure.

### No Tags Behavior
| Option | Description | Selected |
|--------|-------------|----------|
| Single 'default' animation | Create one animation named 'default' with all frames | ✓ |
| Error with fix suggestion | Fail with actionable error | |
| Infer from filename | Use sprite sheet filename as animation name | |

**User's choice:** Single 'default' animation

### Validation Strictness
| Option | Description | Selected |
|--------|-------------|----------|
| Lenient with warnings | Accept valid JSON with expected top-level keys, warn on missing optional fields | ✓ |
| Strict validation | Require all expected fields | |

**User's choice:** Lenient with warnings

### Trim Data Support
| Option | Description | Selected |
|--------|-------------|----------|
| Full support | Parse spriteSourceSize and sourceSize, adjust regions and offsets | ✓ |
| Parse but ignore offsets | Read fields for validation but use frame rect as-is | |

**User's choice:** Full support

### Input Mode
| Option | Description | Selected |
|--------|-------------|----------|
| Files only | Accept path to .json file | ✓ |
| Files and stdin | Accept file path and piped stdin | |

**User's choice:** Files only

### Image Path Resolution
| Option | Description | Selected |
|--------|-------------|----------|
| Relative to JSON file | Resolve meta.image relative to JSON file directory | ✓ |
| Configurable via --sheet flag | Allow explicit --sheet path override | |
| Both with flag override | Default to relative, --sheet to override | |

**User's choice:** Relative to JSON file

### Output Path
| Option | Description | Selected |
|--------|-------------|----------|
| Auto-derive with -o override | Replace .json with .tres, allow -o/--output override | ✓ |
| Always require -o flag | Force explicit output path | |
| Auto-derive only | Always derive from input filename | |

**User's choice:** Auto-derive with -o override

### Image Handling
| Option | Description | Selected |
|--------|-------------|----------|
| Reference in place | .tres references image at current res:// path, no copying | ✓ |
| Copy with --copy-image flag | Optional flag to copy sprite sheet into project | |

**User's choice:** Reference in place

---

## Animation Conversion Strategy

### Timing Conversion
| Option | Description | Selected |
|--------|-------------|----------|
| GCD-based base FPS | Compute GCD of frame durations, derive base FPS, set multipliers | ✓ |
| Uniform FPS only | Use most common duration as speed, warn on variable durations | |
| Per-animation GCD | Compute GCD per animation tag, not globally | |

**User's choice:** GCD-based base FPS
**Notes:** Per-animation GCD (not global) was the recommended approach.

### Ping-Pong Handling
| Option | Description | Selected |
|--------|-------------|----------|
| Duplicate frames | Duplicate reversed middle frames (A-B-C-B pattern) | ✓ |
| Two separate animations | Create forward and reverse animations | |
| You decide | Claude's discretion | |

**User's choice:** Duplicate frames

### Loop Mapping
| Option | Description | Selected |
|--------|-------------|----------|
| 0 -> loop=true, N>0 -> loop=false | Map Aseprite repeat count to Godot boolean | ✓ |
| Always loop, warn on N>0 | Default loop=true, warn on finite playback | |

**User's choice:** 0 -> loop=true, N>0 -> loop=false

### Default FPS
| Option | Description | Selected |
|--------|-------------|----------|
| Derive from duration | Always compute from actual frame data | ✓ |
| Use Aseprite's framerate field | Read meta.framerate if present | |

**User's choice:** Derive from duration

---

## Atlas and Sprite Split Behavior

### Packing Algorithm
| Option | Description | Selected |
|--------|-------------|----------|
| Simple shelf/strip packing | Row-based placement, deterministic | ✓ |
| Max-rects bin packing | Optimal space utilization | |
| You decide | Claude's discretion | |

**User's choice:** Simple shelf/strip packing

### Atlas Size Constraints
| Option | Description | Selected |
|--------|-------------|----------|
| Default power-of-two, flag to disable | POT by default, --no-pot flag | ✓ |
| Always power-of-two | Strict POT only | |
| Always exact fit | Minimal bounding size | |

**User's choice:** Default power-of-two, flag to disable

### Grid Split Without Metadata
| Option | Description | Selected |
|--------|-------------|----------|
| Require --frame-size | User provides WxH, grid-based division | ✓ |
| Auto-detect with heuristics | Try to detect frame size from dimensions | |
| Require either JSON or --frame-size | Accept metadata or explicit size | |

**User's choice:** Require --frame-size

### Scope
| Option | Description | Selected |
|--------|-------------|----------|
| Include all three | import-aseprite, split, create-atlas all in Phase 2 | ✓ |
| import-aseprite only, defer others | Focus on core bridge, defer secondary commands | |

**User's choice:** Include all three

---

## Validation and Error Recovery

### Auto-Validation
| Option | Description | Selected |
|--------|-------------|----------|
| Separate validate command | sprite validate as separate command, import stays Godot-free | ✓ |
| Auto-validate with --validate flag | Optional flag triggers headless Godot validation | |
| Always validate | Always validate in headless Godot | |

**User's choice:** Separate validate command

### Partial Failure Handling
| Option | Description | Selected |
|--------|-------------|----------|
| Generate with warnings | Output .tres with valid animations, warn about skipped tags, exit 0 | ✓ |
| Fail entirely | Reject entire export if any tag has issues | |
| Generate + non-zero exit | Output partial .tres AND exit non-zero | |

**User's choice:** Generate with warnings

### Import Guide Format
| Option | Description | Selected |
|--------|-------------|----------|
| Built-in help text | Rich help text on --help covering settings, pitfalls, workflow | ✓ |
| Generated markdown file | sprite guide command generates detailed markdown | |
| Both | Concise --help plus detailed guide command | |

**User's choice:** Built-in help text

### Pitfall Detection
| Option | Description | Selected |
|--------|-------------|----------|
| You decide | Claude's discretion, researcher identifies impactful pitfalls | ✓ |
| Define specific list now | Lock in specific pitfalls during discussion | |

**User's choice:** You decide

---

## Claude's Discretion

- Specific Aseprite export pitfalls to detect (SPRT-12)
- Internal module organization
- Error message wording and fix suggestion text
- Test fixture design for Aseprite JSON samples

## Deferred Ideas

None -- discussion stayed within phase scope
