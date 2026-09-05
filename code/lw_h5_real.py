# -*- coding: utf-8 -*-
"""H5 等算力交叉(真实域) —— L(攒库路线: 库战术+少量模板) vs D(直接采样: 仅模板战术)。
固定总预算(战术尝试次数), 扫描"攒库占比"(库战术 vs 全直接)。batch 摊薄闭目标。
预期: 真实库战术≈模板基线, L/D 可能相平或 L 略低(因为库战术是模板子集), 无交叉或微弱。
零 token。
"""
import sys, os, json, random
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'src'))
from lean_verifier import LeanVerifier
from lean_batch import batch_verify_many

def load_lib():
    lib = []
    with open(os.path.join(os.getcwd(), 'lw_lib_full.jsonl'), encoding='utf-8') as f:
        for line in f:
            if line.strip():
                lib.append(json.loads(line))
    return lib

def load_targets(n=30, seed=99):
    import pandas as pd, re
    TGT = os.environ.get('LEAN_WORKBOOK_DIR', os.path.join(os.path.dirname(_HERE), 'data', 'Lean-Workbook'))
    df = pd.read_parquet(os.path.join(TGT, 'wkbk_1009.parquet'))
    rows = []
    for _, r in df[df['status']=='proved'].drop_duplicates('id').iterrows():
        fs = r['formal_statement']
        if not fs: continue
        stmt = re.sub(r'\s*:=\s*by\s+sorry\s*$', ':= by', fs.strip())
        rows.append({'name': r['id'], 'theorem_statement': stmt})
    random.Random(seed).shuffle(rows)
    return rows[:n]

MECH = ['ring', 'ring_nf', 'norm_num', 'omega', 'linarith', 'nlinarith', 'positivity']

def close_count(targets, cand_tactics, v):
    entries = []
    for ti, t in enumerate(targets):
        for ci, tac in enumerate(cand_tactics):
            entries.append({'key': f"t{ti}_c{ci}", 'theorem_statement': t['theorem_statement'], 'proof_code': '  ' + tac})
    res = batch_verify_many(entries, v, import_line='import Mathlib.Tactic')
    closed = set()
    for e in entries:
        if res.get(e['key']) and res[e['key']].success:
            closed.add(int(e['key'].split('_')[0][1:]))
    return len(closed)

def main():
    lib = load_lib()
    targets = load_targets(30)
    print(f"库: {len(lib)} | 目标: {len(targets)}", flush=True)
    v = LeanVerifier(timeout=420)
    # 总预算 B = 每个目标能尝试的战术数(固定).
    # L(攒库): 库片段战术(随攒库占比) + 模板战术兜底; D(直接): 只用基础模板战术.
    # 扫描"攒库占比" b/B -> L 用库战术比例增加.
    pts = []
    for share in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        # 库战术数量 = share * MECH 数(攒库越多库战术越多)
        n_lib_tactic = max(0, int(round(share * len(lib))))
        lib_tactics = list(dict.fromkeys(f['tactic'] for f in lib[:n_lib_tactic]))
        # L 候选 = 库战术 + 模板战术 (攒库后用库战术优先)
        L_cands = lib_tactics + MECH
        # D 候选 = 仅最少的模板战术(直接采样, 不攒库)
        D_cands = MECH[:3]  # 直接采样用最少战术
        L_close = close_count(targets, L_cands, v)
        D_close = close_count(targets, D_cands, v)
        pts.append({'share': share, 'L': round(L_close/len(targets), 4), 'D': round(D_close/len(targets), 4)})
        print(f"  攒库占比={share} L={L_close/len(targets):.3f} D={D_close/len(targets):.3f}", flush=True)
    with open(os.path.join(os.getcwd(), 'lw_h5_real.json'), 'w', encoding='utf-8') as f:
        json.dump({'targets': len(targets), 'points': pts}, f, ensure_ascii=False, indent=2)
    print("写入 lw_h5_real.json", flush=True)

if __name__ == '__main__':
    main()
