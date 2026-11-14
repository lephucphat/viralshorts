"""Where a running job is, read from its log lines.

The pipeline reports itself only through logs. This is the one place that turns
them into ``{stage, percent, clips_ready}`` so the project list, the status
endpoint and the project page all say the same thing. The dashboard's
``JobProgress`` keeps its own copy of the same order for the page it is already
polling: keep the two in step.

Stage order matters: the furthest stage seen wins, so an earlier-stage line
repeated later (a retry) never moves the display backwards. Nothing is invented:
``percent`` is only set when the pipeline printed one.
"""
import re
from typing import Iterable, Optional

STAGES = ("download", "transcribe", "analyze", "render")

_TESTS = (
    re.compile(r"download|tải", re.I),
    re.compile(r"transcrib", re.I),
    re.compile(r"analy[sz]|shortlist|scoring window|found \d+ clips|local llm|gemini", re.I),
    re.compile(r"creating clip|clip \d+ ready|clip_ready", re.I),
)
_PERCENT = re.compile(r"transcribing….*?(\d+)%", re.I)
_READY = re.compile(r"clip \d+ ready", re.I)


def read(logs: Optional[Iterable[str]]) -> dict:
    lines = [str(line) for line in (logs or [])]
    stage = -1
    for line in lines:
        for i, test in enumerate(_TESTS):
            if i > stage and test.search(line):
                stage = i
    percent = None
    if stage == 1:
        for line in reversed(lines):
            m = _PERCENT.search(line)
            if m:
                percent = min(100, int(m.group(1)))
                break
    return {
        "stage": STAGES[stage] if stage >= 0 else "queued",
        "step": stage + 1,                     # 0 = queued, 1..4 = the stages
        "steps": len(STAGES),
        "percent": percent,
        "clips_ready": sum(1 for line in lines if _READY.search(line)),
    }
