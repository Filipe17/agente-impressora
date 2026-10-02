
import re, os

pasta = os.path.expanduser('~') + '/agente-impressora'
cfg = {}
with open(pasta + '/config_temp.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()

with open(pasta + '/agente_impressora.py', 'r', encoding='utf-8') as f:
    txt = f.read()

txt = re.sub(r"URL_SERVIDOR\s*=\s*'[^']*'", f"URL_SERVIDOR = '{cfg.get('URL', '')}'", txt)
txt = re.sub(r"TIPO_CONEXAO\s*=\s*'[^']*'", f"TIPO_CONEXAO = '{cfg.get('TIPO', 'usb')}'", txt)
txt = re.sub(r"PORTA\s*=\s*'[^']*'", f"PORTA = '{cfg.get('PORTA', '')}'", txt)
txt = re.sub(r"PAPEL\s*=\s*'[^']*'", f"PAPEL = '{cfg.get('PAPEL', '80mm')}'", txt)

with open(pasta + '/agente_impressora.py', 'w', encoding='utf-8') as f:
    f.write(txt)

os.remove(pasta + '/config_temp.txt')
print('Config aplicada.')
