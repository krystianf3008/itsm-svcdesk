# ai-generated: 85% - Claude Code drafted the tests from every boundary named in slaclock.py's docstrings, I reviewed them
"""Tests for slaclock.py (Lab 5, Stretch 1). Every test calls the module inside a test function, never at import
time (a mutant that breaks a module-level call would otherwise be a collection error, not a kill - P-29 rule 5).
"""
from datetime import datetime

import pytest

import slaclock


# --- priority_of --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("impact,urgency,expected", [
    (1, 1, "P1"),
    (1, 2, "P2"), (2, 1, "P2"),
    (1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"),
    (2, 3, "P4"), (3, 2, "P4"), (3, 3, "P4"),
])
def test_priority_matrix(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency) == expected


def test_vip_floor_is_p2():
    assert slaclock.priority_of(3, 3, vip=True) == "P2"
    assert slaclock.priority_of(2, 3, vip=True) == "P2"


def test_vip_does_not_lower_p1_or_p2():
    assert slaclock.priority_of(1, 1, vip=True) == "P1"
    assert slaclock.priority_of(1, 2, vip=True) == "P2"


@pytest.mark.parametrize("impact,urgency", [(0, 1), (4, 1), (1, 0), (1, 4), (2.0, 1), (1, "1")])
def test_priority_of_rejects_out_of_range_or_wrong_type(impact, urgency):
    with pytest.raises(ValueError):
        slaclock.priority_of(impact, urgency)


def test_priority_of_rejects_bool_despite_being_an_int_subclass():
    # type(value) is not int excludes bool on purpose: True must not pass as impact or urgency 1.
    with pytest.raises(ValueError):
        slaclock.priority_of(True, 1)
    with pytest.raises(ValueError):
        slaclock.priority_of(1, True)


# --- targets -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("priority,expected", [
    ("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)), ("P4", (480, 4320)),
])
def test_targets(priority, expected):
    assert slaclock.targets(priority) == expected


@pytest.mark.parametrize("priority", ["p1", " P1", "P5", ""])
def test_targets_rejects_unknown_priority(priority):
    with pytest.raises(ValueError):
        slaclock.targets(priority)


# --- sla_state -----------------------------------------------------------------------------------------------

def test_sla_state_breached_is_strictly_past_target():
    assert slaclock.sla_state(16, 15) == "breached"


def test_sla_state_equality_is_not_a_breach():
    assert slaclock.sla_state(15, 15) == "warning"


@pytest.mark.parametrize("elapsed,expected", [(11, "ok"), (12, "warning"), (15, "warning")])
def test_sla_state_warning_threshold_on_target_15(elapsed, expected):
    # 75 % of 15 is 11.25: 11 is ok, 12 is warning (no rounding), matching the docstring exactly.
    assert slaclock.sla_state(elapsed, 15) == expected


def test_sla_state_zero_elapsed_is_ok():
    assert slaclock.sla_state(0, 100) == "ok"


@pytest.mark.parametrize("elapsed,target", [(-1, 10), (0, 0), (0, -1)])
def test_sla_state_rejects_invalid_arguments(elapsed, target):
    with pytest.raises(ValueError):
        slaclock.sla_state(elapsed, target)


# --- is_business_time -----------------------------------------------------------------------------------------

def test_business_time_monday_opening_is_inside():
    assert slaclock.is_business_time(datetime(2026, 11, 16, 8, 0)) is True  # a Monday


def test_business_time_one_minute_before_opening_is_outside():
    assert slaclock.is_business_time(datetime(2026, 11, 16, 7, 59)) is False


def test_business_time_one_minute_before_closing_is_inside():
    assert slaclock.is_business_time(datetime(2026, 11, 16, 15, 59)) is True


def test_business_time_closing_instant_is_outside():
    assert slaclock.is_business_time(datetime(2026, 11, 16, 16, 0)) is False


def test_business_time_saturday_is_outside_even_during_hours():
    assert slaclock.is_business_time(datetime(2026, 11, 14, 12, 0)) is False  # a Saturday


# --- add_business_minutes -------------------------------------------------------------------------------------

def test_add_business_minutes_zero_inside_hours_gives_start():
    start = datetime(2026, 11, 16, 10, 0)
    assert slaclock.add_business_minutes(start, 0) == start


def test_add_business_minutes_zero_outside_hours_gives_next_opening():
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 7, 0), 0) == datetime(2026, 11, 16, 8, 0)


def test_add_business_minutes_zero_on_weekend_gives_next_monday():
    assert slaclock.add_business_minutes(datetime(2026, 11, 14, 10, 0), 0) == datetime(2026, 11, 16, 8, 0)


def test_add_business_minutes_tie_at_closing_stays_same_day():
    # A full business day (8 h = 480 min) from opening ends exactly at closing, not at the next opening.
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 8, 0), 480) == datetime(2026, 11, 16, 16, 0)


def test_add_business_minutes_crosses_the_weekend():
    # Friday 15:00: 60 minutes to closing, then 60 more consumed from Monday's opening.
    assert slaclock.add_business_minutes(datetime(2026, 11, 20, 15, 0), 120) == datetime(2026, 11, 23, 9, 0)


def test_add_business_minutes_rejects_negative():
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(datetime(2026, 11, 16, 10, 0), -1)


def test_add_business_minutes_rejects_span_too_large():
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(datetime(2026, 11, 16, 8, 0), 10**8)


# --- business_minutes_between ----------------------------------------------------------------------------------

def test_business_minutes_between_same_instant_is_zero():
    moment = datetime(2026, 11, 16, 10, 0)
    assert slaclock.business_minutes_between(moment, moment) == 0


def test_business_minutes_between_rejects_end_before_start():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(datetime(2026, 11, 16, 10, 0), datetime(2026, 11, 16, 9, 0))


def test_business_minutes_between_rejects_span_too_large():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(datetime(2020, 1, 1), datetime(2030, 1, 1))


@pytest.mark.parametrize("start,minutes", [
    (datetime(2026, 11, 16, 8, 0), 0),
    (datetime(2026, 11, 16, 10, 0), 90),
    (datetime(2026, 11, 16, 8, 0), 480),
    (datetime(2026, 11, 20, 15, 0), 120),
    (datetime(2026, 11, 14, 10, 0), 240),
])
def test_business_minutes_between_is_the_inverse_of_add_business_minutes(start, minutes):
    due = slaclock.add_business_minutes(start, minutes)
    assert slaclock.business_minutes_between(start, due) == minutes


# --- escalation_tier -------------------------------------------------------------------------------------------

def test_escalation_tier_p3_p4_start_at_zero():
    assert slaclock.escalation_tier("P3", breached=False, reopens=0) == 0
    assert slaclock.escalation_tier("P4", breached=False, reopens=0) == 0


def test_escalation_tier_p1_p2_start_at_one():
    assert slaclock.escalation_tier("P1", breached=False, reopens=0) == 1
    assert slaclock.escalation_tier("P2", breached=False, reopens=0) == 1


def test_escalation_tier_breach_adds_one_and_p1_adds_another():
    assert slaclock.escalation_tier("P2", breached=True, reopens=0) == 2
    assert slaclock.escalation_tier("P1", breached=True, reopens=0) == 3


def test_escalation_tier_two_reopens_add_one():
    assert slaclock.escalation_tier("P4", breached=False, reopens=2) == 1
    assert slaclock.escalation_tier("P4", breached=False, reopens=1) == 0


def test_escalation_tier_capped_at_three():
    assert slaclock.escalation_tier("P1", breached=True, reopens=2) == 3


@pytest.mark.parametrize("priority,reopens", [("P5", 0), ("P1", -1)])
def test_escalation_tier_rejects_invalid_arguments(priority, reopens):
    with pytest.raises(ValueError):
        slaclock.escalation_tier(priority, breached=False, reopens=reopens)


# --- parse_duration --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445),
    ("1h59m", 119), ("0h60m", 60), (" 90m ", 90), ("60m", 60),
])
def test_parse_duration_valid(text, expected):
    assert slaclock.parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "0m", "1.5h", "30m1h", "-5m", "1 h", "1h60m"])
def test_parse_duration_rejects_invalid(text):
    with pytest.raises(ValueError):
        slaclock.parse_duration(text)
