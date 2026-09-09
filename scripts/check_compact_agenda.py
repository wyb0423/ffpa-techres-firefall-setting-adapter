#!/usr/bin/env python3
"""Run actual agenda, ballot and aid scripts. Native country facts are explicit;
not a Victoria 3 runtime, native scope or economic validation."""
import copy
import math
from fractions import Fraction as F
from pathlib import Path
from compact_script import parse, child
from check_aid_pool_scripts import World, EFFECTS, VALUES, TRIGGERS

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT/'common/scripted_effects').glob('*.txt'):
    source = path.read_text()
    EFFECTS.update({e.key: source[e.start:e.end] for e in parse(source)})
for folder, dest in [('script_values',VALUES), ('scripted_triggers',TRIGGERS)]:
    for path in (ROOT/'common'/folder).glob('*.txt'):
        dest.update({e.key:e.value for e in parse(path.read_text())})

class Assembly(World):
    def __init__(self):
        super().__init__()
        self.draw = 0
        self.draw_weights = []
        self.g.update(ffpa_sc_founded=1,ffpa_sc_education_open=1,ffpa_sc_trade_open=1,ffpa_sc_works_open=1)

    def country(self, name, **kwargs):
        super().country(name, **kwargs)
        self.c[name].update(ai=True, literacy_rate=F('.8'), construction=False)

    def ops(self, nodes, country, result=F(0)):
        taken = False
        for e in nodes:
            if e.key in ('if','else_if','else'):
                if e.key == 'if': taken = False
                if not taken and (e.key=='else' or self.test(child(e,'limit').value,country)):
                    result=self.ops([n for n in e.value if n.key!='limit'],country,result)
                    taken=True
                continue
            if e.key=='floor':
                assert e.value=='yes';result=F(math.floor(result));continue
            n=self.number(e.value,country)
            if e.key=='value':result=n
            elif e.key=='add':result+=n
            elif e.key=='subtract':result-=n
            elif e.key=='multiply':result*=n
            elif e.key=='divide':result/=n
            elif e.key=='min':result=max(result,n)
            elif e.key=='max':result=min(result,n)
            else:raise AssertionError(('unsupported agenda value',e))
        return result

    def number(self, value, country):
        if isinstance(value,list):return self.ops(value,country)
        # Diplomatic traversal is separately bounded in ballot tests; neutral here.
        if value=='ffpa_sc_proposer_relations':return F(0)
        if value=='total_trade_value':return F(100)
        return super().number(value,country)

    def run(self, key, country=None, **params):
        # Existing domestic reforms, membership rewards and seat allocation are
        # covered by their own checks; use fixed seat/solvency inputs here.
        if key in ('ffpa_sc_ensure_initialized','ffpa_sc_refresh','ffpa_sc_membership_tick','ffpa_sc_select_seats','ffpa_sc_fill_seats'):return
        if key=='ffpa_sc_ai_manage':return super().run('ffpa_sc_aid_ai_register',country)
        return super().run(key,country,**params)

    def test(self,nodes,country,previous=None):
        for e in nodes:
            if e.key=='ffpa_sc_ai_solvent':
                ok=(not self.c[country]['default'] and self.c[country]['scaled_debt']<F('.25'))==(e.value=='yes')
            elif e.key=='ffpa_sc_education_ready':ok=self.c[country]['ready']==(e.value=='yes')
            elif e.key=='ffpa_sc_trade_ready':ok=e.value=='yes'
            elif e.key in ('ruler','has_law_or_variant'):ok=False
            else:ok=super().test([e],country,previous)
            if not ok:return False
        return True

    def execute(self,nodes,country):
        for index,e in enumerate(nodes):
            if e.key in ('random_list','trigger_event'):
                super().execute(nodes[:index],country)
                if e.key=='trigger_event':self.events.append((country,e.value))
                else:
                    options=[]
                    self.draw_weights=[]
                    for option in e.value:
                        modifier=child(option,'modifier')
                        weight=self.ops(modifier.value,country,F(option.key))
                        self.draw_weights.append(weight)
                        if weight>0:options.append(option)
                    assert options and all(w in (0,1) for w in self.draw_weights)
                    selected=options[self.draw % len(options)]
                    self.execute([n for n in selected.value if n.key!='modifier'],country)
                self.execute(nodes[index+1:],country)
                return
        super().execute(nodes,country)


def world():
    w=Assembly()
    for n in 'ABC':
        w.country(n,ready=True,prestige=100)
        w.c[n]['research']='society'  # Production service has no matching domestic penalty pressure.
    for n in 'XY':w.country(n)
    w.c['A']['v']['ffpa_sc_coordinator']=1
    return w


def check():
    # The original protocol IDs use the same nominations and still open correctly.
    for ident,name in enumerate(('education','trade','works'),1):
        w=Assembly();w.g.pop('ffpa_sc_'+name+'_open')
        for n in 'AB':
            w.country(n,ready=True);w.c[n]['construction']=ident==3
        w.run('ffpa_sc_monthly');assert w.g['ffpa_sc_vote']==ident
        for _ in range(3):w.run('ffpa_sc_monthly')
        assert w.g['ffpa_sc_'+name+'_open']==1
    # Entire AI agenda -> 3-month ballot -> registration -> actual aid launch.
    w=world();w.g['ffpa_sc_cooldown']=9
    for remaining in range(8,0,-1):
        w.run('ffpa_sc_monthly')
        assert w.g['ffpa_sc_cooldown']==remaining and 'ffpa_sc_vote' not in w.g
        assert all(c['v']['ffpa_sc_agenda_choice']==6 for c in w.c.values())
    w.run('ffpa_sc_monthly')
    assert w.g['ffpa_sc_vote']==6 and w.g['ffpa_sc_months_left']==3
    w.country('late')
    assert not w.test(TRIGGERS['ffpa_sc_can_vote'],'late')
    before=copy.deepcopy(w.c['late']['v'])
    w.run('ffpa_sc_agenda_endorse','late',ID=6)
    assert w.c['late']['v']==before
    w.c['late']['member']=False
    for remaining in (2,1):
        w.run('ffpa_sc_monthly');assert w.g['ffpa_sc_months_left']==remaining
    w.run('ffpa_sc_monthly')
    assert w.g['ffpa_sc_cooldown']==9 and w.g['ffpa_sc_aid_production_phase']==1
    w.run('ffpa_sc_monthly')
    assert w.g['ffpa_sc_aid_production_phase']==2 and w.g['ffpa_sc_aid_production_months']==36
    assert all(w.c[n]['v']['ffpa_sc_aid_kind']==6 for n in 'XY')
    assert sum(w.c[n]['v']['ffpa_sc_aid_production_paid_income'] for n in 'ABC')==sum(w.c[n]['v']['ffpa_sc_aid_paid_fee'] for n in 'XY')

    for members,threshold in ((2,2),(20,2),(21,3),(30,3),(31,4),(40,4),(41,5),(80,5)):
        w=Assembly()
        for i in range(members):w.country(str(i))
        w.run('ffpa_sc_agenda_tally');assert w.g['ffpa_sc_agenda_threshold']==threshold
    # Ordinary members outvote a high-prestige coordinator's direct nomination.
    w=world();w.g.pop('ffpa_sc_education_open');w.g.pop('ffpa_sc_trade_open')
    w.c['A']['prestige']=10000
    for n,ident in [('A',2),('X',1),('Y',1)]:w.run('ffpa_sc_agenda_endorse',n,ID=ident)
    w.run('ffpa_sc_agenda_select');assert w.g['ffpa_sc_pending']==1
    # Move, withdraw, and membership invalidation cannot leave extra signatures.
    w.run('ffpa_sc_agenda_endorse','X',ID=2)
    assert w.g['ffpa_sc_motion_1_support']==1 and w.g['ffpa_sc_motion_2_support']==2
    w.run('ffpa_sc_agenda_withdraw','X');assert w.g['ffpa_sc_motion_2_support']==1
    w.c['Y']['member']=False;w.run('ffpa_sc_agenda_tally');assert w.g['ffpa_sc_motion_1_support']==0
    w.g.pop('ffpa_sc_pending');w.run('ffpa_sc_agenda_select');assert w.g['ffpa_sc_pending']==2
    w.c['A']['v'].pop('ffpa_sc_coordinator');w.g.pop('ffpa_sc_pending')
    w.run('ffpa_sc_agenda_select');assert 'ffpa_sc_pending' not in w.g
    # Ties give equal nonzero weights only to qualified leaders, independent of prestige.
    for draw,expected in ((0,1),(1,2)):
        w=world();w.g.pop('ffpa_sc_education_open');w.g.pop('ffpa_sc_trade_open');w.draw=draw
        for n,ident in [('A',1),('B',1),('X',2),('Y',2)]:w.run('ffpa_sc_agenda_endorse',n,ID=ident)
        w.run('ffpa_sc_agenda_select')
        assert w.g['ffpa_sc_pending']==expected and w.draw_weights==[1,1,0,0,0,0,0,0]
    # No viable recipients: even coordinators do not repeatedly submit empty aid rounds.
    w=world()
    for n in 'XY':w.c[n]['scaled_debt']=F('.8')
    for _ in range(4):w.run('ffpa_sc_monthly')
    assert 'ffpa_sc_vote' not in w.g and 'ffpa_sc_cooldown' not in w.g
    assert not any('ffpa_sc_agenda_choice' in c['v'] for c in w.c.values())
    w.c['X']['scaled_debt']=F(0)
    w.run('ffpa_sc_monthly');assert w.g['ffpa_sc_vote']==6  # No new nine-month wait.
    # Same personal utility: prefer an existing coalition; stop following when it becomes costly.
    w=world();w.c['X'].update(construction=True)
    w.c['Y']['v']['ffpa_sc_agenda_choice']=5
    w.run('ffpa_sc_agenda_tally');w.run('ffpa_sc_ai_propose','X')
    assert w.c['X']['v']['ffpa_sc_agenda_choice']==5
    w.c['X']['construction']=False;w.run('ffpa_sc_ai_propose','X')
    assert w.c['X']['v']['ffpa_sc_agenda_choice']==6
    # Reserve an intended aid slot only in the last recess month, and only if qualified.
    w=world();w.c['X']['construction']=True
    for n in 'XY':w.run('ffpa_sc_agenda_endorse',n,ID=6)
    for months,reserve in ((9,False),(2,False),(1,True),(0,True)):
        w.g['ffpa_sc_cooldown']=months
        assert w.test(TRIGGERS['ffpa_sc_agenda_reserve_slot'],'X')==reserve
    w.c['X']['scaled_debt']=F('.8')
    assert not w.test(TRIGGERS['ffpa_sc_agenda_reserve_slot'],'X')
    # Current ballot freezes endorsements; old queued motions become endorsements without resetting recess.
    w=world();w.g.update(ffpa_sc_vote=6,ffpa_sc_months_left=2,ffpa_sc_cooldown=7)
    w.c['A']['v']['ffpa_sc_proposer']=1
    w.run('ffpa_sc_agenda_initialize')
    before=copy.deepcopy((w.g,w.c));w.run('ffpa_sc_agenda_endorse','X',ID=5)
    assert (w.g,w.c)==before
    w=world();w.g.update(ffpa_sc_pending=6,ffpa_sc_cooldown=7);w.c['A']['v']['ffpa_sc_proposer']=1
    w.run('ffpa_sc_agenda_initialize')
    assert w.c['A']['v']['ffpa_sc_agenda_choice']==6 and 'ffpa_sc_pending' not in w.g
    assert w.g['ffpa_sc_cooldown']==7
    before=copy.deepcopy((w.g,w.c));w.run('ffpa_sc_agenda_initialize');assert (w.g,w.c)==before
    print('PASS actual agenda scripts: all-AI lifecycle, thresholds, coalitions, equal draws, direct nomination, task reservation, migration; not engine proof')

if __name__=='__main__':check()
