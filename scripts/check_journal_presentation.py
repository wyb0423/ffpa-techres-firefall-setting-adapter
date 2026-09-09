#!/usr/bin/env python3
"""Check rich text and actual display branches; not a game UI renderer."""
from itertools import product
import re

from check_compact import ROOT, State, load
from compact_script import child

CUSTOM = load('common/customizable_localization')
VALUES = load('common/script_values')
TAG = re.compile(r'#!|#([A-Za-z_][\w]*)\s')
REF = re.compile(r'\$([\w.]+)\$')
CALL = re.compile(r"GetCustom\('([^']+)'\)")
VALUE = re.compile(r"ScriptValue\('([^']+)'\)")


def read_locale(lang):
    path = ROOT / 'localization' / lang / f'ffpa_survivor_compact_l_{lang}.yml'
    data = path.read_bytes()
    assert data.startswith(b'\xef\xbb\xbf'), path
    return dict(re.findall(r'^ ([\w.]+): "(.*)"$', data.decode('utf-8-sig'), re.M))


def expand(key, locale, parents=()):
    assert key not in parents, ('localization cycle', parents, key)
    return REF.sub(lambda m: expand(m[1], locale, parents + (key,)), locale[key])


class DisplayState(State):
    """Use the existing predicate checker, with explicit UI-only world inputs."""
    def __init__(self):
        super().__init__()
        self.is_ai = False
        self.bureaucracy = 1
        self.schools = 0
        self.inputs.update(enacting_any_law=False, ffpa_sc_child_law_ready=False,
                           ffpa_sc_trade_ready=False)

    def test(self, nodes):
        for node in nodes:
            if node.key == 'is_ai':
                ok = self.is_ai == (node.value == 'yes')
            elif node.key == 'relative_bureaucracy':
                assert node.op == '<'
                ok = self.bureaucracy < float(node.value)
            elif node.key == 'institution_investment_level':
                assert child(node, 'institution').value == 'institution_schools'
                threshold = child(node, 'value')
                assert threshold.op == '>='
                ok = self.schools >= float(threshold.value)
            else:
                ok = super().test([node])
            if not ok:
                return False
        return True

    def display(self, name):
        for entry in CUSTOM[name].value:
            if entry.key == 'text' and self.test(child(entry, 'trigger').value):
                return child(entry, 'localization_key').value
        raise AssertionError(('missing display fallback', name))


def check():
    locales = {lang: read_locale(lang) for lang in ('english', 'simp_chinese')}
    assert locales['english'].keys() == locales['simp_chinese'].keys()
    for lang, locale in locales.items():
        for key in locale:
            text = expand(key, locale)
            depth = 0
            for match in TAG.finditer(text):
                if match[0] == '#!':
                    depth -= 1
                    assert depth >= 0, (lang, key, 'extra closure')
                else:
                    assert match[1] in {'header', 'b', 'V', 'P', 'N', 'lore', 'yellow'}, (key, match[1])
                    depth += 1
            assert depth == 0, (lang, key, 'unclosed style')
            assert set(CALL.findall(text)) <= CUSTOM.keys(), (lang, key)
            assert set(VALUE.findall(text)) <= VALUES.keys(), (lang, key)
            other = expand(key, locales['simp_chinese' if lang == 'english' else 'english'])
            assert sorted(re.findall(r'\[[^\]]+\]', text)) == sorted(re.findall(r'\[[^\]]+\]', other)), (key, 'dynamic parity')
        for custom in CUSTOM.values():
            for entry in custom.value:
                if entry.key == 'text':
                    assert child(entry, 'localization_key').value in locale
        for name in ('support', 'against', 'abstain'):
            assert not re.search(r'#(?:P|N) ', expand('ffpa_sc_vote_' + name + '_desc', locale))
        # Keep detailed sections out of the native large, centered status box.
        for key in ('ffpa_sc_task_works', 'ffpa_sc_task_schools', 'ffpa_sc_task_trade'):
            assert expand(key, locale).count('\\n') == 1, (key, 'status too long')
        for kind in ('education', 'trade'):
            assert f'ffpa_sc_{kind}_months_left' in expand('ffpa_sc_task_' + ('schools' if kind == 'education' else kind), locale)

    # Existing branch selection, now independent of enactment/budget messages.
    journal = load('common/journal_entries')['ffpa_sc_task_journal']
    statuses = child(child(journal, 'status_desc'), 'first_valid').value
    for task, enacting, ai, bureaucracy in product(range(1, 9), (False, True), (False, True), (0, 1)):
        state = DisplayState()
        state.v['ffpa_sc_task'] = task
        state.inputs['enacting_any_law'] = enacting
        state.is_ai, state.bureaucracy = ai, bureaucracy
        if task >= 4:
            state.v['ffpa_sc_aid_kind'] = task
        status = next(child(e, 'desc').value for e in statuses if state.test(child(e, 'trigger').value))
        assert status not in ('ffpa_sc_task_enacting', 'ffpa_sc_task_budget')
        assert state.display('ffpa_sc_task_details') not in ('ffpa_sc_task_unknown_status',)
        expected = 'ffpa_sc_task_enacting' if enacting else 'ffpa_sc_task_budget' if ai and bureaucracy < .2 else 'ffpa_sc_task_reform_hint'
        if not enacting and not (ai and bureaucracy < .2) and task == 2:
            expected = 'ffpa_sc_task_trade_reform_hint'
        assert state.display('ffpa_sc_preparation_hint') == expected
        state.inputs['ffpa_sc_operational'] = False
        assert state.display('ffpa_sc_preparation_hint') == 'ffpa_sc_task_dormant_hint'

    for ident, pool in enumerate(('education', 'talent', 'production', 'society', 'military'), 4):
        state = DisplayState()
        prefix = 'ffpa_sc_aid_' + pool
        assert state.display(prefix + '_status') == 'ffpa_sc_label_closed'
        state.g[prefix + '_result'] = 0
        assert state.display(prefix + '_status') == 'ffpa_sc_aid_failed'
        state.g[prefix + '_phase'] = 1
        assert state.display(prefix + '_status') == prefix + '_registration_status'
        state.v.update(ffpa_sc_aid_kind=ident, ffpa_sc_aid_quote=100)
        assert state.display(prefix + '_status') == prefix + '_registered_status'
        assert state.display('ffpa_sc_aid_payment') == 'ffpa_sc_aid_payment_none'
        state.g[prefix + '_phase'] = 2
        state.v['ffpa_sc_aid_paid_fee'] = 50
        assert state.display('ffpa_sc_aid_payment') == 'ffpa_sc_aid_payment_none'
        state.mod.add('ffpa_sc_aid_fee_modifier')
        assert state.display('ffpa_sc_aid_payment') == 'ffpa_sc_aid_payment_active'
        assert state.display(prefix + '_status') == prefix + '_recipient_status'
        state.v['ffpa_sc_aid_reduced'] = 1
        assert state.display('ffpa_sc_aid_commitment') == 'ffpa_sc_aid_commitment_reduced'
        del state.v['ffpa_sc_aid_kind']
        state.v[prefix + '_provider'] = 1
        assert state.display(prefix + '_status') == prefix + '_provider_status'
        del state.v[prefix + '_provider']
        assert state.display(prefix + '_status') == prefix + '_active_status'
        del state.g[prefix + '_phase']
        state.g[prefix + '_result'] = 1
        assert state.display(prefix + '_status') == 'ffpa_sc_aid_ended'
    state = DisplayState()
    for ready in (False, True):
        state.inputs['ffpa_sc_child_law_ready'] = ready
        state.inputs['ffpa_sc_trade_ready'] = ready
        state.schools = int(ready)
        for kind in ('child', 'school', 'trade'):
            assert state.display('ffpa_sc_' + kind + '_requirement') == 'ffpa_sc_requirement_' + ('met' if ready else 'missing')
    assert state.display('ffpa_sc_task_brief') == 'ffpa_sc_task_unknown_brief'
    assert state.display('ffpa_sc_task_details') == 'ffpa_sc_task_unknown_status'
    print('PASS: paired rich text/references, compact status layout, task/aid/fee display branches (not game UI proof)')


if __name__ == '__main__':
    check()
