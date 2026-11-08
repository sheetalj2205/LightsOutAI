# Lights Out AI: Pitch

## 2-minute pitch

**1. The problem (20 sec)**
Up to 1 billion birds die hitting U.S. buildings every year. Most of them migrate at night, and lit windows
pull them off course. On foggy, cloudy nights they fly lower, right into the glass.

**2. What exists today (20 sec)**
Cornell Lab's BirdCast already forecasts the big migration nights. Photometrics AI uses those forecasts to dim
**streetlights** automatically. But birds die at **buildings**, and for buildings the only option is a
"Lights Out" request that someone has to remember, every night, by hand. Nothing decides **which** windows to
turn off.

**3. Our solution (20 sec)**
Lights Out AI does it for buildings, window by window. Upload a photo of any building and type its address.
The app finds every lit window, checks tonight's weather, bird migration and eBird sightings, and AI turns off
the most dangerous lights first, and explains why.

**4. Demo (40 sec)**
*(Show Davis Hall.)* Tonight: fog, low clouds, a northwest tailwind, heavy migration.
- The app found **45 lit windows**.
- Heavy migration means the published rule is "every non-essential light off", so AI turned off **35**.
- The **lobby stays on** for people and safety. The **rooftop aircraft light stays on** too.
- Building risk drops from **0.44 to 0.08**. That's an estimated **83%+ fewer bird collisions**, plus
  **16.8 kWh** and about **$2.86** saved in one night.
- The lights switch off on a 3D model of the building, and on a real ESP32 LED building.

**5. Why you can trust it (10 sec)**
We don't make up how many lights go off. That comes from published rules: Audubon, BirdCast, NY DEC, and a
21-year study (Van Doren et al. 2021) that found halving lit windows cut collisions 6× to 11×. Every number on
screen links to its source.

**6. What's next (10 sec)**
Real BirdCast radar data, real building controls or smart plugs, and a campus map showing every building's risk
tonight. Lights Out shouldn't depend on someone remembering. Now it doesn't have to.

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
First, tonight's migration level sets how much goes off: all non-essential lights on heavy nights, at least
half the lit window area on medium nights, nothing required on light nights. Then each window gets a risk score
from how high it is, how bright it is, and how white its light is, plus fog and clouds. The highest-risk windows
go first. AI makes the choice, and we check its answer against tonight's rule.

**Why do higher floors go first?**
Higher windows can be seen from farther away, so they pull in more birds. The top floor scores about 1.7× the
bottom floor. Floor 1 (the lobby) never changes.

**Isn't it dangerous for airplanes to turn off lights on tall buildings?**
No. Aircraft warning lights are separate red or white flashing beacons on the roof, required by the FAA. We
never touch them, and Lights Out programs exempt them too. We only turn off window lights, which pilots don't
rely on.

**Doesn't Cornell already do this?**
Cornell's BirdCast gives the forecast. Photometrics AI uses it for streetlights. Nobody does it for building
windows. That's the gap we fill.

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
