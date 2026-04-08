import sys
import os
from parser import parse_pdf
from agent import generate_slide_spec
from renderer import render_slides


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <paper.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.isfile(pdf_path):
        print(f"Error: file not found: {pdf_path}")
        sys.exit(1)

    print(f"Parsing {pdf_path}...")
    parsed = parse_pdf(pdf_path)
    print(f"  Extracted {len(parsed['figures'])} figure(s)")

    print("Generating slide spec with Claude...")
    spec = generate_slide_spec(parsed["text"], parsed["figures"])
    print(f"  {len(spec['slides'])} slides planned")

    print("Rendering PDF...")
    output = render_slides(spec, parsed["figures_dir"], pdf_path)
    print(f"\nDone. Slides written to: {output}")


if __name__ == "__main__":
    main()
