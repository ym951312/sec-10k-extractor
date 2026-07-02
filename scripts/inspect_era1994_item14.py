"""READ-ONLY root-cause inspection for the MSFT FY1994 Item 14 finding.
Imports rulesets and prints fields only; modifies nothing, writes no files."""
from sec10k.ruleset.era import ERA_1994, ERA_2020

def es(x):
    if x is None:
        return "None"
    return getattr(x, "name", None) or getattr(x, "value", None) or str(x)

def find_item(era, item_id):
    for it in era.items:
        if getattr(it, "item_id", None) == item_id:
            return it
    return None

print("=== ERA_1994: all ItemRules (item_id / part / expectation) ===")
for it in ERA_1994.items:
    print(f"  {getattr(it,'item_id','?'):<5} part={es(getattr(it,'part',None)):<6} exp={es(getattr(it,'expectation',None))}")

print("\n=== KEY CONTRAST: Item 14 across eras (+ ERA_2020 Item 15) ===")
for tag, era, iid in [
    ("ERA_1994 Item 14 (ground truth: Exhibits / Part IV)", ERA_1994, "14"),
    ("ERA_2020 Item 14 (ground truth: modern / Part III)", ERA_2020, "14"),
    ("ERA_2020 Item 15 (ground truth: Exhibits / Part IV)", ERA_2020, "15"),
]:
    it = find_item(era, iid)
    if it is None:
        print(f"  {tag}: <no such ItemRule>")
    else:
        print(f"  {tag}:")
        print(f"      part={es(getattr(it,'part',None))}  exp={es(getattr(it,'expectation',None))}  topic={getattr(it,'topic','N/A')}")

print("\n=== ERA_1994 legal_structures (is '14' wrongly in IBR absences?) ===")
ls_list = getattr(ERA_1994, "legal_structures", [])
if not ls_list:
    print("  (none)")
for ls in ls_list:
    name = getattr(ls, "name", None) or getattr(ls, "structure_id", None) or getattr(ls, "kind", None)
    print(f"  structure: {es(name)}")
    print(f"      absences: {getattr(ls, 'absences', 'N/A')}")
    print(f"      repr    : {repr(ls)}")
