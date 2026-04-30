export default function Home() {
  return (
    <main>
      {/* Header */}
      <header
        style={{
          background: "#161b22",
          padding: "20px 30px",
          borderBottom: "1px solid #30363d",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1 style={{ color: "#58a6ff", fontSize: "24px" }}>
          🤖 Binance Futures Bot
        </h1>
        <span
          style={{
            padding: "8px 16px",
            borderRadius: "20px",
            fontWeight: "bold",
            fontSize: "14px",
            background: "#238636",
            color: "#fff",
          }}
        >
          PAPER
        </span>
      </header>

      {/* Stats Bar */}
      <div
        style={{
          display: "flex",
          gap: "20px",
          padding: "20px 30px",
          background: "#161b22",
          borderBottom: "1px solid #30363d",
          flexWrap: "wrap",
        }}
      >
        {[
          { label: "Bakiye (USDT)", value: "0.00", color: "#e6edf3" },
          { label: "Günlük PnL", value: "0.00%", color: "#3fb950" },
          { label: "Aktif Pozisyon", value: "0", color: "#e6edf3" },
          { label: "Aktif Sinyal", value: "0", color: "#e6edf3" },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              background: "#21262d",
              padding: "15px 25px",
              borderRadius: "8px",
              minWidth: "150px",
            }}
          >
            <div
              style={{ fontSize: "12px", color: "#8b949e", marginBottom: "5px" }}
            >
              {stat.label}
            </div>
            <div
              style={{
                fontSize: "24px",
                fontWeight: "bold",
                color: stat.color,
              }}
            >
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Main Content */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          padding: "20px 30px",
        }}
      >
        {/* Signals Panel */}
        <div
          style={{
            background: "#161b22",
            borderRadius: "8px",
            border: "1px solid #30363d",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "15px 20px",
              background: "#21262d",
              borderBottom: "1px solid #30363d",
              fontWeight: "bold",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 style={{ fontSize: "16px" }}>📊 Sinyaller</h2>
            <span style={{ fontSize: "12px", color: "#8b949e" }}>
              Son tarama: Henüz yok
            </span>
          </div>
          <div style={{ padding: "15px" }}>
            <div
              style={{ color: "#8b949e", textAlign: "center", padding: "40px" }}
            >
              Bot başlatılmadı
            </div>
          </div>
        </div>

        {/* Positions Panel */}
        <div
          style={{
            background: "#161b22",
            borderRadius: "8px",
            border: "1px solid #30363d",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "15px 20px",
              background: "#21262d",
              borderBottom: "1px solid #30363d",
              fontWeight: "bold",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 style={{ fontSize: "16px" }}>💼 Açık Pozisyonlar</h2>
          </div>
          <div style={{ padding: "15px" }}>
            <div
              style={{ color: "#8b949e", textAlign: "center", padding: "40px" }}
            >
              Açık pozisyon yok
            </div>
          </div>
        </div>

        {/* Trade History - Full Width */}
        <div
          style={{
            gridColumn: "1 / -1",
            background: "#161b22",
            borderRadius: "8px",
            border: "1px solid #30363d",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "15px 20px",
              background: "#21262d",
              borderBottom: "1px solid #30363d",
              fontWeight: "bold",
            }}
          >
            <h2 style={{ fontSize: "16px" }}>📜 İşlem Geçmişi</h2>
          </div>
          <div style={{ padding: "15px" }}>
            <div
              style={{ color: "#8b949e", textAlign: "center", padding: "40px" }}
            >
              İşlem geçmişi yok
            </div>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div style={{ padding: "0 30px 30px" }}>
        <div
          style={{
            background: "#161b22",
            borderRadius: "8px",
            border: "1px solid #30363d",
            padding: "20px",
          }}
        >
          <h2 style={{ fontSize: "16px", marginBottom: "12px", color: "#58a6ff" }}>
            ⚙️ Bot Durumu
          </h2>
          <p style={{ color: "#8b949e", fontSize: "14px", lineHeight: "1.6" }}>
            Bu dashboard, Binance Futures Scalper Bot&apos;un web arayüzüdür.
            Botu çalıştırmak için:{" "}
            <code
              style={{
                background: "#21262d",
                padding: "2px 6px",
                borderRadius: "4px",
                color: "#3fb950",
              }}
            >
              python main.py --mode paper
            </code>
          </p>
        </div>
      </div>
    </main>
  );
}
