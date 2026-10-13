import re
import subprocess

with open('templates/index.html', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
print(f'Total script tags found: {len(scripts)}')

for idx, s in enumerate(scripts):
    with open('scripts/temp_script.js', 'w', encoding='utf-8') as out:
        out.write(s)
    p = subprocess.run(['node', '-c', 'scripts/temp_script.js'], capture_output=True, text=True)
    if p.returncode != 0:
        print(f'Script {idx} error:\n{p.stderr[:500]}')
    else:
        print(f'Script {idx} is VALID!')
