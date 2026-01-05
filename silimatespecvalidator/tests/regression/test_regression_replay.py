from pathlib import Path
from specvalidator.eda_integration.iverilog import run_simulation
from specvalidator.testing.regression_store import load_failures

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
ORIG_RTL = str(EXAMPLES / "orig_logic.sv")
REWRITE_RTL = str(EXAMPLES / "rewrite_logic.sv")

def test_replay_saved_equivalence_failures():
    failures = load_failures()
    # If none saved yet, this test should still pass (nothing to replay).
    for rec in failures:
        inputs = rec["inputs"]
        y_orig = run_simulation(ORIG_RTL, "orig_logic", inputs)
        y_rewrite = run_simulation(REWRITE_RTL, "rewrite_logic", inputs)
        assert y_orig == y_rewrite, f"Regression failure for inputs={inputs}"

#we record evry failure once and automatically ensure it doesn't come back as even the copilot evolves
#copilot geneartes rtl, then one input causes a functional mismatch 
#tester sees it,reports and engineer fixes it, again after a time period, lets suppose say the same bug rises again
#so we jsut save the exact input it breaked for and store it permanently