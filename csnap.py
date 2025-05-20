#!/bin/env python3

import os
import sys
import datetime
import shutil
import argparse
import subprocess
import tempfile

from shutil import which

import pygments
from pygments.token import Token
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.formatter import Formatter


class PangoFormatter(Formatter):
    """Based on the HTML 3.2 formatter in pygments:
    http://pygments.org/docs/formatterdevelopment/"""

    def __init__(self, **options):
        Formatter.__init__(self, **options)

        self.styles = {}

        for token, style in self.style:
            start_tag = close_tag = ""

            if style["color"]:
                start_tag += '<span fgcolor="#%s">' % style["color"]
                close_tag = "</span>" + close_tag

            if style["bold"]:
                start_tag += "<b>"
                close_tag = "</b>" + close_tag

            if style["italic"]:
                start_tag += "<i>"
                close_tag = "</i>" + close_tag

            if style["underline"]:
                start_tag += "<u>"
                close_tag = "</u>" + close_tag

            self.styles[token] = (start_tag, close_tag)

    def format(self, tokensource, outfile):
        lastval = ""
        lasttype = None

        for ttype, value in tokensource:
            while ttype not in self.styles:
                ttype = ttype.parent

            if ttype == lasttype:
                lastval += value
            else:
                if lastval:
                    stylebegin, styleend = self.styles[lasttype]
                    outfile.write(stylebegin + lastval + styleend)

                lastval = value
                lasttype = ttype

        if lastval:
            stylebegin, styleend = self.styles[lasttype]
            outfile.write(stylebegin + lastval + styleend)


def snap_snippet(
    snippets,
    background,
    dpi,
    output_file,
    fix_width=True,
    width=800,
    sshoot=False,
    foreground=None,
):
    pango_view = which("pango-view")
    xclip = which("xclip")

    tmp_outs = []

    for n, snippet in enumerate(snippets, start=1):
        try:
            tmp_in = tempfile.NamedTemporaryFile(
                delete=False, prefix="codesnap.", mode="w"
            )
            # Currently leaks with no solution
            tmp_out = tempfile.NamedTemporaryFile(
                delete=False,
                prefix="codesnap.%02i." % n,
                mode="rb",
                suffix=".png",
            )

            tmp_in.write(snippet)
            tmp_in.close()

            w = ["--width=%i" % width] if fix_width else []
            f = ["--foreground=%s" % foreground] if foreground else []

            pango_params = [
                pango_view,
                "--background=%s" % background,
                "--markup",
                *w,
                *f,
                "--wrap=word-char",
                "--font=mono",
                "--dpi=%i" % dpi,
                "-qo",
                tmp_out.name,
                tmp_in.name,
            ]

            p = subprocess.Popen(pango_params)
            p.wait()
            tmp_outs.append(tmp_out.name)
        finally:
            os.unlink(tmp_in.name)
            tmp_in.close()
            tmp_out.close()
    SHOTS_DIR = os.path.expanduser("~/shots")
    if output_file is not None or (sshoot and os.path.exists(SHOTS_DIR)):
        if sshoot:
            n = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            output_file = os.path.join(SHOTS_DIR, "screenshot-%s" % n)
        for n, ft in enumerate(tmp_outs, start=1):
            outfl = output_file + ("-%i" % n) + ".png"
            shutil.copyfile(ft, outfl)
    else:
        xclip_params = [
            xclip,
            "-select",
            "clipboard",
            "-i",
        ]
        p = subprocess.Popen(
            # Crucial for xclip to redirect to DEVNUL - https://emacs.stackexchange.com/questions/39019/xclip-hangs-shell-command
            xclip_params,
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        for ft in tmp_outs:
            p.stdin.write(ft.encode("ascii") + b"\n")
        p.stdin.close()
        p.wait()

    return tmp_outs


def get_args():
    parser = argparse.ArgumentParser(
        description="Make a source file into image on the clipboard"
    )
    parser.add_argument("-f", "--inputfile", help="Input source file")
    parser.add_argument(
        "-o", "--outputfile", help="If set don't copy to clipboard but save to a file"
    )
    parser.add_argument("--dpi", default=70, type=int, help="DPI of the result image")
    parser.add_argument("--style", default="dracula", help="Pygments style")
    parser.add_argument(
        "-l",
        "--lang",
        default=None,
        help="Force lexer for specified language to be used",
    )
    parser.add_argument("-t", "--title", default=None, help="Explicitly set title")
    parser.add_argument(
        "-n",
        "--linenos",
        action="store_true",
        default=False,
        help="Force line numbering",
    )
    parser.add_argument(
        "-s",
        "--startline",
        type=int,
        default=1,
        help="Change start line for line numbering",
    )
    parser.add_argument(
        "-x",
        "--fixwidth",
        action="store_true",
        default=False,
        help="Force width to be set in `pango-view`",
    )
    parser.add_argument(
        "-a",
        "--ansi",
        action="store_true",
        default=False,
        help="Enable ansi processing by ansifilter",
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=800,
        help="Set explicit width for `pango-view` (default: 800)",
    )
    parser.add_argument(
        "-m",
        "--maxlines",
        type=int,
        default=1000,
        help="Max lines per snapshot",
    )
    parser.add_argument(
        "-c",
        "--splitat",
        default="\n\n",
        help="Do not split unless at this sgring sequence",
    )
    parser.add_argument(
        "-y",
        "--sshoot",
        action="store_true",
        default=False,
        help="Save to special folder used for rapid screenshots",
    )
    args = parser.parse_args()
    return args


class LineNum(object):
    def __init__(self, begin, end, startline=1):
        self.begin = begin
        self.end = end
        self.lineno = startline - 1

    def next(self):
        self.lineno += 1
        return self.begin + ("% 5i " % self.lineno) + self.end


def split_big_snippet(text, max_lineno_split=1000, split_at="\n\n\n"):
    i = 0
    r0 = 0
    r = 0
    while r != -1:
        r = text.find("\n", r + 1)
        i += 1
        if i + 1 >= max_lineno_split:
            r = text.find(split_at, r + 1)
            if r >= 0:
                yield text[r0:r]
                r0 = r
            i = 0
        if r < 0:
            yield text[r0:]


def format_text(
    input_text,
    lx,
    st,
    title=None,
    linenos=True,
    startline=1,
    max_lineno_split=1000,
    split_at="\n\n\n",
):
    snippets = split_big_snippet(
        input_text, max_lineno_split=max_lineno_split, split_at=split_at
    )
    lnum = LineNum(
        '<span fgcolor="' + st.styles[Token.Comment] + '">',
        "</span>",
        startline=startline,
    )
    for snippet in snippets:
        # The highlighter highlights (i.e., adds tags around) operators
        # (& and ;, here), so let's use a non-highlighted keyword, and escape them
        # after highlighting.
        text = snippet.replace("&", "__AMP__").replace("<", "__LT__")

        # Pygments messes up initial and final newlines; fix up
        begin = ""
        if text[:1] == "\n":
            begin = "\n"
            text = text[1:]
        end = ""
        if text[-1:] == "\n":
            end = "\n"
            text = text[:-1]

        text = pygments.highlight(text, lx, PangoFormatter(style=st))

        # Show line numbers when processing whole files
        if linenos:
            text = lnum.next() + "".join(
                [line + "\n" + lnum.next() for line in text.split("\n")]
                if "\n" in text
                else text
            )

        if text[0] == "\n" and begin == "\n":
            begin = ""
        if text[-1] == "\n" and end == "\n":
            end = ""

        text = text.replace("__AMP__", "&amp;").replace("__LT__", "&lt;")

        text = begin + text + end

        if title:
            title_str = '<span fgcolor="%s">\n' % st.styles[Token.Comment]
            title_str += "=" * 80 + "\n"
            title_str += "%s\n" % title
            title_str += "=" * 80 + "\n"
            title_str += "</span>\n"
            text = title_str + text

        yield text


def ansi_to_pango(input_text):
    ansifilter = which("ansifilter")
    params = [
        ansifilter,
        "--font=mono",
        "--font-size=12",
        "--pango",
    ]
    p = subprocess.Popen(
        params,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    out, err = p.communicate(input_text.encode("utf-8", errors="ignore"))
    return [out.decode("utf-8", errors="ignore")]


def main():
    args = get_args()

    if args.inputfile is None:
        snippet = "".join([line for line in sys.stdin]).rstrip()
    else:
        snippet = open(args.inputfile, "r").read()

    title = args.title if args.title else (args.inputfile if args.inputfile else None)

    st = get_style_by_name(args.style)

    if not args.ansi:
        try:
            if args.lang is not None:
                lx = get_lexer_by_name(args.lang)
            elif args.inputfile is not None:
                lx = get_lexer_for_filename(args.inputfile)
            else:
                lx = get_lexer_by_name("text")
        except pygments.util.ClassNotFound:
            lx = get_lexer_by_name("text")

        ftexts = format_text(
            snippet,
            lx,
            st,
            title=title,
            linenos=args.inputfile is not None or args.linenos,
            startline=args.startline,
            max_lineno_split=args.maxlines,
            split_at=args.splitat,
        )
    else:
        ftexts = ansi_to_pango(snippet)

    snap_snippet(
        ftexts,
        st.background_color,
        args.dpi,
        args.outputfile,
        fix_width=args.inputfile is not None or args.fixwidth,
        width=args.width,
        sshoot=args.sshoot,
        foreground="white" if args.ansi else None,
    )


if __name__ == "__main__":
    main()
