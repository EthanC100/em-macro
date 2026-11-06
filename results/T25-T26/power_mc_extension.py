# T25-T26 pre-registration: extension-length table (§5.1). Run from the repository root after power_mc.py exists.
import importlib.util, sys
spec = importlib.util.spec_from_file_location("p3", "results/T25-T26/power_mc.py")
src = open("results/T25-T26/power_mc.py").read().split("for name, sc in")[0]
ns = {}
exec(src, ns)
for T2 in (84, 96, 120, 156):
    for sc in (1.0, 0.0):
        o = ns["run"](sc, n=6000, T2=T2)
        print(T2, "real" if sc else "zero", {k: (round(float(v["final: confirmed"]), 3), round(float(v["of which at 8y"]), 3), round(float(v["inconclusive->decayed at 8y"]), 3)) for k, v in o.items()})
