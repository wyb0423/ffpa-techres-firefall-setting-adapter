#!/usr/bin/env python3
"""Evaluate actual scores and ballot effects; native country facts are test inputs."""
from check_compact import State, VALUES, child


class Voter(State):
    def __init__(self, proposal, facts, relations=0):
        super().__init__()
        self.g['ffpa_sc_vote'] = proposal
        self.facts = facts
        self.relations = relations
        self.inputs['ffpa_sc_can_vote'] = True

    def value(self, key):
        if key == 'ffpa_sc_proposer_relations':
            return self.relations  # Diplomatic scope traversal still needs the engine.
        if key in VALUES and isinstance(VALUES[key].value, list):
            return self.score(VALUES[key].value)
        return super().value(key)

    def test(self, nodes):
        for e in nodes:
            if e.key == 'is_ai':
                ok = e.value == 'yes'
            elif e.key in self.facts:
                a = self.facts[e.key]
                b = {'yes': True, 'no': False}.get(e.value) if isinstance(e.value, str) else None
                if b is None:
                    b = float(e.value)
                ok = {'=': a == b, '<': a < b, '>': a > b,
                      '>=': a >= b, '<=': a <= b}[e.op]
            else:
                ok = super().test([e])
            if not ok:
                return False
        return True

    def score(self, nodes):
        result, taken = 0, False
        for e in nodes:
            if e.key in ('if', 'else_if', 'else'):
                if e.key == 'if':
                    taken = False
                if not taken and (e.key == 'else' or self.test(child(e, 'limit').value)):
                    result += self.score([x for x in e.value if x.key != 'limit'])
                    taken = True
            elif e.key == 'value': result = self.value(e.value)
            elif e.key == 'add': result += self.value(e.value)
            elif e.key == 'subtract': result -= self.value(e.value)
            else: raise AssertionError(('unsupported score', e))
        return result


def check_votes():
    for proposal, pool in enumerate(('education', 'talent', 'production', 'society', 'military'), 4):
        ready, need, afford = [f'ffpa_sc_aid_{pool}_{x}' for x in ('ready', 'need', 'afford')]
        pressure = 'ffpa_sc_aid_research_ready' if pool == 'education' else need
        def ballot(provider=False, demand=False, solvent=True, prestige=100, strained=False, relations=0):
            facts = {ready: provider, need: demand, afford: solvent, 'prestige': prestige}
            if provider:
                facts[pressure] = not strained if pool == 'education' else strained
            s = Voter(proposal, facts, relations)
            s.run('ffpa_sc_ai_vote')
            return s.v['ffpa_sc_choice']
        assert ballot() == 0, pool
        assert ballot(relations=2) == 0, pool  # Friendship alone cannot create support.
        assert ballot(demand=True) == 1, pool
        assert ballot(demand=True, solvent=False) == 0, pool
        assert ballot(demand=True, solvent=False, relations=2) == 0, pool
        assert ballot(provider=True) == 1, pool
        assert ballot(provider=True, prestige=20) == 0, pool
        assert ballot(provider=True, strained=True) == 0, pool
        assert ballot(provider=True, prestige=20, strained=True) == -1, pool
        assert ballot(relations=-5) == -1, pool
    for name in ('education', 'trade', 'works'):
        assert child(VALUES[f'ffpa_sc_{name}_score'], 'value').value == '0'
    print('PASS AI ballots: five pools, neutral/benefit/cost/diplomacy cases; legacy base scores')


if __name__ == '__main__':
    check_votes()
