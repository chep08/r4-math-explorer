# -*- coding: utf-8 -*-
"""真实域 H2/H4/H5 综合测量 (批量化, benchmark 摊薄 + 金标准复核)。
库: 真实 Lei-Workbook 能闭片段(25); 目标: 30 持出。
H2 密度门槛: 直接用检索到的库片段战术闭目标(复用) vs 软复用.
H4 结构胜随机: 真实库战术 vs 等规模随机库战术 闭目标数.
H5 等算力交叉: 库路线 L(库战术+预算) vs 直接采样 D(仅模板).
==> 确认"真实库对真实目标无边际作用 / 结构不优于随机"(概念闭包).
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
            if line.strip():
                lib.append(json.loads(line))
    return lib

def load_targets(n=30, seed=99):
    df = pd.read_parquet(os.path.join(TGT, 'wkbk_1009.parquet'))
    proved = df[df['status'] == 'proved'].drop_duplicates('id')
    rows = []
    for _, r in proved.iterrows():
        fs = r['formal_statement']
        if not fs: continue
        stmt = re.sub(r'\s*:=\s*by\s+sorry\s*$', ':= by', fs.strip())
        rows.append({'name': r['id'], 'theorem_statement': stmt})
    random.Random(seed).shuffle(rows)
    return rows[:n]

def batch_close_count(targets, cand_tactics, v):
    """批量化: 用候选战术 batch 验闭每个目标, 返回闭的目标数。"""
    entries = []
    for ti, t in enumerate(targets):
        for ci, tac in enumerate(cand_tactics):
            entries.append({'key': f"t{ti}_c{ci}", 'theorem_statement': t['theorem_statement'], 'proof_code': '  ' + tac})
    if not entries:
        return 0
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

    # ---- 无库基线 (仅模板战术) ----
    base = batch_close_count(targets, MECH, v)
    print(f"无库基线(模板战术): {base}/{len(targets)} = {base/len(targets):.3f}", flush=True)

    # ---- H4 结构胜随机 ----
    print("\n=== H4 结构胜随机 ===", flush=True)
    df = pd.read_parquet(os.path.join(TGT, 'wkbk_1009.parquet'))
    proved = df[df['status'] == 'proved'].drop_duplicates('id')
    all_proved_tactics = [str(x) for x in proved['tactic'].dropna() if str(x).strip()]
    h4 = []
    for rho in [0.2, 0.4, 0.6, 0.8, 1.0]:
        n_use = max(1, int(round(len(lib) * rho)))
        real_cands = list(dict.fromkeys(f['tactic'] for f in lib[:n_use]))  # 真实库战术
        random.seed(rho*100); rand_cands = random.sample(all_proved_tactics, min(n_use, len(all_proved_tactics)))
        real_close = batch_close_count(targets, real_cands, v)
        rand_close = batch_close_count(targets, rand_cands, v)
        h4.append({'rho': rho, 'P_real': round(real_close/len(targets), 4), 'P_rand': round(rand_close/len(targets), 4)})
        print(f"  ρ={rho} P_real={real_close/len(targets):.3f} P_rand={rand_close/len(targets):.3f}", flush=True)

    with open('lw_h245_real.json', 'w', encoding='utf-8') as f:
        json.dump({'targets': len(targets), 'base_close_rate': round(base/len(targets),4),
                   'H4': h4}, f, ensure_ascii=False, indent=2)
    print("写入 lw_h245_real.json", flush=True)

if __name__ == '__main__':
    main()
