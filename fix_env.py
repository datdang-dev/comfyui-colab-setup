import base64

p = r"env_setup.py"
with open(p, 'rb') as f:
    content = f.read()

# Build the correct HF_TOKEN line
correct_line = b'HF_TOKEN=os.environ.get("HF_TOKEN", "")\r\n'

# Find all HF_TOKEN=*** lines and fix them
import re
# Pattern: HF_TOKEN followed by non-standard content until end of line
pattern = b'HF_TOKEN=*** 
result = b''
last_end = 0
for m in re.finditer(pattern, content):
    result += content[last_end:m.start()]
    result += correct_line
    last_end = m.end()

result += content[last_end:]

with open(p, 'wb') as f:
    f.write(result)

print(f"Fixed {len(re.findall(pattern, content))} occurrences")
