"""换表交接：同一房间多块表的有效段裁决。

每块表可以携带交接记录 ``handover_from`` / ``handover_to``，表示该表在房间
连续电量时间轴上覆盖的区间（kWh，累计坐标）。规则：

- 单表且无交接记录：按单表结算，保持旧行为。
- 房间有多块表时，每块表都必须携带交接记录，否则交接说不清。
- 交接段长度必须为正、与该表计差一致，且各段按起点排序后首尾相接：
  重叠说明同一时段被两块表各收一遍，缺口或对不上说明交接说不清。
- 交接说不清或段重叠都是阻断项，即使楼栋总量对平也不能签发。
"""
from collections import OrderedDict
from decimal import Decimal


SEGMENT_OVERLAP = "SEGMENT_OVERLAP"
HANDOVER_UNCLEAR = "HANDOVER_UNCLEAR"


def group_room_meters(items):
    rooms = OrderedDict()
    for item in items:
        rooms.setdefault(item["room_id"], []).append(item)
    return rooms


def _has_handover(meter):
    return meter.get("handover_from") is not None and meter.get("handover_to") is not None


def _segment(meter):
    start = int(meter["handover_from"] * 1000)
    end = int(meter["handover_to"] * 1000)
    return {"meter_id": meter["meter_id"], "from_mwh": start, "to_mwh": end,
            "usage_mwh": meter["usage_mwh"]}


def evaluate_room(room_id, meters):
    """返回房间裁决：有效段列表、合计用量（Wh）、阻断原因（可为空）。"""
    segments = [_segment(meter) for meter in meters if _has_handover(meter)]
    usage = sum(meter["usage_mwh"] for meter in meters)
    if len(meters) == 1 and not segments:
        return {"room_id": room_id, "segments": [], "usage_mwh": usage, "problem": None}
    if len(segments) != len(meters):
        return {"room_id": room_id, "segments": sorted(segments, key=lambda item: item["from_mwh"]),
                "usage_mwh": usage, "problem": HANDOVER_UNCLEAR}
    areas = {meter["area_m2"] for meter in meters}
    if len(areas) != 1:
        return {"room_id": room_id, "segments": segments, "usage_mwh": usage,
                "problem": HANDOVER_UNCLEAR}
    ordered = sorted(segments, key=lambda item: (item["from_mwh"], item["meter_id"]))
    problem = None
    for segment in ordered:
        if segment["from_mwh"] < 0 or segment["to_mwh"] <= segment["from_mwh"]:
            problem = HANDOVER_UNCLEAR
        if segment["to_mwh"] - segment["from_mwh"] != segment["usage_mwh"]:
            problem = HANDOVER_UNCLEAR
    if problem is None:
        for previous, current in zip(ordered, ordered[1:]):
            if current["from_mwh"] < previous["to_mwh"]:
                problem = SEGMENT_OVERLAP
                break
            if current["from_mwh"] != previous["to_mwh"]:
                problem = HANDOVER_UNCLEAR
                break
    return {"room_id": room_id, "segments": ordered, "usage_mwh": usage, "problem": problem}


def evaluate_building(items):
    return [evaluate_room(room_id, meters) for room_id, meters in group_room_meters(items).items()]
