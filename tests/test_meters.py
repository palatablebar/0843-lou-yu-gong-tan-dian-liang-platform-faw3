from app.catalog import SPEC
from app.domain.calculate import calculate_rows
from app.domain.decision import decide_rows
from app.domain.meters import HANDOVER_UNCLEAR, SEGMENT_OVERLAP, evaluate_room
from app.domain.prepare import prepare_rows
from tests.domain_cases import row


def meter(meter_id, room_id, start, end, frm=None, to=None, area="100", building="B1", main="300"):
    item = row(**{"building_id": building, "meter_id": meter_id, "room_id": room_id,
                  "area_m2": area, "start_reading": str(start), "end_reading": str(end),
                  "main_kwh": main})
    item["handover_from"] = "" if frm is None else str(frm)
    item["handover_to"] = "" if to is None else str(to)
    return item


def build(rows):
    items, issues = prepare_rows(rows)
    return decide_rows(calculate_rows(items)), issues


def test_single_meter_without_handover_keeps_legacy_behavior():
    results, issues = build([meter("M1", "R1", 0, 100, main="100")])
    assert issues == []
    assert results[0]["verdict"] == "PASS"
    assert results[0]["usage_mwh"] == 100000


def test_continuous_segments_are_both_counted_once():
    # 换表月：旧表 0–80、新表 80–150，首尾相接，用量 150 不能少算
    results, issues = build([meter("M10", "R10", 0, 80, 0, 80),
                             meter("M11", "R10", 0, 70, 80, 150)])
    assert issues == []
    item = results[0]
    assert item["verdict"] == "PASS"
    assert item["usage_mwh"] == 150000
    assert item["allocations"][0]["usage"] == 150000
    assert item["allocations"][0]["segments_ok"] is True


def test_area_is_counted_once_per_room_not_per_meter():
    # R10 两块表面积各 100，但分摊权重只能出现一次 100
    rows = [meter("M10", "R10", 0, 40, 0, 40, area="100", main="100"),
            meter("M11", "R10", 0, 40, 40, 80, area="100", main="100"),
            meter("M12", "R11", 0, 20, main="100", area="100")]
    results, _ = build(rows)
    item = results[0]
    assert item["verdict"] == "PASS"
    # 总表 100kWh，房间合计 100kWh，公摊为 0；权重不重复即面积只算一次
    assert item["common_mwh"] == 0
    assert [allocation["room"] for allocation in item["allocations"]] == ["R10", "R11"]


def test_overlapping_segments_block_even_when_balanced():
    # 两段 0–60 与 40–100 重叠 20kWh，总表恰好对平也不能签发
    rows = [meter("M12", "R12", 0, 60, 0, 60, main="120"),
            meter("M13", "R12", 0, 60, 40, 100, main="120")]
    results, _ = build(rows)
    item = results[0]
    assert item["metric"] == item["limit"]
    assert item["verdict"] == "REJECT"
    assert item["reason"] == SEGMENT_OVERLAP


def test_gap_between_segments_is_unclear_and_blocks():
    # 旧表 0–60、新表 70–130，中间 10kWh 缺口，交接说不清
    rows = [meter("M1", "R1", 0, 60, 0, 60, main="130"),
            meter("M2", "R1", 0, 60, 70, 130, main="130")]
    results, _ = build(rows)
    assert results[0]["verdict"] == "REJECT"
    assert results[0]["reason"] == HANDOVER_UNCLEAR


def test_missing_handover_in_multi_meter_room_blocks():
    rows = [meter("M1", "R1", 0, 60, 0, 60),
            meter("M2", "R1", 0, 60)]
    results, _ = build(rows)
    assert results[0]["verdict"] == "REJECT"
    assert results[0]["reason"] == HANDOVER_UNCLEAR


def test_segment_length_must_match_meter_difference():
    # 交接段写 0–80，表计差只有 60，记录与读数对不上
    rows = [meter("M1", "R1", 0, 60, 0, 80, main="80")]
    results, _ = build(rows)
    assert results[0]["verdict"] == "REJECT"
    assert results[0]["reason"] == HANDOVER_UNCLEAR


def test_incomplete_handover_is_isolated_at_prepare():
    items, issues = prepare_rows([meter("M1", "R1", 0, 60, frm=0, to=None)])
    assert items == []
    assert issues[0]["code"] == "HANDOVER_INCOMPLETE"


def test_backwards_handover_is_isolated_at_prepare():
    items, issues = prepare_rows([meter("M1", "R1", 0, 60, frm=80, to=20)])
    assert items == []
    assert issues[0]["code"] == "HANDOVER_BACKWARDS"


def test_conflicting_area_in_room_is_unclear():
    rows = [meter("M1", "R1", 0, 40, 0, 40, area="100"),
            meter("M2", "R1", 0, 40, 40, 80, area="120")]
    results, _ = build(rows)
    assert results[0]["verdict"] == "REJECT"
    assert results[0]["reason"] == HANDOVER_UNCLEAR


def test_evaluation_orders_segments_and_exposes_which_counts():
    rows = [meter("M11", "R1", 0, 70, 80, 150), meter("M10", "R1", 0, 80, 0, 80)]
    items, _ = prepare_rows(rows)
    evaluation = evaluate_room("R1", items)
    assert evaluation["problem"] is None
    assert [segment["meter_id"] for segment in evaluation["segments"]] == ["M10", "M11"]
    assert evaluation["usage_mwh"] == 150000


def test_breakdown_shows_each_segment_for_workbench():
    results, _ = build([meter("M10", "R10", 0, 80, 0, 80),
                        meter("M11", "R10", 0, 70, 80, 150)])
    text = "\n".join(results[0]["breakdown"])
    assert "M10 段 0–80000 Wh" in text
    assert "M11 段 80000–150000 Wh" in text


def test_clean_sample_handover_room_passes():
    from tests.domain_cases import run_profile
    results, _ = run_profile("clean")
    handover = [item for item in results
                if any(allocation["segments"] for allocation in item["allocations"])]
    assert handover and handover[0]["verdict"] == "PASS"


def test_dirty_sample_overlap_room_is_rejected_but_balanced():
    from tests.domain_cases import run_profile
    results, _ = run_profile("dirty")
    blocked = [item for item in results if item["reason"] == SEGMENT_OVERLAP]
    assert blocked and blocked[0]["metric"] == blocked[0]["limit"]
