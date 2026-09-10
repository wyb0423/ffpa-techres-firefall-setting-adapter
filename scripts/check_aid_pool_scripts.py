#!/usr/bin/env python3
"""Execute actual aid effects with bounded, explicit world inputs.

NOT a Victoria 3 interpreter: native scopes, macro expansion, fixed-point math,
modifier budget effects, eligibility and war callbacks need in-game validation.
"""
from fractions import Fraction as F
from pathlib import Path
import copy
import math
from compact_script import parse, child, walk

ROOT = Path(__file__).resolve().parents[1]
EFFECTS = {}
for filename in ('ffpa_compact_aid_pools.txt', 'ffpa_compact_aid_integration.txt'):
    source = (ROOT / 'common/scripted_effects' / filename).read_text()
    EFFECTS.update({e.key: source[e.start:e.end] for e in parse(source)})
VALUES = {e.key: e.value for e in parse((ROOT / 'common/script_values/ffpa_compact_aid_values.txt').read_text())}
TRIGGERS = {e.key: e.value for e in parse((ROOT / 'common/scripted_triggers/ffpa_compact_aid.txt').read_text())}


class World:
    def __init__(self):
        self.g, self.c, self.wars = {}, {}, set()
        self.month, self.operational = 0, True
        self.writes = 0
        self.events = []

    def country(self, name, ready=False, prestige=100, gdp=5200000):
        self.c[name] = dict(v={}, mods={}, expiry={}, member=True, eligible=True,
                            ready=ready, prestige=F(prestige), gdp=F(gdp), default=False,
                            ai=False, scaled_debt=F(0), net_fixed_income=F(2000),
                            gold_reserves=F(52000), construction=True, research='production',
                            literacy_rate=F('0.65'), schools=3)

    def number(self, value, country):
        if isinstance(value, list):
            result = F(0)
            taken = False
            for e in value:
                if e.key in ('if', 'else_if', 'else'):
                    if e.key == 'if': taken = False
                    if not taken and (e.key == 'else' or self.test(child(e, 'limit').value, country)):
                        body = [x for x in e.value if x.key != 'limit']
                        result += self.number(body, country)
                        taken = True
                    continue
                taken = False
                if e.key == 'floor':
                    assert e.value == 'yes'
                    result = F(math.floor(result))
                    continue
                n = self.number(e.value, country)
                if e.key == 'value': result = n
                elif e.key == 'add': result += n
                elif e.key == 'subtract': result -= n
                elif e.key == 'multiply': result *= n
                elif e.key == 'divide': result /= n
                elif e.key == 'min': result = max(result, n)
                else: raise AssertionError(('unsupported script value', e))
            return result
        if value.startswith('global_var:'): return self.g.get(value[11:], F(0))
        if value.startswith('var:'): return self.c[country]['v'].get(value[4:], F(0))
        if value in VALUES: return self.number(VALUES[value], country)
        if value in ('gdp', 'prestige', 'scaled_debt', 'net_fixed_income', 'gold_reserves', 'literacy_rate'):
            return self.c[country][value]
        return F(value)

    def test(self, nodes, country, previous=None):
        c = self.c.get(country)
        for e in nodes:
            k, v = e.key, e.value
            if k == 'OR': ok = any(self.test([n], country, previous) for n in v)
            elif k == 'NOT': ok = not self.test(v, country, previous)
            elif k == 'AND': ok = self.test(v, country, previous)
            elif k == 'any_country': ok = any(self.test(v, other, country) for other in self.c)
            elif k == 'has_variable': ok = v in c['v']
            elif k == 'has_global_variable': ok = v in self.g
            elif k == 'has_modifier': ok = v in c['mods']
            elif k == 'always': ok = v == 'yes'
            elif k == 'is_ai': ok = c['ai'] == (v == 'yes')
            elif k == 'institution_investment_level':
                assert child(e, 'institution').value == 'institution_schools'
                threshold = child(e, 'value')
                assert threshold.op == '>='
                ok = c['schools'] >= self.number(threshold.value, country)
            elif k == 'is_researching_technology_category': ok = c['research'] == v
            elif k == 'ffpa_sc_has_work': ok = c['construction'] == (v == 'yes')
            elif k.startswith('ffpa_sc_aid_') and k.endswith('_ready'):
                ok = c['ready'] == (v == 'yes')  # Explicit native eligibility input.
            elif k == 'has_war_with':
                assert v == 'prev'
                ok = frozenset((country, previous)) in self.wars
            elif k == 'is_at_war': ok = any(country in pair for pair in self.wars) == (v == 'yes')
            elif k == 'ffpa_sc_operational': ok = self.operational == (v == 'yes')
            elif k in ('ffpa_sc_member', 'ffpa_sc_eligible', 'in_default', 'test_ready'):
                field = {'ffpa_sc_member': 'member', 'ffpa_sc_eligible': 'eligible',
                         'in_default': 'default', 'test_ready': 'ready'}[k]
                ok = c[field] == (v == 'yes')
            elif k in TRIGGERS: ok = self.test(TRIGGERS[k], country, previous) == (v == 'yes')
            else:
                a, b = self.number(k, country), self.number(v, country)
                ok = {'=': a == b, '>': a > b, '<': a < b,
                      '>=': a >= b, '<=': a <= b, '!=': a != b}[e.op]
            if not ok: return False
        return True

    def run(self, key, country=None, **params):
        source = EFFECTS[key]
        for name, value in params.items(): source = source.replace(f'${name}$', str(value))
        assert '$' not in source, ('unbound effect argument', key)
        self.execute(parse(source)[0].value, country)

    def execute(self, nodes, country):
        taken = False
        for e in nodes:
            k, v = e.key, e.value
            if k in ('if', 'else_if', 'else'):
                if k == 'if': taken = False
                if not taken and (k == 'else' or self.test(child(e, 'limit').value, country)):
                    self.execute([x for x in v if x.key != 'limit'], country)
                    taken = True
                continue
            taken = False
            if k in ('every_country', 'ordered_country'):
                limits = [x for x in v if x.key == 'limit']
                names = [n for n in sorted(self.c) if not limits or self.test(limits[0].value, n, country)]
                if k == 'ordered_country':
                    order = child(e, 'order_by').value
                    names.sort(key=lambda n: self.number(order, n), reverse=True)
                    names = names[:int(child(e, 'max').value)]
                for n in names:
                    self.execute([x for x in v if x.key not in ('limit', 'order_by', 'max', 'check_range_bounds')], n)
            elif k in EFFECTS:
                self.run(k, country, **({} if v == 'yes' else {x.key: x.value for x in v}))
            elif k == 'trigger_event':
                assert v == 'ffpa_sc.6'  # Delivery/presentation needs the real engine.
                self.events.append((country, v))
            elif k in ('set_global_variable', 'set_variable'):
                fields = {'name': v} if isinstance(v, str) else {x.key: x.value for x in v}
                target = self.g if k == 'set_global_variable' else self.c[country]['v']
                target[fields['name']] = self.number(fields.get('value', '1'), country)
                if 'years' in fields:
                    self.c[country]['expiry'][fields['name']] = self.month + 12 * int(fields['years'])
            elif k in ('change_global_variable', 'change_variable'):
                fields = {x.key: x.value for x in v}
                target = self.g if k == 'change_global_variable' else self.c[country]['v']
                name = fields.pop('name')
                assert name in target, ('change absent variable', name)
                for op, value in fields.items():
                    n = self.number(value, country)
                    if op == 'add': target[name] += n
                    elif op == 'subtract': target[name] -= n
                    elif op == 'multiply': target[name] *= n
                    else: raise AssertionError(('unsupported variable operation', op))
            elif k in ('remove_global_variable', 'remove_variable'):
                (self.g if k == 'remove_global_variable' else self.c[country]['v']).pop(v, None)
                if k == 'remove_variable': self.c[country]['expiry'].pop(v, None)
            elif k == 'add_modifier':
                fields = {'name': v} if isinstance(v, str) else {x.key: x.value for x in v}
                assert fields['name'] not in self.c[country]['mods'], ('duplicate add', fields['name'])
                self.c[country]['mods'][fields['name']] = self.number(fields.get('multiplier', '1'), country)
                self.writes += 1
            elif k == 'remove_modifier':
                assert v in self.c[country]['mods'], ('unguarded removal', v)
                del self.c[country]['mods'][v]
                self.writes += 1
            else: raise AssertionError(('unsupported effect', k))

    def tick(self, args):
        self.month += 1
        for c in self.c.values():
            for key, date in list(c['expiry'].items()):
                if date <= self.month:
                    c['v'].pop(key, None)
                    del c['expiry'][key]
        self.run('ffpa_sc_aid_tick_pool', **args)


def check():
    assert not (set(VALUES) & set(TRIGGERS)), 'Value/trigger name collision can recurse'
    # The budget contract depends on the real modifier definitions as well as
    # the allocation multipliers. Do not silently validate just the ledger.
    modifiers = {e.key: e for e in parse((ROOT / 'common/static_modifiers/zzzz_ffpa_survivor_compact.txt').read_text())}
    assert child(modifiers['ffpa_sc_aid_fee_modifier'], 'country_expenses_add').value == '1'
    for pool in ('education', 'talent', 'production', 'society', 'military'):
        assert child(modifiers[f'ffpa_sc_aid_{pool}_income_modifier'], 'country_tax_income_add').value == '1'
    debug = parse((ROOT / 'common/scripted_effects/ffpa_compact_aid_debug.txt').read_text())
    allowed = {'debug_log', 'if', 'limit', 'has_variable', 'has_modifier',
               'ffpa_sc_aid_debug_pool', 'POOL'}
    assert all(e.key in allowed for effect in debug for e in walk(effect.value)), 'Debug probe must be read-only'
    assert {e.value[0].value for e in debug[0].value if e.key == 'ffpa_sc_aid_debug_pool'} == {
        'education', 'talent', 'production', 'society', 'military'}
    for path in (ROOT / 'common').rglob('*.txt'):
        if path.name != 'ffpa_compact_aid_debug.txt':
            assert 'ffpa_sc_aid_debug' not in path.read_text(encoding='utf-8-sig'), 'Debug probe must stay manual'
    settle = parse(EFFECTS['ffpa_sc_aid_settle_pool'])[0]
    fee_add = next(e for e in walk(settle.value) if e.key == 'add_modifier' and isinstance(e.value, list) and child(e, 'name').value == 'ffpa_sc_aid_fee_modifier')
    income_add = next(e for e in walk(settle.value) if e.key == 'add_modifier' and isinstance(e.value, list) and child(e, 'name').value == '$INCOME$')
    assert child(fee_add, 'multiplier').value == 'var:ffpa_sc_aid_paid_fee'
    assert child(income_add, 'multiplier').value == 'var:ffpa_sc_aid_$POOL$_paid_income'
    for pool in 'education talent production society military'.split():
        assert f'ffpa_sc_aid_{pool}_income_multiplier' not in VALUES
    main = {e.key: e for e in parse((ROOT / 'common/scripted_effects/ffpa_survivor_compact.txt').read_text())}
    pulse = list(walk(main['ffpa_sc_monthly'].value))
    tick = next(e.start for e in pulse if e.key == 'ffpa_sc_aid_tick_all')
    resolve = next(e.start for e in pulse if e.key == 'ffpa_sc_resolve_vote')
    assert tick < resolve  # Newly passed registrations retain their full month.
    assert any(e.key == 'ffpa_sc_aid_open_by_vote' for e in walk(main['ffpa_sc_resolve_vote'].value))
    assert any(e.key == 'ffpa_sc_aid_withdraw_current' for e in walk(main['ffpa_sc_stop_task'].value))
    assert any(e.key == 'ffpa_sc_aid_refresh_all' for e in walk(main['ffpa_sc_leave'].value))
    hooks = {e.key: e for e in parse((ROOT / 'common/on_actions/ffpa_survivor_compact.txt').read_text())}
    for name in ('on_diplo_play_war_start', 'on_diplo_play_join_side', 'on_diplo_play_switch_sides'):
        assert any(e.key == 'ffpa_sc_aid_war_refresh' for e in walk(hooks[name].value))
    assert not any(e.key == 'ffpa_sc_aid_tick_all' for e in walk(hooks['ffpa_sc_aid_war_refresh'].value))
    # Category thresholds and modifier semantics are deliberately explicit inputs.
    args = dict(POOL='education', ID='4', READY='test_ready', BENEFIT='test_benefit',
                BENEFIT_ALT='test_benefit_alt', COST='test_provider_cost', INCOME='test_income')
    fee = 'ffpa_sc_aid_fee_modifier'
    phase = 'ffpa_sc_aid_education_phase'
    months = 'ffpa_sc_aid_education_months'

    def setup(providers=3):
        w = World()
        for name, prestige in list(zip('ABC', (600, 300, 100)))[:providers]:
            w.country(name, ready=True, prestige=prestige)
        w.country('X')
        w.country('Y')
        w.run('ffpa_sc_aid_open_registration', **args)
        return w

    def register(w, name):
        w.run('ffpa_sc_aid_register', name, RATE='0.01', **args)

    def income(w): return sum(c['mods'].get('test_income', 0) for c in w.c.values())

    w = setup()
    register(w, 'A')  # Provider cannot self-register.
    assert not w.c['A']['v'].get('ffpa_sc_aid_kind')
    register(w, 'X')
    assert not w.c['X']['mods'] and not w.c['X']['expiry']
    assert w.c['X']['v']['ffpa_sc_aid_quote'] == 1000
    w.c['X']['gdp'] *= 2
    register(w, 'X')  # Cannot re-sign to alter a quote or task.
    assert w.c['X']['v']['ffpa_sc_aid_quote'] == 1000
    w.tick(args)
    assert w.g[phase] == 2 and w.g[months] == 36
    assert w.c['X']['expiry']['ffpa_sc_works_retry'] == 61
    assert w.c['X']['mods'] == {fee: 1000, 'test_benefit': 1}
    assert [w.c[n]['mods']['test_income'] for n in 'ABC'] == [600, 300, 100]
    before = copy.deepcopy(w.c)
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert w.c == before  # Rebuilding modifiers must not stack or reset contracts.

    # A pre-upgrade recipient without a persisted quote must heal on refresh.
    del w.c['X']['v']['ffpa_sc_aid_quote']
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert w.c['X']['v']['ffpa_sc_aid_quote'] == 1200
    assert w.c['X']['mods'][fee] == income(w) == 1200
    w.c['X']['v']['ffpa_sc_aid_quote'] = 1000
    w.run('ffpa_sc_aid_settle_pool', **args)
    register(w, 'Y')
    assert not w.c['Y']['v'].get('ffpa_sc_aid_kind')  # No late admission.
    w.c['X']['ready'] = True
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert 'ffpa_sc_aid_education_provider' not in w.c['X']['v']

    w.c['C']['member'] = False
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert w.c['X']['mods'][fee] == 750 and income(w) == 750
    assert not w.c['C']['mods']
    w.c['B']['ready'] = False
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert w.c['X']['mods'][fee] == 500 and income(w) == 500
    w.run('ffpa_sc_aid_reduce', 'X', **args)
    assert 'ffpa_sc_aid_reduced' not in w.c['X']['v']  # Too early.
    for _ in range(12): w.tick(args)
    w.run('ffpa_sc_aid_reduce', 'X', **args)
    assert w.c['X']['mods'] == {fee: 250, 'test_benefit': F(1, 4)}
    w.run('ffpa_sc_aid_reduce', 'X', **args)
    assert w.c['X']['mods'][fee] == 250  # Cannot halve repeatedly.
    assert w.c['X']['expiry']['ffpa_sc_works_retry'] == 61
    for _ in range(24): w.tick(args)
    assert phase not in w.g and all(not c['mods'] for c in w.c.values())
    assert w.c['X']['expiry']['ffpa_sc_works_retry'] == 61

    for count in (0, 1):
        empty = setup(count)
        empty.tick(args)
        assert phase not in empty.g
        assert all(not c['mods'] and not c['expiry'] for c in empty.c.values())

    w = setup()
    register(w, 'X'); register(w, 'Y'); w.tick(args)
    original_retry = copy.deepcopy(w.c['X']['expiry'])
    w.wars.add(frozenset(('X', 'A')))
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert not w.c['X']['mods'] and w.c['X']['expiry'] == original_retry
    assert w.c['Y']['mods'][fee] == income(w) == 1000
    w.wars.clear()
    w.run('ffpa_sc_aid_settle_pool', **args)
    register(w, 'X')
    assert not w.c['X']['mods']
    w.c['Y']['default'] = True
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert phase not in w.g and all(not c['mods'] for c in w.c.values())

    w = setup()
    for name in 'ABC': w.c[name]['prestige'] = 0
    register(w, 'X'); w.tick(args)
    assert [w.c[n]['mods']['test_income'] for n in 'ABC'] == [F('333.34'), F('333.33'), F('333.33')]
    assert income(w) == w.c['X']['mods'][fee]
    w.run('ffpa_sc_aid_withdraw', 'X', **args)
    assert all(not c['mods'] for c in w.c.values())
    w.run('ffpa_sc_aid_withdraw', 'X', **args)  # Repeated cleanup is harmless.

    # Existing engineering cooldown and task reservations also block enrolment.
    w = setup()
    w.c['X']['v']['ffpa_sc_works_retry'] = 1
    w.c['Y']['v']['ffpa_sc_task'] = 3
    register(w, 'X'); register(w, 'Y'); w.tick(args)
    assert phase not in w.g and w.c['Y']['v']['ffpa_sc_task'] == 3

    w = setup()
    register(w, 'X'); w.tick(args)
    for n in 'ABC': w.c[n]['ready'] = False
    w.run('ffpa_sc_aid_settle_pool', **args)
    assert phase not in w.g and all(not c['mods'] for c in w.c.values())
    assert w.c['X']['expiry']['ffpa_sc_works_retry'] == 61

    # Two live pools: closing one cannot remove the other pool's budget/cost.
    w = setup()
    register(w, 'X'); w.tick(args)
    other = dict(args, POOL='talent', ID='5', BENEFIT='talent_benefit',
                 BENEFIT_ALT='talent_benefit_alt', COST='talent_cost', INCOME='talent_income')
    w.run('ffpa_sc_aid_open_registration', **other)
    w.run('ffpa_sc_aid_register', 'Y', RATE='0.01', **other)
    w.tick(other)
    w.run('ffpa_sc_aid_withdraw', 'X', **args)
    assert w.c['Y']['mods'] == {fee: 1000, 'talent_benefit': 1}
    assert sum(w.c[n]['mods']['talent_income'] for n in 'ABC') == 1000
    assert all(w.c[n]['mods']['talent_cost'] == 1 for n in 'ABC')
    assert all('test_income' not in c['mods'] for c in w.c.values())
    # Concrete wrappers and AI use real rates/triggers, with eligibility injected.
    w = World()
    w.country('A', ready=True, prestige=600)
    w.country('B', ready=True, prestige=300)
    w.country('C', ready=True, prestige=100)
    w.country('X'); w.c['X']['ai'] = True
    w.run('ffpa_sc_aid_talent_open')
    w.run('ffpa_sc_aid_ai_register', 'X')
    assert w.c['X']['v']['ffpa_sc_aid_quote'] == 400
    w.month = 1
    w.run('ffpa_sc_aid_tick_all')
    assert w.g['ffpa_sc_aid_talent_months'] == 36
    assert w.c['X']['mods']['ffpa_sc_aid_talent_benefit_modifier'] == 1
    assert w.c['X']['mods'][fee] == 400
    assert [w.c[n]['mods']['ffpa_sc_aid_talent_income_modifier'] for n in 'ABC'] == [240, 120, 40]
    for _ in range(12):
        w.month += 1
        w.run('ffpa_sc_aid_tick_all')
    w.c['X']['scaled_debt'] = F('0.5')
    w.run('ffpa_sc_aid_notify_review', 'X')
    assert w.c['X']['mods'][fee] == 200
    assert w.c['X']['v']['ffpa_sc_aid_reviewed'] == 1
    w.run('ffpa_sc_aid_notify_review', 'X')
    assert w.c['X']['mods'][fee] == 200
    w.run('ffpa_sc_aid_withdraw_current', 'X')
    assert all(not c['mods'] for c in w.c.values())

    w = World()
    w.country('A', ready=True); w.country('X'); w.c['X']['ai'] = True
    w.c['X']['research'] = 'society'
    w.run('ffpa_sc_aid_production_open')
    w.run('ffpa_sc_aid_ai_register', 'X')
    assert 'ffpa_sc_aid_kind' not in w.c['X']['v']
    w.c['X']['research'] = 'production'
    w.c['X']['net_fixed_income'] = F(-1000)
    w.c['X']['gold_reserves'] = F(0)
    w.run('ffpa_sc_aid_ai_register', 'X')
    assert 'ffpa_sc_aid_kind' not in w.c['X']['v']  # Reject unaffordable full quote.
    w.c['X']['net_fixed_income'] = F(600)
    w.run('ffpa_sc_aid_ai_register', 'X')
    assert w.c['X']['v']['ffpa_sc_aid_kind'] == 6

    # Default-on education must actually open, charge, scale both effects and exit.
    w = World()
    for name in 'ABC': w.country(name, ready=True)
    w.country('X')
    w.run('ffpa_sc_aid_education_open')
    assert w.g['ffpa_sc_aid_education_phase'] == 1
    w.run('ffpa_sc_aid_education_register', 'X')
    assert w.c['X']['v']['ffpa_sc_aid_quote'] == 600 and not w.c['X']['mods']
    w.month = 1
    w.run('ffpa_sc_aid_tick_all')
    benefit = 'ffpa_sc_aid_education_benefit_modifier'
    assert w.c['X']['mods'][fee] == 600 and w.c['X']['mods'][benefit] == 1
    mods = {e.key: e for e in parse((ROOT / 'common/static_modifiers/zzzz_ffpa_survivor_compact.txt').read_text())}
    access = F(child(mods[benefit], 'state_education_access_add').value)
    growth = F(child(mods[benefit], 'state_literacy_growth_add').value)
    assert access == F('0.05') and growth == F('0.005')
    w.c['C']['member'] = False
    w.run('ffpa_sc_aid_education_refresh')
    assert w.c['X']['mods'][fee] == 450
    assert access * w.c['X']['mods'][benefit] == F('0.0375')
    assert growth * w.c['X']['mods'][benefit] == F('0.00375')
    w.wars.add(frozenset(('X', 'A')))
    w.run('ffpa_sc_aid_refresh_all')
    assert all(not c['mods'] for c in w.c.values())
    assert w.c['X']['expiry']['ffpa_sc_works_retry'] == 61
    # A persisted modifier can disagree with our bookkeeping. Exercise all real
    # wrappers: unchanged quotes must not leave a base-1 income/fee or full buff.
    for pool in ('education', 'talent', 'production', 'society', 'military'):
        for providers in (1, 2, 3):
            w = World()
            for name in 'ABC'[:providers]: w.country(name, ready=True)
            w.country('X')
            w.run(f'ffpa_sc_aid_{pool}_open')
            w.run(f'ffpa_sc_aid_{pool}_register', 'X')
            w.month = 1
            w.run('ffpa_sc_aid_tick_all')
            expected = copy.deepcopy(w.c)
            revenue = f'ffpa_sc_aid_{pool}_income_modifier'
            benefit = f'ffpa_sc_aid_{pool}_benefit_modifier'
            for name in 'ABC'[:providers]: w.c[name]['mods'][revenue] = F(1)
            w.c['X']['mods'][fee] = F(1)
            w.c['X']['mods'][benefit] = F('0.1')
            w.run('ffpa_sc_aid_refresh_all')
            assert w.c == expected, ('stale modifier survived settlement', pool, providers)
            w.run('ffpa_sc_aid_refresh_all')
            assert w.c == expected  # Repeated refresh preserves timers and balances.
    check_alternatives(modifiers)
    print('PASS: actual aid scripts, registration/launch/settlement/exit/rounding/timers/stale modifiers/annual alternatives')


def check_alternatives(modifiers):
    events = {e.key: e for e in parse((ROOT / 'events/ffpa_survivor_compact.txt').read_text())}
    choices = [e for e in events['ffpa_sc.6'].value if e.key == 'option']
    assert [child(e, 'name').value for e in choices] == ['ffpa_sc_aid_keep', 'ffpa_sc_aid_change_direction', 'ffpa_sc_aid_reduce_current', 'ffpa_sc_aid_cancel']
    assert child(choices[1], 'ffpa_sc_aid_change_direction').value == 'yes'

    def start(pool):
        w = World()
        for name in 'ABC': w.country(name, ready=True)
        w.country('X')
        w.run(f'ffpa_sc_aid_{pool}_open')
        w.run(f'ffpa_sc_aid_{pool}_register', 'X')
        w.run('ffpa_sc_aid_tick_all')
        return w

    for pool in ('education', 'talent', 'production', 'society', 'military'):
        base = f'ffpa_sc_aid_{pool}_benefit_modifier'
        alt = base + '_alternative'
        fields = {e.key: F(e.value) for e in modifiers[alt].value if e.key != 'icon'}
        expected = ({'state_education_access_add': F('.075'), 'state_literacy_growth_add': F('.0025')}
                    if pool == 'education' else {'state_pop_qualifications_mult': F('.30'), 'state_education_access_add': F('.025')}
                    if pool == 'talent' else {f'country_{pool}_tech_research_speed_mult': F('.10'), f'country_{pool}_tech_spread_mult': F('.20')})
        assert fields == expected
        for ending in ('withdraw', 'war', 'default', 'expiry', 'no_provider'):
            w = start(pool); c = w.c['X']; months = f'ffpa_sc_aid_{pool}_months'
            original = copy.deepcopy((w.g, w.c))
            w.run('ffpa_sc_aid_change_direction', 'X')
            assert (w.g, w.c) == original  # Before the first anniversary.
            w.g[months] = 24
            fee, deadline = c['v']['ffpa_sc_aid_paid_fee'], c['expiry']['ffpa_sc_works_retry']
            receipts = [w.c[n]['v'][f'ffpa_sc_aid_{pool}_paid_income'] for n in 'ABC']
            w.run('ffpa_sc_aid_change_direction', 'X')
            assert base not in c['mods'] and c['mods'][alt] == 1
            assert c['v']['ffpa_sc_aid_paid_fee'] == fee and w.g[months] == 24
            assert [w.c[n]['v'][f'ffpa_sc_aid_{pool}_paid_income'] for n in 'ABC'] == receipts
            after = copy.deepcopy((w.g, w.c))
            for action in ('change_direction', 'reduce_current', 'keep_commitment'):
                w.run('ffpa_sc_aid_' + action, 'X')
                assert (w.g, w.c) == after  # Review consumed; no stacking or repeat switch.
            for provider, strength in (('C', F('.75')), ('B', F('.5'))):
                w.c[provider]['ready'] = False
                w.run('ffpa_sc_aid_refresh_all')
                assert base not in c['mods'] and c['mods'][alt] == strength
                assert c['v']['ffpa_sc_aid_paid_fee'] == fee * strength
                assert c['expiry']['ffpa_sc_works_retry'] == deadline
            if ending == 'withdraw': w.run('ffpa_sc_aid_withdraw_current', 'X')
            elif ending == 'expiry':
                w.g[months] = 1; w.run('ffpa_sc_aid_tick_all')
            else:
                if ending == 'war': w.wars.add(frozenset(('A', 'X')))
                elif ending == 'default': c['default'] = True
                else: w.c['A']['ready'] = False
                w.run('ffpa_sc_aid_refresh_all')
            assert alt not in c['mods'] and base not in c['mods']
            assert 'ffpa_sc_aid_alternative' not in c['v'] and 'ffpa_sc_aid_kind' not in c['v']
            assert c['expiry']['ffpa_sc_works_retry'] == deadline
        # Keeping or reducing the original route also consumes the review.
        for action in ('keep_commitment', 'reduce_current'):
            w = start(pool); w.g[f'ffpa_sc_aid_{pool}_months'] = 24
            w.run('ffpa_sc_aid_' + action, 'X')
            before = copy.deepcopy((w.g, w.c))
            w.run('ffpa_sc_aid_change_direction', 'X')
            assert (w.g, w.c) == before
        for case in ('coverage', 'literate', 'schools', 'debt', 'deficit', 'default'):
            w = start(pool); c = w.c['X']; w.g[f'ffpa_sc_aid_{pool}_months'] = 24
            c.update(ai=True, literacy_rate=F('.5'), schools=2)
            if case == 'literate': c['literacy_rate'] = F('.6')
            if case == 'schools': c['schools'] = 3
            if case == 'debt': c['scaled_debt'] = F('.4')
            if case == 'deficit': c.update(net_fixed_income=F(-2000), gold_reserves=F(0))
            if case == 'default': c['default'] = True
            w.run('ffpa_sc_aid_ai_review', 'X')
            assert ('ffpa_sc_aid_alternative' in c['v']) == (case == 'coverage' and pool in ('education','talent'))
            if case in ('debt', 'deficit'): assert c['v']['ffpa_sc_aid_reduced'] == 1
            if case == 'default': assert 'ffpa_sc_aid_kind' not in c['v']
        # Pre-upgrade projects lack the alternative flag. Preserve decisions and
        # queued reviews; these are script-state snapshots, not engine save loads.
        for legacy in ('unreviewed', 'offered', 'kept', 'reduced'):
            w = start(pool); c = w.c['X']; w.g[f'ffpa_sc_aid_{pool}_months'] = 20
            if legacy == 'offered': c['v']['ffpa_sc_aid_review_offered'] = 1
            if legacy in ('kept', 'reduced'):
                w.run('ffpa_sc_aid_' + ('keep_commitment' if legacy == 'kept' else 'reduce_current'), 'X')
            deadline = c['expiry']['ffpa_sc_works_retry']
            for _ in range(2):
                w.run('ffpa_sc_aid_refresh_all')
                w.run('ffpa_sc_aid_notify_review', 'X')
            assert len(w.events) == (1 if legacy == 'unreviewed' else 0)
            assert alt not in c['mods'] and 'ffpa_sc_aid_alternative' not in c['v']
            assert c['mods'][base] == (F('.5') if legacy == 'reduced' else 1)
            assert c['expiry']['ffpa_sc_works_retry'] == deadline
            # A delivered review may remain open when its project ends.
            w.run('ffpa_sc_aid_withdraw_current', 'X')
            after = copy.deepcopy((w.g, w.c))
            for action in ('change_direction', 'keep_commitment', 'reduce_current', 'withdraw_current'):
                w.run('ffpa_sc_aid_' + action, 'X')
                assert (w.g, w.c) == after


if __name__ == '__main__':
    check()
