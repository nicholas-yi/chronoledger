"""Content-independent REAL2 CPU-duration and prompt-fit safeguards."""

from __future__ import annotations

import math


class SustainedCPU:
    def __init__(self) -> None:
        self.trace: list[dict] = []
        self.active = False
        self.high_since: float | None = None
        self.max_high_seconds = 0.0

    def activate(self) -> None:
        self.active = True
        self.high_since = None

    def add(self, start: float, end: float, percent: float, timestamp: str) -> bool:
        if (
            not all(math.isfinite(x) for x in (start, end, percent))
            or end <= start or not 0 <= percent <= 100
            or (self.trace and abs(start - self.trace[-1]["end_seconds"]) > 1e-6)
        ):
            raise ValueError("CPU trace requires contiguous, ordered finite intervals")
        row = {"start_seconds": start, "end_seconds": end, "timestamp_UTC": timestamp,
               "host_CPU_percent": percent, "phase": "generation" if self.active else "launch_wait"}
        self.trace.append(row)
        left = end - 60
        duration, weighted = 0.0, 0.0
        for interval in reversed(self.trace):
            if interval["end_seconds"] <= left:
                break
            weight = interval["end_seconds"] - max(left, interval["start_seconds"])
            duration += weight
            weighted += weight * interval["host_CPU_percent"]
        mean = weighted / duration if duration >= 60 - 1e-6 else None
        row["rolling_60second_mean_percent"] = mean
        if self.active and mean is not None and mean > 95:
            if self.high_since is None:
                self.high_since = end
            self.max_high_seconds = max(self.max_high_seconds, end - self.high_since)
        else:
            self.high_since = None
        row["consecutive_high_mean_seconds"] = (
            end - self.high_since if self.high_since is not None else 0.0
        )
        return self.active and row["consecutive_high_mean_seconds"] >= 120

    def summary(self) -> dict:
        seconds = sum(r["end_seconds"] - r["start_seconds"] for r in self.trace)
        return {
            "samples": len(self.trace), "sampled_seconds": seconds,
            "host_CPU_time_weighted_mean_percent": sum(
                (r["end_seconds"] - r["start_seconds"]) * r["host_CPU_percent"]
                for r in self.trace
            ) / seconds if seconds else None,
            "host_CPU_max_percent": max((r["host_CPU_percent"] for r in self.trace), default=None),
            "rolling_60second_mean_max_percent": max(
                (r["rolling_60second_mean_percent"] for r in self.trace
                 if r["rolling_60second_mean_percent"] is not None), default=None),
            "max_consecutive_seconds_rolling_mean_above95": self.max_high_seconds,
        }


def input_fit(encoded: bytes, options: dict) -> tuple[int, int, bool]:
    estimate = math.ceil(len(encoded) / 3)
    limit = options["num_ctx"] - options["num_predict"] - 256
    if limit <= 0:
        raise ValueError("invalid context/output/margin allocation")
    return estimate, limit, estimate <= limit


def truncation_reason(raw: dict, options: dict, log_sign: bool = False) -> str | None:
    message = raw.get("message")
    if (
        log_sign or raw.get("truncated") is True or raw.get("prompt_truncated") is True
        or (isinstance(message, dict) and message.get("truncated") is True)
    ):
        return "input_truncation_reported"
    prompt_count = raw.get("prompt_eval_count")
    if type(prompt_count) is not int or prompt_count < 0:
        return "prompt_eval_count_unverified"
    if prompt_count >= options["num_ctx"] - options["num_predict"]:
        return "prompt_eval_count_at_or_above_context_output_bound"
    if raw.get("done_reason") in ("length", "max_tokens") or (
        type(raw.get("eval_count")) is int and raw["eval_count"] >= options["num_predict"]
    ):
        return "output_token_limit_or_truncation"
    return None
