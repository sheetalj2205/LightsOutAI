# Lights Out AI: Pitch

## 2-minute pitch

**1. The problem (20 sec)**
Up to 1 billion birds die hitting U.S. buildings every year. Most of them migrate at night, and lit windows pull them off course. On foggy, cloudy nights they fly lower, right into the glass.

**2. What exists today (20 sec)**
Cornell Lab's BirdCast already forecasts the big migration nights. Photometrics AI uses those forecasts to dim **streetlights** automatically. But birds die at **buildings**, and for buildings the only option is a "Lights Out" request that someone has to remember, every night, by hand. Nothing decides **which** windows to turn off.

**3. Our solution (20 sec)**
Lights Out AI does it for buildings, window by window. Upload a photo of any building and type its address. The app finds every lit window, checks tonight's weather, bird migration and eBird sightings, and AI turns off the most dangerous lights first, and explains why.

**4. Demo (40 sec)**
*(Show Davis Hall.)* Tonight: fog, low clouds, a northwest tailwind, heavy migration.
- The app found **45 lit windows**.
- Heavy migration means the published rule is "every non-essential light off", so AI turned off **35**.
- The **lobby stays on** for people and safety. The **rooftop aircraft light stays on** too.
- Building risk drops from **0.44 to 0.08**. That's an estimated **83%+ fewer bird collisions**, plus
  **16.8 kWh** and about **$2.86** saved in one night.
- The lights switch off on a 3D model of the building, and on a real ESP32 LED building.

**5. Why you can trust it (10 sec)**
We don't make up how many lights go off. That comes from published rules: Audubon, BirdCast, NY DEC, and a 21-year study (Van Doren et al. 2021) that found halving lit windows cut collisions 6× to 11×. Every number on screen links to its source.

**6. What's next (10 sec)**
Real BirdCast radar data, real building controls or smart plugs, and a campus map showing every building's risk tonight. Lights Out shouldn't depend on someone remembering. Now it doesn't have to.

---

## 30-second version

Up to 1 billion birds die hitting U.S. buildings every year, pulled in by lit windows at night. Streetlights
already dim automatically on big migration nights, but buildings still rely on someone remembering to turn
lights off. Lights Out AI fixes that: upload a photo of any building, and it finds every lit window, checks
tonight's weather and migration, and turns off the most dangerous lights first, following published Lights Out
rules. On Davis Hall it turned off 35 of 45 windows, for an estimated 83%+ fewer bird collisions, while the
lobby and aircraft lights stay on.

---

## Judge questions

**How do you choose which windows go off?**
First, tonight's migration level sets how much goes off: all non-essential lights on heavy nights, at least half the lit window area on medium nights, nothing required on light nights. Then each window gets a risk score
from how high it is, how bright it is, and how white its light is, plus fog and clouds. The highest-risk windows go first. AI makes the choice, and we check its answer against tonight's rule.

**Why do higher floors go first?**
Higher windows can be seen from farther away, so they pull in more birds. The top floor scores about 1.7× the bottom floor. Floor 1 (the lobby) never changes.

**Isn't it dangerous for airplanes to turn off lights on tall buildings?**
No. Aircraft warning lights are separate red or white flashing beacons on the roof, required by the FAA. We never touch them, and Lights Out programs exempt them too. We only turn off window lights, which pilots don't rely on.

**Doesn't Cornell already do this?**
Cornell's BirdCast gives the forecast. Photometrics AI uses it for streetlights. Nobody does it for building windows. That's the gap we fill.

**What's real and what's estimated?**
- **Real:** the photos, the weather forecast, eBird sightings.
- **Estimated:** tonight's migration (from weather, using BirdCast's method, not radar), the collision drop
  (from one Chicago study), and energy saved (about 60 W per window).
- **Simulated:** the lights switch on a 3D model and an LED board, not real building controls yet.

**Your risk weights: where do they come from?**
How much goes off comes from published research. The ranking uses known risk factors from bird-safety guidance
(height, white light, fog), with weights we chose.

**What if the AI fails?**
Gemini first, then UB's BullsAI, then a rule-based backup. The app always gives an answer.

**Why isn't it on a cloud server?**
We planned to use Vultr but hit a credits issue, so it runs on our laptop through a Cloudflare Tunnel. A server
would let it check migration at sunset every night and alert building managers by itself.

---

## Tech stack questions

**What's your tech stack, in one line?**
Python and FastAPI on the backend, OpenCV to find windows, Gemini to choose which ones go off, weather from the
National Weather Service and Open-Meteo, eBird for sightings, Three.js for the 3D model, an ESP32 LED building
(simulated in Wokwi), ElevenLabs for the voice alert and Tiger Data for the log.

**Why Python and FastAPI?**
The hard part is image processing, and Python has the best tools for it (OpenCV, NumPy). FastAPI is fast to build
with, gives us API docs for free at `/docs`, and handles photo uploads and WebSockets in the same server.

**Why OpenCV to find windows, and not just send the photo to the AI?**
We need exact pixel boxes for every window, the same answer every time, in under a second, for free. OpenCV gives
us that. AI models are good at judgment but can miscount or invent windows. We use Gemini only when OpenCV can't
work alone: on day photos, where no window is lit, Gemini counts the floors and windows.

**Why Gemini?**
It can look at the photo and read our window list and tonight's weather in one request, and reply in strict JSON
that our code can check. It also writes the one-to-two sentence reason for building staff. We set temperature 0 and
a fixed seed so the same building gets the same answer.

**Why not let the AI decide everything?**
How many lights go off is a rule from published research, not a guess. The AI picks which windows, then our code
checks its answer against tonight's rule, adds the riskiest windows if it turned off too few, and removes the lobby.

**Why BullsAI as a backup?**
It's UB's AI service, so it's a second, independent provider. When our Gemini quota ran out, it kept the app working.
If both fail, a rule-based backup decides, so a building never goes without an answer.

**Why the National Weather Service and Open-Meteo?**
Both are free and need no key. The NWS is the official U.S. forecast. Open-Meteo gives us NOAA's GFS model data
(low clouds, wind by height) and covers addresses outside the U.S., or steps in if the NWS is down.

**Why eBird?**
It's Cornell Lab's real bird sightings near the address. It shows which species are around tonight, so the alert
isn't only a weather guess.

**Why WebSockets?**
One decision has to reach several screens at once: the 3D model, the LED building and any open page. WebSockets
push it instantly, and the LED board sends back "ok" when its lights have changed, so we know it worked.

**Why Three.js?**
It shows a 3D model of the building in any browser, with nothing to install. Staff can see which windows went dark
on the building itself, not in a table.

**Why an ESP32, and why Wokwi?**
An ESP32 is a cheap board with built-in Wi-Fi, the same kind of part used in smart plugs and light controllers. It
shows the decision can control real hardware, not only a web page. We used Wokwi, an online ESP32 simulator,
so anyone can run the LED building without wiring a board, and it runs real ESP32 code.

**Why ElevenLabs?**
A security guard or building manager isn't always looking at a screen. ElevenLabs reads the AI's reason out loud in a
calm, natural voice. If there's no key, the page falls back to the browser's built-in voice.

**Why Tiger Data?**
Every window change is an event with a time, so a time-series database fits. Tiger Data (Timescale on Postgres) logs
each decision and each confirmation from the LED board. Over many nights, that history is what we'd compare against
collision counts to check our impact. If it's down, the app keeps running and skips the log.

**Why a Cloudflare Tunnel?**
It gives our laptop server a public HTTPS link for free, so judges and the LED board can reach it. On a real server
(we planned Vultr) the link would stay the same and the app could run every night on its own.

**What would you change to make it production-ready?**
A 24/7 server, BirdCast radar data instead of our estimate, real building controls or smart plugs instead of the LED
model, and logins for building managers.
