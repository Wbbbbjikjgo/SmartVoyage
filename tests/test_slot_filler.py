"""Unit tests for the slot filler."""

from core.slot_filler import SlotFiller


def test_extract_destination():
    filler = SlotFiller()
    slots = filler.fill_slots("我想从北京去上海玩", {})
    assert slots["departure"] == "北京"
    assert slots["destination"] == "上海"


def test_extract_duration():
    filler = SlotFiller()
    slots = filler.fill_slots("北京3日游", {})
    assert slots["duration"] == 3


def test_extract_guests():
    filler = SlotFiller()
    slots = filler.fill_slots("两个人去成都", {})
    assert slots["guests"] == 2


def test_extract_budget():
    filler = SlotFiller()
    slots = filler.fill_slots("预算5000元去三亚", {})
    assert slots["budget"] == 5000.0


def test_extract_date():
    filler = SlotFiller()
    slots = filler.fill_slots("8月20日去北京", {})
    assert slots["date"].endswith("08-20")


def test_high_speed_detection():
    filler = SlotFiller()
    slots = filler.fill_slots("杭州到北京的高铁", {})
    assert slots["is_high_speed"] == 1


def test_no_high_speed_detection():
    filler = SlotFiller()
    slots = filler.fill_slots("杭州到北京", {})
    assert "is_high_speed" not in slots
