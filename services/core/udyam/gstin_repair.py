"""Repairs an OCR'd GSTIN using the checksum and registry."""

import sys, re, itertools, csv, os
try:
    from udyam.kyc_rules import validate_gstin, gstin_check_char
except ImportError:
    from kyc_rules import validate_gstin, gstin_check_char
TO_DIGIT = {'O':'0','D':'0','Q':'0','I':'1','L':'1','T':'1','Z':'2','S':'5','B':'8','G':'6','A':'4'}
TO_ALPHA = {v:k for k,v in [('O','0'),('I','1'),('Z','2'),('S','5'),('B','8'),('G','6'),('A','4')]}
CONFUSE = {'I':'JLT1','J':'I','1':'IL','L':'1I','T':'I1','O':'0DQ','0':'OD','D':'0O','S':'5','5':'S','B':'8','8':'B','Z':'2','2':'Z','G':'6','6':'G'}
SLOTS = "DDAAAAADDDDAXZX"   # D digit, A alpha, X alnum, Z literal Z
def coerce(raw):
    s = re.sub(r"[^0-9A-Z]", "", raw.upper())
    if len(s) != 15: return s
    out = []
    for ch, t in zip(s, SLOTS):
        if t == 'D': ch = TO_DIGIT.get(ch, ch)
        elif t == 'A': ch = TO_ALPHA.get(ch, ch)
        elif t == 'Z' and ch == '2': ch = 'Z'
        out.append(ch)
    return "".join(out)
def candidates(s, registry=None, max_edits=2):
    if validate_gstin(s)['checksum_ok']: yield s, 0
    pos = [(i, CONFUSE.get(c, '')) for i, c in enumerate(s) if CONFUSE.get(c)]
    for n in range(1, max_edits + 1):
        for combo in itertools.combinations(pos, n):
            for subs in itertools.product(*[alts for _, alts in combo]):
                t = list(s)
                for (i, _), c in zip(combo, subs): t[i] = c
                t = "".join(t)
                if validate_gstin(t)['checksum_ok'] and (registry is None or t in registry): yield t, n
def repair(raw, registry=None, max_edits=2):
    """Return (best_gstin, edits) or (coerced, None) if nothing valid is found."""
    s = coerce(raw)
    if len(s) != 15: return s, None
    for cand, n in candidates(s, registry, max_edits):
        return cand, n
    return s, None
