import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';

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
  const [photosLoading, setPhotosLoading] = useState<boolean>(false);

  const fetchPresentes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/presentes?date=${date}&min_presencas=${minPresencas}`);
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

  const fetchPhotos = async (uuid: string) => {
    setPhotosLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/photos`);
      const data: PessoaPhotos = await res.json();
      setPhotos(data.image_urls);
    } catch (error) {
      console.error('Erro ao buscar fotos da pessoa:', error);
    }
    setPhotosLoading(false);
  };

  const openModal = (uuid: string) => {
    setSelectedPessoaUuid(uuid);
    setModalIsOpen(true);
    fetchPhotos(uuid);
  };

  const closeModal = () => {
    setModalIsOpen(false);
    setPhotos([]);
    setSelectedPessoaUuid(null);
  };

  const removePhoto = async (photoUrl: string) => {
    if (!selectedPessoaUuid) return;
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${selectedPessoaUuid}/photos`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo: photoUrl }),
      });
      if (res.ok) {
        // Atualiza a listagem de fotos após a remoção
        fetchPhotos(selectedPessoaUuid);
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
        headers: { 'Content-Type': 'application/json' },
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
        headers: { 'Content-Type': 'application/json' },
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
        <label style={{ marginLeft: '20px' }}>
          Mínimo de Presenças:
          <input
            type="number"
            value={minPresencas}
            onChange={(e) => setMinPresencas(parseInt(e.target.value))}
            style={{ marginLeft: '10px' }}
          />
        </label>
        <button onClick={fetchPresentes} style={{ marginLeft: '20px' }}>
          Buscar
        </button>
      </div>
      {loading && <div>Carregando...</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      <div style={{ marginBottom: '20px' }}>
        <strong>Total de Pessoas:</strong> {pessoas.length}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ border: '1px solid #ccc', padding: '8px', maxWidth: '15%' }}>Foto</th>
            <th style={{ border: '1px solid #ccc', padding: '8px' }}>Tags</th>
            <th style={{ border: '1px solid #ccc', padding: '8px' }}>Registros</th>
            <th style={{ border: '1px solid #ccc', padding: '8px' }}>Ações</th>
          </tr>
        </thead>
        <tbody>
          {pessoas.map((pessoa) => (
            <tr key={pessoa.uuid}>
              <td style={{ border: '1px solid #ccc', padding: '8px', textAlign: 'center', maxWidth: '15%' }}>
                {pessoa.primary_photo ? (
                  <img
                    src={pessoa.primary_photo}
                    alt={`Foto de ${pessoa.uuid}`}
                    style={{
                      width: '75px',
                      height: '75px',
                      borderRadius: '4px',
                      transition: 'transform 0.2s',
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.transform = 'scale(1.5)')}
                    onMouseOut={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                  />
                ) : (
                  <div style={{ width: '75px', height: '75px', backgroundColor: '#eee' }} />
                )}
                <input
                  type="text"
                  placeholder="Adicionar tag"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      addTag(pessoa.uuid, e.currentTarget.value);
                      e.currentTarget.value = '';
                    }
                  }}
                  style={{ marginTop: '10px', width: '100%' }}
                />
              </td>
              <td style={{ border: '1px solid #ccc', padding: '8px' }}>
                {pessoa.tags.map((tag) => (
                  <span key={tag} style={{ display: 'inline-block', margin: '5px' }}>
                    {tag}
                    <button
                      onClick={() => removeTag(pessoa.uuid, tag)}
                      style={{
                        marginLeft: '5px',
                        backgroundColor: 'red',
                        color: 'white',
                        border: 'none',
                        borderRadius: '50%',
                        cursor: 'pointer',
                      }}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </td>
              <td style={{ border: '1px solid #ccc', padding: '8px' }}>{pessoa.presencas_count}</td>
              <td style={{ border: '1px solid #ccc', padding: '8px', textAlign: 'center' }}>
                <button onClick={() => openModal(pessoa.uuid)} style={{ marginBottom: '10px' }}>
                  Ver Fotos
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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