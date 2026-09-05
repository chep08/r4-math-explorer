# -*- coding: utf-8 -*-
"""扩大 Lean-Workbook 闭合基线到 n=150 + 累积库片段(可rw引理), batch 摊薄 + 金标准复核。
用户要求"尽量做全量", 且零 token(纯 Lean)。
"""
import sys, os, json, re, random
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'src'))
from lean_verifier import LeanVerifier
from lean_batch import batch_verify_many
import pandas as pd

TGT = os.environ.get('LEAN_WORKBOOK_DIR', os.path.join(os.path.dirname(_HERE), 'data', 'Lean-Workbook'))
MECH = ['ring', 'ring_nf', 'norm_num', 'omega', 'linarith', 'nlinarith', 'positivity']

def load_proved_unique(n=150, seed=7):
    df = pd.read_parquet(os.path.join(TGT, 'wkbk_1009.parquet'))
    proved = df[df['status'] == 'proved'].drop_duplicates('id')
    rows = []
    for _, r in proved.iterrows():
        fs = r['formal_statement']
        if not fs:
            continue
        stmt = re.sub(r'\s*:=\s*by\s+sorry\s*$', ':= by', fs.strip())
        rows.append({'name': r['id'], 'theorem_statement': stmt})
    random.Random(seed).shuffle(rows)
    return rows[:n]

def main():
    sample = load_proved_unique(150)
    print(f"样本: {len(sample)}", flush=True)
    entries = []
    for ti, t in enumerate(sample):
        for tac in MECH:
            entries.append({'key': f"t{ti}_{tac}", 'theorem_statement': t['theorem_statement'], 'proof_code': '  ' + tac})
    print(f"batch entries: {len(entries)}", flush=True)
    v = LeanVerifier(timeout=420)
    res = batch_verify_many(entries, v, import_line='import Mathlib.Tactic')

    batch_ok = {}
    for e in entries:
        r = res.get(e['key'])
        if r and r.success:
            ti = int(e['key'].split('_')[0][1:]); batch_ok.setdefault(ti, []).append(e['key'].split('_', 1)[1])
    print(f"batch 判 success: {len(batch_ok)} 目标", flush=True)

    closed_list = []
    for ti, tacs in sorted(batch_ok.items()):
        stmt = sample[ti]['theorem_statement']
        closed = False; used = ''
        for tac in MECH:
            if tac not in tacs: continue
            r = v.verify(stmt, '  ' + tac, import_line='import Mathlib.Tactic')
            if r.success:
                closed = True; used = tac; break
        if closed:
            closed_list.append({'name': sample[ti]['name'], 'theorem_statement': stmt, 'tactic': used})
    n = len(closed_list)
    print(f"\n闭合率: {n}/{len(sample)} = {n/len(sample):.3f}", flush=True)
    with open('lw_close150_result.json', 'w', encoding='utf-8') as f:
        json.dump({'n': len(sample), 'closed': n, 'rate': n/len(sample), 'results': closed_list}, f, ensure_ascii=False, indent=2)
    # 累积库片段: 合并已闭合到 lw_lib_full.jsonl
    import os as _os
    existing = []
    if _os.path.exists('lw_lib_full.jsonl'):
        with open('lw_lib_full.jsonl', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.append(json.loads(line))
    seen = {e['problem'] for e in existing}
    new = [c for c in closed_list if c['name'] not in seen]
    existing += [{'problem': c['name'], 'category': 'lean_workbook',
                  'theorem_statement': c['theorem_statement'],
                  'proof_code': '  ' + c['tactic'], 'tactic': c['tactic']} for c in new]
    with open('lw_lib_full.jsonl', 'w', encoding='utf-8') as f:
        for e in existing:
            json.dump(e, f, ensure_ascii=False); f.write('\n')
    print(f"库片段总数: {len(existing)} -> lw_lib_full.jsonl", flush=True)

if __name__ == '__main__':
    main()
