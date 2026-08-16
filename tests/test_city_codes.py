"""Unit tests for city code mappings."""

from mcp_servers.city_codes import city_to_adcode, city_to_iata, iata_to_city


def test_city_to_adcode():
    assert city_to_adcode("北京") == "110000"
    assert city_to_adcode("上海") == "310000"


def test_city_to_adcode_normalizes_suffix():
    assert city_to_adcode("北京市") == "110000"
    assert city_to_adcode("四川省成都市") == "510100"


def test_city_to_adcode_unknown():
    assert city_to_adcode("不存在的城市") is None


def test_city_to_iata():
    assert city_to_iata("北京") == "BJS"
    assert city_to_iata("上海") == "SHA"
    assert city_to_iata("广州") == "CAN"


def test_iata_to_city():
    assert iata_to_city("BJS") == "北京"
    assert iata_to_city("bjs") == "北京"


def test_city_to_iata_unknown():
    assert city_to_iata("火星") is None
