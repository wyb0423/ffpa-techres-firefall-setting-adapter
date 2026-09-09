#!/usr/bin/env python3
"""CMF API/GUI contracts and actual read-only calculations; not engine/UI proof."""
import argparse
import json
import math
import re
from itertools import product
from pathlib import Path

from check_compact import ROOT, State, VALUES, TRIGGERS, load
from check_journal_presentation import DisplayState
from compact_script import parse, walk, child


class Values(DisplayState):
    def test(self, nodes):
        for e in nodes:
            if e.key == 'ffpa_sc_can_vote':
                if self.test(TRIGGERS[e.key].value) != (e.value == 'yes'): return False
            elif not super().test([e]): return False
        return True

    def value(self, key):
        if key in VALUES and isinstance(VALUES[key].value, list):
            return self.calculate(VALUES[key].value)
        return super().value(key)

    def calculate(self, nodes):
        result, taken = 0, False
        for e in nodes:
            key, val = e.key, e.value
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    taken = False
                if not taken and (key == 'else' or self.test(child(e, 'limit').value)):
                    # The chosen branch continues the surrounding accumulator.
                    result = self.calculate(parse(f'value = {result}') + [n for n in val if n.key != 'limit'])
                    taken = True
                continue
            taken = False
            if key == 'ceiling':
                assert val == 'yes'
                result = math.ceil(result)
                continue
            number = self.calculate(val) if isinstance(val, list) else self.value(val)
            if key == 'value': result = number
            elif key == 'add': result += number
            elif key == 'subtract': result -= number
            elif key == 'divide': result /= number
            elif key == 'multiply': result *= number
            # Paradox min/max set lower/upper bounds, not mathematical min/max.
            elif key == 'min': result = max(result, number)
            elif key == 'max': result = min(result, number)
            else: raise AssertionError(('unsupported value', key))
        return result


class Initialization(State):
    """Run real registration wrappers; record contextless additions instead of an engine."""
    def __init__(self, upstream):
        super().__init__()
        self.upstream, self.lists, self.journals = upstream, {}, []

    def test(self, nodes):
        for e in nodes:
            if e.key == 'is_target_in_global_variable_list':
                fields = {n.key: n.value for n in e.value}
                if fields['target'] not in self.lists.get(fields['name'], []): return False
            elif not super().test([e]): return False
        return True

    def execute(self, nodes):
        # These initialization wrappers use independent if blocks, not if/else chains.
        for e in nodes:
            if e.key in self.upstream:
                params = {n.key: n.value for n in e.value} if isinstance(e.value, list) else {}
                source = self.upstream[e.key]
                for key, val in params.items(): source = source.replace('$' + key + '$', val)
                assert '$' not in source, (e.key, params)
                self.execute(parse(source)[0].value)
            elif e.key in ('hidden_effect', 'custom_tooltip'):
                self.execute([n for n in e.value if n.key not in ('text', 'set_local_variable')])
            elif e.key == 'add_to_global_variable_list':
                fields = {n.key: n.value for n in e.value}
                self.lists.setdefault(fields['name'], []).append(fields['target'])
            elif e.key == 'add_contextless_journal_entry': self.journals.append(e.value)
            else: super().execute([e])


class Binding(State):
    """Exercise country/JE reference writes; engine validity remains a runtime check."""
    def __init__(self):
        super().__init__()
        self.journals = {'ffpa_sc_overview': {}, 'ffpa_sc_cmf_organization': {}}

    def value(self, key):
        if key.startswith('je:'):
            assert key[3:] in self.journals
            return key
        return super().value(key)

    def test(self, nodes):
        for e in nodes:
            if e.key == 'has_journal_entry':
                if e.value not in self.journals: return False
            elif not super().test([e]): return False
        return True

    def execute(self, nodes):
        pending = []
        for e in nodes:
            if e.key.startswith('je:'):
                super().execute(pending)
                pending = []
                country = self.v
                self.v = self.journals[e.key[3:]]
                self.execute(e.value)
                self.v = country
            else: pending.append(e)
        super().execute(pending)


def check(cmf):
    metadata = json.loads((cmf / '.metadata/metadata.json').read_text())
    assert metadata['id'] == 'com.github.Victoria-3-Modding-Co-op.Community-Mod-Framework'
    upstream = {}
    for file in ('com_international_organization_effects.txt', 'com_journal_entry_effects.txt'):
        source = (cmf / 'common/scripted_effects' / file).read_text(encoding='utf-8-sig')
        upstream.update({e.key: source[e.start:e.end] for e in parse(source)})
    state = Initialization(upstream)
    state.run('ffpa_sc_cmf_initialize')
    assert not state.journals and not state.lists
    state.g['ffpa_sc_founded'] = 1
    for _ in range(10): state.run('ffpa_sc_cmf_initialize')
    assert state.journals == ['ffpa_sc_cmf_organization']
    assert state.lists['com_international_organization_journal_groups'] == ['flag:je_group_ffpa_sc_cmf']
    assert state.lists['com_hidden_journal_groups'].count('flag:je_group_ffpa_sc_cmf') == 1
    # Existing CMF sidebars and other mods' registrations are preserved.
    old = Initialization(upstream)
    old.g.update(ffpa_sc_founded=1, com_international_organization_panel_active=1)
    old.lists['com_international_organization_journal_groups'] = ['flag:other_mod']
    old.run('ffpa_sc_cmf_initialize')
    assert old.lists['com_international_organization_journal_groups'] == ['flag:other_mod', 'flag:je_group_ffpa_sc_cmf']

    old = Binding()
    old.v.update(ffpa_sc_membership=1, ffpa_sc_cooperation_months=25)
    old.g.update(ffpa_sc_vote=4, ffpa_sc_months_left=2)
    for _ in range(3): old.run('ffpa_sc_cmf_bind_overview')
    assert old.v['ffpa_sc_cmf_overview_ref'] == 'je:ffpa_sc_overview'
    assert old.journals['ffpa_sc_overview'] == {'com_hide_scripted_buttons': 1}
    assert old.g['ffpa_sc_cmf_public_ref'] == 'je:ffpa_sc_cmf_organization'
    assert old.v['ffpa_sc_cooperation_months'] == 25 and old.g['ffpa_sc_months_left'] == 2
    del old.v['ffpa_sc_membership']
    old.run('ffpa_sc_cmf_bind_overview')
    assert 'ffpa_sc_cmf_overview_ref' not in old.v
    old.v['ffpa_sc_membership'] = 1
    del old.journals['ffpa_sc_overview']
    old.run('ffpa_sc_cmf_bind_overview')
    assert 'ffpa_sc_cmf_overview_ref' not in old.v

    state = Values()
    # Native semantics, independently anchored in base-game command_values.txt:
    # max caps combat width; min establishes a lower bound (also used by aid values).
    assert state.calculate(parse('value = 10 max = 3')) == 3
    assert state.calculate(parse('value = -2 min = 0')) == 0
    assert state.value('ffpa_sc_cmf_vote_progress') == 0
    # Threshold equals the existing resolution rule, including nonmultiples of 3.
    for n in range(25):
        for support in range(n + 1):
            for against in range(n - support + 1):
                state.g.update(ffpa_sc_vote=1, ffpa_sc_electorate=n, ffpa_sc_support=support, ffpa_sc_against=against)
                expected = support >= 2 and support * 3 >= n and support > against
                assert (state.value('ffpa_sc_cmf_vote_progress') == 1) == expected
    for task, key, duration in ((1, 'education', 60), (2, 'trade', 60), (3, 'works', 36)):
        state.v = {'ffpa_sc_task': task}
        for left in (duration, duration / 2, 0, -1, duration + 1):
            state.v[f'ffpa_sc_{key}_months_left'] = left
            assert state.value('ffpa_sc_cmf_task_progress') == max(0, min(1, 1 - max(0, left) / duration))
    for ident, pool in enumerate(('education', 'talent', 'production', 'society', 'military'), 4):
        state.v = {'ffpa_sc_task': ident, 'ffpa_sc_aid_kind': ident}
        for phase, duration, stage in ((1, 1, 'registration'), (2, 36, 'execution')):
            state.g = {f'ffpa_sc_aid_{pool}_phase': phase, f'ffpa_sc_aid_{pool}_months': duration}
            assert state.display('ffpa_sc_cmf_task_stage') == 'ffpa_sc_cmf_stage_' + stage
            assert state.value('ffpa_sc_cmf_task_duration') == duration
            assert state.value('ffpa_sc_cmf_task_progress') == 0
            state.g[f'ffpa_sc_aid_{pool}_months'] = 0
            assert state.value('ffpa_sc_cmf_task_progress') == 1

    # One and only one bucket per member during a session, using the real filters.
    filters = load('common/scripted_guis')
    for eligible, admitted, choice in product((False, True), (False, True), (None, -1, 0, 1)):
        state = Values()
        state.g['ffpa_sc_vote'] = 1
        state.v['ffpa_sc_membership'] = 1
        state.inputs['ffpa_sc_eligible'] = eligible
        if admitted: state.v['ffpa_sc_ballot_eligible'] = 1
        if choice is not None: state.v['ffpa_sc_choice'] = choice
        selected = [name for name in ('support', 'against', 'neutral', 'ineligible')
                    if state.test(child(filters[f'ffpa_sc_cmf_{name}_filter'], 'is_shown').value)]
        expected = 'ineligible' if not eligible or not admitted else {-1: 'against', 1: 'support'}.get(choice, 'neutral')
        assert selected == [expected]
    for ident, pool in enumerate(('education', 'talent', 'production', 'society', 'military'), 4):
        state = Values()
        prefix = f'ffpa_sc_aid_{pool}'
        # Even with stale numbers/modifiers, registration and closed pools do not charge.
        state.v.update(ffpa_sc_membership=1, ffpa_sc_aid_kind=ident, ffpa_sc_aid_paid_fee=10)
        state.v[prefix + '_paid_income'] = 20
        state.v[prefix + '_provider'] = 1
        state.mod.update(('ffpa_sc_aid_fee_modifier', prefix + '_income_modifier'))
        state.g[prefix + '_total'] = 30
        for phase in (0, 1, 2):
            state.g[prefix + '_phase'] = phase
            for value, expected in (('total', 30), ('income', 20), ('fee', 10)):
                assert state.value(f'ffpa_sc_cmf_{pool}_{value}') == (expected if phase == 2 else 0)
        state.g[prefix + '_phase'] = 1
        for providers, strength in ((0, 0), (1, 50), (2, 75), (3, 100), (8, 100)):
            state.g[prefix + '_providers'] = providers
            assert state.value(f'ffpa_sc_cmf_{pool}_strength') == strength
        state.g.update({prefix + '_phase': 2, prefix + '_strength': .75})
        assert state.value(f'ffpa_sc_cmf_{pool}_strength') == 75
        state.mod.clear()
        assert state.value(f'ffpa_sc_cmf_{pool}_income') == state.value(f'ffpa_sc_cmf_{pool}_fee') == 0
        for role in ('provider', 'recipient'):
            nodes = child(filters[f'ffpa_sc_cmf_{pool}_{role}_filter'], 'is_shown').value
            assert state.test(nodes)
            state.g.pop(prefix + '_phase')
            assert not state.test(nodes)
            state.g[prefix + '_phase'] = 2

    gui = (ROOT / 'gui/ffpa_compact_cmf.gui').read_text()
    event_gui = (ROOT / 'gui/ffpa_compact_event_windows.gui').read_text()
    details = (ROOT / 'gui/ffpa_compact_cmf_details.gui').read_text()
    for text in (gui, event_gui, details):
        # Normalize GUI declarations only for bracket/key parsing, not GUI semantics.
        text = re.sub(r'\b(?:types|blockoverride|block)\s+("[^"]+"|\w+)\s*\{', r'\1 = {', text)
        text = re.sub(r'\btype\s+(\w+)\s*=\s*\w+\s*\{', r'\1 = {', text)
        entries = parse(text)
        names = [child(e, 'name').value if e.key == 'flowcontainer' else e.key for e in entries]
        assert len(set(names)) == len(names)
    assert 'ScriptedProgressBar.' not in gui and 'ComProgressBar.' not in gui
    base = (cmf / 'gui/com_gui_progressbars.gui').read_text()
    component = base[base.index('type com_progressbar_base ='):base.index('type com_progressbar =')]
    for name in ('com_base_value', 'noprogresstexture', 'progresstexture'):
        assert f'block "{name}"' in component
    journal_gui = (cmf / 'gui/com_gui_journal_entry.gui').read_text()
    for key, journal in load('common/journal_entries').items():
        for widget in (e for e in journal.value if e.key == 'widget'):
            path = child(widget, 'gui').value.strip('"')
            if not path.startswith('gui/ffpa_compact_cmf'): continue
            assert child(widget, 'name').value in (ROOT / path).read_text()
            assert child(widget, 'container').value in journal_gui
    public = load('common/journal_entries')['ffpa_sc_cmf_organization']
    assert not any(e.key in ('scripted_button', 'on_monthly_pulse') for e in public.value)
    assert child(public, 'group').value == 'je_group_ffpa_sc_cmf'
    assert child(load('common/journal_entry_groups')['je_group_ffpa_sc_cmf'], 'context').value == 'none'
    # Three groups cover every original overview button exactly once. CMF's actual
    # grouping example compares ScriptedButton.GetName to the localization-key flag.
    assigned = re.findall(r"EqualTo_string\(ScriptedButton.GetName, '(ffpa_sc_[^']+)'\)", details)
    overview = load('common/journal_entries')['ffpa_sc_overview']
    original = [e.value for e in overview.value if e.key == 'scripted_button']
    assert sorted(assigned) == sorted(original) and len(assigned) == len(set(assigned))
    assert 'scripted_journal_entry_button = ' in details
    assert 'ExecuteEffect' not in details  # Native component owns execution/validation.
    assert details.count('InformationPanelBar.OpenJournalEntryPanel(JournalEntry.AccessSelf)') == 2
    assert details.count('And(JournalEntry.IsValid, JournalEntry.IsActive)') == 2
    for name in re.findall(r"GetScriptedGui\('([^']+)'\)", details):
        assert child(filters[name], 'scope').value == 'country'
        assert not any(e.key == 'effect' for e in filters[name].value)
    for text in (gui, details):
        assert 'Scope.GetFlagName' not in text  # No legacy situation/struct grouping.
    for e in parse((ROOT / 'common/script_values/ffpa_compact_cmf.txt').read_text()):
        assert not any(n.key.startswith(('set_', 'change_', 'remove_')) for n in walk(e.value))
    assert 'FONT:' not in event_gui and 'default_format = "#com_letter"' in event_gui
    for name, file in (('com_event_window_letter_simple', 'com_letter_event_windows.gui'), ('com_event_window_telegram', 'com_telegram_event_windows.gui')):
        assert f'type {name} =' in (cmf / 'gui/com_event_windows' / file).read_text()
    for lang in ('english', 'simp_chinese'):
        source = (ROOT / f'localization/{lang}/ffpa_survivor_compact_l_{lang}.yml').read_text(encoding='utf-8-sig')
        for number in (2, 3):
            desc = re.search(rf'^ ffpa_sc\.{number}\.d: "(.*)"$', source, re.M)[1]
            assert '#' not in desc, 'Paper telegram must not inherit pale journal colors'
    print(f'PASS CMF {metadata["version"]}: initialization/binding, ballot groups/thresholds, aid phase/fee guards, all 21 grouped buttons, GUI contracts (not engine proof)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cmf-root', type=Path, required=True)
    check(parser.parse_args().cmf_root)
