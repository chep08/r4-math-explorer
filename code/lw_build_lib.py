# -*- coding: utf-8 -*-
"""Lean-Workbook 全量闭合基线 + 库片段构建 (n=50, batch 摊薄 + 金标准复核, 4.8.0-rc1)。
1) 扫 proved 前 50 个不同 id, batch 验单步机械战术, 得闭合率(基线大样本)。
2) 能闭的命题作为"库片段"(formal_statement + 闭合 tactic) 供 H1/H2/H3 复用。
"""
import sys, os, json, re, random
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'src'))
from lean_verifier import LeanVerifier
from lean_batch import batch_verify_many
import pandas as pd

TGT = os.environ.get('LEAN_WORKBOOK_DIR', os.path.join(os.path.dirname(_HERE), 'data', 'Lean-Workbook'))
MECH = ['ring', 'ring_nf', 'norm_num', 'omega', 'linarith', 'nlinarith', 'positivity']

def load_proved_unique(n=50, seed=42):
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
    sample = load_proved_unique(50)
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

    # 金标准复核 batch-ok 目标, 记录闭合 tactic
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
        print(f"  [复核] {sample[ti]['name']} closed={closed} ({used})", flush=True)

    n = len(closed_list)
    print(f"\n闭合率: {n}/{len(sample)} = {n/len(sample):.3f}", flush=True)
    with open('lw_close50_result.json', 'w', encoding='utf-8') as f:
        json.dump({'n': len(sample), 'closed': n, 'rate': n/len(sample), 'results': closed_list}, f, ensure_ascii=False, indent=2)
    # 库片段 = 闭合的命题(含证明战术)
    with open('lw_lib_full.jsonl', 'w', encoding='utf-8') as f:
        for c in closed_list:
            json.dump({'problem': c['name'], 'category': 'lean_workbook',
                       'theorem_statement': c['theorem_statement'],
                       'proof_code': '  ' + c['tactic'], 'tactic': c['tactic']}, f, ensure_ascii=False)
            f.write('\n')
    print(f"库片段(可rw引理): {len(closed_list)} -> lw_lib_full.jsonl", flush=True)

if __name__ == '__main__':
    main()
