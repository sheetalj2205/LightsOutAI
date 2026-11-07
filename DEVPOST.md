# Lights Out AI — Devpost write-up (draft, finalize Sunday)

> Fill in the [brackets] on Sunday. Keep the "What is real vs estimated" section as is: judges value honesty.

## Inspiration
Up to a billion birds die in building collisions in the US every year. Most of them migrate at night and are
drawn in by lit windows, especially on foggy, cloudy nights. Buffalo sits on a major migration route along
Lake Erie. "Lights Out" programs ask buildings to switch off lights during migration, but they rely on people
remembering, every night, for every window. We wanted a system that decides, window by window, automatically.

## What it does
1. **Sees the building.** It takes a real night photo of a UB building and finds every lit window, along with
   how bright it is and what color the light is.
2. **Reads the night.** It pulls tonight's Buffalo forecast from the National Weather Service (sky cover, fog,
   rain, wind) and estimates how many birds are migrating.
3. **Scores the risk.** Each window gets a risk score from 0 to 1: migration × sky danger × how attractive that
   window is to birds (brightness, cool vs warm light, height).
4. **Decides.** Gemini looks at the photo, the windows and the conditions, and picks which windows to turn off or
   dim, with a plain-English reason. Lobby lights always stay on.
5. **Acts.** The commands go over a WebSocket to a digital twin of the building, which switches the windows and
   confirms each one. A calm voice alert (ElevenLabs) tells building staff what was done.
6. **Shows the impact.** Risk before vs after, energy and money saved, and the real photo next to the same
   photo with the chosen windows darkened.

## How we built it
- **Backend (Python, FastAPI):** REST API + WebSocket command channel with confirmations.
- **Computer vision (OpenCV):** bright-region detection, shape filtering and row/column clustering to number
  windows by floor; a fallback that straightens the facade from 4 corner points and checks a floors × columns grid.
- **AI decision (Gemini [model]):** multimodal prompt (photo + window list + conditions) with a strict JSON
  answer, validated with Pydantic. If Gemini fails or returns bad JSON, a rule-based policy takes over, so the
  system never stops protecting birds.
- **Weather + migration:** National Weather Service API (free, no key) for Buffalo's hourly forecast.
- **Data:** every decision and every confirmed switch is logged to Tiger Data (TimescaleDB) as a time series.
- **Frontend:** [Sakshi: stack] — digital twin, live dashboard, before/after view, ElevenLabs voice.
- **Deployment:** Vultr Ubuntu server, Caddy (HTTPS) + systemd, [domain] via GoDaddy Registry.

## Challenges we ran into
- [Real night photos are messy: streetlights, reflections and glare look like windows. We tuned the brightness
  threshold per building and added size, shape and fill filters.]
- [Turning a blob list into floors and columns: we cluster window centers into rows and columns.]
- [Keeping the demo reliable: every external service (Gemini, Tiger Data, weather) has a fallback.]

## Accomplishments we're proud of
- A full loop from a real photo to windows switching off, in [N] seconds.
- [Davis Hall: N windows detected, risk cut from X to Y on a foggy migration night.]

## What we learned
[...]

## What is real vs estimated
- **Real:** night photos of UB buildings taken on [date]; tonight's Buffalo weather from the National Weather Service.
- **Estimated:** migration level, inferred from wind direction, precipitation and season (not radar counts);
  energy savings use ~60 W per lit window over 8 hours.
- **Simulated:** the lights switch on a digital twin of the building, not real building controls. The same
  WebSocket commands could drive a real building management system or smart switches.

## What's next
- Live migration forecasts (e.g. BirdCast radar) instead of the weather-based estimate.
- Connect to real building automation (BACnet) or smart plugs.
- Fixed cameras for nightly automatic checks across campus.

## Built with
python, fastapi, opencv, numpy, gemini, websockets, elevenlabs, tiger-data, timescaledb, postgresql, vultr, caddy, [frontend stack]
