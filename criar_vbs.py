import os

pasta = os.path.expanduser('~') + '\\agente-impressora'
vbs_path = pasta + '\\iniciar_agente.vbs'
agente_path = pasta + '\\agente_impressora.py'

# Aspas duplas dentro do VBS precisam ser escapadas com chr(34)
conteudo  = 'Set WshShell = CreateObject("WScript.Shell")\r\n'
conteudo += 'WshShell.Run "python " & Chr(34) & "' + agente_path + '" & Chr(34), 0, False\r\n'

with open(vbs_path, 'w') as f:
    f.write(conteudo)

print('VBS criado em: ' + vbs_path)
