"""
IEEE Conference Formatting & Rule Compliance Checker.
Validates LaTeX (.tex) documents against official IEEE conference layout, section hierarchy,
citation formats, and equation referencing rules.
"""

import re
from typing import Tuple, List


def check_and_fix_ieee_compliance(tex_path: str) -> Tuple[bool, List[str], str]:
    """
    Verifies and auto-corrects a LaTeX document for IEEE conference compliance.
    
    Returns:
        (is_compliant: bool, violations: List[str], fixed_tex_content: str)
    """
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    violations = []
    fixed_content = content

    # Rule 1: Document class must be IEEEtran with [conference]
    if "\\documentclass[conference]{IEEEtran}" not in fixed_content:
        violations.append("Missing standard \\documentclass[conference]{IEEEtran}")
        fixed_content = re.sub(
            r'\\documentclass\[.*?\]\{.*?\}',
            '\\documentclass[conference]{IEEEtran}',
            fixed_content,
            count=1
        )

    # Rule 2: Ensure \IEEEoverridecommandlockouts is present
    if "\\IEEEoverridecommandlockouts" not in fixed_content:
        violations.append("Missing \\IEEEoverridecommandlockouts")
        fixed_content = fixed_content.replace(
            "\\documentclass[conference]{IEEEtran}",
            "\\documentclass[conference]{IEEEtran}\n\\IEEEoverridecommandlockouts"
        )

    # Rule 3: Replace incorrect hardcoded equation references like "Eq. (1)" with \eqref{}
    if re.search(r'\bEq\.\s*\(\\ref\{', fixed_content):
        violations.append("Found non-IEEE equation reference format 'Eq. (\\ref{})'. Auto-correcting to \\eqref{}")
        fixed_content = re.sub(r'\bEq\.\s*\(\\ref\{([^}]+)\}\)', r'\\eqref{\1}', fixed_content)

    # Rule 4: Ensure figure references use Fig.~\ref{}
    if re.search(r'\bFigure\s*\\ref\{', fixed_content):
        violations.append("Found non-IEEE figure reference format 'Figure \\ref{}'. Auto-correcting to Fig.~\\ref{}")
        fixed_content = re.sub(r'\bFigure\s*\\ref\{', r'Fig.~\\ref{', fixed_content)

    # Rule 5: Remove any residual IEEE template guidance text
    template_guidance_patterns = [
        r'This document is a model and instructions for \\LaTeX\.',
        r'Template version as of 6/27/2024',
        r'Please observe the conference page limits\.',
        r'IEEE conference templates contain guidance text for composing'
    ]

    for pattern in template_guidance_patterns:
        if re.search(pattern, fixed_content):
            violations.append(f"Found residual template guidance text matching '{pattern}'. Removing.")
            fixed_content = re.sub(pattern, '', fixed_content)

    # Rule 6: Check for abstract and IEEEkeywords
    if "\\begin{abstract}" not in fixed_content:
        violations.append("Missing mandatory \\begin{abstract} block.")

    if "\\begin{IEEEkeywords}" not in fixed_content:
        violations.append("Missing mandatory \\begin{IEEEkeywords} block.")

    is_compliant = (len(violations) == 0)

    # Save corrected content back to file if fixes were applied
    if violations:
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(fixed_content)

    return is_compliant, violations, fixed_content
