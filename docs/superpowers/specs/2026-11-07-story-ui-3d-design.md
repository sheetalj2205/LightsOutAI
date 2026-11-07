# Story UI with 3D building — design

Date: 2026-11-07 · Status: approved in brainstorming

## Goal
Replace the current dashboard (too many cards and toggles at once) with a light-themed page that a
judge understands in one glance during a 2-minute pitch: **tonight's sky → the AI acts → the impact**,
with a 3D building as the single hero visual.

## Decisions
- Audience: judges watching a projected demo. Few controls, big visuals, big numbers.
- Hero: a 3D building (Three.js) generated from the backend's window list.
- Flow: a 3-step story bar; only the current step's controls are shown.
- Light page theme; the 3D view sits in a rounded panel with a dusk sky so lit windows glow.
- Sakshi's dashboard is kept as `classic.html`; her `js/api.js` (`window.LO`) is reused unchanged.

## Layout
- **Top bar:** logo + name, building picker, connection dot (Live / Fake / Offline), clock,
  ⋯ menu (Fake mode toggle, open twin screen, classic dashboard).
- **Step bar:** ① Tonight's sky · ② AI decides · ③ Impact. Current step highlighted; earlier steps
  clickable. "Start over" on step ③ resets windows and returns to ①.
- **Main row:** 3D panel (~65% width) + step card (~35%). Stacks vertically under 1000 px.
  - ① card: one-line weather summary, migration badge (LOW/MEDIUM/HIGH + "estimated"),
    sky-danger bar, current building risk, scenario buttons Clear / Foggy migration / Live, **Next →**.
  - ② card: one large "⚡ Let the AI decide" button; while waiting, "Thinking…" with the AI name;
    on success the windows switch in 3D and the page moves to ③ automatically.
  - ③ card: animated risk number before → after with % reduction, windows off / dimmed,
    kWh and $ saved, AI reason with "decided by Gemini / BullsAI (UB) / rule-based fallback",
    🔊 replay button; voice plays automatically once.
- **Below:** real photo before/after comparison slider (drag handle); toggle "Show detected windows"
  swaps the before image to the debug image. Hidden when the building has no photo.
- **3D panel overlay:** 3-item legend (Lit / Dim / Off) and a "Risk view" toggle.

## 3D scene (`js/scene3d.js`)
- Three.js r160, ES modules, vendored at `frontend/vendor/three/` (no CDN needed at the venue).
- Public interface:
  - `createScene(container) → scene`
  - `scene.setBuilding({floors, cols, windows})` rebuild geometry for a building
  - `scene.setWindow(id, state)` fade one window to on / dim / off (~0.4 s)
  - `scene.setWindows(windows)` apply a full window list
  - `scene.setRiskView(bool)` tint lit windows green → amber → red by `risk`
  - `scene.setMood(litFraction)` drives bird behaviour
  - `scene.dispose()`
- Building: light concrete body, floors × cols window panels on front and back faces (both mirror
  the real data), vertical fins on the sides, ground plane, soft shadow. Dusk gradient background.
- Windows: emissive panels using each window's detected color; dim = 35 % emissive; off = dark glass.
- Camera: slow auto-orbit; drag to rotate (OrbitControls, no pan, limited zoom); auto-orbit resumes
  after 4 s idle.
- Birds (illustration): ~25 small V shapes orbiting the building; pulled toward the lit floors in
  proportion to lit fraction; drift outward/up as windows go dark. Caption: "Birds: illustration".
- Performance: one InstancedMesh for windows, pixel ratio capped at 2, animation paused when the
  tab is hidden.

## Data flow (`js/story.js`)
- Load: `LO.api().windows()` → `setBuilding`; `LO.api().conditions()` → step ① card.
- WebSocket via `LO.connectSocket`: `building` → `setBuilding`; command `{id,state}` → `setWindow`;
  `decision` → fill step ③; `conditions` → refresh step ①.
- Decide: `LO.api().decide()`; the response's `windows` are also applied directly, so fake mode
  (no WebSocket) animates too. Then go to ③ and `LO.speak(reason)`.
- Scenario buttons: `LO.api().simulate(name)`. Reset: `LO.api().reset()`.

## Failure handling
- No WebGL / Three.js fails to load → render Sakshi's flat grid (`js/twin.js`) in the 3D panel.
- Backend down → existing fake mode (status dot shows "Fake").
- Decide fails → error toast, stay on step ②, button re-enabled.
- No photo for the building → hide the before/after section.

## Files
- `frontend/index.html` new story page (old one moved to `frontend/classic.html`, unchanged).
- `frontend/css/story.css`, `frontend/js/scene3d.js`, `frontend/js/story.js`, `frontend/vendor/three/`.
- No backend changes.

## Testing
- Run against the live local backend; walk ① → ③ for Clear and Foggy migration; Start over.
- Headless-browser screenshots at 1920×1080 and 1440×900; check console has no errors.
- Fake mode: stop the backend, reload, run the full flow.
- WebGL fallback: force the fallback flag and check the flat grid appears.

## Out of scope
- Redesigning `twin.html`, multi-building comparison, mobile-first layout.
