import React, { useEffect, useState } from "react";
import Modal from "react-modal";
import PeopleCard from "./PeopleCard";


interface Pessoa {
  uuid: string;
  tags: string[];
}

interface PessoaPhotos {
  uuid: string;
  image_urls: string[];
}

Modal.setAppElement("#root"); // ajuste conforme o elemento raiz

export const PeopleList: React.FC = () => {
  const [pessoas, setPessoas] = useState<Pessoa[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const limit = 10;
  const [total, setTotal] = useState<number>(0);
  
  // Estado para o modal de fotos
  const [modalIsOpen, setModalIsOpen] = useState<boolean>(false);
  const [selectedPessoaUuid, setSelectedPessoaUuid] = useState<string | null>(null);
  const [photos, setPhotos] = useState<string[]>([]);
  const [photosLoading, setPhotosLoading] = useState<boolean>(false);

  const fetchPessoas = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/pessoas?page=${page}&limit=${limit}`);
      const data = await res.json();
      setPessoas(data.pessoas);
      setTotal(data.total);
    } catch (error) {
      console.error("Erro ao buscar pessoas:", error);
    }
    setLoading(false);
  };

  const fetchPhotos = async (uuid: string) => {
    setPhotosLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/photos`);
      const data: PessoaPhotos = await res.json();
      setPhotos(data.image_urls);
    } catch (error) {
      console.error("Erro ao buscar fotos da pessoa:", error);
    }
    setPhotosLoading(false);
  };

  const deletePessoa = async (uuid: string) => {
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchPessoas();
      } else {
        console.error("Erro ao deletar pessoa", uuid);
      }
    } catch (error) {
      console.error("Erro ao deletar pessoa", error);
    }
  };

  useEffect(() => {
    fetchPessoas();
  }, [page]);

  const totalPages = Math.ceil(total / limit);

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
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo: photoUrl }),
      });
      if (res.ok) {
        // Atualiza a listagem de fotos após a remoção
        fetchPhotos(selectedPessoaUuid);
      } else {
        console.error("Erro ao remover foto para", selectedPessoaUuid);
      }
    } catch (error) {
      console.error("Erro ao remover foto:", error);
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
      <h2>Pessoas Reconhecidas</h2>
      {loading ? (
        <div>Carregando...</div>
      ) : (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "20px" }}>
            {pessoas.map((pessoa) => (
              <PeopleCard
                key={pessoa.uuid}
                uuid={pessoa.uuid}
                tags={pessoa.tags}
                onOpenModal={openModal}
                onDelete={deletePessoa}
              />
            ))}
          </div>
          {/* Paginação */}
          <div style={{ marginTop: "20px", display: "flex", justifyContent: "center", gap: "10px" }}>
            <button
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1}
              style={{
                padding: "8px 12px",
                backgroundColor: "#4285F4",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: page === 1 ? "not-allowed" : "pointer",
              }}
            >
              Anterior
            </button>
            <span>
              Página {page} de {totalPages}
            </span>
            <button
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages}
              style={{
                padding: "8px 12px",
                backgroundColor: "#4285F4",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: page === totalPages ? "not-allowed" : "pointer",
              }}
            >
              Próxima
            </button>
          </div>
        </>
      )}
      {/* Modal para exibir todas as fotos da pessoa */}
      <Modal
        isOpen={modalIsOpen}
        onRequestClose={closeModal}
        contentLabel="Fotos da Pessoa"
        style={{
          content: {
            top: "50%",
            left: "50%",
            right: "auto",
            bottom: "auto",
            transform: "translate(-50%, -50%)",
            maxWidth: "800px",
            width: "90%",
            maxHeight: "80vh",
            overflowY: "auto",
            padding: "20px",
          },
          overlay: { backgroundColor: "rgba(0, 0, 0, 0.5)" },
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Fotos da Pessoa {selectedPessoaUuid}</h2>
          <button
            onClick={closeModal}
            style={{
              backgroundColor: "#4285F4",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              padding: "6px 12px",
              cursor: "pointer",
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
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "10px",
              marginTop: "20px",
            }}
          >
            {photos.map((url, idx) => (
              <div key={idx} style={{ position: "relative" }}>
                <img
                  src={url}
                  alt={`Face ${idx}`}
                  style={{
                    width: "150px",
                    height: "auto",
                    borderRadius: "8px",
                    boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                  }}
                />
                <button
                  onClick={() => removePhoto(url)}
                  style={{
                    position: "absolute",
                    top: "5px",
                    right: "5px",
                    background: "rgba(255,255,255,0.8)",
                    border: "none",
                    borderRadius: "50%",
                    cursor: "pointer",
                    fontSize: "16px",
                    lineHeight: "1",
                    padding: "2px 6px",
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
