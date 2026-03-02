import os
import socket
from flask import Flask, request, jsonify

PRINTER_IP = os.getenv("PRINTER_IP", "192.168.3.147")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))

app = Flask(__name__)

# --------- ESC/POS helpers ----------
ESC = b"\x1b"
GS  = b"\x1d"

def esc_init():
    return ESC + b"@"

def esc_align(mode: str):
    # left=0, center=1, right=2
    m = {"left": 0, "center": 1, "right": 2}.get(mode, 0)
    return ESC + b"a" + bytes([m])

def esc_bold(on: bool):
    return ESC + b"E" + (b"\x01" if on else b"\x00")

def esc_size(w: int = 1, h: int = 1):
    # w,h: 1..8
    w = max(1, min(8, w))
    h = max(1, min(8, h))
    n = ((w - 1) << 4) | (h - 1)
    return GS + b"!" + bytes([n])

def esc_cut():
    # Full cut
    return GS + b"V" + b"\x00"

def esc_beep(times=2, dur=2):
    # ESC ( A n t  (varies by model; many support)
    times = max(1, min(9, times))
    dur   = max(1, min(9, dur))
    return ESC + b"(" + b"A" + b"\x02\x00" + bytes([times, dur])

def esc_qr(data: str):
    # Model 2 QR code (ESC/POS standard)
    # Steps: select model, set size, set error correction, store data, print
    bdata = data.encode("utf-8")
    # 1) Model 2
    cmd_model = GS + b"(k" + b"\x04\x00" + b"1A" + b"\x32\x00"
    # 2) Size (1..16)
    size = 6
    cmd_size  = GS + b"(k" + b"\x03\x00" + b"1C" + bytes([size])
    # 3) Error correction (48=L,49=M,50=Q,51=H)
    ecc = 49  # M
    cmd_ecc   = GS + b"(k" + b"\x03\x00" + b"1E" + bytes([ecc])
    # 4) Store data
    pL = (len(bdata) + 3) & 0xFF
    pH = (len(bdata) + 3) >> 8
    cmd_store = GS + b"(k" + bytes([pL, pH]) + b"1P0" + bdata
    # 5) Print
    cmd_print = GS + b"(k" + b"\x03\x00" + b"1Q0"
    return cmd_model + cmd_size + cmd_ecc + cmd_store + cmd_print

def send_to_printer(payload: bytes):
    with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=5) as s:
        s.sendall(payload)

# --------- API ----------
@app.post("/print_text")
def print_text():
    body = request.get_json(force=True, silent=True) or {}
    text = str(body.get("text", "")).strip()
    align = str(body.get("align", "left"))
    bold = bool(body.get("bold", False))
    w = int(body.get("w", 1))
    h = int(body.get("h", 1))
    cut = bool(body.get("cut", True))
    beep = bool(body.get("beep", False))

    payload = b"".join([
        esc_init(),
        esc_align(align),
        esc_bold(bold),
        esc_size(w, h),
        text.encode("cp437", errors="replace") + b"\n",
        b"\n\n",
        esc_bold(False),
        esc_size(1, 1),
        (esc_beep() if beep else b""),
        (esc_cut() if cut else b"")
    ])

    send_to_printer(payload)
    return jsonify({"ok": True})

@app.post("/print_qr")
def print_qr():
    body = request.get_json(force=True, silent=True) or {}
    data = str(body.get("data", "")).strip()
    if not data:
        return jsonify({"ok": False, "error": "missing data"}), 400

    payload = b"".join([
        esc_init(),
        esc_align("center"),
        esc_qr(data),
        b"\n\n",
        esc_cut()
    ])
    send_to_printer(payload)
    return jsonify({"ok": True})

@app.get("/health")
def health():
    return jsonify({"ok": True, "printer": f"{PRINTER_IP}:{PRINTER_PORT}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)