import json
import os
import anthropic

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system.txt")
MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096


def generate_slide_spec(text: str, figures: list[dict]) -> dict:
    """
    Send paper text and figure list to Claude and return a validated slide spec dict.

    Args:
        text: Full extracted paper text.
        figures: List of {"filename": str, "caption": str} dicts.

    Returns:
        Slide spec dict matching the JSON schema defined in system.txt.
    """
    with open(SYSTEM_PROMPT_PATH) as f:
        system_prompt = f.read()

    figures_section = _format_figures(figures)
    user_message = f"PAPER TEXT:\n\n{text}\n\n---\n\nFIGURES:\n\n{figures_section}"

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the JSON anyway
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    spec = json.loads(raw)
    _validate_spec(spec)
    return spec


def _format_figures(figures: list[dict]) -> str:
    if not figures:
        return "No figures extracted."
    lines = []
    for fig in figures:
        lines.append(f"- {fig['filename']}: {fig['caption']}")
    return "\n".join(lines)


def _validate_spec(spec: dict) -> None:
    if "title" not in spec or "slides" not in spec:
        raise ValueError("Slide spec missing 'title' or 'slides' key")
    if not isinstance(spec["slides"], list) or len(spec["slides"]) == 0:
        raise ValueError("Slide spec 'slides' must be a non-empty list")
    valid_types = {"title", "overview", "content", "figure_only", "conclusion"}
    for i, slide in enumerate(spec["slides"]):
        if slide.get("type") not in valid_types:
            raise ValueError(f"Slide {i} has invalid type: {slide.get('type')!r}")


if __name__ == "__main__":
    # Standalone debug mode: print raw JSON spec for a given PDF
    import sys
    from parser import parse_pdf

    if len(sys.argv) < 2:
        print("Usage: python agent.py <paper.pdf>")
        sys.exit(1)

    parsed = parse_pdf(sys.argv[1])
    spec = generate_slide_spec(parsed["text"], parsed["figures"])
    print(json.dumps(spec, indent=2))
