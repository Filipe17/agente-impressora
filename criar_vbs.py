
import os

pasta = os.path.expanduser('~') + '\\agente-impressora'
vbs_path = pasta + '\\iniciar_agente.vbs'
agente_path = pasta + '\\agente_impressora.py'

conteudo = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python \"{agente_path}\"", 0, False
'''

with open(vbs_path, 'w') as f:
    f.write(conteudo)

print('VBS criado em: ' + vbs_path)
