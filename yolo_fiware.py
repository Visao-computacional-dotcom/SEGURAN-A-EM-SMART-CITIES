#!/usr/bin/env python3
"""
Sistema de Detecção de Pessoas com YOLOv8 e FIWARE
Comandos interativos:
  r - Reiniciar conexão com a câmera
  i - Informações do sistema
  q - Sair do programa
  s - Status da conexão FIWARE
  c - Capturar screenshot
"""

import cv2
from ultralytics import YOLO
import requests
import time
import threading
from datetime import datetime
import json
import os
import signal
import sys

class PersonDetectionSystem:
    def __init__(self):
        # Configurações
        self.model_path = 'yolov8n.pt'
        self.stream_url = 'http://192.168.43.189:80/stream'
        self.fiware_url = 'http://192.168.43.25:1026/v2/entities/PersonCounter/attrs'
        
        # Inicialização
        self.model = None
        self.cap = None
        self.running = True
        self.connected = False
        self.fiware_connected = False
        self.person_count = 0
        self.total_frames = 0
        self.detected_frames = 0
        self.start_time = time.time()
        
        # Configuração do log
        self.log_file = "detection_log.txt"
        self.setup_logging()
        
        # Configurar handler para Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def setup_logging(self):
        """Configura sistema de logging"""
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"Sessão iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Stream URL: {self.stream_url}\n")
            f.write(f"FIWARE URL: {self.fiware_url}\n")
            f.write(f"{'='*50}\n")
    
    def log_event(self, event):
        """Registra evento no log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {event}\n"
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
        print(f"[LOG] {event}")
    
    def signal_handler(self, sig, frame):
        """Handler para Ctrl+C"""
        print("\n\n[!] Interrupção recebida. Encerrando...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def load_model(self):
        """Carrega o modelo YOLO"""
        try:
            self.log_event("Carregando modelo YOLOv8...")
            self.model = YOLO(self.model_path)
            self.log_event("Modelo carregado com sucesso")
            return True
        except Exception as e:
            self.log_event(f"ERRO ao carregar modelo: {e}")
            return False
    
    def connect_camera(self):
        """Conecta à câmera/stream"""
        try:
            if self.cap:
                self.cap.release()
            
            self.log_event(f"Conectando ao stream: {self.stream_url}")
            self.cap = cv2.VideoCapture(self.stream_url)
            
            # Configurar timeout
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Testar conexão
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.connected = True
                    self.log_event("Conexão com câmera estabelecida")
                    return True
            
            self.connected = False
            self.log_event("Falha na conexão com a câmera")
            return False
            
        except Exception as e:
            self.log_event(f"ERRO na conexão com câmera: {e}")
            self.connected = False
            return False
    
    def check_fiware_connection(self):
        """Verifica conexão com FIWARE"""
        try:
            response = requests.get(self.fiware_url.replace('/attrs', ''), timeout=3)
            if response.status_code == 200:
                self.fiware_connected = True
                return True
        except Exception as e:
            self.fiware_connected = False
        return False
    
    def send_to_fiware(self, count):
        """Envia dados para FIWARE em thread separada"""
        def send_data():
            try:
                payload = {
                    "count": {
                        "value": count,
                        "type": "Integer"
                    },
                    "lastUpdate": {
                        "value": datetime.now().isoformat() + "Z",
                        "type": "DateTime"
                    }
                }
                
                response = requests.patch(
                    self.fiware_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=2
                )
                
                if response.status_code == 204:
                    return True
                else:
                    self.log_event(f"FIWARE: HTTP {response.status_code}")
                    return False
                    
            except requests.exceptions.Timeout:
                self.log_event("FIWARE: Timeout na conexão")
                return False
            except Exception as e:
                self.log_event(f"FIWARE: Erro {e}")
                return False
        
        # Executar em thread para não bloquear o vídeo
        thread = threading.Thread(target=send_data)
        thread.daemon = True
        thread.start()
        return thread
    
    def get_system_info(self):
        """Retorna informações do sistema"""
        uptime = time.time() - self.start_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        detection_rate = 0
        if self.total_frames > 0:
            detection_rate = (self.detected_frames / self.total_frames) * 100
        
        info = f"""
{'='*60}
SISTEMA DE DETECÇÃO DE PESSOAS - INFORMAÇÕES
{'='*60}
Status da Câmera: {'CONECTADO' if self.connected else 'DESCONECTADO'}
Status FIWARE: {'CONECTADO' if self.fiware_connected else 'DESCONECTADO'}
Stream: {self.stream_url}
Modelo: {self.model_path}
{'='*60}
ESTATÍSTICAS:
  Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s
  Total de frames: {self.total_frames}
  Taxa de detecção: {detection_rate:.1f}%
  Pessoas atuais: {self.person_count}
{'='*60}
COMANDOS DISPONÍVEIS:
  [r] - Reiniciar conexão com câmera
  [i] - Mostrar esta informação
  [s] - Status da conexão FIWARE
  [c] - Capturar screenshot
  [q] - Sair do programa
{'='*60}
"""
        return info
    
    def capture_screenshot(self, frame):
        """Captura screenshot do frame atual"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.jpg"
        
        # Criar diretório se não existir
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")
        
        filepath = os.path.join("screenshots", filename)
        cv2.imwrite(filepath, frame)
        self.log_event(f"Screenshot salvo: {filepath}")
        return filepath
    
    def process_frame(self, frame):
        """Processa um frame para detecção"""
        try:
            # Realizar detecção
            results = self.model(frame, classes=[0], verbose=False)
            
            # Contar pessoas
            self.person_count = len(results[0].boxes) if results[0].boxes is not None else 0
            
            # Atualizar estatísticas
            self.detected_frames += 1 if self.person_count > 0 else 0
            
            # Desenhar resultados
            annotated_frame = results[0].plot()
            
            # Adicionar overlay de informação
            cv2.putText(annotated_frame, f'Pessoas: {self.person_count}', 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Adicionar status da conexão
            status_color = (0, 255, 0) if self.connected else (0, 0, 255)
            status_text = f"Camera: {'OK' if self.connected else 'ERRO'}"
            cv2.putText(annotated_frame, status_text, 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            
            # Adicionar status FIWARE
            fiware_color = (0, 255, 0) if self.fiware_connected else (0, 0, 255)
            fiware_text = f"FIWARE: {'OK' if self.fiware_connected else 'ERRO'}"
            cv2.putText(annotated_frame, fiware_text, 
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, fiware_color, 2)
            
            # Adicionar timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(annotated_frame, timestamp, 
                       (10, frame.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            return annotated_frame, True
            
        except Exception as e:
            self.log_event(f"ERRO no processamento: {e}")
            return frame, False
    
    def display_help(self):
        """Exibe ajuda na tela"""
        help_text = """
CONTROLES:
  r - Reconectar camera
  i - Informações do sistema
  s - Testar conexão FIWARE
  c - Capturar screenshot
  q - Sair
  
  Pressione qualquer tecla para ocultar esta mensagem
"""
        print(help_text)
    
    def run(self):
        """Loop principal do sistema"""
        
        # Inicializar
        if not self.load_model():
            return
        
        if not self.connect_camera():
            self.log_event("Tentando reconexão automática em 5 segundos...")
            time.sleep(5)
            if not self.connect_camera():
                self.log_event("Não foi possível conectar à câmera")
                return
        
        # Verificar FIWARE
        self.check_fiware_connection()
        
        # Configurar janela
        cv2.namedWindow('Sistema de Detecção - ESP32 + YOLO + FIWARE', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Sistema de Detecção - ESP32 + YOLO + FIWARE', 800, 600)
        
        self.log_event("Sistema iniciado. Pressione 'i' para ajuda.")
        
        # Variáveis para controle de FPS
        last_fiware_update = 0
        fiware_update_interval = 2  # segundos
        
        # Loop principal
        while self.running:
            # Ler frame
            if self.connected:
                ret, frame = self.cap.read()
                if not ret:
                    self.log_event("Frame perdido. Tentando reconectar...")
                    self.connected = False
                    continue
                
                self.total_frames += 1
                
                # Processar frame
                processed_frame, success = self.process_frame(frame)
                
                # Enviar para FIWARE periodicamente
                current_time = time.time()
                if success and self.fiware_connected and (current_time - last_fiware_update > fiware_update_interval):
                    self.send_to_fiware(self.person_count)
                    last_fiware_update = current_time
                
                # Exibir frame
                cv2.imshow('Sistema de Detecção - ESP32 + YOLO + FIWARE', processed_frame)
            else:
                # Tela de espera quando desconectado
                blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank_frame, "AGUARDANDO CONEXAO...", 
                           (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow('Sistema de Detecção - ESP32 + YOLO + FIWARE', blank_frame)
                
                # Tentar reconectar a cada 3 segundos
                if time.time() - last_fiware_update > 3:
                    if self.connect_camera():
                        self.log_event("Reconexão bem-sucedida!")
            
            # Processar teclas (timeout curto para responsividade)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):  # Sair
                break
            elif key == ord('r'):  # Reiniciar conexão
                self.log_event("Reiniciando conexão com câmera...")
                self.connect_camera()
            elif key == ord('i'):  # Informações
                print(self.get_system_info())
            elif key == ord('s'):  # Status FIWARE
                if self.check_fiware_connection():
                    self.log_event("FIWARE: Conexão estabelecida")
                else:
                    self.log_event("FIWARE: Falha na conexão")
            elif key == ord('c'):  # Capturar screenshot
                if self.connected and ret:
                    self.capture_screenshot(frame)
            elif key == 27:  # ESC
                break
            elif key != 255:  # Qualquer outra tecla
                self.display_help()
        
        self.cleanup()
    
    def cleanup(self):
        """Limpeza final"""
        self.log_event("Encerrando sistema...")
        
        if self.cap:
            self.cap.release()
        
        cv2.destroyAllWindows()
        
        # Registrar estatísticas finais
        uptime = time.time() - self.start_time
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"Sessão encerrada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Uptime: {uptime:.1f} segundos\n")
            f.write(f"Total de frames processados: {self.total_frames}\n")
            f.write(f"Frames com detecção: {self.detected_frames}\n")
            f.write(f"{'='*50}\n")
        
        print("\nSistema encerrado. Log salvo em:", self.log_file)

# Adicionar import do numpy se necessário
import numpy as np

if __name__ == "__main__":
    # Configurações iniciais
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║      SISTEMA DE DETECÇÃO DE PESSOAS - v2.0           ║
    ║      ESP32 + YOLOv8 + FIWARE                         ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    # Criar e executar sistema
    system = PersonDetectionSystem()
    system.run()