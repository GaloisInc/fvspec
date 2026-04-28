import re, os
d = '/Users/maxvonhippel/projects/research/fvspec/comms/paper/sections'
order = ['abstract','introduction','task','pipeline','dataset','results','threats','related','conclusion']
for name in order:
    path = os.path.join(d, name + '.tex')
    if not os.path.exists(path):
        print(f'{name}.tex: MISSING')
        continue
    text = open(path).read()
    pat = re.compile(r'\\(sub)*section\{([^}]+)\}')
    for m in pat.finditer(text):
        depth = m.group(1) or ''
        title = m.group(2)
        lineno = text[:m.start()].count(chr(10)) + 1
        print(f'{name}.tex:{lineno}: {depth}section{{{title}}}')