from datetime import date, timedelta
from app.catalog import SPEC
from app.domain.helpers import *  # noqa: F401,F403
from app.domain.meters import HANDOVER_UNCLEAR, SEGMENT_OVERLAP, evaluate_building


def _segment_lines(room_id, evaluation):
    if not evaluation["segments"]:
        return [f'{room_id} · 单表 {evaluation["usage_mwh"]} Wh']
    return [f'{room_id} · {segment["meter_id"]} 段 {segment["from_mwh"]}–{segment["to_mwh"]} Wh · 计 {segment["usage_mwh"]} Wh'
            for segment in evaluation["segments"]]


def calculate_rows(items):
    out = []
    buildings = {}
    for item in items:
        buildings.setdefault(item["building_id"], []).append(item)
    for building_id, rooms in buildings.items():
        first = rooms[0]
        room_evaluations = evaluate_building(rooms)
        room_area = {}
        for meter in rooms:
            room_area.setdefault(meter["room_id"], int(meter["area_m2"] * 100))
        usage = sum(evaluation["usage_mwh"] for evaluation in room_evaluations)
        common = first["main_mwh"] - usage
        weights = [room_area[evaluation["room_id"]] for evaluation in room_evaluations]
        shares = largest_remainder(max(0, common), weights)
        handover_problem = next((evaluation["problem"] for evaluation in room_evaluations
                                 if evaluation["problem"]), None)
        problem = handover_problem or (None if common >= 0 else "MAIN_UNDER_ROOMS")
        allocations = []
        breakdown = []
        for evaluation, share in zip(room_evaluations, shares):
            room_usage = evaluation["usage_mwh"]
            allocations.append({"room": evaluation["room_id"], "usage": room_usage,
                                "shared": share, "total": room_usage + share,
                                "segments": evaluation["segments"],
                                "segments_ok": evaluation["problem"] is None})
            breakdown.extend(_segment_lines(evaluation["room_id"], evaluation))
            breakdown.append(f'{evaluation["room_id"]} · 公摊 {share} Wh')
        out.append({"label": building_id, "main_kwh": D(str(first["main_mwh"] / 1000), "CALC"),
                    "usage_mwh": usage, "common_mwh": max(0, common), "allocations": allocations,
                    "breakdown": breakdown,
                    "problem": problem, "metric": D(str(first["main_mwh"] / 1000), "CALC"),
                    "limit": D(str((usage + max(0, common)) / 1000), "LIMIT")})
    for item in out:
        item.setdefault("label", str(item.get(SPEC["key"], "")))
    return out
