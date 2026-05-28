from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lab4.binary import ProgramImage
from lab4.disasm import disassemble_image


def main() -> None:
    parser = argparse.ArgumentParser(prog="lab4")
    subparsers = parser.add_subparsers(dest="command", required=True)

    disasm_parser = subparsers.add_parser("disasm", help="disassemble a binary program image")
    disasm_parser.add_argument("binary", type=Path)
    disasm_parser.add_argument("output", type=Path, nargs="?")

    args = parser.parse_args()

    match args.command:
        case "disasm":
            image = ProgramImage.from_bytes(args.binary.read_bytes())
            text = disassemble_image(image)
            if args.output is None:
                sys.stdout.write(text + "\n")
            else:
                args.output.write_text(text + "\n", encoding="utf-8")
        case _:
            msg = "argparse should reject unknown commands"
            raise AssertionError(msg)


if __name__ == "__main__":
    main()
