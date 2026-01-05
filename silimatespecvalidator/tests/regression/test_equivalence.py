import random #used to generate random test inputs
from pathlib import Path
from specvalidator.eda_integration.iverilog import run_simulation
from specvalidator.testing.regression_store import append_failure, load_failures #imports a helper that compiles/runs a system verilog design and returns the output for given inputs
#Imports a helper that logs failing test cases into some regression file/store.
# Resolve paths robustly from this test file location
ROOT = Path(__file__).resolve().parents[1]   # .../silimate-specvalidator
EXAMPLES = ROOT / "examples"
ORIG_RTL = str(EXAMPLES / "orig_logic.sv")
REWRITE_RTL = str(EXAMPLES / "rewrite_logic.sv")

def test_equivalence_orig_vs_rewrite():
    """
    Verify that rewritten RTL is functionally equivalent
    to original RTL for multiple random inputs.
    """

    for _ in range(20):
        inputs = {
            "a": random.randint(0, 1),
            "b": random.randint(0, 1),
            "c": random.randint(0, 1),#we might need to consider some more edge cases, i think?
        }

        y_orig = run_simulation(#run simulation for original version that the user gives
            rtl_file=ORIG_RTL,
            top_module="orig_logic",
            inputs=inputs
        )

        y_rewrite = run_simulation(#run simulation for original version that the silimate-copilot gives
            rtl_file=REWRITE_RTL,
            top_module="rewrite_logic",
            inputs=inputs
        )
        #logging mismatches and failing the test
        if y_orig != y_rewrite:
            append_failure(
                inputs=inputs,
                meta={"y_orig": y_orig, "y_rewrite": y_rewrite}
            )
            assert False, f"Mismatch for inputs {inputs} (saved to regressions/equiv_vectors.jsonl)"
        #raise an assertion failure with a descriptive message, causing the test to fail for that input set

def test_regression_replay_saved_failures():
    """
    Replay equivalence failures saved previously.
    If no failures exist yet, this test passes (nothing to replay).
    """

    failures = load_failures()
    if not failures:
        return  # nothing to replay yet

    for rec in failures:
        inputs = rec["inputs"]

        y_orig = run_simulation(
            rtl_file=ORIG_RTL,
            top_module="orig_logic",
            inputs=inputs
        )

        y_rewrite = run_simulation(
            rtl_file=REWRITE_RTL,
            top_module="rewrite_logic",
            inputs=inputs
        )

        assert y_orig == y_rewrite, f"Regression failure for saved inputs={inputs}"