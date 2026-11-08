# YouTube upload: Lights Out AI

Video file: `Desktop/video-clips/LightsOutAI-Video-with-Hardware.mp4` (2:46)
Thumbnail: `Desktop/video-clips/LightsOutAI-thumbnail.png`

---

## Title (pick one, under 100 characters)

1. Lights Out AI: Turning Off the Right Windows to Save Migrating Birds
2. Lights Out AI: AI That Decides Which Building Lights Go Dark for Birds
3. Up to 1 Billion Birds Hit Buildings Each Year. Lights Out AI Helps Fix That.

---

## Description (copy everything between the lines)

---
Up to 1 billion birds die hitting U.S. buildings every year. Most migrate at night, and lit windows pull them off course, especially on foggy, cloudy nights. Streetlights can already dim themselves on big migration nights, but buildings still depend on someone remembering to turn the lights off.

Lights Out AI decides which windows go dark, one by one.

📸 Upload a photo of any building, with its lights on or off, and type its address.
🪟 It finds every lit window and builds the building in 3D.
🌧️ It checks tonight's weather, bird migration and nearby eBird sightings.
🌙 AI turns off the riskiest windows first, dims the next ones, and keeps the lobby on.
🔌 An ESP32 LED building (simulated in Wokwi) mirrors the building, and an ElevenLabs voice alert tells building staff what changed.

HOW IT DECIDES
• How much goes dark comes from published rules: on heavy migration nights, every non-essential light (Audubon, BirdCast, NY DEC Lights Out guidance). On medium nights, at least half the lit window area (Van Doren et al. 2021, PNAS: 6–11× fewer collisions over 21 years).
• Which windows go first comes from a risk score: higher floors, brighter light, and whiter light score higher, and fog, low clouds and migration raise them all.
• The AI picks the windows, and we check its answer against tonight's rule.

WHAT'S NEXT
Today we estimate migration from the weather forecast, using BirdCast's method. With Cornell Lab's BirdCast radar data, Lights Out AI would know how many birds are really flying, run on its own every night, and alert building managers.

CHAPTERS
0:00 Why birds hit buildings at night
0:31 Lights Out AI demo
1:05 Hardware: ESP32 LED building
1:53 How it decides which windows go dark
2:24 What's next: Cornell BirdCast data

BUILT WITH
Python, FastAPI, OpenCV, Gemini, JavaScript, Three.js, ESP32, Wokwi, ElevenLabs, eBird, National Weather Service, NOAA GFS (via Open-Meteo)

CREDITS
Animated scenes, images and voiceover created with ElevenLabs.
Migration estimate based on Cornell Lab of Ornithology's BirdCast method. Bird sightings from eBird.
Inspired by Cornell Lab's "Lights Out for Birds."

SOURCES
• Loss et al. 2014, The Condor: bird–building collisions in the U.S.
• Van Doren et al. 2021, PNAS: https://www.pnas.org/doi/10.1073/pnas.2101666118
• BirdCast Lights Out: https://birdcast.org/lights-out/

#LightsOut #BirdConservation #AI
---

---

## Tags (paste into the Tags box)

Lights Out AI, lights out for birds, bird collisions, bird migration, migratory birds, BirdCast, Cornell Lab of Ornithology, eBird, bird friendly buildings, light pollution, AI for good, conservation technology, ESP32, Wokwi, ElevenLabs, Gemini, computer vision, OpenCV, hackathon project, smart buildings

---

## Upload settings

| Setting | Choose |
|---------|--------|
| Thumbnail | Upload `LightsOutAI-thumbnail.png` |
| Audience | No, it's not made for kids |
| Visibility | Unlisted (anyone with the link can watch; good for Devpost) or Public |
| Category | Science & Technology |
| Video language | English |
| Captions | Turn on auto-captions, then check the spelling of "Wokwi" and "BirdCast" |
| Altered or synthetic content | Probably "No": the animation is clearly cartoon-style. If you're unsure, "Yes" is the safe choice. |
| Comments | On |

After uploading, paste the YouTube link into the "Video demo link" field on Devpost.
