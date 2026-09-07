#!/usr/bin/env python3
"""Static and focused script-state checks. This is not a Victoria 3 interpreter."""
from pathlib import Path
import argparse, hashlib, json, re
from compact_script import parse, walk, child
ROOT=Path(__file__).resolve().parents[1]

def load(folder):
    out={}
    for p in sorted((ROOT/folder).glob('*.txt')):
        for e in parse(p.read_text(encoding='utf-8-sig')):
            if e.key=='namespace':continue
            assert e.key not in out, (folder,'duplicate key',e.key)
            out[e.key]=e
    return out
EFFECTS=load('common/scripted_effects')
VALUES=load('common/script_values')
SCALARS={k:float(e.value) for k,e in VALUES.items() if isinstance(e.value,str)}

class State:
    """Run the actual scalar effects/branches for the clock and enrolment contracts.

    World/pop/law queries are explicit inputs. Unsupported commands fail closed.
    Country loops are skipped only in these focused single-state checks; engine
    scope traversal, AI law legality and economic behavior require in-game tests.
    """
    def __init__(self):
        self.g={};self.v={};self.mod=set();self.expiry={};self.now=0
        self.inputs={'ffpa_sc_operational':True,'ffpa_sc_education_ready':False,'ffpa_sc_trade_ready':False,'ffpa_sc_eligible':True}
        self.tally=(2,0,3)
    def value(self,s):
        if s in SCALARS:return SCALARS[s]
        if s.startswith('global_var:'):return self.g.get(s[11:],0)
        if s.startswith('var:'):return self.v.get(s[4:],0)
        return float(s)
    def test(self,nodes):
        for e in nodes:
            k,v=e.key,e.value
            if k=='OR':ok=any(self.test([x]) for x in v)
            elif k=='AND':ok=self.test(v)
            elif k=='NOT':ok=not self.test(v)
            elif k=='NOR':ok=not any(self.test([x]) for x in v)
            elif k=='always':ok=v=='yes'
            elif k=='has_global_variable':ok=v in self.g
            elif k=='has_variable':ok=v in self.v
            elif k=='has_modifier':ok=v in self.mod
            elif k=='ffpa_sc_member':ok=('ffpa_sc_membership' in self.v)==(v=='yes')
            elif k=='is_ai':ok=v=='no'
            elif k in self.inputs:ok=self.inputs[k]==(v=='yes')
            elif k.startswith(('var:','global_var:')) or k in SCALARS:
                a,b=self.value(k),self.value(v)
                ok={'=':a==b,'>':a>b,'<':a<b,'>=':a>=b,'<=':a<=b,'!=':a!=b}[e.op]
            elif k.startswith('ffpa_sc_can_join_'):
                trigger=TRIGGERS[k]
                ok=self.test(trigger.value)==(v=='yes')
            elif k=='any_country':ok=False  # only used for vacant seats in clock checks
            else:raise AssertionError(('unsupported test',k,v))
            if not ok:return False
        return True
    def run(self,key):
        if key in ('ffpa_sc_ensure_initialized','ffpa_sc_select_seats','ffpa_sc_fill_seats'):return
        if key=='ffpa_sc_count_votes':
            a,b,n=self.tally
            self.g.update(ffpa_sc_support=a,ffpa_sc_against=b,ffpa_sc_electorate=n,ffpa_sc_quorum_support=a*SCALARS['ffpa_sc_quorum_divisor'])
            return
        self.execute(EFFECTS[key].value)
    def execute(self,nodes):
        taken=False
        for e in nodes:
            k,v=e.key,e.value
            if k in ('if','else_if','else'):
                if k=='if':taken=False
                if not taken and (k=='else' or self.test(child(e,'limit').value)):
                    self.execute([x for x in v if x.key!='limit']);taken=True
                continue
            taken=False
            if k in ('every_country','ordered_country','trigger_event'):continue
            if k in ('set_global_variable','set_variable'):
                dest=self.g if k=='set_global_variable' else self.v
                if isinstance(v,str):dest[v]=1
                else:
                    fields={x.key:x.value for x in v};name=fields['name'];dest[name]=self.value(fields.get('value','1'))
                    duration=float(fields.get('months',0))+12*float(fields.get('years',0))
                    if duration:self.expiry[(k,name)]=self.now+duration
            elif k in ('change_global_variable','change_variable'):
                dest=self.g if k=='change_global_variable' else self.v
                fields={x.key:x.value for x in v};name=fields['name'];a=dest.get(name,0)
                if 'add' in fields:a+=self.value(fields['add'])
                if 'multiply' in fields:a*=self.value(fields['multiply'])
                dest[name]=a
            elif k in ('remove_global_variable','remove_variable'):
                (self.g if k=='remove_global_variable' else self.v).pop(v,None)
                self.expiry.pop(('set_global_variable' if k=='remove_global_variable' else 'set_variable',v),None)
            elif k=='add_modifier':self.mod.add(v)
            elif k=='remove_modifier':self.mod.discard(v)
            elif k in EFFECTS:self.run(k)
            else:raise AssertionError(('unsupported effect',k,v))
    def advance(self,months):
        self.now+=months
        for (kind,name),deadline in list(self.expiry.items()):
            if deadline<=self.now:
                (self.g if kind=='set_global_variable' else self.v).pop(name,None)
                self.expiry.pop((kind,name))
TRIGGERS=load('common/scripted_triggers')

def check_states():
    # Read the actual resolver branches; quorum, ties and abstention are not reimplemented.
    for tally,expected in [((1,0,3),False),((2,0,10),False),((4,3,10),True),((2,2,3),False),((0,0,3),False),((2,0,2),True)]:
        s=State();s.g['ffpa_sc_vote']=1;s.tally=tally;s.run('ffpa_sc_resolve_vote')
        assert ('ffpa_sc_education_open' in s.g)==expected,tally
        assert s.g['ffpa_sc_cooldown']==9
    # Queued proposal opens on one global pulse; exactly three subsequent pulses close it.
    for members in (2,3,10):
        s=State();s.tally=(max(2,(members+2)//3),0,members);s.g['ffpa_sc_pending']=1
        s.run('ffpa_sc_monthly');assert s.g['ffpa_sc_months_left']==3
        for remaining in (2,1):s.run('ffpa_sc_monthly');assert s.g['ffpa_sc_months_left']==remaining
        s.run('ffpa_sc_monthly');assert 'ffpa_sc_vote' not in s.g and s.g['ffpa_sc_cooldown']==9
        for remaining in range(8,0,-1):s.run('ffpa_sc_monthly');assert s.g['ffpa_sc_cooldown']==remaining
        s.run('ffpa_sc_monthly');assert 'ffpa_sc_cooldown' not in s.g
    # Late joining opens no tasks; re-entry cannot refresh the five-year deadline.
    s=State();s.g.update(ffpa_sc_founded=1,ffpa_sc_education_open=1,ffpa_sc_trade_open=1,ffpa_sc_works_open=1)
    s.run('ffpa_sc_join');assert 'ffpa_sc_task' not in s.v
    s.run('ffpa_sc_join_education');assert s.v['ffpa_sc_task']==1
    deadline=s.expiry['set_variable','ffpa_sc_education_window'];assert deadline==60
    assert 'ffpa_sc_education_modifier' not in s.mod
    s.advance(12);s.run('ffpa_sc_leave');s.run('ffpa_sc_join');s.run('ffpa_sc_join_education')
    assert s.expiry['set_variable','ffpa_sc_education_window']==deadline
    s.run('ffpa_sc_join_trade');assert s.v['ffpa_sc_task']==1 and 'ffpa_sc_trade_joined' not in s.v
    # Failure cooldown runs from original deadline, including time spent outside the organization.
    s.advance(48);s.run('ffpa_sc_refresh');assert 'ffpa_sc_task' not in s.v and 'ffpa_sc_education_joined' not in s.v
    s.inputs['ffpa_sc_education_ready']=True;s.run('ffpa_sc_join_education');assert 'ffpa_sc_education_joined' not in s.v
    s.advance(36);s.run('ffpa_sc_join_education');assert 'ffpa_sc_education_modifier' in s.mod and 'ffpa_sc_task' not in s.v
    # Post-compliance regression pauses both sides and never creates a new deadline.
    s.inputs['ffpa_sc_education_ready']=False;s.run('ffpa_sc_refresh');assert 'ffpa_sc_education_modifier' not in s.mod
    s.run('ffpa_sc_leave_education');s.run('ffpa_sc_join_education');assert 'ffpa_sc_task' not in s.v
    s.inputs['ffpa_sc_education_ready']=True;s.run('ffpa_sc_refresh');assert 'ffpa_sc_education_modifier' in s.mod
    s.run('ffpa_sc_leave');assert not s.mod
    # Three-year work benefit and five-year start interval survive cancellation/re-entry.
    s=State();s.inputs['ffpa_sc_has_work']=True
    s.g.update(ffpa_sc_founded=1,ffpa_sc_works_open=1);s.run('ffpa_sc_join')
    s.run('ffpa_sc_start_works');assert s.v['ffpa_sc_task']==3
    assert s.expiry['set_variable','ffpa_sc_works_window']==36
    assert 'ffpa_sc_works_modifier' in s.mod
    s.advance(12);s.run('ffpa_sc_leave');s.run('ffpa_sc_join');s.run('ffpa_sc_start_works')
    assert 'ffpa_sc_task' not in s.v and s.expiry['set_variable','ffpa_sc_works_retry']==60
    s.advance(48);s.run('ffpa_sc_start_works');assert s.v['ffpa_sc_task']==3
    s.advance(36);s.run('ffpa_sc_refresh');assert 'ffpa_sc_works_modifier' not in s.mod and 'ffpa_sc_task' not in s.v
    print('PASS actual-script checks: voting clock/quorum, late join, task cap, retry dates, rollback and cleanup')

def check_static(workshop):
    files=[p for d in ('common','events') for p in (ROOT/d).rglob('*.txt')]
    all_nodes=[]
    for p in files:all_nodes+=list(walk(parse(p.read_text(encoding='utf-8-sig'))))
    definitions={e.key for p in files for e in parse(p.read_text(encoding='utf-8-sig'))}
    for e in all_nodes:
        if e.key.startswith('ffpa_sc_') and e.key not in definitions:
            assert isinstance(e.value,list),('undefined script reference',e.key)
        if e.op in ('>','<','>=','<=') and isinstance(e.value,str) and e.value.startswith('ffpa_sc_'):
            assert e.value in VALUES,('undefined script value',e.value)
    # No force-enacted domestic reform or revived sanctions in the delivered scripts.
    forbidden={'activate_law','change_infamy','end_play','set_country_type','set_institution_investment_level','cancel_enactment','add_enactment_modifier'}
    assert not forbidden.intersection(e.key for e in all_nodes)
    # Independent clock ownership: no per-country/JE callback is allowed to invoke the global clock.
    for p in (ROOT/'common/journal_entries').glob('*.txt'):
        assert not any(e.key in ('change_global_variable','ffpa_sc_monthly') for e in walk(parse(p.read_text()))),p
    assert sum(e.key=='ffpa_sc_monthly' for p in (ROOT/'common/on_actions').glob('*.txt') for e in walk(parse(p.read_text())))==1
    assert len([k for k in load('common/journal_entries') if k.startswith('ffpa_sc_')])==2
    for k,e in load('common/journal_entries').items():
        if k.startswith('ffpa_sc_'):
            assert not any(x.key=='invalid' for x in e.value),k
            assert child(e,'can_deactivate').value=='yes',k
    assert 'ztr_un_permanent_member_ranking_effect' not in {e.key for e in walk(EFFECTS['ffpa_sc_select_seats'].value)}
    mods=load('common/static_modifiers')
    expected={
        'ztr_onu_member':{'country_tech_spread_mult':.1,'country_influence_mult':-.1},
        'ztr_onu_permanent_member':{'country_tech_spread_mult':.1,'country_influence_mult':-.15},
        'ffpa_sc_education_modifier':{'country_tech_spread_mult':.25,'state_education_access_add':.05,'state_pop_qualifications_mult':.25,'country_institution_cost_institution_schools_mult':.25,'country_government_wages_mult':.1},
        'ffpa_sc_trade_modifier':{'state_import_advantage_mult':.25,'state_export_advantage_mult':.25,'state_trade_capacity_mult':.2,'state_tariff_import_add':-.1,'state_tariff_export_add':-.1,'country_bureaucracy_mult':-.05},
        'ffpa_sc_works_modifier':{'state_construction_mult':.2,'state_devastation_decay_mult':.25,'country_construction_goods_cost_mult':.1,'country_bureaucracy_mult':-.05}}
    for key,values in expected.items():assert {e.key:float(e.value) for e in mods[key].value if e.key!='icon'}==values,key
    locales={}
    for lang in ('english','simp_chinese'):
        keys=set()
        for p in (ROOT/'localization'/lang).glob('*.yml'):
            data=p.read_bytes();assert data.startswith(b'\xef\xbb\xbf'),p
            text=data.decode('utf-8-sig');assert text.splitlines()[0]=='l_'+lang+':'
            for line in text.splitlines()[1:]:
                if not line.strip() or line.lstrip().startswith('#'):continue
                m=re.fullmatch(r'\s*([\w.\-]+):(?:\d+)?\s+"(?:[^"\\]|\\.)*"\s*',line)
                assert m,(p,line)
                key=m.group(1);assert key not in keys,(lang,key);keys.add(key)
        locales[lang]=keys
    assert locales['english']==locales['simp_chinese']
    for folder in ('common/scripted_buttons','common/decisions','common/static_modifiers','common/journal_entries'):
        for k,e in load(folder).items():
            if k.startswith('ffpa_sc_'):assert k in locales['english'],k
    assert SCALARS['ffpa_sc_vote_duration']==3 and SCALARS['ffpa_sc_cooldown_duration']==9
    meta=json.loads((ROOT/'.metadata/metadata.json').read_text());assert meta['supported_game_version']=='1.13.*'
    assert {r['id'] for r in meta['relationships']}=={'tech.res','alter_time_2050_fire_falls'}
    assert len(load('common/technology/technologies'))==8
    if workshop:
        sources=json.loads((ROOT/'scripts/compact_upstream_sources.json').read_text())
        for rel,digest in sources.items():assert hashlib.sha256((workshop/rel).read_bytes()).hexdigest()==digest,('upstream changed',rel)
        # Confirm matching event files cover every inherited ID; saves can contain queued events.
        for p in (ROOT/'events').rglob('*.txt'):
            if p.name=='ffpa_survivor_compact.txt':continue
            rel=p.relative_to(ROOT);up=workshop/'3768192009'/rel
            if not up.exists():up=workshop/'3472248460'/rel
            before={e.key for e in parse(up.read_text(encoding='utf-8-sig')) if isinstance(e.value,list)}
            after={e.key for e in parse(p.read_text()) if isinstance(e.value,list)}
            assert before==after,rel
    print(f'PASS static checks: {len(files)} scripts, 8 technologies, paired BOM localization, approved effects, upstream fingerprints')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workshop-root',type=Path);args=ap.parse_args()
    check_static(args.workshop_root);check_states()
