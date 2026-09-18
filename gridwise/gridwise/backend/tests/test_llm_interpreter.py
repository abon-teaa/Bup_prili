import pytest
from app.llm_interpreter import parse_time_window, fallback_rule_interpreter

def test_parse_time_window():
    h1 = parse_time_window("Cloud cover from 12 PM to 2 PM")
    assert h1 == [12, 13]

    h2 = parse_time_window("Reserve between 18:00 and 22:00")
    assert h2 == [18, 19, 20, 21]

    h3 = parse_time_window("No charging from 9 AM to 11 AM")
    assert h3 == [9, 10]

def test_fallback_rule_interpreter():
    res1 = fallback_rule_interpreter("Cloud cover will reduce solar generation by 30% from 12 PM to 2 PM.", 0, 200.0)
    assert res1["applies"] is True
    assert res1["directive_type"] == "solar_reduction"
    assert res1["structured_adjustment"]["hours"] == [12, 13]
    assert res1["structured_adjustment"]["factor"] == 0.7

    res2 = fallback_rule_interpreter("Do not charge battery from 17:00 to 21:00 due to peak grid tariff.", 1, 200.0)
    assert res2["applies"] is True
    assert res2["directive_type"] == "no_charge_window"
    assert res2["structured_adjustment"]["hours"] == [17, 18, 19, 20]

    res3 = fallback_rule_interpreter("Water the plants at the substation.", 2, 200.0)
    assert res3["applies"] is False
    assert res3["directive_type"] == "no_op"

def test_canonical_pdf_examples():
    # PDF Section 4.2 examples:
    ex1 = fallback_rule_interpreter("Solar output will drop to about 20% from 1 PM to 3 PM.", 0, 500.0)
    assert ex1["applies"] is True
    assert ex1["directive_type"] == "solar_reduction"
    assert ex1["structured_adjustment"]["hours"] == [13, 14]
    assert ex1["structured_adjustment"]["factor"] == 0.2

    ex2 = fallback_rule_interpreter("Do not charge the battery between 2 PM and 4 PM.", 1, 500.0)
    assert ex2["applies"] is True
    assert ex2["directive_type"] == "no_charge_window"
    assert ex2["structured_adjustment"]["hours"] == [14, 15]

    ex3 = fallback_rule_interpreter("Keep at least 120 kWh in reserve from 6 PM until 9 PM.", 2, 500.0)
    assert ex3["applies"] is True
    assert ex3["directive_type"] == "minimum_battery_reserve"
    assert ex3["structured_adjustment"]["hours"] == [18, 19, 20]
    assert ex3["structured_adjustment"]["minimum_energy_kwh"] == 120.0

    # PDF Section 11.4 variations:
    v1 = fallback_rule_interpreter("PV production will drop to about 20% between 13:00 and 15:00.", 0, 500.0)
    assert v1["directive_type"] == "solar_reduction"
    assert v1["structured_adjustment"]["hours"] == [13, 14]
    assert v1["structured_adjustment"]["factor"] == 0.2

    v2 = fallback_rule_interpreter("Panel washing from one until three will leave roughly one-fifth of normal solar output.", 0, 500.0)
    assert v2["directive_type"] == "solar_reduction"
    assert v2["structured_adjustment"]["hours"] == [13, 14]
    assert v2["structured_adjustment"]["factor"] == 0.2

    v3 = fallback_rule_interpreter("Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window.", 0, 500.0)
    assert v3["directive_type"] == "solar_reduction"
    assert v3["structured_adjustment"]["hours"] == [13, 14]
    assert v3["structured_adjustment"]["factor"] == 0.2

