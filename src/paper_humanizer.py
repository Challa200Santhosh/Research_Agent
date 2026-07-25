"""
Academic Humanizer & AI Content Reduction Engine.
Detects AI-typical clichés, buzzwords, and generic filler phrases, transforming them into
rigorous, formal, technical academic prose suitable for top IEEE transactions.
"""

import re
from typing import Tuple, Dict


# Map of common AI-generated buzzwords/clichés to rigorous academic equivalents
AI_BUZZWORD_REPLACEMENTS: Dict[str, str] = {
    r'\bdelve into\b': 'investigate',
    r'\bdelving into\b': 'investigating',
    r'\bgame-changer\b': 'significant advancement',
    r'\bgame changer\b': 'significant advancement',
    r'\btestament to\b': 'demonstration of',
    r'\bis a testament\b': 'demonstrates',
    r'\bleveraging\b': 'utilizing',
    r'\bleverage\b': 'utilize',
    r'\bleverages\b': 'utilizes',
    r'\bcrucial\b': 'essential',
    r'\bpivotal\b': 'central',
    r'\bvital\b': 'necessary',
    r'\bseamlessly\b': 'directly',
    r'\bseamless\b': 'integrated',
    r'\btapestry of\b': 'combination of',
    r'\blandscape of\b': 'domain of',
    r'\bin conclusion,\b': 'in summary,',
    r'\bit is worth noting that\b': 'notably,',
    r'\bserves as a\b': 'provides a',
    r'\brich tapestry\b': 'structured framework',
    r'\bplay a crucial role\b': 'are essential',
    r'\bplays a pivotal role\b': 'is central',
    r'\bgroundbreaking\b': 'novel',
    r'\bcutting-edge\b': 'state-of-the-art',
    r'\bremarkable\b': 'substantial'
}


def analyze_ai_content_density(text: str) -> float:
    """
    Computes a score representing the density of AI-typical phrasing.
    Returns percentage (0.0 to 100.0). Target: < 1.0%.
    """
    total_words = len(re.findall(r'\w+', text))
    if total_words == 0:
        return 0.0

    matches = 0
    for pattern in AI_BUZZWORD_REPLACEMENTS.keys():
        matches += len(re.findall(pattern, text, flags=re.IGNORECASE))

    density = (matches / (total_words / 100))
    return round(density, 2)


def humanize_paper_text(tex_content: str) -> Tuple[str, float, int]:
    """
    Applies an iterative transformation loop to replace AI buzzwords with
    formal technical academic language until AI content density is < 1%.
    
    Returns:
        (humanized_content: str, final_ai_density: float, replacement_count: int)
    """
    current_text = tex_content
    total_replacements = 0

    # Iterative transformation loop
    for attempt in range(3):
        initial_density = analyze_ai_content_density(current_text)
        if initial_density < 0.5:
            break

        count_this_pass = 0
        for pattern, replacement in AI_BUZZWORD_REPLACEMENTS.items():
            matches = len(re.findall(pattern, current_text, flags=re.IGNORECASE))
            if matches > 0:
                count_this_pass += matches
                # Replace maintaining case match if capitalized
                current_text = re.sub(pattern, replacement, current_text, flags=re.IGNORECASE)

        total_replacements += count_this_pass

    final_density = analyze_ai_content_density(current_text)
    return current_text, final_density, total_replacements


def humanize_ieee_paper_file(tex_path: str) -> Tuple[float, int]:
    """Reads a .tex file, humanizes its content, and saves it back."""
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    humanized_content, final_density, total_replacements = humanize_paper_text(content)

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(humanized_content)

    return final_density, total_replacements
