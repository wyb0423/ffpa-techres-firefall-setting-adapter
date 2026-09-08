#!/usr/bin/env python3
"""Executable design examples, NOT an interpreter or an engine/budget test.

Run: python3 scripts/check_aid_pool_model.py
Amounts are exact weekly quotes. Country eligibility is an explicit input;
innovation, AI, wars and default detection require separate engine validation.
"""
from fractions import Fraction as F
from pathlib import Path
from compact_script import parse, child


def check_innovation_script():
    """Evaluate the actual new script values with explicit modifier inputs.

    Fail on unsupported syntax; this does not simulate engine modifier queries
    or fixed-point rounding. Native calculations still need a save comparison.
    """
    root = Path(__file__).resolve().parents[1]
    values = {e.key: e.value for e in parse((root / 'common/script_values/ffpa_compact_aid_values.txt').read_text())}
    provider = 'ffpa_sc_aid_education_provider_modifier'
    modifiers = {e.key: e for e in parse((root / 'common/static_modifiers/zzzz_ffpa_survivor_compact.txt').read_text())}
    assert F(child(modifiers[provider], 'country_weekly_innovation_mult').value) == F('-0.10')
    assert F(child(modifiers[provider], 'country_weekly_innovation_max_add').value) == -30

    def evaluate(entries, inputs, active):
        result = F(0)
        for e in entries:
            if e.key == 'if':
                guard = child(e, 'limit').value
                assert len(guard) == 1 and guard[0].key == 'has_modifier'
                body = [x for x in e.value if x.key != 'limit']
                assert all(x.key == 'add' for x in body)
                if guard[0].value in active:
                    result += sum(F(x.value) for x in body)
                continue
            if isinstance(e.value, list):
                operand = evaluate(e.value, inputs, active)
            elif e.value.startswith('modifier:'):
                operand = inputs[e.value]
            else:
                operand = F(e.value)
            if e.key == 'value': result = operand
            elif e.key == 'add': result += operand
            elif e.key == 'multiply': result *= operand
            elif e.key == 'min': result = max(result, operand)  # Script lower bound.
            else: raise AssertionError(('Unsupported value operation', e.key))
        return result

    # base, other production bonuses, provider active, expected actual/eligible.
    cases = [
        (200, '0', False, 200, 200),
        (200, '0', True, 180, 200),
        (200, '0.20', True, 220, 240),
        (200, '-0.20', True, 140, 160),
        (100, '0', True, 90, 100),  # A real loss of production still matters.
        (0, '0.20', True, 0, 0),
        (200, '-0.95', True, 0, 10),  # Restore own penalty BEFORE the zero floor.
        (200, '-1.20', True, 0, 0),
    ]
    for base, other, providing, actual, eligible in cases:
        inputs = {
            'modifier:country_weekly_innovation_add': F(base),
            'modifier:country_weekly_innovation_mult': F(other) - (F('0.10') if providing else 0),
        }
        active = {provider} if providing else set()
        assert evaluate(values['ffpa_sc_aid_raw_innovation'], inputs, active) == actual
        assert evaluate(values['ffpa_sc_aid_eligibility_innovation'], inputs, active) == eligible
        # No cap is supplied: querying an upper-limit input would fail closed.


def settle(providers, quotes, reduced=()):
    """Return fee/effect/income maps for one pool and one eligibility snapshot."""
    if set(providers) & set(quotes):
        raise ValueError("A country cannot provide and receive in the same pool")
    if any(F(q) <= 0 for q in quotes.values()):
        raise ValueError("Weekly quotes must be positive")
    if not set(reduced) <= set(quotes):
        raise ValueError("Reduced participation requires an active recipient")
    if not providers or not quotes:
        return {}, {}, {}
    strength = (F(0), F(1, 2), F(3, 4), F(1))[min(len(providers), 3)]
    effects = {c: strength / (2 if c in reduced else 1) for c in quotes}
    fees = {c: F(q) * effects[c] for c, q in quotes.items()}
    weights = {c: max(F(0), F(p)) for c, p in providers.items()}
    if not sum(weights.values()):
        weights = dict.fromkeys(providers, F(1))
    total = sum(fees.values())
    total_weight = sum(weights.values())
    income = {c: total * w / total_weight for c, w in weights.items()}
    return fees, effects, income


def launch(month, providers, applicants):
    """No applicant is charged or given a retry date before actual launch."""
    if not providers or not applicants:
        return None, {}
    if set(providers) & set(applicants):
        raise ValueError("Invalid launch roles")
    return month + 36, {c: month + 60 for c in applicants}


def war_exit(providers, recipients, enemy_pairs):
    """Enemy pairs, not all war participants; allies/outside wars do not exit."""
    return {
        c: quote for c, quote in recipients.items()
        if not any(frozenset((c, p)) in enemy_pairs for p in providers)
    }


def check():
    # Full-rate pool, distribution by prestige; no dilution by recipients.
    providers = {"A": 600, "B": 300, "C": 100}
    fees, effects, income = settle(providers, {"X": 6000, "Y": 4000})
    assert income == {"A": 6000, "B": 3000, "C": 1000}
    assert sum(fees.values()) == sum(income.values()) == 10000
    assert effects == {"X": 1, "Y": 1}

    for count, strength in enumerate((F(0), F(1, 2), F(3, 4), F(1), F(1))):
        p = {f"P{i}": i for i in range(count)}
        fees, effects, income = settle(p, {"X": 1000})
        assert sum(fees.values()) == sum(income.values()) == 1000 * strength
        assert effects.get("X", 0) == strength
    fees, effects, income = settle({"A": 0, "B": -10}, {"X": 1000}, {"X"})
    assert fees["X"] == 375 and effects["X"] == F(3, 8)
    assert income == {"A": F(375, 2), "B": F(375, 2)}
    assert settle(providers, {}) == ({}, {}, {})
    assert settle({}, {"X": 1000}) == ({}, {}, {})
    try:
        settle({"A": 1}, {"A": 100})
    except ValueError:
        pass
    else:
        raise AssertionError("Self-payment accepted")

    # Month 0 vote -> month 3 resolution -> month 4 launch.
    # Registration is inside the nine-month parliament cooldown.
    vote_start = 0
    resolution = vote_start + 3
    signup_end = resolution + 1
    assert resolution + 9 == 12
    deadline, retry = launch(signup_end, providers, {"X": 1000, "Y": 2000})
    assert deadline == 40 and retry == {"X": 64, "Y": 64}
    assert launch(signup_end, providers, {}) == (None, {})
    assert launch(signup_end, {}, {"X": 1000}) == (None, {})

    # X's war removes X, not providers or unrelated Y; no past cash reversal.
    remaining = war_exit(providers, {"X": 1000, "Y": 2000}, {frozenset(("X", "A"))})
    assert remaining == {"Y": 2000}
    fees, effects, income = settle(providers, remaining)
    assert "X" not in fees and "X" not in effects
    assert sum(income.values()) == 2000
    assert retry["X"] == 64 and deadline == 40
    assert war_exit(providers, remaining, set()) == remaining  # Peace cannot restore X.
    assert war_exit(providers, remaining, {frozenset(("Y", "OUTSIDE"))}) == remaining
    remaining = war_exit(providers, remaining, {frozenset(("Y", "B"))})
    assert settle(providers, remaining) == ({}, {}, {})

    # A different category can reverse roles; accounts remain independent.
    a = settle({"A": 10}, {"X": 1000})
    b = settle({"X": 20}, {"A": 800})
    assert a[2] == {"A": 500} and b[2] == {"X": 400}
    assert settle({"A": 10}, {"X": 1000}) == a  # Repeat refresh is not additive.
    print("PASS: aid-pool design examples (not game-engine validation)")


if __name__ == "__main__":
    check_innovation_script()
    check()
