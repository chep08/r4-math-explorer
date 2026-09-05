# -*- coding: utf-8 -*-
"""H1 密度扫描 P(ρ) —— 真实 Lean-Workbook 库片段(25) + 真实持出目标(30), 真实 Lean。
库密度 ρ 递增 → 目标用"库片段战术 + 模板战术"闭合 → P(ρ)。
batch 摊薄(一次 import 验多候选) + 金标准复核 batch-成功候选。
==> 检验"库密度是否提升真实目标闭合概率"(库边际作用/相变)。
"""
import sys, os, json, re, random
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'src'))
from lean_verifier import LeanVerifier
from lean_batch import batch_verify_many
import pandas as pd

TGT = os.environ.get('LEAN_WORKBOOK_DIR', os.path.join(os.path.dirname(_HERE), 'data', 'Lean-Workbook'))
MECH = ['ring', 'ring_nf', 'norm_num', 'omega', 'linarith', 'nlinarith', 'positivity']

def load_lib():
    lib = []
    with open('lw_lib_full.jsonl', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lib.append(json.loads(line))
    return lib

def load_targets(n=30, seed=99):
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

def density_slice(lib, rho, seed=42):
    n = len(lib)
    size = int(round(n * rho))
    rng = random.Random(seed)
    idx = list(range(n)); rng.shuffle(idx); idx = sorted(idx[:size])
    return [lib[i] for i in idx]

def main():
    lib = load_lib()
    targets = load_targets(30)
    print(f"库片段: {len(lib)} | 目标: {len(targets)}", flush=True)
    v = LeanVerifier(timeout=420)
    pts = []
    for i in range(0, 6):
        rho = round(i / 5, 2)
        lib_slice = density_slice(lib, rho) if rho > 0 else []
        lib_tactic = [f['tactic'] for f in lib_slice]
        # 目标候选 = 库片段战术 + 模板战术(去重)
        cand_set = []
        for t in lib_tactic:
            if t not in cand_set: cand_set.append(t)
        for t in MECH:
            if t not in cand_set: cand_set.append(t)
        # 构造 batch entries
        entries = []
        for ti, tg in enumerate(targets):
            for ci, tac in enumerate(cand_set):
                entries.append({'key': f"t{ti}_c{ci}", 'theorem_statement': tg['theorem_statement'], 'proof_code': '  ' + tac})
        res = batch_verify_many(entries, v, import_line='import Mathlib.Tactic')
        batch_ok = set()
        for e in entries:
            if res.get(e['key']) and res[e['key']].success:
                batch_ok.add(int(e['key'].split('_')[0][1:]))
        closed = 0
        for ti in sorted(batch_ok):
            stmt = targets[ti]['theorem_statement']
            ok = False
            for tac in cand_set:
                r = v.verify(stmt, '  ' + tac, import_line='import Mathlib.Tactic')
                if r.success:
                    ok = True; break
            if ok:
                closed += 1
        p = closed / len(targets)
        pts.append({'rho': rho, 'lib_size': len(lib_slice), 'closed': closed, 'P': round(p, 4)})
        print(f"  ρ={rho} 库size={len(lib_slice)} 闭={closed}/{len(targets)} P={p:.4f}", flush=True)
    with open('lw_h1_rho.json', 'w', encoding='utf-8') as f:
        json.dump({'lib': len(lib), 'targets': len(targets), 'points': pts}, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
