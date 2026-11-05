#!/usr/bin/env python3
"""
dump_claude_context.py
Exports a token-optimized briefing of NOVA 2.0 designed to give Claude (or any LLM)
complete working knowledge of the codebase in ~1,200 tokens.

Usage:
    python scripts/dump_claude_context.py          # Prints briefing to stdout with token stats
    python scripts/dump_claude_context.py --copy   # Copies directly to Windows clipboard
    python scripts/dump_claude_context.py --save   # Saves to CLAUDE_CONTEXT.txt
"""

import os
import sys
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT_DIR / "CLAUDE.md"

def get_git_info() -> str:
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        last_commit = subprocess.check_output(["git", "log", "-1", "--oneline"], cwd=ROOT_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        return f"Git Branch: {branch} | Last Commit: {last_commit}"
    except Exception:
        return "Git info unavailable"

def copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text, encoding="utf-8", check=True)
        return True
    except Exception:
        try:
            process = subprocess.Popen(["powershell", "-Command", "Set-Clipboard -Value $input"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return process.returncode == 0
        except Exception:
            return False

def main():
    copy_flag = "--copy" in sys.argv or "-c" in sys.argv
    save_flag = "--save" in sys.argv or "-s" in sys.argv

    if not CLAUDE_MD.exists():
        print(f"[ERROR] CLAUDE.md not found at {CLAUDE_MD}")
        sys.exit(1)

    claude_content = CLAUDE_MD.read_text(encoding="utf-8")
    git_info = get_git_info()

    header = f"""<!-- NOVA 2.0 AI AGENT CONTEXT BRIEFING -->
<!-- {git_info} -->
<!-- Paste this entire block into a new Claude chat. Consumes ~1,200 tokens. -->

"""
    full_output = header + claude_content

    words = len(full_output.split())
    tokens = int(words * 1.3)
    chars = len(full_output)

    if copy_flag:
        success = copy_to_clipboard(full_output)
        if success:
            print(f"[SUCCESS] Copied NOVA 2.0 context to clipboard! (~{tokens} tokens, {chars} characters)")
            print("Now open Claude (or any new chat) and press Ctrl+V.")
        else:
            print("[WARNING] Could not copy to clipboard. Printing to stdout instead:")
            print(full_output)
    elif save_flag:
        out_file = ROOT_DIR / "CLAUDE_CONTEXT.txt"
        out_file.write_text(full_output, encoding="utf-8")
        print(f"[SUCCESS] Saved context to {out_file} (~{tokens} tokens, {chars} characters)")
    else:
        print(full_output)
        print("-" * 60, file=sys.stderr)
        print(f"Stats: ~{tokens} tokens | {words} words | {chars} characters", file=sys.stderr)
        print("Tip: Run with '--copy' to copy directly to clipboard:", file=sys.stderr)
        print("     python scripts/dump_claude_context.py --copy", file=sys.stderr)
        print("-" * 60, file=sys.stderr)

if __name__ == "__main__":
    main()
