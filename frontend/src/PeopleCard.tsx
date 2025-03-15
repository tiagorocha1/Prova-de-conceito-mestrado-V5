import React, { useEffect, useState } from "react";

interface PeopleCardProps {
  uuid: string;
  tags: string[];
  onOpenModal: (uuid: string) => void;
  onDelete: (uuid: string) => void;
}

interface PessoaDetails {
  uuid: string;
  tags: string[];
  primary_photo: string;
}

const PeopleCard: React.FC<PeopleCardProps> = ({ uuid, tags, onOpenModal, onDelete }) => {
  const [primaryPhoto, setPrimaryPhoto] = useState<string>("");
  const [tagInput, setTagInput] = useState<string>("");
  const [localTags, setLocalTags] = useState<string[]>(tags);
  const [photoCount, setPhotoCount] = useState<number>(0);

  // Busca os detalhes da pessoa (incluindo a foto primária e tags)
  useEffect(() => {
    async function fetchDetails() {
      try {
        const res = await fetch(`http://localhost:8000/pessoas/${uuid}`);
        const data: PessoaDetails = await res.json();
        setPrimaryPhoto(data.primary_photo);
        setLocalTags(data.tags);
      } catch (error) {
        console.error("Erro ao buscar detalhes da pessoa", uuid, error);
      }
    }
    fetchDetails();
  }, [uuid]);

  // Busca a quantidade de fotos da pessoa
  useEffect(() => {
    async function fetchPhotoCount() {
      try {
        const res = await fetch(`http://localhost:8000/pessoas/${uuid}/photos/count`);
        const data = await res.json();
        if (data.photo_count !== undefined) {
          setPhotoCount(data.photo_count);
        }
      } catch (error) {
        console.error("Erro ao buscar quantidade de fotos para pessoa", uuid, error);
      }
    }
    fetchPhotoCount();
  }, [uuid]);

  const addTag = async () => {
    if (!tagInput.trim()) return;
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag: tagInput.trim() }),
      });
      if (res.ok) {
        setLocalTags((prev) => [...prev, tagInput.trim()]);
        setTagInput("");
      } else {
        console.error("Erro ao adicionar tag para", uuid);
      }
    } catch (error) {
      console.error("Erro ao adicionar tag", error);
    }
  };

  const removeTag = async (tag: string) => {
    try {
      const res = await fetch(`http://localhost:8000/pessoas/${uuid}/tags`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag }), // O backend deve tratar a remoção da tag
      });
      if (res.ok) {
        setLocalTags((prev) => prev.filter((t) => t !== tag));
      } else {
        console.error("Erro ao remover tag para", uuid);
      }
    } catch (error) {
      console.error("Erro ao remover tag", error);
    }
  };



  // Estilo para o badge da contagem de fotos
  const badgeStyle: React.CSSProperties = {
    backgroundColor: "red",
    borderRadius: "50%",
    color: "white",
    padding: "2px 6px",
    fontSize: "12px",
    marginLeft: "5px",
  };

  return (
    <div
      style={{
        border: "1px solid #ccc",
        borderRadius: "8px",
        padding: "10px",
        width: "220px",
        textAlign: "center",
      }}
    >
      <h3 style={{ fontSize: "16px", margin: "0 0 10px 0" }}>UUID: {uuid}</h3>
      {primaryPhoto ? (
        <img
          src={primaryPhoto}
          alt={`Face da pessoa ${uuid}`}
          style={{ width: "100%", borderRadius: "4px" }}
        />
      ) : (
        <div style={{ width: "100%", height: "120px", backgroundColor: "#eee" }} />
      )}
      <div style={{ marginTop: "10px", fontSize: "14px", color: "#333" }}>
        <strong>Tags:</strong>{" "}
        {localTags && localTags.length > 0 ? (
          localTags.map((tag, idx) => (
            <span key={idx} style={{ marginRight: "5px" }}>
              {tag}{" "}
              <button
                onClick={() => removeTag(tag)}
                style={{
                  background: "none",
                  border: "none",
                  color: "red",
                  cursor: "pointer",
                  fontSize: "12px",
                }}
                title="Remover tag"
              >
                ×
              </button>
            </span>
          ))
        ) : (
          "Nenhuma"
        )}
      </div>
      <div style={{ marginTop: "10px" }}>
        <input
          type="text"
          placeholder="Adicionar tag"
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          style={{
            width: "140px",
            padding: "4px",
            marginRight: "5px",
            fontSize: "12px",
          }}
        />
        <button
          onClick={addTag}
          style={{
            padding: "4px 8px",
            backgroundColor: "#4285F4",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontSize: "12px",
          }}
        >
          Add
        </button>
      </div>
      <div style={{ marginTop: "10px" }}>
        <button
          onClick={() => onOpenModal(uuid)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#4285F4",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            width: "100%",
          }}
        >
          Listar Fotos
          {photoCount > 0 && <span style={badgeStyle}>{photoCount}</span>}
        </button>
      </div>
      <div style={{ marginTop: "10px" }}>
        <button
          onClick={() => onDelete(uuid)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#d93025",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            width: "100%",
          }}
        >
          Deletar
        </button>
      </div>
    </div>
  );
};

export default PeopleCard;
