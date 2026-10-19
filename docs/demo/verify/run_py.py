"""backend/app/services/nlu.py 원본을 그대로 불러, 데모와 같은 메뉴로 같은 문장을 읽는다 (LLM 다시 쓰기는 끔)."""
import json, sys, types
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.services import nlu  # noqa: E402

demo = json.loads(sys.argv[1])  # 메뉴·옵션·별명 (run.py 가 data.js 에서 넘김)
cat = nlu.Catalog.__new__(nlu.Catalog)
cat.menus = {m["id"]: types.SimpleNamespace(**m) for m in demo["menus"]}
keys = {(nlu.norm(w), m["id"]) for m in demo["menus"] for w in {m["name"], nlu._base_name(m["name"]), *m["aliases"]}}
cat.menu_keys = sorted(keys, key=lambda k: (-len(k[0]), k[0], k[1]))  # 길이가 같을 때 순서를 JS 와 같게 고정
cat.options = {o["id"]: types.SimpleNamespace(**o) for o in demo["options"]}
okeys = {(nlu.norm(w), o["id"]) for o in demo["options"] for w in {o["name"], *demo["aliases"].get(o["name"], [])}}
cat.option_keys = sorted(okeys, key=lambda k: (-len(k[0]), k[0], k[1]))
out = []
for t in json.loads(Path(__file__).with_name("phrases.json").read_text(encoding="utf-8")):
    p = nlu.parse(t, cat, _rewritten=True)
    out.append({"text": t, "intent": p.intent, "menus": [[m.ref_id, m.is_set, m.quantity] for m in p.menus], "options": [o.ref_id for o in p.options],
                "dine": p.dine_type, "set": p.set_choice, "qd": p.qty_delta, "qa": p.qty_absolute, "cat": p.category})
print(json.dumps(out, ensure_ascii=False))
