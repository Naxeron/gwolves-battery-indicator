with open('/home/naxeron/.gemini/antigravity-ide/brain/082d389c-5841-4aea-a6ee-be2298f987a9/scratch/index.js') as f:
    content = f.read()

import re

# Look for ModelCN references to locate the database array/object
for m in re.finditer(r'ModelCN', content):
    idx = m.start()
    print(f"Index {idx}:")
    print(content[idx-100:idx+200])
    print("-" * 50)




