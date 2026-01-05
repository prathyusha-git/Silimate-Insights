from specvalidator.core.ppa_validator import check_ppa

def test_ppa_pass():
    flags = check_ppa(
        {"target_power": 750, "target_freq": 2400, "target_area": 11},
        {"actual_power": 700, "actual_freq": 2500, "actual_area": 10},
    )
    assert flags.label == "PASS"

def test_ppa_fail_power():
    flags = check_ppa(
        {"target_power": 750, "target_freq": 2400, "target_area": 11},
        {"actual_power": 800, "actual_freq": 2500, "actual_area": 10},
    )
    assert "POWER" in flags.label

def test_ppa_fail_freq():
    flags = check_ppa(
        {"target_power": 750, "target_freq": 2400, "target_area": 11},
        {"actual_power": 700, "actual_freq": 2000, "actual_area": 10},
    )
    assert "FREQ" in flags.label

def test_ppa_fail_area():
    flags = check_ppa(
        {"target_power": 750, "target_freq": 2400, "target_area": 11},
        {"actual_power": 700, "actual_freq": 2500, "actual_area": 12},
    )
    assert "AREA" in flags.label

def test_ppa_multiple_fails():
    flags = check_ppa(
        {"target_power": 750, "target_freq": 2400, "target_area": 11},
        {"actual_power": 800, "actual_freq": 2000, "actual_area": 12},
    )
    assert flags.label.startswith("FAIL_")
