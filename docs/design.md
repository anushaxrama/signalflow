# SignalFlow interface

The grid observatory uses warm ivory, forest green and restrained chart colors. The permanent navigation is dark; analytical surfaces are light, with a distinct forest-green workload lab. Space Grotesk supplies display type and tabular numbers; DM Sans handles interface text. Both fonts are hosted locally under their included SIL Open Font Licenses in `signalflow/static/fonts/`.

The hierarchy moves from source context to metrics, observed/forecast comparison, generation mix, historical workload exploration and operational evidence. Small labels carry secondary context; source timestamps, status and null actuals remain explicit.

Polish is functional:

- Real-data sparklines and generation bars; no simulated dashboard values.
- Pointer and keyboard chart inspection, null/gap-aware paths and independently selectable series.
- A timestamped latest observed value when the newest source actual is still pending.
- A default workload comparison; editing inputs clears the previous result until recalculation.
- Range tabs on wide screens, a native select on mobile, responsive navigation and active-section indication.
- Refresh/loading/error states, an accessible source-information dialog, semantic forms, focus indicators and reduced-motion support.
- Responsive checks at 390 px, laptop and desktop widths; no horizontal overflow at checked sizes.

The case-study page shares the font and color system. Python API and storage contracts are preserved; the local container dashboard remains at http://127.0.0.1:8001.
