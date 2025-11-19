import React, { useState } from "react";
import { useAuth } from "./AuthContext";

const Login: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || "Erro ao fazer login");
    }
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#1976d2",
        fontFamily: "Roboto, sans-serif",
        padding: "20px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          backgroundColor: "#fff",
          borderRadius: "12px",
          padding: "50px 40px",
          boxShadow: "0 6px 16px rgba(0, 0, 0, 0.15)",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            marginBottom: "36px",
            color: "#1976d2",
            fontWeight: 600,
            fontSize: "22px",
          }}
        >
          Registro de Presenças
        </h2>

        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            alignItems: "stretch",
          }}
        >
          <div style={{ textAlign: "left" }}>
            <label
              style={{
                display: "block",
                marginBottom: "6px",
                fontWeight: 500,
                fontSize: "14px",
                color: "#444",
              }}
            >
              Usuário
            </label>
            <input
              type="text"
              placeholder="Digite seu usuário"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{
                width: "100%",
                padding: "12px 14px",
                borderRadius: "6px",
                border: "1px solid #ccc",
                fontSize: "14px",
                outline: "none",
                transition: "border 0.2s, box-shadow 0.2s",
                boxSizing: "border-box",
              }}
              onFocus={(e) => {
                e.target.style.border = "1px solid #1976d2";
                e.target.style.boxShadow = "0 0 0 2px rgba(25,118,210,0.2)";
              }}
              onBlur={(e) => {
                e.target.style.border = "1px solid #ccc";
                e.target.style.boxShadow = "none";
              }}
            />
          </div>

          <div style={{ textAlign: "left" }}>
            <label
              style={{
                display: "block",
                marginBottom: "6px",
                fontWeight: 500,
                fontSize: "14px",
                color: "#444",
              }}
            >
              Senha
            </label>
            <input
              type="password"
              placeholder="Digite sua senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: "100%",
                padding: "12px 14px",
                borderRadius: "6px",
                border: "1px solid #ccc",
                fontSize: "14px",
                outline: "none",
                transition: "border 0.2s, box-shadow 0.2s",
                boxSizing: "border-box",
              }}
              onFocus={(e) => {
                e.target.style.border = "1px solid #1976d2";
                e.target.style.boxShadow = "0 0 0 2px rgba(25,118,210,0.2)";
              }}
              onBlur={(e) => {
                e.target.style.border = "1px solid #ccc";
                e.target.style.boxShadow = "none";
              }}
            />
          </div>

          {error && (
            <div
              style={{
                backgroundColor: "#fdecea",
                color: "#b71c1c",
                border: "1px solid #f5c6cb",
                borderRadius: "6px",
                padding: "10px",
                fontSize: "13px",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            style={{
              width: "100%",
              backgroundColor: "#1976d2",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              padding: "12px 0",
              fontSize: "15px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background 0.2s, transform 0.1s",
              boxSizing: "border-box",
            }}
            onMouseOver={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.backgroundColor =
                "#1565c0")
            }
            onMouseOut={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.backgroundColor =
                "#1976d2")
            }
            onMouseDown={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.transform =
                "scale(0.98)")
            }
            onMouseUp={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.transform =
                "scale(1)")
            }
          >
            Entrar
          </button>
        </form>

        <p
          style={{
            marginTop: "26px",
            fontSize: "13px",
            color: "#777",
          }}
        >
          © {new Date().getFullYear()} IFPB - Registro de Presenças
        </p>
      </div>
    </div>
  );
};

export default Login;
