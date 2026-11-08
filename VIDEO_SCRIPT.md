# Lights Out AI: 2-Minute Video

Style: inspired by Cornell Lab's "Lights Out for Birds" animated short. A small songbird's night journey
frames the story, and the product demo sits in the middle. Soft, painterly animation for the bird scenes; clean
screen recordings for the demo.

Total: about 1:55. Narration is about 270 words (a calm pace of roughly 150 words per minute, with pauses).

---

## Script

### Scene 1: The journey (0:00 – 0:18) · animated
**Visual:** Night sky, moon, a tiny warbler flying over dark forest. Stars. Then a city glow appears on the
horizon.
**Sound:** Soft piano, wind, a single chirp.
**Narration (Voice A, warm, gentle):**
> [softly] Every spring and fall, billions of birds migrate at night... steering by the stars.
> [pause] But tonight, something brighter is on the horizon.

### Scene 2: The danger (0:18 – 0:35) · animated
**Visual:** Fog rolls in. The bird drops lower. A tall building with rows of lit windows. The bird circles,
confused, and heads toward the glass. Cut to black just before impact.
**Sound:** Music thins out. Low hum. A soft thud in silence.
**Narration:**
> [quietly] On foggy nights, birds fly lower... and lit windows pull them off course.
> [pause] In the U.S., up to one billion birds die hitting buildings every year.

### Scene 3: The gap (0:35 – 0:50) · animated / simple graphics
**Visual:** Streetlights dimming automatically along a road (label: "BirdCast + Photometrics AI"). Then a
building stays fully lit, with a sticky note on the switch: "Remember: Lights Out tonight!"
**Narration:**
> Streetlights can already dim themselves on big migration nights.
> But buildings? They still depend on someone remembering, every night, by hand.

### Scene 4: Meet Lights Out AI (0:50 – 1:00) · title card → screen recording
**Visual:** Logo "Lights Out AI". Then the app home screen.
**Sound:** Music lifts, more hopeful.
**Narration (Voice B, clear, confident; or keep Voice A):**
> [brighter] So we built Lights Out AI. It decides which windows go dark, one by one.

### Scene 5: Demo (1:00 – 1:35) · screen recording
**Visual + narration, beat by beat:**

| Time | On screen | Narration |
|------|-----------|-----------|
| 1:00 | Upload the Davis Hall photo, type the address | "Upload a photo of any building and type its address." |
| 1:06 | Window boxes appear on the photo: **45 lit windows** | "It finds every lit window: forty-five here." |
| 1:12 | Weather + migration panel: fog, low clouds, northwest tailwind, **heavy migration**, eBird sightings | "Then it checks tonight's weather, bird migration and nearby sightings. Tonight: fog, and heavy migration." |
| 1:20 | AI explanation; windows switch off on the 3D model, highest floors first; lobby and roof beacon stay lit | "AI turns off the most dangerous lights first: thirty-five windows. The lobby and the aircraft light stay on." |
| 1:28 | ESP32 LED building switching off (real footage) | "And it works on real hardware too." |
| 1:31 | Results card: **risk 0.44 → 0.08**, **83%+ fewer collisions**, **16.8 kWh**, **$2.86** saved | "Risk drops from point four four to point zero eight. That's over eighty percent fewer collisions, and energy saved too." |

### Scene 6: Why you can trust it (1:35 – 1:43) · screen recording
**Visual:** Click a number → its source citation (Audubon, BirdCast, Van Doren et al. 2021).
**Narration:**
> We don't guess. The rules come from published research, and every number links to its source.

### Scene 7: The ending (1:43 – 1:55) · animated
**Visual:** Same building, now mostly dark: lobby glowing, red beacon blinking on the roof. The warbler flies
past safely and joins its flock under the stars. Fade to logo + "Lights Out AI" + project link.
**Sound:** Opening piano theme returns, a happy chirp.
**Narration (Voice A):**
> [warmly] Lights Out shouldn't depend on someone remembering.
> [pause] Now... it doesn't have to.

---

## Narration only (paste into ElevenLabs)

Scene 1–3 (Voice A):
```
[softly] Every spring and fall, billions of birds migrate at night... steering by the stars.
[pause] But tonight, something brighter is on the horizon.

[quietly] On foggy nights, birds fly lower... and lit windows pull them off course.
[pause] In the U.S., up to one billion birds die hitting buildings every year.

Streetlights can already dim themselves on big migration nights.
But buildings? They still depend on someone remembering, every night, by hand.
```

Scene 4–6 (Voice B, or Voice A):
```
[brighter] So we built Lights Out AI. It decides which windows go dark, one by one.

Upload a photo of any building and type its address.
It finds every lit window: forty-five here.
Then it checks tonight's weather, bird migration and nearby sightings. Tonight: fog, and heavy migration.
AI turns off the most dangerous lights first: thirty-five windows. The lobby and the aircraft light stay on.
And it works on real hardware too.
Risk drops from point four four to point zero eight. That's over eighty percent fewer collisions, and energy saved too.

We don't guess. The rules come from published research, and every number links to its source.
```

Scene 7 (Voice A):
```
[warmly] Lights Out shouldn't depend on someone remembering.
[pause] Now... it doesn't have to.
```

---

## Final narration (as used in LightsOutAI-Video-FINAL.mp4, voice: Roger, Eleven v3)

The demo lines match the recorded building (24 windows, 16 lit, medium migration, 12 turned off).

| Time | On screen | Line |
|------|-----------|------|
| 0:31 | Home page | So, we built Lights Out AI. It decides which windows go dark, one by one. |
| 0:37 | Photo upload | Upload a photo of any building, with its lights on or off. |
| 0:41 | Analysis + 3D model | It finds sixteen lit windows, and builds the building in 3D. |
| 0:47 | Address | Then add its address. |
| 0:49 | Weather, migration, eBird | It checks tonight's weather and migration. Medium tonight, with fourteen species seen nearby. |
| 0:57 | Lights off, 83%+ | One click, and AI turns off the twelve riskiest windows. Over eighty percent fewer collisions. |
| — | *Hardware section, only in LightsOutAI-Video-with-Hardware.mp4 (1:05–1:52):* | |
| 1:05 | ESP32 boots, connects, LEDs light up | We built the hardware side too: an ESP32 driving a small LED building, simulated in Wokwi. It connects to Lights Out AI, and each LED lights up like a window in the photo. |
| 1:18 | Davis Hall photo, 3D model | Here it is live on Davis Hall in Buffalo. The app reads the photo and builds it in 3D. |
| 1:25 | Buffalo weather | Tonight in Buffalo: rain and low clouds, but low migration. |
| 1:30 | Click → result | One click. On a low-migration night, nothing has to go off, so the AI just dims ten of the riskiest windows. |
| 1:40 | Voice alert | And it tells building staff, out loud. *(then the app's own ElevenLabs alert plays)* |
| 1:05 | How much goes dark? | So how does it decide? Migration sets how much goes dark. Every non-essential light on heavy nights. At least half on medium nights, which a twenty-one-year study tied to six to eleven times fewer collisions. |
| 1:21 | Which windows first? | Only the windows lit in your photo are scored. Higher, brighter and whiter light scores higher, and fog raises them all. The riskiest go off first, the next are dimmed, and the lobby stays on. |
| 1:36 | Today vs. Cornell data | Today, we estimate migration from the weather. With Cornell's BirdCast radar data, we'd know how many birds are really flying. |
| 1:45 | Ending | Lights Out shouldn't depend on someone remembering. Now... it doesn't have to. |

---

## Image/video prompts for the animated scenes

Use one style line on every prompt so the scenes match:
**Style:** `soft painterly 2D animation, storybook style, deep blue night palette with warm yellow window glow, gentle film grain, 16:9`

1. **Journey:** "A tiny yellow warbler flying across a starry night sky over a dark forest, full moon, a faint
   orange city glow on the far horizon. [style]"
2. **Danger:** "Fog rolling over a city at night, a tall office building with rows of bright lit windows, a
   small warbler flying low and confused toward the glass. [style]"
3. **Gap A:** "A road at night with streetlights dimming one after another. [style]"
   **Gap B:** "A fully lit building at night, a sticky note on a light switch that says 'Lights Out tonight!' [style]"
4. **Ending:** "The same building at night, now mostly dark, only the lobby glowing and a red light blinking on
   the roof, a small warbler flying past safely to join a flock under the stars. [style]"

Make each image first, then animate it into a 5–8 second clip (image-to-video), so the bird and building stay
consistent.

---

## Screen recordings to capture (do this before ElevenLabs)

Record at 1920×1080 with QuickTime (File → New Screen Recording) or OBS:
1. Uploading the Davis Hall photo and typing the address
2. Windows being detected (boxes appearing)
3. The weather / migration / eBird panel
4. The AI explanation and the 3D model switching windows off
5. The results card (risk, collisions, kWh, $)
6. Clicking a number to show its source
7. Phone video of the ESP32 LED building switching off

Keep each clip a little longer than you need; you'll trim in ElevenLabs.

---

## Image-to-video motion prompts

Upload each image as the starting frame, then paste its prompt. Describe only motion, since the image already
sets the look. Length: 5–8 sec, 16:9.

**Clip 1: Journey (image 1, bird over forest)**
```
The small yellow warbler flaps its wings smoothly and glides slowly from left to right across the night sky.
Stars twinkle gently, thin clouds drift slowly, mist moves softly over the forest. The cabin window glows warmly.
Slow cinematic camera push-in toward the orange city glow on the horizon. Calm, peaceful, storybook animation.
Keep the bird's shape and colors consistent. No new objects, no text.
```

**Clip 2: Danger (image 2, bird near glass building)**
```
Thick fog swirls and drifts through the city. The small warbler flutters uncertainly in mid-air, then turns and
flies slowly toward the bright glowing glass windows on the right, drawn in by the light. Its reflection in the
glass grows closer. Slight handheld camera drift, tense and quiet mood. The bird does not hit the glass.
Keep the bird's shape consistent. No new objects, no text.
```

**Clip 3A: Streetlights dim (top panel of image 3)**
```
Static camera. Along the quiet street at night, the streetlamps dim and switch off one by one, starting from
the farthest lamp and moving toward the camera. Leaves sway gently in the breeze, the moon glows softly.
Calm, peaceful. No people, no cars, no text changes.
```

**Clip 3B: Building stays lit (bottom panel of image 3)**
```
Static camera. The building stays fully lit, every window glowing brightly. Leaves sway gently, the clock face
stays still, light flickers subtly in the lamps. Very slow camera push-in toward the sticky note on the light
switch. The note text stays unchanged and readable. No people.
```

**Clip 4: Ending (image 4, dark building, bird flies away)**
```
The small warbler flaps its wings and flies upward to the right, away from the dark glass building, joining the
flock of birds in the starry sky. The red aircraft beacon on the roof blinks slowly on and off. The lobby lights
stay warm and steady, the upper windows stay dark. Leaves and flowers sway gently, stars twinkle. Slow camera
tilt up toward the sky. Hopeful, peaceful mood. No new objects, no text.
```
