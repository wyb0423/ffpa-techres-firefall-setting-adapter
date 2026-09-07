"""Small ordered Clausewitz reader for validation and scoped upstream edits."""
from __future__ import annotations
from dataclasses import dataclass
import re
TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|(?:\?=|>=|<=|!=|=|>|<)|[^\s{}=<>!?#]+')
@dataclass
class Entry:
    key: str
    op: str | None
    value: object
    start: int
    end: int

def parse(text):
    tokens=[]
    pos=0
    for m in TOKEN.finditer(text.lstrip('\ufeff')):
        if m.start()!=pos:
            raise ValueError(f'Unparsed input near {text[pos:pos+30]!r}')
        pos=m.end()
        tok=m.group()
        if not tok.isspace() and not tok.startswith('#'):
            tokens.append((tok,m.start(),m.end()))
    if pos!=len(text.lstrip('\ufeff')):
        raise ValueError('Unparsed suffix')
    def block(i, nested):
        out=[]
        while i<len(tokens):
            key,start,end=tokens[i]; i+=1
            if key=='}':
                if not nested: raise ValueError('Unexpected closing brace')
                return out,i,end
            if key=='{': raise ValueError('Unexpected opening brace')
            if i<len(tokens) and tokens[i][0] in ('=','?=','>=','<=','!=','>','<'):
                op=tokens[i][0]; i+=1
                if i>=len(tokens): raise ValueError('Missing value')
                v,_,end=tokens[i];i+=1
                if v=='{': v,i,end=block(i,True)
                elif v=='}': raise ValueError('Missing value before closing brace')
                out.append(Entry(key,op,v,start,end))
            else: out.append(Entry(key,None,None,start,end))
        if nested: raise ValueError('Unclosed block')
        return out,i,len(text)
    return block(0,False)[0]

def walk(entries):
    for e in entries:
        yield e
        if isinstance(e.value,list): yield from walk(e.value)

def child(entry,key):
    return next(e for e in entry.value if e.key==key)
