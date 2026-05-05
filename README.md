# Segurança em Smart Cities: Vulnerabilidades Lógicas da Visão Computacional Aplicada a Sistemas de Monitoramento e Identificação

**Autores:** Gabriel Pereira da Fonseca Oliveira, Giovanna Pardini Cansian, Giovanna Xavier de Lima, Rafael dos Reis Silva  
**Orientador:** Prof. Dr. Fábio Henrique Cabrini  
**Instituição:** FATEC São Caetano do Sul – Curso Superior de Tecnologia em Segurança da Informação  
**Ano:** 2026

---

## Resumo

O avanço das cidades inteligentes baseia-se na integração de IoT e IA para otimizar a gestão urbana. Contudo, a expansão dessa infraestrutura amplia a superfície de ataque, especialmente em modelos de visão computacional. Este trabalho investiga a viabilidade de ataques de **Data Poisoning** em um ambiente de monitoramento inteligente composto por ESP32-CAM, YOLOv8 e FIWARE. Através de uma Prova de Conceito (PoC), demonstramos que a ausência de autenticação e criptografia permite IP spoofing, deauthentication e injeção de dados fraudulentos. Com base nesse diagnóstico, são propostas diretrizes de hardenização baseadas em Zero Trust. O repositório contém todos os códigos-fonte utilizados nos experimentos.

---

## Arquitetura do Sistema

A arquitetura da PoC é composta por três camadas principais:

1. **Camada de Percepção (IoT)** – ESP32-CAM captura imagens e transmite stream MJPEG via HTTP.
2. **Camada de Processamento (Edge)** – Script Python consome o stream, aplica YOLOv8 para detecção de pessoas e extrai a contagem.
3. **Camada de Dados (Middleware)** – A contagem é enviada para o FIWARE Orion Context Broker via API REST, sendo persistida e disponibilizada para um dashboard de gestão.

A seguir, os componentes e suas vulnerabilidades exploradas:
- **Rede Wi-Fi** sem segmentação VLAN, WPA2-Personal sem PMF → suscetível a deauthentication flood.
- **ESP32-CAM** servindo stream sem autenticação → IP spoofing.
- **YOLO** confiando cegamente no IP de origem → aceitação de stream malicioso.
- **FIWARE** sem autenticação nos endpoints → atualização de contagem fraudulenta.

---

## Conteúdo do Repositório

| Arquivo | Descrição |
|---------|------------|
| `stream_otimizado.ino` | Firmware para ESP32-CAM (Arduino IDE). Transmite MJPEG a 15 FPS, resolução 640x480, qualidade JPEG ajustável. |
| `WebServerCam.py` | Implementação alternativa de servidor MJPEG em Python (útil para testes com webcam local ou substituição do ESP32). |
| `yolo_fiware.py` | Sistema principal de detecção de pessoas: consome o stream, executa YOLOv8, exibe contagem em tela e envia periodicamente ao FIWARE. |
| `TCC_FATEC_2025_2_1.pdf` | Trabalho de Conclusão de Curso completo com fundamentação teórica, metodologia, análise de resultados e diretrizes de mitigação. |

---

## Pré‑requisitos

### Hardware
- ESP32-CAM (módulo com câmera OV2640 ou OV5640)
- Placa de programação USB‑TTL (ex.: FTDI)
- Rede Wi-Fi 2.4 GHz
- (Opcional) M5Stack Cardputer para ataques de deauthentication

### Software
- **Arduino IDE** com suporte a ESP32 (biblioteca `esp32` e `esp_camera`)
- **Python 3.8+** com as seguintes bibliotecas:
  ```bash
  pip install opencv-python ultralytics requests numpy
