# Lights Out AI

> Fill in the [brackets] before submitting.

## Inspiration
Up to 1 billion birds die hitting buildings in the U.S. every year. Most migrate at night, and lit windows pull
them off course, worst of all on foggy, cloudy nights. Buffalo sits on a major migration route. "Lights Out"
programs ask buildings to turn lights off during migration, but someone has to remember, every night, for every
window. We built a tool that decides for you.

## What it does
You upload a photo of a building and type its address. The app:

1. **Finds every window** in the photo, and which ones are lit. You can add photos of the other sides too.
2. **Reads tonight's sky**: the weather forecast for that address, an estimate of how many birds are migrating
   tonight, and recent eBird sightings of night-migrating birds nearby.
3. **Picks a rule for tonight**, taken from published guidance (see below).
4. **Lets AI choose the windows**: Gemini picks which lights to turn off or dim, highest-risk first (high
   floors, bright white light), and explains why in plain English. Lobby and safety lights always stay on.
5. **Turns them off**: the lights go out top floor first on a 3D model of the building made from your photo,
   and on a small LED "building" (ESP32). A voice alert tells staff what was done.
6. **Shows the impact**: estimated drop in bird collisions, share of lit window area turned off, energy and
   money saved, and a before/after view of the real photo.

## Tonight's rule (from published sources, not our guesses)
| Migration tonight | Rule | Source |
|---|---|---|
| High | Turn off every non-essential lit window | Lights Out guidance (Audubon, BirdCast, NY DEC) |
| Medium | Turn off at least half of the lit window area | Van Doren et al. 2021, *PNAS* |
| Low | No target; dimming the brightest windows is optional | Low risk |

Van Doren et al. studied 21 years of bird collisions at one Chicago building: halving the lit window area cut
collisions **6× in fall and 11× in spring**. We use that result to estimate the impact for your building.

## How we built it
- **Backend:** Python, FastAPI, WebSockets.
- **Finding windows (OpenCV):**
  - Glass buildings: find the big lit areas, then split them along the dark window frames into panes.
  - Separate windows on a wall: bright-blob detection.
  - Day photos: Gemini counts floors and windows, then we simulate tonight's lights.
  - Lamps, puddles and glare are filtered out. The app never asks the user to count floors.
- **Weather and migration:** National Weather Service forecast (U.S. addresses); a migration estimate built
  with the factors of the BirdCast forecast model (season, tailwind, temperature and pressure change, rain) on
  NOAA's GFS weather model via Open-Meteo; live eBird sightings, counting only species that really migrate at night.
- **AI:** Gemini (photo + window list + tonight's rule) returns JSON. If Gemini is down, UB's BullsAI takes
  over, then a rule-based safety net. If the AI's choice doesn't meet tonight's rule, the highest-risk windows
  are added until it does.
- **Frontend:** HTML, CSS, JavaScript, Three.js (3D scene with the real photo on the building).
- **Voice:** ElevenLabs. **Data:** every decision is logged to Tiger Data (TimescaleDB).
- **Hardware:** an ESP32 with a 5×6 LED grid, simulated in Wokwi, joins the same WebSocket and switches its
  LEDs with the building.
- **Hosting:** [Vultr + Caddy / domain].

## Challenges we ran into
- **Glass buildings.** Bright-blob detection failed on glass walls: boxes on trees, puddles and street lamps.
  We switched to finding the window frames, which follows the real grid of panes.
- **Made-up numbers.** Our first version used our own percentages for how many lights to turn off. We replaced
  them with rules from published research and official guidance, so every number can be checked.
- **The AI being too timid.** With a vague prompt, the AI turned off only 4 windows. Now it gets tonight's rule,
  and the result is checked against it.
- **Reliability.** The Gemini quota ran out during the hackathon. Every step has a fallback, so the demo keeps
  working.

## Accomplishments we're proud of
- From a phone photo to lights switching off, in about [N] seconds.
- A glass campus building: 133 panes found; on a medium-migration night the AI turned off 57 of them (half the
  lit window area), an estimated **≥83% fewer bird collisions**.
- Every number on screen links to its source.

## What we learned
- Real night photos are messy; a method that works on one building can fail on the next.
- AI decisions need clear rules and a check afterwards, not just a good prompt.
- Being honest about what is measured and what is estimated makes the project stronger.

## What is real and what is estimated
- **Real:** the building photos; tonight's weather forecast; eBird sightings.
- **From published research:** tonight's rule and the collision estimate (Van Doren et al. 2021; Lights Out
  guidance).
- **Estimated:** tonight's migration level (weather-based, BirdCast's method, not radar; we link to BirdCast's
  radar for comparison). The collision estimate applies one Chicago building's result to other buildings; when
  more than half the lit area goes dark we only claim "at least" the measured result. Energy uses about 60 W per
  window for 8 hours at $0.17/kWh.
- **Our own model:** the per-window risk score (height, brightness, light color). It only decides which
  windows go first, not how many.
- **Simulated:** lights switch on a 3D model and an LED board, not real building controls. The same commands
  could drive a building management system or smart switches.

## What's next
- Use BirdCast radar data instead of our weather-based estimate.
- Connect to real building controls (BACnet) or smart plugs.
- Send building managers an automatic alert at sunset on high-risk nights.
- A campus map with every building's risk tonight.

## Built with
python, fastapi, opencv, numpy, gemini, bullsai, websockets, javascript, three.js, html, css, elevenlabs,
tiger-data, timescaledb, national-weather-service, open-meteo, ebird, esp32, wokwi, [vultr, caddy]
