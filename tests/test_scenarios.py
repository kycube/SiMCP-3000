"""Scenario files: the script text format, text records, the IXF container and a whole .SNR written and read back
(no game needed; the shipped scenarios are read too when the game is installed)."""
import os

import pytest

from sc3k_mcp import ixf, scenarios as sc


def test_script_round_trip():
    ins = [{"name": "AddGoal", "args": [[0, 1], [0, -1169696760], [0, 141]]},
           {"name": "If", "args": []}, {"name": "GreaterThan", "args": [[0, 15], [1, 1]]},
           {"name": "Divide", "args": [[0, 5], [1, 5], [0, 187.33]]}]
    text = sc.format_script(ins)
    assert text.startswith("; Script Code\r\n 4 ")
    back = sc.parse_script(text)
    assert [b["name"] for b in back] == ["AddGoal", "If", "GreaterThan", "Divide"]
    assert back[0]["args"] == [[0, 1], [0, -1169696760], [0, 141]]
    assert back[3]["args"][2] == [0, 187.33]


def test_text_record():
    d = sc.text_record("Café %CITYNAME%")
    assert d[:4] == (15).to_bytes(4, "little") and sc.read_text_record(d) == "Café %CITYNAME%"


def test_ixf_round_trip():
    recs = [(1, 2, 3, b"abc"), (0x2026960B, 9, 1, b"\x01\x00\x00\x00x"), (5, 5, 5, b"")]
    assert ixf.read(ixf.build(recs)) == recs


def test_build_and_read(tmp_path):
    table = sc.table_id("Test")
    city = [(0x99F47014, 0x79F4702D, 0, b"city record"), (0x0525A6B9, 0x4525A6E2, 1, b"\x00" * 12)]
    scripts = {149: [{"name": "AddGoal", "args": [[0, 1], [0, sc.s32(table)], [0, 141]]}],
               150: [{"name": "GetPopulation", "args": [[0, 1]]}]}
    texts = {0: "A test scenario", 1: "Test", 141: "Reach 1000 people"}
    recs = sc.build(city, table, texts, scripts, 149, sc.ADVISORS["planner"], sc.picture("Test"), "base.sc3")
    p = tmp_path / "Test.SNR"
    ixf.write(str(p), recs)
    r = sc.read(str(p))
    assert r["name"] == "Test" and r["description"] == "A test scenario" and r["entry_script"] == 149
    assert r["picture"] == [163, 152] and r["city_records"] == 2
    assert r["scripts"]["149"][0]["name"] == "AddGoal"
    assert sc.listing(r["scripts"]["149"], table, {141: "Reach 1000 people"}) == ["AddGoal(1, text#141 'Reach 1000 people')"]


SHIPPED = sc.folder()


@pytest.mark.skipif(not os.path.isdir(SHIPPED), reason="no SimCity 3000 install (SC3K_GAME_DIR)")
def test_shipped_scenarios_parse():
    files = [f for f in os.listdir(SHIPPED) if f.lower().endswith(".snr") and not f.startswith("MCP")]
    assert len(files) >= 13
    for f in files:
        r = sc.read(f)
        assert r["scripts"] and r["entry_script"] and str(r["entry_script"]) in r["scripts"], f
        for v in r["scripts"].values():
            assert sc.parse_script(sc.format_script(v)) == v, f
