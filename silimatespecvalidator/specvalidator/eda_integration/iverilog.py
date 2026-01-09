import subprocess #command line tools
import tempfile
import os #for operating system tasks such as building file paths, checking files
#this function expects a first input called rtl_file, which should be text string pointing to a verilog/system verilog source file on disk
#second input: the name of the top level hardware module inside that file
#third input: a dictionary, inputs: dict like {"a": 0, "b": 1, "c": 0}
  
def run_simulation(rtl_file: str, top_module: str, inputs: dict):
    """
    Compile and simulate a simple combinational module using iverilog.
    inputs: dict like {"a": 0, "b": 1, "c": 0}
    Returns output value of y.
    """
    #creates a temporary folder on disk and calls it tmpdir
    #everthying inside this with block uses that folder, when teh block ends, python automatically deletes
    #generate a simple testbench
    with tempfile.TemporaryDirectory() as tmpdir:
        tb_path = os.path.join(tmpdir, "tb.v")
        out_path = os.path.join(tmpdir, "a.out")

        # Generate a simple testbench
        with open(tb_path, "w") as f:
            f.write(f"""
module tb;
  reg a, b, c;
  wire y;

  {top_module} dut(.a(a), .b(b), .c(c), .y(y));

  initial begin
    a = {inputs['a']};
    b = {inputs['b']};
    c = {inputs['c']};
    #1;
    $display("%b", y);
    $finish;
  end
endmodule
""")

        # Compile
        compile_cmd = ["iverilog", "-g2012", "-o", out_path, rtl_file, tb_path]
        subprocess.check_call(compile_cmd)

        # Run
        result = subprocess.check_output(["vvp", out_path], text=True)
        # Take only the first non-empty line (the $display output)
        lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
        return int(lines[0], 2)  # base-2 because we printed %b
        #The printed value of y from $display will be in result

def lint_rtl(rtl_file: str):
    """
    Lint RTL by asking iverilog to elaborate it.
    Returns a dict with: ok (bool), stderr (str)
    """
    # -g2012: SystemVerilog
    # -Wall: enable warnings
    # -tnull: compile/elaborate only, no output file
    cmd = ["iverilog", "-g2012", "-Wall", "-tnull", rtl_file]
    #cmd is a list describing the comamnd to run "iverilog" the program, and the next three options, and the rtl_file, the design file to check
    #runs the command and waits for it to finish and returns a completed process object p
    #so p now conatins, normal output from verilog, p.stderr,errors and warnings from verilog
    p = subprocess.run(cmd, capture_output=True, text=True)
    stderr = (p.stderr or "").strip()
    stdout = (p.stdout or "").strip()
  #if p.stderr is None, use "" empty string instead
    # iverilog writes most diagnostics to stderr; treat nonzero returncode as fail
    ok = (p.returncode == 0)
    #0 if success and non zero if failure
    return {
        "ok": ok,
        "stderr": stderr,
        "stdout": stdout,
        "returncode": p.returncode,
    }