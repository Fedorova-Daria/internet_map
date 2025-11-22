import React from 'react';
import { Handle, Position } from 'reactflow';

function CustomDomainNode({ data }) {
  const label = data.label || 'Неизвестный домен';
  const isLongLabel = label.length > 28;
  return (
    <div
      style={{
        background: '#fff',
        padding: '10px 12px',
        borderRadius: '6px',
        border: `2px solid #38BDF8`,
        position: 'relative',
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
        minWidth: '150px',
        maxWidth: '300px',
      }}
    >
      <Handle
        type='target'
        position={Position.Top}
        style={{
          background: '#38BDF8',
          width: '10px',
          height: '10px',
          borderRadius: '50%',
        }}
      />

      <div
        style={{
          fontSize: '12px',
          marginBottom: '5px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <span
          style={{
            display: 'inline-block',
            background: '#E6E6E6',
            color: '#666',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '10px',
            flexShrink: 0,
          }}
        >
          Домен
        </span>
        <span
          style={{
            fontWeight: 'bold',
            color: '#333',
            fontSize: isLongLabel ? '11px' : '12px', // Уменьшаем шрифт для очень длинных доменов

            wordBreak: 'break-all', // Позволяет разрывать длинные слова (важно для доменов без дефисов)
            whiteSpace: 'pre-wrap', // Уважаем пробелы и переносим текст
          }}
        >
          {label}
        </span>
      </div>

      {data.organization && (
        <div
          style={{
            fontSize: '11px',
            color: '#666',
            marginTop: '5px',
            paddingTop: '5px',
            borderTop: '1px solid #E6E6E6',
            wordBreak: 'break-word',
          }}
        >
          {data.organization}
        </div>
      )}

      <Handle
        type='source'
        position={Position.Bottom}
        style={{
          background: '#38BDF8',
          width: '10px',
          height: '10px',
          borderRadius: '50%',
        }}
      />
    </div>
  );
}

export default CustomDomainNode;
