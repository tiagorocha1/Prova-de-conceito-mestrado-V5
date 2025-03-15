import React, { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';

function FaceDetectionComponent() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDetecting, setIsDetecting] = useState<boolean>(false);
  const cameraRef = useRef<Camera | null>(null);
  const throttleInterval = 1000; // Envia 1 frame a cada 1000 ms (1 segundo)
  const lastSentTimeRef = useRef<number>(0);

  // Configura a câmera para capturar os frames
  useEffect(() => {
    if (videoRef.current) {
      cameraRef.current = new Camera(videoRef.current, {
        onFrame: async () => {
          if (isDetecting) {
            sendFrame();
          }
        },
        width: 640,
        height: 480,
      });
      cameraRef.current.start();
    }
  }, [isDetecting]);

  // Função que captura o frame atual e envia para o backend
  const sendFrame = () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const now = Date.now();
    if (now - lastSentTimeRef.current < throttleInterval) {
      return; // Se não passou 1 segundo, sai sem enviar
    }
    lastSentTimeRef.current = now;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Atualiza o canvas com o frame atual
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Converte o canvas para Base64
    const base64Image = canvas.toDataURL('image/png');

    // Prepara o payload com o frame e o timestamp
    const payload = {
      image: base64Image,
      timestamp: now
    };

    // Envia o payload para o backend; o retorno é ignorado
    fetch('http://localhost:8000/frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(err => {
      console.error('Erro ao enviar frame:', err);
    });
  };

  // Função para alternar entre iniciar e parar a detecção
  const toggleDetection = () => {
    setIsDetecting((prev) => !prev);
  };

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ margin: '0 auto', maxWidth: '640px', position: 'relative' }}>
        <video
          ref={videoRef}
          style={{ width: '100%' }}
          autoPlay
          muted
          playsInline
        />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>
      <div style={{ marginTop: '20px' }}>
        <button
          onClick={toggleDetection}
          style={{
            padding: '10px 20px',
            backgroundColor: isDetecting ? '#d93025' : '#4285F4',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '16px',
          }}
        >
          {isDetecting ? 'Parar Detecção' : 'Iniciar Detecção'}
        </button>
      </div>
    </div>
  );
}

export default FaceDetectionComponent;
