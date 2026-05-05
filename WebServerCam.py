#!/usr/bin/env python3

""" Servidor de Streaming MJPEG em Python Estilo ESP32-CAM - Otimizado para YOLO """

import cv2
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import sys
import signal
import json

# ========== CONFIGURAÇÕES ==========

HOST = '0.0.0.0'
PORT = 80
TARGET_FPS = 15
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 80          # 0-100 (menor = mais compressão)
CHUNK_SIZE = 1024

# Cabeçalho MJPEG
MJPEG_HEADER = '--frame\r\nContent-Type: image/jpeg\r\n\r\n'
MJPEG_FOOTER = '\r\n'


class CameraStream:
    """Classe para gerenciar a câmera e captura de frames"""

    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None
        self.running = False
        self.frame = None
        self.frame_count = 0
        self.fps = 0
        self.last_frame_time = time.time()
        self.lock = threading.Lock()

        # Configurações de captura
        self.target_fps = TARGET_FPS
        self.frame_interval = 1.0 / TARGET_FPS

    def start(self):
        """Inicia a captura da câmera"""
        print(f"[CAMERA] Tentando inicializar câmera {self.camera_id}...")

        # Tenta diferentes backends
        backends = [cv2.CAP_DSHOW, cv2.CAP_V4L2, cv2.CAP_ANY]

        for backend in backends:
            self.cap = cv2.VideoCapture(self.camera_id, backend)
            if self.cap.isOpened():
                print(f"[CAMERA] Usando backend: {backend}")
                break

        if not self.cap or not self.cap.isOpened():
            print("\n❌ [STATUS DA WEBCAM] ERRADO: Não foi possível abrir a câmera! Verifique se ela está conectada ou sendo usada por outro app.\n")
            return False

        # Configura resolução
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer mínimo

        # Verifica configurações
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        print("\n✅ [STATUS DA WEBCAM] CERTO: Webcam detectada e funcionando perfeitamente!")
        print(f"   ↳ Resolução: {actual_width}x{actual_height}")
        print(f"   ↳ FPS configurado: {actual_fps}")
        print(f"   ↳ Qualidade JPEG: {JPEG_QUALITY}\n")

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()

        return True

    def _capture_loop(self):
        """Loop principal de captura"""
        print("[CAMERA] Loop de captura iniciado")

        frame_time = time.time()
        frame_count = 0

        while self.running:
            try:
                # Captura frame
                ret, frame = self.cap.read()

                if ret and frame is not None:
                    # Mantém aspecto e redimensiona se necessário
                    if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
                        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

                    # Converte para JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                    ret, jpeg = cv2.imencode('.jpg', frame, encode_param)

                    if ret:
                        with self.lock:
                            self.frame = jpeg.tobytes()
                            self.frame_count += 1

                    # Calcula FPS
                    frame_count += 1
                    current_time = time.time()
                    if current_time - frame_time >= 1.0:
                        self.fps = frame_count
                        frame_count = 0
                        frame_time = current_time

                # Controle de FPS
                elapsed = time.time() - self.last_frame_time
                sleep_time = max(0, self.frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.last_frame_time = time.time()

            except Exception as e:
                print(f"[ERRO] Captura: {e}")
                time.sleep(0.1)

    def get_frame(self):
        """Retorna o último frame capturado"""
        with self.lock:
            return self.frame, self.fps

    def stop(self):
        """Para a captura"""
        print("[CAMERA] Parando captura...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        print("[CAMERA] Captura parada")


class StreamingHandler(BaseHTTPRequestHandler):
    """Handler para streaming MJPEG"""

    camera = None  # Referência estática para a câmera

    def do_GET(self):
        """Processa requisições GET"""
        if self.path == '/':
            self._send_html_page()
        elif self.path == '/stream':
            self._send_mjpeg_stream()
        elif self.path == '/status':
            self._send_status()
        elif self.path == '/snapshot':
            self._send_snapshot()
        else:
            self.send_error(404, "Página não encontrada")

    def _send_html_page(self):
        """Envia página HTML com o stream"""
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Python MJPEG Stream</title>
    <style>
        body {{ font-family: monospace; margin: 20px; background: #1a1a1a; color: #eee; }}
        .container {{ max-width: 800px; margin: 0 auto; text-align: center; }}
        img {{ border: 2px solid #444; max-width: 100%; }}
        .info {{ margin-top: 10px; font-size: 14px; }}
        .label {{ color: #888; }}
        .value {{ color: #0f0; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📡 Python MJPEG Stream</h1>
    <img src="/stream" alt="Stream ao vivo">
    <div class="info">
        <div><span class="label">Status:</span> <span class="value">Online LIVE</span></div>
        <div><span class="label">Servidor:</span> <span class="value">{self.headers.get('Host', 'Unknown')}</span></div>
        <div><span class="label">Resolução:</span> <span class="value">{FRAME_WIDTH}x{FRAME_HEIGHT}</span></div>
        <div><span class="label">FPS alvo:</span> <span class="value">{TARGET_FPS}</span></div>
        <div id="fps-display"><span class="label">FPS atual:</span> <span class="value">Calculando...</span></div>
    </div>
    <div class="info">
        <a href="/snapshot" style="color:#0f0;">📸 Snapshot</a> |
        <a href="/status" style="color:#0f0;">📊 Status</a>
    </div>
</div>
<script>
    function updateFPS() {{
        fetch('/status')
            .then(response => response.json())
            .then(data => {{
                document.getElementById('fps-display').innerHTML =
                    '<span class="label">FPS atual:</span>' +
                    '<span class="value">' + data.fps + '</span>';
            }});
    }}
    setInterval(updateFPS, 1000);
</script>
</body>
</html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_mjpeg_stream(self):
        """Envia stream MJPEG"""
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

        print(f"[CLIENTE] Novo cliente conectado: {self.client_address}")

        frame_count = 0
        last_log = time.time()

        try:
            while True:
                # Obtém frame da câmera
                frame, fps = self.camera.get_frame()

                if frame:
                    # Envia frame no formato MJPEG
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(frame)}\r\n'.encode())
                    self.wfile.write(b'\r\n')

                    # Envia em chunks
                    for i in range(0, len(frame), CHUNK_SIZE):
                        chunk = frame[i:i + CHUNK_SIZE]
                        self.wfile.write(chunk)

                    self.wfile.write(b'\r\n')

                    frame_count += 1

                    # Log a cada 30 frames
                    current_time = time.time()
                    if current_time - last_log >= 2:
                        print(f"[CLIENTE] {self.client_address}: Enviados {frame_count} frames (FPS: {fps})")
                        frame_count = 0
                        last_log = current_time

                # Controle de FPS - pequeno delay para não sobrecarregar
                time.sleep(0.001)

        except (BrokenPipeError, ConnectionResetError):
            print(f"[CLIENTE] {self.client_address} desconectado")
        except Exception as e:
            print(f"[ERRO] Cliente {self.client_address}: {e}")

    def _send_snapshot(self):
        """Envia uma única imagem (snapshot)"""
        frame, _ = self.camera.get_frame()

        if frame:
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(frame)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(frame)
        else:
            self.send_error(503, "Frame não disponível")

    def _send_status(self):
        """Envia status em JSON"""
        _, fps = self.camera.get_frame()

        status = {
            'status': 'online',
            'fps': fps,
            'resolution': f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
            'target_fps': TARGET_FPS,
            'jpeg_quality': JPEG_QUALITY
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status).encode())

    def log_message(self, format, *args):
        """Suprime logs padrão"""
        return


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Servidor HTTP com threads para múltiplos clientes"""
    allow_reuse_address = True
    daemon_threads = True


def signal_handler(sig, frame):
    """Handler para Ctrl+C"""
    print("\n\n[SHUTDOWN] Encerrando servidor...")
    sys.exit(0)


def main():
    """Função principal"""
    print("\n" + "=" * 60)
    print("🚀 SERVIDOR DE STREAMING MJPEG - PYTHON")
    print("=" * 60)

    # Inicializa câmera
    camera = CameraStream(camera_id=0)
    if not camera.start():
        # Encerra caso a câmera não funcione, evitando rodar o servidor "vazio"
        return

    # Configura handler para a câmera
    StreamingHandler.camera = camera

    # Configura handler de sinal
    signal.signal(signal.SIGINT, signal_handler)

    # Inicia servidor
    try:
        server = ThreadedHTTPServer((HOST, PORT), StreamingHandler)

        print(f"\n📡 Servidor rodando em:")
        print(f"   Local: http://localhost:{PORT}")

        # Descobre IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            print(f"   Rede:  http://{local_ip}:{PORT}")
        except Exception:
            print("   Rede:  Não foi possível determinar IP")
        finally:
            s.close()

        print(f"\n📊 Endpoints disponíveis:")
        print(f"   • Página:     http://localhost:{PORT}/")
        print(f"   • Stream:     http://localhost:{PORT}/stream")
        print(f"   • Snapshot:   http://localhost:{PORT}/snapshot")
        print(f"   • Status:     http://localhost:{PORT}/status")

        print(f"\n🛑 Pressione CTRL+C para parar")
        print("=" * 60 + "\n")

        # Inicia servidor
        server.serve_forever()

    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Servidor interrompido pelo usuário")
    except Exception as e:
        print(f"\n[ERRO] Servidor: {e}")
    finally:
        camera.stop()
        print("[SHUTDOWN] Servidor encerrado")


if __name__ == '__main__':
    main()