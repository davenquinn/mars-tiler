from pydantic import BaseModel
from typing import List
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter


code_timer = ContextVar("code_timer", default=None)


class Timing(BaseModel):
    name: str
    delta: float
    total: float
    time: float


class Timer:
    timings: List[Timing] = []

    @classmethod
    def add_step(cls, name: str):
        timer = code_timer.get()
        if timer is None:
            return
        timer._add_step(name)

    def __init__(self):
        self.timings = [Timing(name="start", delta=0, total=0, time=perf_counter())]

    def _add_step(self, name: str) -> Timing:
        last_step = self.timings[-1]
        t = perf_counter()
        rec = Timing(
            name=name, delta=t - last_step.time, total=t - self.timings[0].time, time=t
        )
        self.timings.append(rec)
        return rec

    def server_timings(self):
        return ", ".join(
            [f"{t.name};dur={round(t.delta*1000, 1)}" for t in self.timings[1:]]
        )

    @contextmanager
    def context(self):
        token = code_timer.set(self)
        try:
            yield self
        finally:
            code_timer.reset(token)
