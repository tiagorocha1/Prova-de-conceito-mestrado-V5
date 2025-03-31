import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';
import { useAuth } from "./AuthContext";

interface Pessoa {
  uuid: string;
  primary_photo: string | null;
  tags: string[];
  presencas_count: number;
}

interface PessoaPhotos {
  uuid: string;
  image_urls: string[];
}

Modal.setAppElement('#root'); // ajuste conforme o elemento raiz

const Presentes: React.FC = () => {
  const [date, setDate] = useState<string>('');
  const [minPresencas, setMinPresencas] = useState<number>(1);
  const [pessoas, setPessoas] = useState<Pessoa[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Estado para o modal de fotos
  const [modalIsOpen, setModalIsOpen] = useState<boolean>(false);
  const [selectedPessoaUuid, setSelectedPessoaUuid] = useState<string | null>(null);
  const [photos, setPhotos] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]); // Estado para armazenar as tags da pessoa selecionada
  const [photosLoading, setPhotosLoading] = useState<boolean>(false);

  const { token } = useAuth();
  const fetchPresentes = useCallback(async () => {
    setLoading(true);
    setError(null);

     // Formata a data para o formato "dd-MM-yyyy"
  const dateObj = new Date(date);
  const day = String(dateObj.getUTCDate()).padStart(2, '0');
  const month = String(dateObj.getUTCMonth() + 1).padStart(2, '0');
  const year = dateObj.getUTCFullYear();
  const formattedDate = `${day}-${month}-${year}`;
  
    try {
      const response = await fetch(`http://localhost:8000/presentes?date=${formattedDate}&min_presencas=${minPresencas}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error('Erro ao buscar os presentes.');
      }
      const data = await response.json();
      setPessoas(data.pessoas);
    } catch (err) {
      setError('Erro ao buscar os presentes.');
    } finally {
      setLoading(false);
    }
  }, [date, minPresencas]);

  useEffect(() => {
    if (date) {
      fetchPresentes();
    }
  }, [date, minPresencas, fetchPresentes]);

  const fetchPhotosAndTags = async (uuid: string) => {
    setPhotosLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/photos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data: PessoaPhotos = await res.json();
      setPhotos(data.image_urls);

      const pessoa = pessoas.find(p => p.uuid === uuid);
      if (pessoa) {
        setTags(pessoa.tags);
      }
    } catch (error) {
      console.error('Erro ao buscar fotos da pessoa:', error);
    }
    setPhotosLoading(false);
  };

  const openModal = (uuid: string) => {
    setSelectedPessoaUuid(uuid);
    setModalIsOpen(true);
    fetchPhotosAndTags(uuid);
  };

  const closeModal = () => {
    setModalIsOpen(false);
    setPhotos([]);
    setTags([]);
    setSelectedPessoaUuid(null);
  };

  const removePhoto = async (photoUrl: string) => {
    if (!selectedPessoaUuid) return;
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${selectedPessoaUuid}/photos`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ photo: photoUrl }),
      });
      if (res.ok) {
        // Atualiza a listagem de fotos após a remoção
        fetchPhotosAndTags(selectedPessoaUuid);
      } else {
        console.error('Erro ao remover foto para', selectedPessoaUuid);
      }
    } catch (error) {
      console.error('Erro ao remover foto:', error);
    }
  };

  const addTag = async (uuid: string, tag: string) => {
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' , Authorization: `Bearer ${token}`},
        body: JSON.stringify({ tag }),
      });
      if (res.ok) {
        fetchPresentes();
      } else {
        console.error('Erro ao adicionar tag', uuid);
      }
    } catch (error) {
      console.error('Erro ao adicionar tag', error);
    }
  };

  const removeTag = async (uuid: string, tag: string) => {
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/tags`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tag }),
      });
      if (res.ok) {
        fetchPresentes();
      } else {
        console.error('Erro ao remover tag', uuid);
      }
    } catch (error) {
      console.error('Erro ao remover tag', error);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Roboto, sans-serif' }}>
      <h2>Presentes</h2>
      <div style={{ marginBottom: '20px' }}>
        <label>
          Data:
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{ marginLeft: '10px' }}
          />
        </label>

        <button onClick={fetchPresentes} style={{ marginLeft: '10px' }}>
          Atualizar
        </button>
 
      </div>
      {loading && <div>Carregando...</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      <div style={{ marginBottom: '20px' }}>
        <strong>Total de Pessoas:</strong> {pessoas.length}
      </div>

      <div style={{ marginTop: '20px', display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
        {pessoas.map((pessoa) => (
          pessoa.primary_photo && (
            <img key={pessoa.uuid} src={pessoa.primary_photo} alt={`Foto de ${pessoa.uuid}`} style={{ width: '100px', height: '100px', objectFit: 'cover', borderRadius: '4px', cursor: 'pointer' }} 
            onMouseOver={(e) => (e.currentTarget.style.transform = 'scale(1.5)')}
            onMouseOut={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            onClick={() => openModal(pessoa.uuid)}  />
          )
        ))}
      </div>
      <Modal
        isOpen={modalIsOpen}
        onRequestClose={closeModal}
        contentLabel="Fotos da Pessoa"
        style={{
          content: {
            top: '50%',
            left: '50%',
            right: 'auto',
            bottom: 'auto',
            transform: 'translate(-50%, -50%)',
            maxWidth: '800px',
            width: '90%',
            maxHeight: '80vh',
            overflowY: 'auto',
            padding: '20px',
          },
          overlay: { backgroundColor: 'rgba(0, 0, 0, 0.5)' },
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Fotos da Pessoa {selectedPessoaUuid}</h2>
          <h3>{tags.join(', ')}</h3> {/* Exibe as tags da pessoa */}
          <button
            onClick={closeModal}
            style={{
              backgroundColor: '#4285F4',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            Fechar
          </button>
        </div>
        {photosLoading ? (
          <div>Carregando fotos...</div>
        ) : photos.length === 0 ? (
          <div>Nenhuma foto encontrada.</div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '10px',
              marginTop: '20px',
            }}
          >
            {photos.map((url, idx) => (
              <div key={idx} style={{ position: 'relative' }}>
                <img
                  src={url}
                  alt={`Face ${idx}`}
                  style={{
                    maxWidth: '100%',
                    height: 'auto',
                    borderRadius: '8px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                  }}
                />
                <button
                  onClick={() => removePhoto(url)}
                  style={{
                    position: 'absolute',
                    top: '5px',
                    right: '5px',
                    background: 'rgba(255,255,255,0.8)',
                    border: 'none',
                    borderRadius: '50%',
                    cursor: 'pointer',
                    fontSize: '16px',
                    lineHeight: '1',
                    padding: '2px 6px',
                  }}
                  title="Remover foto"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Presentes;