// src/components/CustomIpNode.js
import React from 'react';
import { Handle, Position } from 'reactflow';
import { Card, Typography } from 'antd';

const { Text } = Typography;

function CustomIpNode({ data }) {
  const { ip, domains } = data;

  return (
    <Card
      title={<Text strong>{ip}</Text>}
      size='small'
      style={{
        width: 200,
        border: '2px solid #1890ff',
        borderRadius: '15px',
        textAlign: 'center',
        background: '#141414',
      }}
    >
      <Handle type='source' position={Position.Top} style={{ opacity: 0 }} />
      <Handle type='target' position={Position.Bottom} style={{ opacity: 0 }} />

      {domains && domains.length > 0 && (
        <div style={{ marginTop: '5px' }}>
          {domains.map((domain) => (
            <Text
              key={domain}
              style={{ display: 'block', fontSize: '12px', color: '#aaa' }}
            >
              {domain}
            </Text>
          ))}
        </div>
      )}
    </Card>
  );
}

export default CustomIpNode;
