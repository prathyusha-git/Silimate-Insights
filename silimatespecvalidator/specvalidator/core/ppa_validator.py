from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


@dataclass
class PPAFlags:
    power_fail: bool
    freq_fail: bool
    area_fail: bool

    @property
    def label(self) -> str:
        fails = []
        if self.power_fail:
            fails.append("POWER")
        if self.freq_fail:
            fails.append("FREQ")
        if self.area_fail:
            fails.append("AREA")
        return "PASS" if not fails else "FAIL_" + "_".join(fails)


def check_ppa(target: Dict[str, float], actual: Dict[str, float]) -> PPAFlags:
    return PPAFlags(
        power_fail=actual["actual_power"] > target["target_power"],
        freq_fail=actual["actual_freq"] < target["target_freq"],
        area_fail=actual["actual_area"] > target["target_area"],
    )
