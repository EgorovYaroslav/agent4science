"""
clear.py — reset project to clean state for a new study.

Removes all generated files and artifacts, leaving only:
  - init commit files (AGENT.md, literature/, materials/,
    notes/paper/ai4math_ysda2026_template/, skills/)
  - statement/MOTIVATION.md  (the research question)
  - statement/diary.md       (empty placeholder)
  - statement/STATUS.md      (template placeholder)

Usage:
    python3 clear.py
"""

import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

KEEP_DIRS = {
    'statement',
    'literature',
    'materials',
    'notes',
    'skills',
}

KEEP_FILES = {
    'AGENT.md',
    'clear.py',
    'README.md',
}


def _keep(path):
    relative = os.path.relpath(path, ROOT)
    if relative == '.':
        return True
    if relative.startswith('.git/'):
        return True
    if relative in KEEP_FILES:
        return True
    # Keep entire directory trees for these
    for d in KEEP_DIRS:
        if relative == d or relative.startswith(d + '/'):
            return True
    # Keep dotfiles like .gitignore
    if os.path.basename(relative).startswith('.'):
        return True
    return False


def clean_statement():
    """Remove generated files inside statement/, keep MOTIVATION.md."""
    stmt = os.path.join(ROOT, 'statement')
    if not os.path.isdir(stmt):
        os.makedirs(stmt)
        return

    keep_in_stmt = {'MOTIVATION.md'}
    for f in os.listdir(stmt):
        if f not in keep_in_stmt:
            path = os.path.join(stmt, f)
            if os.path.isfile(path):
                os.remove(path)
                print(f'  rm  statement/{f}')
            elif os.path.isdir(path):
                shutil.rmtree(path)
                print(f'  rmdir statement/{f}/')


def main():
    for entry in sorted(os.listdir(ROOT)):
        full = os.path.join(ROOT, entry)
        if _keep(full):
            continue
        if os.path.isfile(full):
            os.remove(full)
            print(f'  rm  {entry}')
        elif os.path.isdir(full):
            shutil.rmtree(full)
            print(f'  rmdir {entry}/')

    # Clean statement/ of generated files
    clean_statement()

    # Ensure MOTIVATION.md placeholder exists
    moti = os.path.join(ROOT, 'statement', 'MOTIVATION.md')
    if not os.path.exists(moti):
        with open(moti, 'w') as f:
            f.write('# MOTIVATION.md\n\n## Research question\n\n')

    # Ensure .gitignore prevents re-adding garbage
    gitignore_path = os.path.join(ROOT, '.gitignore')
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, 'w') as f:
            f.write('*.pyc\n__pycache__/\n')

    print('\nDone. Project is clean. Edit MOTIVATION.md and AGENT.md for your study.')
    print(f'See: README.md section "Adapting for a new study".')


if __name__ == '__main__':
    main()
