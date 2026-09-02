# Diagrams

## Choose the view

Use a diagram when it makes relationships, structure or change easier to understand. Match the question and audience; split an overloaded view into an overview and focused details.

| What needs explaining | Suitable view |
|---|---|
| Responsibilities, dependencies or deployment boundaries | Architecture diagram |
| Data preparation, retrieval, training or inference | Data-flow diagram with transformations and stores |
| Calls, messages, tool use or hand-offs over time | Sequence diagram |
| Lifecycles, decisions, retries or recovery | State diagram or flowchart with labelled transitions |
| Entities, fields and cardinality | Schema or entity-relationship diagram |
| Alternatives or measured results | Aligned comparison views, a table or a chart |

Use D2 for source-controlled diagrams and compositions with multiple boards. Honour the requested format and preserve existing formats unless asked to convert them. Repository D2 conventions override these defaults.

## Defaults

- Use `--sketch` unless it harms the requested style, a formal template, accessibility or precise notation.
- Animate workflows, processes and state changes by default when motion explains direction, order or change. Keep schemas, code, rendered Markdown, inventories and other fixed reference material static.
- For animation, provide a complete, readable static SVG or PNG fallback. A static glyph cannot stand in for requested movement.
- Follow the existing file layout. Otherwise use `diagrams/src/` for D2 and shared styles, `diagrams/assets/` for images and fonts, and `diagrams/rendered/` for output. Create only what is needed.
- Keep `.d2` as the source of truth for structure and styling, with reproducible scripts for any capture or post-processing. Regenerate rendered images rather than hand-editing them; editable exports have their own rules below. Do not assume generated files belong in version control.

## Author and render

Establish the message, scope and destination → choose the view, output and canvas → edit source → format → validate → render → inspect → revise as needed.

```sh
d2 fmt diagrams/src/architecture.d2
d2 validate diagrams/src/architecture.d2
d2 --sketch --layout=elk --pad=24 --bundle=true \
  diagrams/src/architecture.d2 \
  diagrams/rendered/architecture.svg
```

- Render locally. Before using an unfamiliar export path, check the installed tools → test a small output. Report missing tools without triggering installation or interactive prompts. Use a hosted playground only when explicitly requested and permitted by the global policy.
- Reuse working sources, styles and render commands. Use the clearest layout; ELK is a useful starting point for dense architecture diagrams.
- Verify uncertain responsibilities, boundaries and connections against available code or documentation. Mark proposals and assumptions. Simplify detail without changing meaning, and explain material omissions in the hand-off.
- Keep text short and put caveats in surrounding prose. Connect the actual participants; distinguish data flow, control flow and structural relationships. Label actions, payloads or cardinality as appropriate.
- For AI systems, distinguish offline preparation from runtime behaviour and separate stores, model calls and tool execution where relevant. Show branching, concurrency, retries, failures and human decisions when they affect the explanation.
- Use `--bundle=true` for self-contained SVG assets. Rich content such as Markdown tables can require `<foreignObject>` support; use native D2 elements or a raster export if the destination cannot display it.

## Output selection

| Requirement | Preferred output |
|---|---|
| Documentation or Codex preview | Bundled SVG |
| Static presentation image | PNG; start with `--scale=2` and inspect at target size |
| Short, silent workflow loop | GIF from an export path verified to preserve every required motion type |
| Longer animation or playback controls | H.264 MP4 using available capture tools and FFmpeg |
| Presenter-controlled progression | One rendered image per D2 board |
| Quick, lower-fidelity slides | D2-generated PPTX |
| Interactive exploration | An available interactive visualisation |
| Shape-level editing | The target application's native format |

Do not assume animated SVG will play in Codex's file preview or import reliably into presentation software.

## Boards and progressive diagrams

- Use the root for an overview, `steps` for cumulative reveals, `scenarios` for alternatives inheriting from the base, and `layers` for independent views.
- For a progressive sequence, set the canvas → record a short storyboard in source comments or adjacent Markdown. Map each step number to a stable board key, output, event and visibility changes.
- Inspect the existing storyboard and source before revising numbered steps. Preserve their meaning and order, and stay within the requested sequence. Give each frame one coherent event; reserve space only for known future participants.
- D2 `steps` inherit previous states. Hide or reset temporary labels, connections, icons and styles in the first frame where they should disappear.
- Keep identifiers, canvas, layout, theme, fonts, padding and scale consistent. Render individual boards with `--target=''` for the root or, for example, `--target='steps.01'`.

## Animation export

- Decide what moves, what it means and when it starts and stops. Stabilise the layout before adding motion.
- `--animate-interval` controls board transitions; `style.animated: true` animates SVG/CSS connections. Verify each motion type in use. Bundling, rasterisation and imports may discard motion.
- Looping static PNGs freezes animated arrows, even if an overlaid spinner still moves. Use an export path verified to preserve every required motion type.
- If GIF or video export loses SVG motion: run the SVG in a local capture engine → advance every relevant animation timeline → capture at the target size and frame rate → encode with FFmpeg. Synchronise independently timed assets when deterministic capture is needed. Use reproducible composition for movement D2 cannot express.
- For GIF or video: render to a temporary path → check successful exit, non-empty output, dimensions, duration, frame count and GIF looping → inspect representative frames and transitions → replace the final artefact only after validation.
- Compare the same region across different animation phases for each requested motion type, including arrow paths. Frame count or a moving spinner alone cannot prove that the arrows move.

## Visual verification

Inspect every rendered diagram at its intended display size. Check:

- Accurate meaning, boundaries, endpoints, arrowheads and relationship labels.
- Complete assets with correct proportions, readable labels, clear contrast and no clipping or overlaps. Do not rely on colour alone to convey meaning.
- Correct aspect ratio, dimensions and safe area; balanced spacing, clear routing and enough raster resolution.
- For sequences, stable positions and correct visibility. Standalone frames must match their sequence counterparts, and static fallbacks must match their declared state.
- For animation, readable pacing and every intended movement in the delivered file.

Check command exit status as well as appearance. If SVG cannot be inspected, render a PNG verification copy. After edits, rebuild affected outputs. For progressive work, rebuild all implemented frames after shared-source or layout changes → compare consecutive frames or an overlay/contact sheet → inspect the current complete sequence before delivery. Equal canvas dimensions do not guarantee stable positions.

## Presentation and delivery

- For presentations, follow the applicable presentation instructions. Keep slide layout, editable titles, copy and branding in the template, and fit diagram frames inside its image area without cropping.
- Use direct PPTX export only when image-backed slides are acceptable. A presentation theme will not restyle the diagram itself.
- Return editable source, rendered output, the render command and any capture or post-processing script. Link the source and display the render using absolute paths in Codex; use file links where previews are unavailable. A D2 code block alone is not a preview.
- For progressive work, include changed frames and the complete sequence through the latest implemented step. For animation, identify the complete animation as the primary output and include its static fallback; overlays are optional supporting assets.
- Identify the current deliverables and their source inputs. Exclude scratch, temporary and superseded files from the hand-off.

## Draw.io export

When editable draw.io output is requested, use [d2-to-drawio](https://github.com/Moawiah188/d2-to-drawio).

With the converter installed: validate D2 → convert in strict mode → inspect warnings and output → deliver the `.drawio` file for manual editing.

```sh
d2 validate diagrams/src/architecture.d2
d2-to-drawio diagrams/src/architecture.d2 \
  --layout elk \
  --strict \
  -o diagrams/rendered/architecture.drawio
```

- Editable output takes precedence over sketch and animation defaults, which the converter does not support. If strict mode rejects only those presentation features: disclose the loss → rerun without `--strict` → inspect the result. Do not silently accept changes to meaning or explicit requirements.
- Omit `--waypoints` so draw.io can reroute edges, unless preserving D2 routes matters more than flexible editing.
- Manual edits do not round-trip. Once editing begins, treat `.drawio` as a separate editable source and write fresh conversions to a new file.

For other editors, prefer native output. Treat conversion as best-effort, disclose losses and inspect labels, connectors and layout; do not promise element-level SVG editing, animation or round-tripping.
