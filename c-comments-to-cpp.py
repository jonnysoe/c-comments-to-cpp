#!/usr/bin/env python3
# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
"""
  Copyright (C) 2017-2020 Marcus Geelnard

  This software is provided 'as-is', without any express or implied
  warranty.  In no event will the authors be held liable for any damages
  arising from the use of this software.

  Permission is granted to anyone to use this software for any purpose,
  including commercial applications, and to alter it and redistribute it
  freely, subject to the following restrictions:

  1. The origin of this software must not be misrepresented; you must not
     claim that you wrote the original software. If you use this software
     in a product, an acknowledgment in the product documentation would be
     appreciated but is not required.
  2. Altered source versions must be plainly marked as such, and must not be
     misrepresented as being the original software.
  3. This notice may not be removed or altered from any source distribution.
"""

import argparse
import sys
import os


def convert(in_file, out_file, keep_empty_start_end, drop_empty_lines):
    inside_c_comment = False
    comment_style = "//"
    comment_indent = 0
    inside_doxygen = False

    for line in in_file:
        # Start by dropping trailing whitespace from the input.
        line = line.rstrip()
        out_line = ""

        # Cater for empty lines in the middle of comments
        # which we want to be empty comment lines to make
        # it a consistent block.
        if (not drop_empty_lines) and len(line) == 0 and inside_c_comment:
            out_line += comment_style

        inside_string = False
        inside_indentation = True
        start_or_end_line = False
        k = 0
        while k < len(line):
            if inside_string:
                assert k > 0
                if line[k] == '"' and line[k - 1] != "\\":
                    inside_string = False
                out_line += line[k]
                k += 1
            else:
                if inside_c_comment:
                    if inside_indentation:
                        # Check for transition from inside of indentation white space to real comments
                        if (k >= comment_indent) or not (line[k] in [" ", "\t"]):
                            inside_indentation = False
                            # Consume up to len(comment_style) chars from the line.
                            for m in range(k, min(k + len(comment_style), len(line))):
                                if line[m] in [" ", "\t"]:
                                    k += 1
                                elif line[m] == "*" and (
                                    (m + 1) == len(line) or line[m + 1] != "/"
                                ):
                                    k += 1
                                else:
                                    break

                                # Found valid multiline comment, check for real doxygen
                                if not inside_doxygen:
                                    text = line[k:].lstrip()
                                    if len(text) >= 1 and text[0] == "@":
                                        inside_doxygen = True
                                        comment_style = "///"
                                    else:
                                        # Replace downgrade Doxygen comment
                                        comment_style = "//"
                            out_line += comment_style
                            if k < len(line) and not (line[k] in [" ", "\t", "*"]):
                                # Replace skipped starting symbols on multiline string
                                out_line += " "
                    if k < len(line):
                        if (
                            line[k] == "*"
                            and (k + 1) < len(line)
                            and line[k + 1] == "/"
                        ):
                            # Found end of C style comment
                            inside_c_comment = False
                            start_or_end_line = True
                            inside_doxygen = False
                            if k > 0 and line[k - 1] == "*":
                                # Replace '*/' with '**' in case this is a '...*****/'-style line.
                                out_line += "**"
                            out_line += "\n"
                            k += 2
                        else:
                            out_line += line[k]
                            k += 1
                else:
                    if line[k] == "/" and (k + 1) < len(line) and line[k + 1] == "*":
                        # Start of C style comment.
                        comment_indent = k
                        inside_c_comment = True
                        start_or_end_line = True
                        inside_doxygen = False
                        comment_style = "//"
                        k += 2
                        if (
                            (k + 1) < len(line)
                            and line[k] == "*"
                            and line[k + 1] == "/"
                        ):
                            # Ridiculous case of a completely empty, single line C-style comment
                            inside_c_comment = False
                            start_or_end_line = True
                            break
                        if k < len(line) and (line[k] == "*" or line[k] == "!"):
                            if (k + 1) >= len(line) or line[k + 1] != "*":
                                # Start of Doxygen comment.
                                comment_style = "///"
                                k += 1
                                if k < len(line) and line[k] == "<":
                                    # Start of Doxygen after-member comment.
                                    comment_style = "///<"
                                    k += 1
                        out_line += comment_style
                        inside_indentation = False
                    elif line[k] == "/" and (k + 1) < len(line) and line[k + 1] == "/":
                        # Start of C++ style comment.
                        first = k
                        if (k + 2) < len(line) and line[k + 2] == "/":
                            # Found Doxygen comment
                            if not inside_doxygen:
                                if (k + 3) < len(line):
                                    text = line[(k + 3):].lstrip()
                                    if len(text) > 0 and text[0] == "@":
                                        inside_doxygen = True
                            if not inside_doxygen:
                                # Separate `if not`` instead of duplicate codes in multiple `else`
                                # Accidental Doxygen comment. Skip the fisrt extra '/'
                                first += 1
                                if (first + 2) >= len(line):
                                    # Skip empty comment
                                    first = len(line)
                        out_line += line[first:]
                        k = len(line)
                    else:
                        # Normal code
                        inside_doxygen = False
                        if line[k] == '"':
                            # Found string
                            inside_string = True
                        out_line += line[k]
                        k += 1

        # Strip trailing whitespace (including newline chars).
        out_line = out_line.rstrip()

        # Print output if options and circumstances permit.
        empty_comment_line = len(out_line.lstrip()) == len(comment_style)
        if (
            (not empty_comment_line)
            or (start_or_end_line and keep_empty_start_end)
            or (not start_or_end_line and not drop_empty_lines)
        ):
            out_file.write(f"{out_line}\n")


def main():
    # Handle the program arguments.
    parser = argparse.ArgumentParser(
        description="Convert C-style comments to C++-style."
    )
    parser.add_argument(
        "--keep-empty-start-end",
        action="store_true",
        help="preserve empty start/end comment lines",
    )
    parser.add_argument(
        "--drop-empty-lines",
        action="store_true",
        help="drop empty lines in comment blocks",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="edit specified file in-place"
    )
    parser.add_argument("infile", nargs="?", help="input file (default: stdin)")
    parser.add_argument("outfile", nargs="?", help="output file (default: stdout)")
    args = parser.parse_args()

    # Select input and output files.
    in_file = sys.stdin
    out_file = sys.stdout

    if args.infile:
        in_file = open(args.infile, "r", encoding="utf8")
    # Defaults to output to outfile
    outfile = args.outfile
    if not outfile and args.inplace:
        # If outfile wasn't provided then check for --inplace option
        # Append ".bak" to infile
        # Python cannot use the same file for different input/output streams
        outfile = args.infile + ".bak"
    if outfile:
        out_file = open(outfile, "w", encoding="utf8")

    convert(
        in_file=in_file,
        out_file=out_file,
        keep_empty_start_end=args.keep_empty_start_end,
        drop_empty_lines=args.drop_empty_lines,
    )

    if outfile.endswith(".bak"):
        os.rename(outfile, args.infile)

if __name__ == "__main__":
    main()
