# Diagrams

## Defaults

- Use a diagram when it materially clarifies relationships, hierarchy, flow, topology, state, or change over time.
- Honour the requested format and preserve an existing diagram's format unless asked to convert it. Use D2 for deterministic, source-controlled diagrams and multi-board compositions.
- Repository D2 conventions override this guide.

Use this layout by default:

```text
diagrams/
  src/          # Editable .d2 source and shared styles
  assets/       # Images, icons, fonts, and shared styling
  rendered/     # Generated SVG, PNG, GIF, PPTX, or downstream .drawio
```

- Treat `.d2` as the source of truth for topology and static styling. Keep motion capture or post-processing reproducible and identify its authoritative inputs. Do not hand-edit generated output or assume it belongs in version control.
- Use `--sketch` by default unless it harms a requested style, formal template, accessibility, or precision-heavy content.
- Animate workflows, processes, lifecycles, pipelines, request paths, state changes and progressive reveals by default when motion explains direction, order or change. Do not animate static schemas, code, rendered Markdown, inventories or fixed reference structures.
- Genuine animation cannot be replaced by a static glyph. Always provide a complete, readable static SVG or PNG fallback.

## Workflow

For every created or changed D2 diagram, use:

**Define the message, abstraction level, destination, and any known sequence → choose the output and canvas → edit source → format → validate → render → inspect the delivered format → revise if needed.**

Example:

```sh
d2 fmt diagrams/src/architecture.d2
d2 validate diagrams/src/architecture.d2
d2 --sketch --layout=elk --pad=24 --bundle=true \
  diagrams/src/architecture.d2 \
  diagrams/rendered/architecture.svg
```

- Render locally with D2 and use FFmpeg for video. For raster, presentation or video output: identify a non-interactive render path → test a small output → create the final artefact. If tooling is missing, report it; do not install software, invoke an interactive installer or use a hosted D2 playground without an explicit request.
- Use the clearest layout; prefer ELK for dense architecture or container diagrams when it routes better.
- Use the minimum topology and text needed. Put caveats in surrounding prose or speaker notes.
- When depicting an existing system: verify uncertain actors, responsibilities, boundaries and connections → draw the verified structure. Simplification may omit detail, but not change responsibilities, causal relationships or deployment boundaries; disclose it at hand-off.
- Connect the real initiating and receiving elements. Keep direction consistent and labels concise and verb-led where the action is otherwise ambiguous.
- Use `--bundle=true` for self-contained SVG assets, but test the destination. Rich content such as Markdown tables may require `<foreignObject>` support; prefer native D2 elements or make a raster export authoritative.
- Check command exit status and inspect the delivered format visually. A file's existence or a successful validation is not proof of a usable render.

## Output selection

| Requirement | Preferred output |
|---|---|
| Documentation or Codex preview | Bundled SVG |
| Static presentation image | PNG; start with `--scale=2` and inspect at target size |
| Short, silent workflow loop | GIF from an export path verified to preserve every required motion type |
| Longer or controlled animation | H.264 MP4 when capture and conversion tools are available |
| Presenter-controlled progression | One rendered image per D2 board |
| Quick, lower-fidelity slides | D2-generated PPTX |
| Interactive exploration | An available interactive visualisation |
| Shape-level editing | The target application's native format |

Do not assume animated SVG will play in Codex's file preview or import reliably into presentation software.

## Progressive diagrams

- Before authoring: set the destination canvas or aspect ratio → write a numbered storyboard with each frame's stable board key, title, event, affected elements and visibility changes. Keep the mapping in source comments or adjacent Markdown.
- Treat numbering as a contract: inspect the storyboard and source before implementing a requested step; never repurpose or skip one silently.
- Give each frame one coherent event and only the labels and connections needed to explain it. Implement only requested frames; declare shared topology early and reserve space only for known future participants.
- D2 `steps` are cumulative. Explicitly hide or reset temporary labels, connections, icons and styles when they should disappear.
- Keep canvas, layout, theme, fonts, padding and scale stable. Render boards with `--target`, such as `--target=''` for the root and `--target='steps.01'` for a step.

## Animation export

- Plan what moves and when. Use animated connections for flow, boards or `steps` for state progression, and captured GIF or MP4 composition for movement D2 cannot express.
- Board transitions and in-board motion are separate: `--animate-interval` advances boards, while `style.animated: true` creates SVG/CSS connection motion. Preserving one does not prove the other survived.
- Never preserve in-board motion by looping static PNG renders; this freezes animated arrows even when an independent asset, such as a spinner, still moves.
- To preserve animated connections: run the SVG in a local, time-aware capture engine → advance every relevant animation timeline, normalising independently timed assets when deterministic synchronisation is required → capture at the target dimensions and frame rate → encode with FFmpeg.
- Stabilise the static layout → keep post-processing reproducible → rebuild affected outputs from the same inputs → test the actual destination format. Bundling, rasterisation and imports may discard animation.
- Render to a temporary path → verify exit status, size, dimensions, duration, frame count and, for GIF, looping → inspect transitions and a fixed crop for every requested motion type → replace the final artefact. One moving element does not prove that all motion survived.

## Presentation-like diagrams

When the deliverable is a presentation, also follow the applicable presentation instructions.

- D2 owns topology, relationships, states and base styling; capture or composition owns otherwise-lost motion; the presentation owns layout, editable copy and branding.
- Use the root board for an overview, `steps` for cumulative reveals, `scenarios` for alternatives and `layers` for drill-downs.
- Keep slide titles and explanatory copy outside D2, and fit diagram frames within the template's image area.
- Use direct PPTX export only when image-backed, lower-fidelity slides are acceptable. A presentation theme will not restyle the diagram itself.

## Visual verification

Inspect every rendered diagram at its intended display size. Check:

- meaning: semantic accuracy, responsibilities, relationships, boundaries and disclosed simplifications;
- content: complete assets with correct proportions, readable unclipped labels, no overlaps and sufficient contrast;
- connections: correct endpoints, direction and arrowheads, with avoidable crossings removed;
- composition: target aspect ratio, dimensions and safe area, balanced spacing and sufficient raster resolution;
- continuity: stable positions and visibility, with standalone renders matching their corresponding sequence frames and each fallback matching its declared state;
- motion: intended direction, order and change at a readable pace.

If SVG cannot be inspected directly, render a PNG verification copy. After any shared-source or layout change, and before delivery: render every implemented frame and the current complete sequence → verify identical canvases → compare consecutive frames at target size or with an overlay or contact sheet → inspect the final format. Equal dimensions alone do not prove layout stability.

## Codex delivery

- Return editable source and rendered artefact together; a D2 code block is not a preview. In Codex, link or display them using absolute paths.
- State the render command and any reproducible capture or post-processing script.
- For progressive work, return changed frames, the complete sequence to the latest frame and a static fallback; identify the authoritative motion file.
- Identify canonical outputs and exclude scratch, temporary and superseded files. When post-processing is required, the complete destination-ready animation is primary; reusable overlays are secondary.

## Draw.io export

When the user requests editable draw.io output for manual changes, use [https://github.com/Moawiah188/d2-to-drawio](https://github.com/Moawiah188/d2-to-drawio).

Workflow: validate the D2 source → convert in strict mode → inspect warnings and the generated file → hand off the `.drawio` file for manual editing.

With the converter already available:

```sh
d2 validate diagrams/src/architecture.d2
d2-to-drawio diagrams/src/architecture.d2 \
  --layout elk \
  --strict \
  -o diagrams/rendered/architecture.drawio
```

- Animation and sketch styling are unsupported. Run with `--strict` first; if it rejects only presentation features: report the loss → rerun without `--strict` only if the user still wants editable output → inspect the conversion.
- Omit `--waypoints` so draw.io can reroute edges, unless preserving D2 routes matters more than flexible editing.
- Manual edits do not round-trip. Once editing begins, treat `.drawio` as authoritative downstream output and never overwrite it with a fresh conversion.

For other editors, prefer native output. Treat conversion as best-effort, disclose losses and inspect labels, connectors and layout; do not promise element-level SVG editing, animation or round-tripping.
