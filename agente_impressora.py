#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║           AGENTE LOCAL DE IMPRESSÃO — PIZZARIA SYSTEM            ║
║                                                                  ║
║  Roda no computador do estabelecimento.                          ║
║  Puxa a fila do servidor Railway e imprime na térmica local.     ║
║                                                                  ║
║  Compatível com: Windows · Linux · macOS                         ║
║  Impressoras:    USB · Serial (RS-232/DB9)                       ║
╚══════════════════════════════════════════════════════════════════╝

CONFIGURAÇÃO (edite as variáveis abaixo antes de rodar):
──────────────────────────────────────────────────────────
  URL_SERVIDOR   → endereço do seu sistema no Railway
  TIPO_CONEXAO   → 'usb' ou 'serial'
  PORTA          → porta da impressora (veja exemplos abaixo)
  BAUD_RATE      → velocidade serial (só para Serial/RS-232)
  INTERVALO      → segundos entre cada verificação da fila
  TIPO_CUPOM     → 'cozinha', 'conta' ou None (todos)
  PAPEL          → '80mm' (48 colunas) ou '58mm' (32 colunas)

EXEMPLOS DE PORTA:
  Windows USB    → 'USB' ou nome da impressora (usa win32print)
  Windows Serial → 'COM3'  (veja Gerenciador de Dispositivos)
  Linux USB      → '/dev/usb/lp0'
  Linux Serial   → '/dev/ttyUSB0' ou '/dev/ttyS0'
  macOS USB      → '/dev/usb/lp0' ou '/dev/cu.usbserial-...'
  macOS Serial   → '/dev/cu.usbserial-0001'

INSTALAÇÃO DAS DEPENDÊNCIAS:
  pip install requests pyserial

  (Windows com impressora USB via spooler):
  pip install requests pyserial pywin32
──────────────────────────────────────────────────────────
"""

import sys
import os
import time
import platform
import requests

# ══════════════════════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÃO — EDITE AQUI
# ══════════════════════════════════════════════════════════════

URL_SERVIDOR  = 'https://SEU-SISTEMA.up.railway.app'   # ← coloque sua URL do Railway
TIPO_CONEXAO  = 'usb'          # 'usb' ou 'serial'
PORTA         = ''             # Ex: 'COM3', '/dev/usb/lp0', '/dev/ttyUSB0'
BAUD_RATE     = 9600           # Velocidade serial (ignorado no modo USB)
INTERVALO     = 2              # Segundos entre verificações
TIPO_CUPOM    = None           # None = todos | 'cozinha' | 'conta'
PAPEL         = '80mm'         # '80mm' (48 col) ou '58mm' (32 col)

# ══════════════════════════════════════════════════════════════
#  CONSTANTES ESC/POS
# ══════════════════════════════════════════════════════════════

ESC = b'\x1b'
GS  = b'\x1d'

CMD_INIT         = ESC + b'@'           # Inicializa impressora
CMD_CORTAR       = GS  + b'V\x41\x03'  # Corte parcial
CMD_NEGRITO_ON   = ESC + b'E\x01'
CMD_NEGRITO_OFF  = ESC + b'E\x00'
CMD_CENTRALIZAR  = ESC + b'a\x01'
CMD_ESQUERDA     = ESC + b'a\x00'
CMD_LINHA        = b'\n'
# Tamanho de fonte via ESC ! (mais compatível com térmicas genéricas)
CMD_FONTE_NORMAL = ESC + b'!\x00'      # Fonte normal
CMD_FONTE_GRANDE = ESC + b'!\x38'      # Dupla largura + dupla altura + negrito
CMD_FONTE_MEDIA  = ESC + b'!\x10'      # Dupla altura

COLUNAS = 48 if PAPEL == '80mm' else 32

# ══════════════════════════════════════════════════════════════
#  DETECÇÃO DE SO
# ══════════════════════════════════════════════════════════════

SO = platform.system()   # 'Windows', 'Linux', 'Darwin'

# ══════════════════════════════════════════════════════════════
#  IMPRESSÃO
# ══════════════════════════════════════════════════════════════

def _montar_bytes(texto: str) -> bytes:
    """Converte texto puro em bytes ESC/POS prontos para imprimir."""
    import re as _re

    buf = bytearray()
    buf += CMD_INIT
    buf += CMD_ESQUERDA
    buf += CMD_FONTE_NORMAL

    linhas = texto.splitlines()
    for linha in linhas:
        stripped = linha.strip()

        # ── Separadores (=== --- ***) → centralizado ──────────
        if stripped and all(c in ('*', '-', '=') for c in stripped):
            buf += CMD_CENTRALIZAR + CMD_NEGRITO_ON + CMD_FONTE_NORMAL
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_NEGRITO_OFF + CMD_ESQUERDA + CMD_FONTE_NORMAL

        # ── Número do pedido → fonte GRANDE + centralizado ────
        elif _re.match(r'^\s*Pedido\s+', stripped):
            buf += CMD_CENTRALIZAR + CMD_FONTE_GRANDE
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_FONTE_NORMAL + CMD_ESQUERDA

        # ── Tipo (PARA ENTREGA, MESA X, BALCAO) → centralizado + negrito
        elif _re.match(r'^\s*(PARA ENTREGA|BALCAO|MESA\s|COZINHA)', stripped):
            buf += CMD_CENTRALIZAR + CMD_NEGRITO_ON + CMD_FONTE_NORMAL
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_NEGRITO_OFF + CMD_ESQUERDA + CMD_FONTE_NORMAL

        # ── Seções (Itens, Cliente, Pagamento) → negrito ──────
        elif stripped in ('Itens', 'Cliente', 'Pagamento'):
            buf += CMD_NEGRITO_ON + CMD_FONTE_NORMAL
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_NEGRITO_OFF + CMD_FONTE_NORMAL

        # ── Data → centralizado ───────────────────────────────
        elif _re.match(r'^\d{2}/\d{2}/\d{4}', stripped):
            buf += CMD_CENTRALIZAR
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_ESQUERDA

        # ── Entrega prevista → centralizado ───────────────────
        elif stripped.startswith('Entrega prevista'):
            buf += CMD_CENTRALIZAR
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_ESQUERDA

        # ── Nome da loja → centralizado ───────────────────────
        elif stripped.startswith('Na hora') or (
            stripped and len(stripped) < 40
            and not any(c in stripped for c in (':', 'R$', '+', '-'))
            and _re.match(r'^[A-Za-z\s]+$', stripped)
        ):
            buf += CMD_CENTRALIZAR
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_ESQUERDA

        # ── Total → negrito ───────────────────────────────────
        elif stripped.startswith('Total:') or stripped.startswith('TOTAL:'):
            buf += CMD_NEGRITO_ON
            buf += (linha + '\n').encode('cp850', errors='replace')
            buf += CMD_NEGRITO_OFF

        # ── Cobrar do cliente → centralizado + negrito ────────
        elif '* Cobrar do cliente *' in stripped:
            buf += CMD_CENTRALIZAR + CMD_NEGRITO_ON
            buf += (stripped + '\n').encode('cp850', errors='replace')
            buf += CMD_NEGRITO_OFF + CMD_ESQUERDA

        # ── Normal ────────────────────────────────────────────
        else:
            buf += CMD_FONTE_NORMAL
            buf += (linha + '\n').encode('cp850', errors='replace')

    # Espaço e corte
    buf += b'\n\n\n'
    buf += CMD_CORTAR
    return bytes(buf)


def imprimir_usb_linux(dados: bytes):
    """Linux/macOS: escreve direto na porta /dev/usb/lp0 ou similar."""
    with open(PORTA, 'wb') as f:
        f.write(dados)


def imprimir_usb_windows(dados: bytes):
    """Windows: tenta arquivo direto na porta (LPT1, \\.\COM3, etc.)
    ou usa win32print se disponível."""
    try:
        import win32print
        printer_name = PORTA if PORTA else win32print.GetDefaultPrinter()
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1, ('Cupom', None, 'RAW'))
            try:
                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, dados)
                win32print.EndPagePrinter(hPrinter)
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
    except ImportError:
        # Fallback: escreve direto na porta (funciona para LPT1 e algumas COM)
        porta_win = PORTA if PORTA else 'LPT1'
        with open(porta_win, 'wb') as f:
            f.write(dados)


def imprimir_serial(dados: bytes):
    """USB-Serial / RS-232 / DB9 via pyserial."""
    try:
        import serial
    except ImportError:
        print('[ERRO] pyserial não instalado. Rode: pip install pyserial')
        return
    with serial.Serial(PORTA, baudrate=BAUD_RATE, timeout=3) as s:
        s.write(dados)


def imprimir(texto: str):
    """Seleciona o método correto e imprime."""
    dados = _montar_bytes(texto)

    if TIPO_CONEXAO == 'serial':
        imprimir_serial(dados)
        return

    # USB — depende do SO
    if SO == 'Windows':
        imprimir_usb_windows(dados)
    else:
        imprimir_usb_linux(dados)


# ══════════════════════════════════════════════════════════════
#  COMUNICAÇÃO COM O SERVIDOR
# ══════════════════════════════════════════════════════════════

def buscar_pendentes():
    """Retorna lista de jobs pendentes do servidor."""
    url = URL_SERVIDOR.rstrip('/') + '/api/imprimir/pendentes'
    params = {}
    if TIPO_CUPOM:
        params['tipo'] = TIPO_CUPOM
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get('jobs', [])


def confirmar_job(job_id: int):
    """Confirma que o job foi impresso — remove da fila do servidor."""
    url = URL_SERVIDOR.rstrip('/') + '/api/imprimir/ok'
    requests.post(url, json={'id': job_id}, timeout=10)


# ══════════════════════════════════════════════════════════════
#  VALIDAÇÃO DA CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════

def validar_config():
    erros = []

    if 'SEU-SISTEMA' in URL_SERVIDOR:
        erros.append('URL_SERVIDOR não configurada. Edite a variável no topo do script.')

    if not PORTA and SO != 'Windows':
        erros.append('PORTA não configurada. Ex: /dev/usb/lp0 (Linux) ou COM3 (Windows).')

    if TIPO_CONEXAO not in ('usb', 'serial'):
        erros.append("TIPO_CONEXAO deve ser 'usb' ou 'serial'.")

    if erros:
        print('\n' + '═' * 55)
        print('  ⚠️  CONFIGURAÇÃO INCOMPLETA')
        print('═' * 55)
        for e in erros:
            print(f'  • {e}')
        print('═' * 55)
        print('  Edite as variáveis no topo do arquivo e tente novamente.')
        print('═' * 55 + '\n')
        sys.exit(1)


# ══════════════════════════════════════════════════════════════
#  LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════════

def loop():
    validar_config()

    print('═' * 55)
    print('  🖨️  AGENTE DE IMPRESSÃO — PIZZARIA SYSTEM')
    print('═' * 55)
    print(f'  Servidor  : {URL_SERVIDOR}')
    print(f'  Conexão   : {TIPO_CONEXAO.upper()}')
    print(f'  Porta     : {PORTA or "(padrão do sistema)"}')
    print(f'  Papel     : {PAPEL} ({COLUNAS} colunas)')
    print(f'  Filtro    : {TIPO_CUPOM or "todos os tipos"}')
    print(f'  Intervalo : {INTERVALO}s')
    print(f'  SO        : {SO}')
    print('═' * 55)
    print('  Aguardando jobs... (Ctrl+C para parar)\n')

    impressos = set()   # IDs já processados nesta sessão (evita reimpressão)
    erros_seq = 0       # Contador de erros consecutivos

    while True:
        try:
            jobs = buscar_pendentes()
            erros_seq = 0

            for job in jobs:
                jid   = job.get('id')
                texto = job.get('texto', '')
                tipo  = job.get('tipo', 'conta')

                if jid in impressos:
                    continue

                print(f'  [{time.strftime("%H:%M:%S")}] Job #{jid} ({tipo}) — imprimindo...', end=' ')
                try:
                    imprimir(texto)
                    confirmar_job(jid)
                    impressos.add(jid)
                    # Mantém o set pequeno (últimos 200 IDs)
                    if len(impressos) > 200:
                        impressos.pop()
                    print('✅')
                except Exception as e_imp:
                    print(f'❌ Erro na impressora: {e_imp}')

        except requests.exceptions.ConnectionError:
            erros_seq += 1
            if erros_seq == 1 or erros_seq % 30 == 0:
                print(f'  [{time.strftime("%H:%M:%S")}] ⚠️  Sem conexão com o servidor ({erros_seq}x). Tentando...')

        except requests.exceptions.Timeout:
            print(f'  [{time.strftime("%H:%M:%S")}] ⚠️  Timeout ao conectar no servidor.')

        except Exception as e:
            erros_seq += 1
            if erros_seq <= 3 or erros_seq % 30 == 0:
                print(f'  [{time.strftime("%H:%M:%S")}] ⚠️  Erro: {e}')

        time.sleep(INTERVALO)


# ══════════════════════════════════════════════════════════════
#  ENTRADA
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    try:
        loop()
    except KeyboardInterrupt:
        print('\n\n  Agente encerrado pelo usuário. Até logo! 👋\n')
        sys.exit(0)
