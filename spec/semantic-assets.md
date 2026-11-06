# Semantic assets

## Purpose and ownership

Presentation assets have semantic names rather than being selected through
glyphs, color literals or file locations in component implementations. Icons
are the first consumer, not a separate resource system. Colors and stateful
appearances use the same index, reference rules, validation and resolution owner.

One packaged JSON index and adjacent schema own the default resources. An
optional project `artifact.assetIndex` selects a vault-local override index;
configuration defaults, path constraints and limits belong in cfg/schema.
This replaces the unreleased icon-only `artifact.iconCatalog` proposal. Do not
ship two registries, configuration knobs or competing reference mechanisms.

Assets describe reusable presentation, not authored content. Text and sections
remain content under [[architecture]]; their reusable appearances may be assets.

Text, icons and cards share the same appearance/color owner, including colors
selected by existing conditional rules. A color-only appearance is valid; an
icon consumer additionally requires an icon. Do not copy prose into the index
or introduce another conditional-color palette/evaluator. This unification does
not introduce new authored text syntax.

The index is data-only source alongside the Obsidian vault. Existing Obsidian
Base declarations select names through `obsHtml.icon.name` or composed
`obsHtml.icons[*].name`; old names remain aliases into the same index.

Ordinary Markdown note/image/file links keep their existing resolver. This
change does not introduce another inline Markdown language or turn external
source-system web links into presentation assets.

## Existing models and deliberate limits

Borrow the design-token model: typed named values, aliases, nested groups,
explicit local overrides and cycle detection. Relevant existing references:

- [[dtcg-format|DTCG format 2025.10]],
  particularly groups, aliases, type inheritance and extension errors.
- [[dtcg-resolver|DTCG resolver 2025.10]],
  for separating values from theme/context selection.
- [[style-dictionary-tokens|Style Dictionary tokens]],
  as an existing implementation/tooling comparison.

The profile below is intentionally smaller and tailored to confined Obsidian
resources. It is not a claim of full DTCG conformance: icon/appearance types and
implicit parent state defaults are obs-html contracts. In particular, do not
treat a JSON Schema `$ref` validator as an application-data deep-merge engine.

Reuse JSON Schema validation and existing resource doors; do not add a separate
Node build pipeline or dependency merely to imitate a larger token tool.

Initial types are `icon`, `color` and `appearance`. Do not add a general style,
arithmetic, scripting, selector or expression language. Additional asset kinds
need a concrete consumer and an input-model decision, not an unrestricted object.

## Index, names and references

An index has `schemaVersion` and an `assets` mapping. Each named node can have
`children`. A node with children is a group/template, not a concrete asset.
Its `type`, base appearance properties, `states` and `defaultState` supply
defaults to descendants. A node is a typed concrete asset or an alias.

Semantic IDs are case-sensitive paths joined by dots, such as
`evidence.snapshot`. Segment names cannot contain dots or reserved structural
field names; accepted identifier syntax and bounds belong in the schema.

Identifier matching consumes the entire string; whitespace is rejected, not trimmed.
Every consuming declaration uses that same identifier profile; a valid indexed
resource must not become unselectable because a consumer imposes a shorter limit.

Structural `children` keys are not part of an ID. References are whole data
objects, `{"ref": "evidence.snapshot"}`, never interpolated strings or executable
expressions. A reference denotes an indexed asset, not a URL or filesystem path.
Node aliases can chain; they cannot add children or change the referenced type.

Concrete values occur only at resource definitions:

- An `icon` value is either a UTF-8 `glyph`, including multicodepoint sequences,
  or a local `asset` image path. Prefer glyphs when they represent the icon well.

  A local SVG file icon may explicitly declare `monochrome: true` in its value
  to use its alpha coverage with the current semantic foreground color. Ordinary
  file icons retain their intrinsic artwork colors. This bounded resource opt-in
  does not introduce inline authored SVG/HTML trust or a separate palette; source
  bytes still use the existing single payload owner, including print and saving.
- A `color` value is a validated theme-aware literal, or a reference to another
  color asset. Keep the existing light/dark palette and light print behavior.
  Literal color syntax and accepted theme-value shapes belong in the schema.
- An `appearance` combines optional `icon` and `color` references with named
  `states`. Its fields do not contain raw glyphs, file paths or color literals.
  Concrete appearances must resolve the fields required by their consumer for
  every selectable state; groups may intentionally provide only partial defaults.

`defaultState` is explicit where an appearance should work without a caller
state. Otherwise a stateful consumer supplies the state. Unknown requested
states are errors, not guessed transitions or fallback to another named state.

Packaged action appearances retain the same identifying icon in active and
inactive states; the inactive ("passive") state is grayed out through the shared
muted semantic color and a visibly reduced shared icon opacity, not grayscale
alone.

Its default and accepted range belong in cfg/schema; apply it to the inactive
icon, not its explanatory text or tooltip. Active icons retain their
normal opacity and each icon remains recognizable in light, dark and print views.

Full-color
image/emoji icons also need a grayscale projection so changing wrapper color
alone does not leave them visually active. Authors need only one icon file.
An explicitly authored inactive-icon override, including a shared unavailable
icon, remains supported; appearance does not decide
whether the action is enabled.

## Deterministic inheritance and override order

1. Overlay the selected project index on the packaged index by semantic node
   path. Named nodes/properties merge; a local property replaces the same
   inherited property. A concrete `value` is atomic: replacing a glyph with an
   image must not leave both variants, and arrays are replaced, not concatenated.
   A partial project node may inherit its packaged type/value.
2. Walk lexical parents from outermost group to the node. The closest explicit
   field wins. Merge state maps by state name and appearance field, so overriding
   one child's active icon does not erase its inherited inactive state or color.
   Concrete type changes are errors, not coercions.
3. Resolve the effective base appearance across that lineage, then resolve the
   requested state's overlay across the same lineage and apply it over the base.
   State-specific values are more specific than base values; child overrides
   win within the same state. Omitted fields inherit, not become null/deleted.
4. Resolve typed aliases and appearance references against the complete overlaid
   index, not a previously flattened copy of the packaged values. Consequently
   overriding a shared color or inactive icon changes every dependent child.
5. Apply the existing theme context through the stylesheet projection. Theme
   selection and an appearance's active/inactive state are independent inputs.

References may point forward; declaration order has no semantic effect. There is
no implicit deletion/null reset, multiple inheritance, remote import graph or
string-template expansion in this first profile. Do not silently add such rules.
Each value retains its defining source location: inherited packaged file assets
still resolve relative to their package, not the overriding project's directory.

## One icon with a derived inactive appearance

This abbreviated valid-shape example illustrates the contract; actual defaults
and complete validation belong in the packaged index/schema:

```json
{
  "schemaVersion": 1,
  "assets": {
    "icon": {
      "children": {
        "snapshot": {"type": "icon", "value": {"glyph": "📷"}},
        "source": {"type": "icon", "value": {"glyph": "🔗"}}
      }
    },
    "color": {
      "children": {
        "action": {"type": "color", "value": {"light": "#000000", "dark": "#ffffff"}},
        "muted": {"type": "color", "value": {"light": "#555555", "dark": "#bdbdbd"}}
      }
    },
    "evidence": {
      "type": "appearance",
      "defaultState": "active",
      "states": {
        "active": {"color": {"ref": "color.action"}},
        "inactive": {"color": {"ref": "color.muted"}}
      },
      "children": {
        "snapshot": {"icon": {"ref": "icon.snapshot"}},
        "source": {"icon": {"ref": "icon.source"}}
      }
    }
  }
}
```

In an Obsidian Base slot, `name: evidence.snapshot` chooses that resource.
When the existing action owner determines that the snapshot is available, the
view resolves its `active` state; otherwise it resolves `inactive`.

Each icon is defined and referenced once. Inactive appearance derives from
that same
resource using the shared muted/grayscale projection, not a second file or
second state-specific icon reference. A shared color override changes the
dependent appearances without editing their declarations or action handlers.

Select the project index in vault `cfg.json`:

```json
{"artifact": {"assetIndex": "presentation/assets.json"}}
```

With that index's example definitions, an ordinary Obsidian Base can declare:

```yaml
properties:
  actions:
    obsHtml:
      icons:
        - name: evidence.snapshot
          label: Download included snapshot
          linkProperty: snapshotAsset
          download: true
          unavailable: No snapshot is included.
        - name: evidence.source
          label: Open source system
          linkProperty: sourceLink
          download: false
          unavailable: No source link is configured.
views:
  - type: table
    order: [title, actions]
```

The linked fields remain ordinary canonical frontmatter links. An image path
such as `icons/snapshot.png` is relative to `presentation/assets.json`, not to
the note containing the Base. Override concrete definitions such as
`icon.snapshot`; an alias node cannot also supply its own value.

## State and conditional-color boundaries

Asset resolution consumes a semantic ID, a declared state and the existing theme
context; it does not inspect arbitrary artifact records or decide business truth.

The existing control/action owner determines availability, expansion or selection.
The asset changes appearance only. An inactive icon does not enable/disable an
action, grant trust, alter download behavior or remove accessible explanations.

There is already bounded conditional formatting in metric `toneRules`, not a
general logic language. Preserve that evaluator and authoritative query results.

Existing `neutral`, `positive`, `negative` and `warning` tones resolve semantic
color assets through the shared owner. Add no second conditional evaluator or
parallel literal palette. Custom stateful appearances can reference other declared
colors without teaching the generic resolver domain predicates.

The index owns actual palette values and aliases; CSS owns layout, application
of those semantic colors, focus/disabled treatment and theme/print behavior.
Generate the existing CSS custom-property values from that owner rather than
maintaining an index palette and independent hardcoded stylesheet palette.
Data-driven chart colors remain authored data, not a new domain-color algorithm.

## Boundaries, packaging and diagnostics

All semantic references stay inside the selected logical index. Only an icon
resource definition may introduce a file image path. Files are confined to the
owning package or vault, resolve relative to their defining index, and use the
existing image validation/resource/payload boundary.

Reject remote URLs, network icon fonts/services, data/javascript URLs,
absolute/source-machine paths and
symlink/traversal escapes. Do not execute SVG script, arbitrary markup or CSS.

This prohibition concerns presentation dependencies, not existing authored
source-system links, ordinary note references or separately approved application
runtime dependencies. Do not silently change those contracts.

Resolve and validate before generation, including the existing CLI check path.
Errors identify the source file, semantic ID, state and reference/inheritance
chain where relevant: malformed/duplicate definitions, unknown IDs/states,
type mismatch, incomplete concrete appearance, cycles and missing/unsafe files.
No blank icon, silent default or success-shaped fallback for invalid input.

Generated markup and late browser controls consume one resolved semantic owner.
Do not serialize separate icon/color registries, a hierarchy plus duplicate flat
index, or per-view copies of resource bytes. Share actual image payloads through
the existing payload owner; derived DOM and CSS variables are projections.

Saving/reopening and physical printing preserve selected resources and state
semantics; source reproduction retains the authored index and file dependencies.
Keep canonical artifact data, actions and query populations unchanged.

## Delivery order

Generalize the current isolated icon work package rather than shipping an
icon-only public API and immediately replacing it. The first complete slice must
prove the parent/child active/inactive example, semantic colors and existing
Obsidian icon references end-to-end, then migrate the other identified UI icon
consumers through that same owner.

Add regression cases before behavior changes for hierarchy/state merge,
project overrides updating aliases, type/cycle/error cases and availability
transitions.

Verify the actual rendered glyph/image and computed color, not only resolver
dictionary equality. Preserve actions, compact widths, accessible
tooltips, saved reopening, independent PDF, table paging and stable logical
footers. Worker tickets/evidence own delivery status; this note owns the design.

## Initial consumer projection

Base icon slots accept an icon or icon-bearing appearance. Their action owner
supplies `active`/`inactive` to stateful appearances; a plain icon is stateless.

Every selectable state of a Base appearance must supply an icon; color is optional
and otherwise inherits the component's stylesheet color. Static controls use an
appearance's explicit default state. Native appearance-menu options retain plain
labels with the selected resource adjacent, so image resources work too.

The initial color literal profile accepts six/eight-digit hexadecimal strings
or a `{light, dark}` pair. Static SVG geometry and PNG/JPEG/GIF/WebP are the image
profile; executable SVG, stylesheet/link references and source symlinks are rejected.

Namespace segments `icon` and `color` are permitted; structural control words
such as `type`, `value`, `children`, `states` and `ref` are reserved. Empty templates
remain partial definitions, but their declared references/types are validated even
when no concrete descendant consumes them.
