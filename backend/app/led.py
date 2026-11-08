"""LED mode: shows the building on a small physical LED grid (ESP32 + NeoPixel strip).

The ESP32 connects to /ws?device=led&floors=5&cols=6. The real building (say 7 x 10 windows)
is mapped onto that smaller grid, and the board gets compact messages:
    {"type": "frame", "floors": 5, "cols": 6, "states": "OODF...", "colors": ["ffe6b4", ...]}
    {"led": 7, "state": "off"}
LED index = (floor - 1) * cols + (col - 1), floor 1 = bottom row. O = on, D = dim, F = off.
An LED that covers several windows shows the brightest of them.
"""
from dataclasses import dataclass, field

STATE_CODE = {"on": "O", "dim": "D", "off": "F"}
RANK = {"off": 0, "dim": 1, "on": 2}
COLOR_HEX = {"white": "ffe6b4", "yellow": "ffc060", "orange": "ff9030", "blue": "c8dcff",
             "red": "ff4030", "green": "a0ffa0"}
DEFAULT_HEX = "ffe6b4"  # warm white
MAX_LEDS = 300


@dataclass
class LedView:
    floors: int
    cols: int
    led_of: dict[int, int] = field(default_factory=dict)     # window id -> LED index
    win_state: dict[int, str] = field(default_factory=dict)  # window id -> on/dim/off
    win_color: dict[int, str] = field(default_factory=dict)
    shown: list[str] = field(default_factory=list)           # state each LED shows now

    def __post_init__(self) -> None:
        self.floors = max(1, min(self.floors, 50))
        self.cols = max(1, min(self.cols, MAX_LEDS // self.floors))
        self.shown = ["off"] * (self.floors * self.cols)

    def _led_state(self, led: int) -> str:
        states = [self.win_state[w] for w, i in self.led_of.items() if i == led]
        return max(states, key=RANK.get) if states else "off"

    def _led_color(self, led: int) -> str:
        lit = [w for w, i in self.led_of.items() if i == led and self.win_state[w] != "off"]
        return COLOR_HEX.get(self.win_color.get(lit[0], ""), DEFAULT_HEX) if lit else DEFAULT_HEX

    def load_building(self, msg: dict) -> dict:
        windows = [w for w in msg.get("windows", []) if w.get("face", "front") == "front"]  # LEDs = front side
        bf = max([w["floor"] for w in windows] + [1])
        bc = max([w["col"] for w in windows] + [1])
        self.led_of.clear(), self.win_state.clear(), self.win_color.clear()
        for w in windows:
            f = min(self.floors, (w["floor"] - 1) * self.floors // bf + 1)
            c = min(self.cols, (w["col"] - 1) * self.cols // bc + 1)
            self.led_of[w["id"]] = (f - 1) * self.cols + (c - 1)
            self.win_state[w["id"]] = w.get("state", "on")
            self.win_color[w["id"]] = w.get("color", "white")
        n = self.floors * self.cols
        self.shown = [self._led_state(i) for i in range(n)]
        return {"type": "frame", "floors": self.floors, "cols": self.cols,
                "states": "".join(STATE_CODE[s] for s in self.shown),
                "colors": [self._led_color(i) for i in range(n)]}

    def translate(self, msg: dict) -> list[dict]:
        """Turn a twin-page message into the LED messages this board needs."""
        if msg.get("type") == "building":
            return [self.load_building(msg)]
        if "type" not in msg and "id" in msg and msg.get("state") in RANK:
            wid = msg["id"]
            if wid not in self.led_of:
                return []
            self.win_state[wid] = msg["state"]
            led = self.led_of[wid]
            new = self._led_state(led)
            if new == self.shown[led]:
                return []
            self.shown[led] = new
            return [{"led": led, "state": new}]
        return []  # decisions / conditions: not shown on LEDs
