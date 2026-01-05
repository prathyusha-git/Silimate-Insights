from pathlib import Path
from specvalidator.eda_integration.iverilog import lint_rtl

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

def test_lint_orig_logic_clean():
    rtl = str(EXAMPLES / "orig_logic.sv")
    r = lint_rtl(rtl)
    assert r["ok"], f"Lint failed for orig_logic.sv\n{r['stderr']}"

def test_lint_rewrite_logic_clean():
    rtl = str(EXAMPLES / "rewrite_logic.sv")
    r = lint_rtl(rtl)
    assert r["ok"], f"Lint failed for rewrite_logic.sv\n{r['stderr']}"
