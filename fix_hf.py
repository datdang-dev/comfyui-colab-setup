"""Fix HF_TOKEN lines in env_setup.py"""
import re

p = "env_setup.py"
with open(p, "rb") as f:
    content = f.read()

# Find and replace lines starting with HF_TOKEN= until end of line
lines = content.split(b"\n")
fixed = 0
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith(b"HF_TOKEN=") and b"os.environ" not in stripped:
        # Replace with correct version
        indent = len(line) - len(line.lstrip())
        lines[i] = b" " * indent + b'HF_TOKEN=os.environ.get("HF_TOKEN", "")'
        fixed += 1

content = b"\n".join(lines)
with open(p, "wb") as f:
    f.write(content)

print(f"Fixed {fixed} lines")
