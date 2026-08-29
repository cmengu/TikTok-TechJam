"""Task adapters for synthetic and KuaiRand benchmarks."""

from __future__ import annotations

from harness.protocol import Protocol


def make_task(protocol: Protocol, *, n_impressions: int = 1_000_000):
    if protocol.task == "synthetic":
        from harness.tasks.synthetic import SyntheticTask

        return SyntheticTask(n_impressions=n_impressions)
    if protocol.task == "kuairand":
        from harness.tasks.kuairand import KuaiRandTask

        return KuaiRandTask()
    raise ValueError(f"unknown protocol.task: {protocol.task!r}")
