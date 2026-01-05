from __future__ import annotations
from dataclasses import dataclass, asdict
#imports dataclass to define simple "data container" classes without writing boiler plate
from pathlib import Path
#imports path, an object-oriented way to work with file paths
import re
#imports the regular expressions module, used for searching patterns in text
from typing import Dict, Any
#imports type hints:

_OP_PATTERNS = {
    "op_add": r"\+",
    "op_sub": r"-",
    "op_mul": r"\*",
    "op_xor": r"\^",
    "op_and": r"&",
    "op_or": r"\|",
    "op_not": r"~",
    "op_shl": r"<<",
    "op_shr": r">>",
    "op_ternary": r"\?",
}
#op_patterns is a dictionary whose keys are operation names and whose values are regex patterns
#describing those operators in the rtl code

_KEYWORDS = {
    "always_ff": r"\balways_ff\b",
    "always_comb": r"\balways_comb\b",
    "assign": r"\bassign\b",
    "case": r"\bcase\b",
    "if": r"\bif\b",
    "for": r"\bfor\b",
    "generate": r"\bgenerate\b",
}
#keywords maps names like "always_ff" to regex patterns that match the whole word.
#frozen=True makes instances immutable,:once created, you can't change their attributes(like a read-only record)
@dataclass(frozen=True)
class RTLFeatures:
    lines: int #how many lines of code in the file
    always_ff: int
    always_comb: int
    assign: int
    mux_ternary: int #count of ternary ? operators
    bitwidth_tokens: int
    max_ops_in_line: int
    op_counts: Dict[str, int]
    keyword_counts: Dict[str, int]

    #to_dict returns a normal python dictionary of all fields and their values
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d
    #asdict(self) is a helper from dataclasses that does the cnversion

def _count_regex(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))
 #takes text(a string with the rtl code) and pattern (a regex string)
#uses re.findall to find all matches of pattern in text, returns all the matches as an integer
#defines a function that: accepts rtl_path which can be string or path
#returns an rtl features instance describing that file 
def extract_features(rtl_path: str | Path) -> RTLFeatures:
    p = Path(rtl_path)
    text = p.read_text(encoding="utf-8", errors="ignore")#skips an invalid character are skipped rather than raising an error, beacause of ignore
    lines = text.splitlines()
    #splits the file text into a list of lines at newline characters
    keyword_counts = {k: _count_regex(text, pat) for k, pat in _KEYWORDS.items()}
    #same idea, but counts operators instead of keywords
    op_counts = {k: _count_regex(text, pat) for k, pat in _OP_PATTERNS.items()}
    #uses a dictionary to build keyword_counts: 
    # bitwidth tokens like [7:0], [31:0]
    bitwidth_tokens = len(re.findall(r"\[\s*\d+\s*:\s*\d+\s*\]", text))

    # max ops in a single line (proxy for combinational complexity)
    max_ops = 0
    for ln in lines:
        # ignore comments
        ln2 = ln.split("//")[0]
        ops_in_line = 0
        
        #loops over each operator pattern pat, finds all the occurences of that operator in the line  
        for pat in _OP_PATTERNS.values():
            ops_in_line += len(re.findall(pat, ln2))
        if ops_in_line > max_ops:
            max_ops = ops_in_line
        #if the line has more operators than any previous line update the max_ops
    return RTLFeatures(
        lines=len(lines),
        always_ff=keyword_counts.get("always_ff", 0),
        always_comb=keyword_counts.get("always_comb", 0),
        assign=keyword_counts.get("assign", 0),
        mux_ternary=op_counts.get("op_ternary", 0),
        bitwidth_tokens=bitwidth_tokens,
        max_ops_in_line=max_ops,
        op_counts=op_counts,
        keyword_counts=keyword_counts,
    )

#creates and returns an rtl features object using all the computed values
#compare before and after 
def diff_features(before: RTLFeatures, after: RTLFeatures) -> Dict[str, Any]:
    """Return deltas (after - before) for key numeric fields."""
    return {
        "d_lines": after.lines - before.lines,
        #difference in the total lines of code
        "d_always_ff": after.always_ff - before.always_ff,
        #how many more or fewer of those constructs in the rewritten code
        "d_always_comb": after.always_comb - before.always_comb,
        "d_assign": after.assign - before.assign,
        "d_mux_ternary": after.mux_ternary - before.mux_ternary,
        "d_bitwidth_tokens": after.bitwidth_tokens - before.bitwidth_tokens,
        "d_max_ops_in_line": after.max_ops_in_line - before.max_ops_in_line,
        "d_op_add": after.op_counts.get("op_add", 0) - before.op_counts.get("op_add", 0),
        "d_op_mul": after.op_counts.get("op_mul", 0) - before.op_counts.get("op_mul", 0),
        "d_op_xor": after.op_counts.get("op_xor", 0) - before.op_counts.get("op_xor", 0),
    }
#extarcting all the rtl before and after features so to evaluate the qulaity and the competence of its intelligence with the input it is getting
#summarise an rtl file numerically , using extract_features(foo.sv), you get a small structured object that tells the comparision between both rtl's
#as a qa signal, you can flag rewrites that suddenly add a lot of operators, or does weird things, before running full ppa or simulation
#as a feature generator, these numbers can feed into an ml model which predicts acceptance, rollback risk or ppa risk for a suggestion.
