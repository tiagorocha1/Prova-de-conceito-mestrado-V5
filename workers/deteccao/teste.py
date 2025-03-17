import cv2
from deepface import DeepFace

def main():
    # Caminho para a imagem de teste (substitua "input.jpg" pelo caminho da sua imagem)
    img_path = "teste.jpg"
    
    # Extraindo as faces utilizando o detector retinaface
    faces = DeepFace.extract_faces(img_path=img_path, detector_backend="retinaface")
    
    print(f"Total de faces detectadas: {len(faces)}")
    
    # Carrega a imagem original para desenhar os retângulos
    img = cv2.imread(img_path)
    
    # Itera sobre as faces detectadas e desenha retângulos
    for i, face in enumerate(faces):
        facial_area = face["facial_area"]
        x, y, w, h = facial_area["x"], facial_area["y"], facial_area["w"], facial_area["h"]
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # Salva a face extraída em um arquivo separado
        cv2.imwrite(f"face_{i}.jpg", face["face"])
    
    # Exibe a imagem com os retângulos das faces detectadas
    cv2.imshow("Faces Detectadas", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
