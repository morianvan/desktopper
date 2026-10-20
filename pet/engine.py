"""Animation timing and movement; deliberately independent of Qt."""
from dataclasses import dataclass
import math
import random
from bisect import bisect_right
from functools import cached_property

ACTIONS = ("idle", "walk", "run", "knife", "jumppad")
DEFAULT_NEXT = {"stim": "run", "knife": "idle", "jumppad": "idle"}


@dataclass(frozen=True)
class Clip:
    frames: tuple[int, ...]
    fps: float
    next_state: str | None = None
    durations_ms: tuple[float, ...] = ()
    loop_start: int = 0
    exit_frames: tuple[int, ...] = ()

    @cached_property
    def ends(self):
        total = 0.0
        result = []
        for index in range(len(self.frames)):
            total += self.durations_ms[index] / 1000 if self.durations_ms else 1 / self.fps
            result.append(total)
        return tuple(result)

    @property
    def duration(self):
        return self.ends[-1]


class Animator:
    """One-shot clips consume their full duration, then transition without looping."""

    def __init__(self, clips: dict[str, Clip]):
        self.clips = clips
        self.state = "idle"
        self.elapsed = 0.0
        self.pending = None
        self.settling = False

    def _enter(self, state):
        self.state = state
        self.elapsed = 0.0

    def request(self, action: str) -> None:
        action = action.lower()
        if action not in ACTIONS or action not in self.clips:
            raise ValueError(f"Unknown action: {action}")
        if action == "run" and self.state in ("stim", "run"):
            self.pending = None
            return
        target = "stim" if action == "run" else action
        if target == self.state:
            self.pending = None
        elif self.state == "idle" and self.frame_position == 0 and not self.settling:
            self.pending = None
            self._enter(target)
        else:
            # Latest request wins; finish a safe pose instead of cutting an action in half.
            self.pending = action

    def advance(self, seconds: float) -> tuple[str, ...]:
        remaining = max(0.0, seconds)
        completed = []
        while remaining > 1e-10:
            clip = self.clips[self.state]
            index = self.frame_position
            until_boundary = max(0.0, clip.ends[index] - self.elapsed)
            if remaining + 1e-10 < until_boundary:
                self.elapsed += remaining
                break
            remaining = max(0.0, remaining - until_boundary)
            self.elapsed = clip.ends[index]
            successor = clip.next_state or DEFAULT_NEXT.get(self.state)
            safe_exit = index in (clip.exit_frames or (len(clip.frames) - 1,))
            if not successor and self.pending and safe_exit:
                action = self.pending
                if self.state in ("walk", "run") and action in ("knife", "jumppad", "run"):
                    # Come to rest before handling a prop or injecting Stim.
                    self._enter("idle")
                    self.settling = True
                else:
                    self.pending = None
                    self.settling = False
                    self._enter("stim" if action == "run" else action)
            elif index == len(clip.frames) - 1:
                if successor:
                    completed.append(self.state)
                    self._enter(successor)
                    self.settling = successor == "idle"
                else:
                    self.elapsed = clip.ends[clip.loop_start - 1] if clip.loop_start else 0.0
            elif self.state == "idle" and index == 0:
                self.settling = False
        return tuple(completed)

    @property
    def one_shot(self):
        return bool(self.clips[self.state].next_state or DEFAULT_NEXT.get(self.state))

    @property
    def frame_position(self) -> int:
        clip = self.clips[self.state]
        return min(bisect_right(clip.ends, self.elapsed + 1e-10), len(clip.frames) - 1)


def bounded_motion(x, y, dx, dy, speed, seconds, bounds):
    """Clamp and reflect at a screen's available work area, including negative origins."""
    left, top, right, bottom = bounds
    right, bottom = max(left, right), max(top, bottom)
    x += dx * speed * seconds
    y += dy * speed * seconds
    if x <= left:
        x, dx = left, abs(dx)
    elif x >= right:
        x, dx = right, -abs(dx)
    if y <= top:
        y, dy = top, abs(dy)
    elif y >= bottom:
        y, dy = bottom, -abs(dy)
    return x, y, dx, dy


class Behavior:
    def __init__(self, clips, movement, rng=None):
        self.animator = Animator(clips)
        self.movement = movement
        self.rng = rng or random.Random()
        self.auto = True
        self.dx, self.dy = 1.0, 0.0
        self.remaining = self._duration()
        self.velocity = 0.0

    def _duration(self):
        return self.rng.uniform(*self.movement["duration_seconds"])

    def choose(self, action):
        self.animator.request(action)
        self.remaining = self._duration()
        # Count the requested run's duration after the one-shot introduction.
        if self.animator.state == "stim":
            clip = self.animator.clips["stim"]
            self.remaining += clip.duration
        # Keep the ground direction stable while animations switch.
        self.dx = math.copysign(1.0, self.dx)
        self.dy = 0.0

    def advance(self, seconds):
        previous = self.animator.state
        completed = self.animator.advance(seconds)
        state = self.animator.state
        target_speed = self.movement.get(f"{state}_speed", 0) if state in ("walk", "run") else 0
        if self.animator.pending is not None:
            target_speed = 0
        if state not in ("walk", "run"):
            self.velocity = 0.0
        else:
            change = self.movement.get("acceleration", 900) * seconds
            self.velocity += max(-change, min(change, target_speed - self.velocity))
        if "knife" in completed or "jumppad" in completed:
            # Guarantee a full idle interval even if the random timer expired mid-action.
            self.remaining = self._duration()
            return
        if state != previous:
            self.remaining = self._duration()
        if self.auto:
            self.remaining -= seconds
            if self.remaining <= 0 and not self.animator.one_shot and self.animator.pending is None:
                current = self.animator.state
                choices = [s for s in ACTIONS if s != current and s in self.animator.clips]
                weights = self.movement.get("action_weights", {})
                self.choose(self.rng.choices(choices, weights=[weights.get(s, 1) for s in choices])[0])

    @property
    def speed(self):
        return self.velocity
