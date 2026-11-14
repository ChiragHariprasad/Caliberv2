import re
from pathlib import Path

files = [
    Path(r"e:\Caliberv2\frontend\src\components\integrity\IntegrityMatrix.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\integrity\DecisionInspector.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\logic_lab\SiaLogicLabView.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\logic_lab\SuperpositionView.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\logic_lab\EntanglementGraph.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\logic_lab\ContextualityDag.tsx"),
    Path(r"e:\Caliberv2\frontend\src\components\logic_lab\StateAlgebraTree.tsx")
]

styles = Path(r"e:\Caliberv2\frontend\src\styles.css").read_text(encoding="utf-8")

for f in files:
    content = f.read_text(encoding="utf-8")
    classes = set()
    for m in re.finditer(r'className=(?:\{`([^`]+)`\}|"([^"]+)")', content):
        raw = m.group(1) or m.group(2)
        # split by whitespace and filter template interpolations
        for c in raw.split():
            if not c.startswith('$') and not '${' in c:
                classes.add(c)
    
    missing = [c for c in sorted(classes) if f".{c}" not in styles]
    print(f"=== {f.name} ({len(classes)} classes) ===")
    if missing:
        print(f"  Missing in styles.css: {missing}")
    else:
        print("  All classes found in styles.css!")
