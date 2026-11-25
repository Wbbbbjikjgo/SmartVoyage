"""Unit tests for the slot filler."""

from core.slot_filler import SlotFiller, missing_slots, slot_present


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


def test_extract_small_city_train():
    """回归：商丘/洛阳这类地级市也应能识别（之前白名单太小导致失败）。"""
    filler = SlotFiller()
    slots = filler.fill_slots("搜索从商丘到洛阳的火车票", {})
    assert slots["departure"] == "商丘"
    assert slots["destination"] == "洛阳"


def test_extract_city_before_travel_keyword():
    """回归：「洛阳的酒店」这类无介词结构应能识别目的地。"""
    filler = SlotFiller()
    slots = filler.fill_slots("洛阳的酒店搜搜", {})
    assert slots["destination"] == "洛阳"


def test_extract_departure_strips_suffix():
    filler = SlotFiller()
    slots = filler.fill_slots("从商丘市到洛阳", {})
    assert slots["departure"] == "商丘"
    assert slots["destination"] == "洛阳"


def test_extract_flight_no():
    filler = SlotFiller()
    slots = filler.fill_slots("查一下 CA1234 这个航班", {})
    assert slots["flight_no"] == "CA1234"


def test_extract_hotel_name_with_verb_prefix():
    filler = SlotFiller()
    slots = filler.fill_slots("帮我查一下北京饭店的详情", {})
    assert slots["hotel_name"] == "北京饭店"


def test_extract_forecast_days_chinese_number():
    filler = SlotFiller()
    slots = filler.fill_slots("北京未来三天天气怎么样", {})
    assert slots["days"] == 3
    assert slots["duration"] == 3


def test_extract_labeled_check_in_check_out():
    filler = SlotFiller()
    slots = filler.fill_slots("8月20日入住，8月23日退房，住3晚", {})
    assert slots["check_in"].endswith("08-20")
    assert slots["check_out"].endswith("08-23")
    assert slots["duration"] == 3


def test_extract_direct_flight_max_segments():
    filler = SlotFiller()
    slots = filler.fill_slots("只要直飞航班", {})
    assert slots["max_segments"] == 1


def test_missing_slots_understands_aliases():
    # 火车的 start/end 可以来自 departure/destination
    slots = {"departure": "杭州", "destination": "北京"}
    assert missing_slots(slots, "search_trains") == []
    # 航班的 location 可以来自 destination
    assert missing_slots({"destination": "北京"}, "search_hotels") == []
    # 行程的 start_date 可以来自 date
    assert missing_slots(
        {"destination": "北京", "date": "2026-08-20", "duration": 3},
        "plan_itinerary",
    ) == []
    # 航班缺少日期时必须报告 date
    assert missing_slots({"departure": "北京", "destination": "上海"}, "search_flights") == ["date"]


def test_parse_answer_with_multiple_values_in_one_line():
    filler = SlotFiller()

    parsed = filler.parse_answer(
        "北京 上海 明天", ["departure", "arrival", "date"]
    )
    assert parsed["departure"] == "北京"
    assert parsed["arrival"] == "上海"
    assert parsed["date"]

    parsed = filler.parse_answer(
        "从北京到上海，明天", ["departure", "arrival", "date"]
    )
    assert parsed["departure"] == "北京"
    assert parsed["arrival"] == "上海"
    assert parsed["date"]

    parsed = filler.parse_answer(
        "北京 明天 3天", ["destination", "start_date", "duration"]
    )
    assert parsed["destination"] == "北京"
    assert parsed["start_date"]
    assert parsed["duration"] == 3


def test_extract_slot_value_for_short_follow_up():
    filler = SlotFiller()
    assert filler.extract_slot_value("location", "北京") == "北京"
    assert filler.extract_slot_value("departure", "从北京出发") == "北京"
    assert filler.extract_slot_value("flight_no", "MU5100") == "MU5100"
    assert filler.extract_slot_value("hotel_name", "北京饭店") == "北京饭店"
    assert filler.extract_slot_value("duration", "3天") == 3
    assert filler.extract_slot_value("date", "明天")
    assert slot_present({"destination": "北京"}, "location") is True
    assert slot_present({"guests": 2}, "passengers") is True
