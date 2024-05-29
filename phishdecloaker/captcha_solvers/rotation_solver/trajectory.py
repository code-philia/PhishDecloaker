import math
import random


class Trajectory:
    def __init__(self, start: int, end: int, top: int, bottom: int) -> None:
        """
        Humanlike mouse trajectory generator.

        Attributes:
            start: start x-position of trajectory
            end: end x-position of trajectory
            top: top-most y-position of trajectory
            bottom: bottom-most y-position of trajectory
        """
        self.ease_ins = [
            self._ease_in_quad,
            self._ease_in_cubic,
            self._ease_in_quint,
            self._ease_in_sine,
            self._ease_in_circ,
            self._ease_in_expo,
        ]

        self.ease_outs = [
            self._ease_out_quad,
            self._ease_out_cubic,
            self._ease_out_quint,
            self._ease_out_sine,
            self._ease_out_circ,
            self._ease_out_expo,
        ]

        self.start = start
        self.end = end
        self.top = top
        self.bottom = bottom
        self.dist = int(self.end - self.start)

        # Fitts Law
        self.a = 0
        self.b = 1
        self.width = 60
        self.interval = 0.015

        # Perlin noise
        self.slopes = [random.uniform(-1, 1) for _ in range(self.dist)]
        self.octaves = 4
        self.frequency = 1
        self.amplitude = 1

    def generate(self, steps: int) -> list[tuple[int, int]]:
        result = []

        u = random.betavariate(5, 5)
        change = self.start * u + self.end * (1 - u)
        ease_in = random.choice(self.ease_ins)
        ease_out = random.choice(self.ease_outs)

        n = self._fitts_law(self.dist)
        n1 = int(n * u)
        n2 = int(n * (1 - u))

        for i in range(n1 + 1):
            x = i / n1
            x = ease_in(x)
            x = change * x + self.start * (1 - x)
            v = self._perlin_noise(x)
            y = self.top * v + self.bottom * (1 - v)
            result.append((x, y))

        for i in range(n2 + 1):
            x = i / n2
            x = ease_out(x)
            x = self.end * x + change * (1 - x)
            v = self._perlin_noise(x)
            y = self.top * v + self.bottom * (1 - v)
            result.append((x, y))

        return result

    def _ease_in_quad(self, x: float) -> float:
        return x * x

    def _ease_in_cubic(self, x: float) -> float:
        return x * x * x

    def _ease_in_quint(self, x: float) -> float:
        return x * x * x * x * x

    def _ease_in_sine(self, x: float) -> float:
        return 1 - math.cos((x * math.pi) / 2)

    def _ease_in_circ(self, x: float) -> float:
        return 1 - math.sqrt(1 - math.pow(x, 2))

    def _ease_in_expo(self, x: float) -> float:
        return 0 if x == 0 else math.pow(2, 10 * x - 10)

    def _ease_out_quad(self, x: float) -> float:
        return 1 - (1 - x) * (1 - x)

    def _ease_out_cubic(self, x: float) -> float:
        return 1 - pow(1 - x, 3)

    def _ease_out_quint(self, x: float) -> float:
        return 1 - pow(1 - x, 5)

    def _ease_out_sine(self, x: float) -> float:
        return math.sin((x * math.pi) / 2)

    def _ease_out_circ(self, x: float) -> float:
        return math.sqrt(1 - math.pow(x - 1, 2))

    def _ease_out_expo(self, x: float) -> float:
        return 1 if x == 1 else 1 - math.pow(2, -10 * x)

    def _fitts_law(self, d: float) -> int:
        """
        Square-root variant of Fitts' Law that returns the number of points relative to
        target width and distance between mouse and target.

        Returns:
            Number of points to generate.
        """
        time = self.a + self.b * math.sqrt(d / self.width)
        return math.floor(time / self.interval) + 1

    def _perlin_noise(self, x: float) -> float:
        """
        1-dimensional noise generation with linear interpolation and smoothstep function.
        Frequency, amplitude, octaves can be adjusted.

        Returns:
            Noise in range [0, 1].
        """

        def _interpolate(x: float) -> float:
            lo = int(x)
            hi = lo + 1
            dist = x - lo
            lo_pos = self.slopes[lo % self.dist] * dist
            hi_pos = -self.slopes[hi % self.dist] * (1 - dist)
            u = (6 * dist**5) - (15 * dist**4) + (10 * dist**3)
            return lo_pos * (1 - u) + hi_pos * u

        frequency = self.frequency
        amplitude = self.amplitude
        result = 0
        for _ in range(self.octaves):
            result += _interpolate(x * frequency) * amplitude
            frequency *= 2
            amplitude /= 2

        return (result + 1) / 2