import { useState } from 'react';
import { Btn, Badge } from './ui/Primitives';

const C = {
  border: '#232840',
  accent: '#4f8ef7',
  green: '#34d399',
  purple: '#a78bfa',
  orange: '#f97316',
  textMuted: '#64748b',
};

export function ERDView({ loading, error, diagram, format, onBack, onReset, onDownload }) {
  const [showDotSource, setShowDotSource] = useState(false);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div
          style={{
            animation: 'spin 1s linear infinite',
            fontSize: 40,
            marginBottom: 16,
          }}
        >
          ◆
        </div>
        <p style={{ color: C.textMuted }}>Generating Entity Relationship Diagram...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          background: '#3d2222',
          border: '1px solid #8b4444',
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ color: '#ff7b7b', fontWeight: 600, marginBottom: 8 }}>Error generating ERD</div>
        <div style={{ color: C.textMuted, fontSize: 14 }}>{error}</div>
      </div>
    );
  }

  if (!diagram || !diagram.diagram_data) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <p style={{ color: C.textMuted }}>No diagram data available</p>
      </div>
    );
  }

  // Determine MIME type based on format
  const mimeType = 
    diagram.format === 'png' ? 'image/png' :
    diagram.format === 'pdf' ? 'application/pdf' :
    'image/svg+xml';

  const imageSrc = `data:${mimeType};base64,${diagram.diagram_data}`;

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 24,
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 6,
              flexWrap: 'wrap',
            }}
          >
            <h2 style={{ fontSize: 22, fontWeight: 700 }}>Entity Relationship Diagram</h2>
            <Badge color={C.orange}>Generated</Badge>
            <Badge color={C.textMuted}>{diagram.format?.toUpperCase() || 'SVG'}</Badge>
          </div>
          <p style={{ color: C.textMuted, fontSize: 14 }}>
            Visual representation of your database schema showing all tables, relationships, and constraints.
          </p>
        </div>

        <Btn variant="ghost" onClick={onBack}>
          ← Back to SQL
        </Btn>
      </div>

      {/* ERD Display */}
      <div
        style={{
          background: '#090b10',
          border: '1px solid ' + C.border,
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 400,
          maxHeight: 700,
          overflow: 'auto',
        }}
      >
        {diagram.format === 'pdf' ? (
          <div style={{ textAlign: 'center', color: C.textMuted }}>
            <p>PDF preview not supported in browser</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>Use the download button to view the PDF</p>
          </div>
        ) : (
          <img
            src={imageSrc}
            alt="Entity Relationship Diagram"
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
          />
        )}
      </div>

      {/* DOT Source Toggle */}
      <div style={{ marginBottom: 20 }}>
        <button
          onClick={() => setShowDotSource(!showDotSource)}
          style={{
            background: 'transparent',
            border: '1px solid ' + C.border,
            color: C.accent,
            padding: '8px 14px',
            borderRadius: 8,
            cursor: 'pointer',
            fontSize: 12,
            fontWeight: 600,
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => (e.target.style.borderColor = C.accent)}
          onMouseLeave={(e) => (e.target.style.borderColor = C.border)}
        >
          {showDotSource ? '▼' : '▶'} Graphviz Source (.DOT)
        </button>
      </div>

      {showDotSource && diagram.dot_source && (
        <div
          style={{
            background: '#090b10',
            border: '1px solid ' + C.border,
            borderRadius: 12,
            padding: 20,
            marginBottom: 24,
          }}
        >
          <pre
            style={{
              fontSize: 11,
              lineHeight: 1.6,
              color: '#c9d1d9',
              fontFamily: '"Fira Code", monospace',
              overflowX: 'auto',
              margin: 0,
            }}
          >
            <code>{diagram.dot_source}</code>
          </pre>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Btn
          onClick={onDownload}
          style={{
            background: C.orange,
            color: '#fff',
            border: 'none',
            padding: '10px 20px',
          }}
        >
          ⬇ Download {diagram.format?.toUpperCase() || 'SVG'}
        </Btn>
        <Btn variant="ghost" onClick={onReset}>
          ✦ Start New Model
        </Btn>
      </div>
    </div>
  );
}
