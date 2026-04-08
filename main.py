import sys
import os
import argparse
from parser import parse_pdf
from agent import generate_slide_spec
from renderer import render_slides


def main():
    ap = argparse.ArgumentParser(description="Generate slides from a scientific PDF")
    ap.add_argument("pdf", help="Path to the input PDF paper")
    ap.add_argument("--presenter", default="",
                    help="Presenter line for the title slide (e.g. 'Presented by Name on Date')")
    args = ap.parse_args()

    pdf_path = args.pdf
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
    output = render_slides(spec, parsed["figures_dir"], pdf_path,
                           presenter=args.presenter)
    print(f"\nDone. Slides written to: {output}")


if __name__ == "__main__":
    main()
