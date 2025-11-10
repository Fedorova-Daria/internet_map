import React, { useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  ReactFlowProvider,
} from 'reactflow';
import { useStore } from '../store/store';
import CustomDomainNode from './CustomDomainNode';
import CustomIpNode from './CustomIpNode';
import 'reactflow/dist/style.css';
import * as d3 from 'd3-force';
import { Button } from 'antd';

const createForceLayout = (nodes, edges, { width, height }) => {
  const graphData = {
    nodes: nodes.map((node) => ({
      ...node,
      radius: Math.max(node.style.width, node.style.minHeight) / 2,
    })),
    links: edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
    })),
  };

  const simulation = d3
    .forceSimulation(graphData.nodes)
    .force(
      'link',
      d3
        .forceLink(graphData.links)
        .id((d) => d.id)
        .distance(250)
        .strength(0.8)
    )
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collision',
      d3.forceCollide().radius((d) => d.radius + 30)
    )
    .stop();

  for (
    let i = 0,
      n = Math.ceil(
        Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay())
      );
    i < n;
    ++i
  ) {
    simulation.tick();
  }

  const layoutedNodes = graphData.nodes.map((node) => ({
    ...node,
    position: {
      x: node.x,
      y: node.y,
    },
  }));

  return { nodes: layoutedNodes, edges };
};

function GraphPage() {
  const { nodes: rawNodes, edges: rawEdges, loading, error } = useStore();

  const [layoutedNodes, setLayoutedNodes, onNodesChange] = useNodesState([]);
  const [layoutedEdges, setLayoutedEdges, onEdgesChange] = useEdgesState([]);
  const containerRef = useRef(null);
  const navigate = useNavigate();

  const nodeTypes = useMemo(
    () => ({
      customDomainNode: CustomDomainNode,
      customIpNode: CustomIpNode,
    }),
    []
  );

  useEffect(() => {
    if (
      loading ||
      !rawNodes ||
      rawNodes.length === 0 ||
      !containerRef.current
    ) {
      return;
    }

    const { width, height } = containerRef.current.getBoundingClientRect();

    const flowNodes = rawNodes.map((node) => ({
      id: node.id.toString(),
      type: node.type === 'ip' ? 'customIpNode' : 'customDomainNode',
      data: {
        label: node.label,
        organization: node.organization,
        type: node.type,
      },
      position: { x: 0, y: 0 },
      style: {
        width: node.type === 'ip' ? 120 : 180,
        minHeight: node.type === 'ip' ? 60 : 80,
      },
    }));

    const flowEdges = rawEdges.map((edge) => {
      let edgeColor = '#ccc';
      let edgeWidth = 2;

      if (edge.type === 'direct') {
        edgeColor = '#ff4d4f';
        edgeWidth = 2.5;
      } else if (edge.type === 'via_ip') {
        edgeColor = '#1890ff';
        edgeWidth = 2;
      }

      return {
        id: edge.id.toString(),
        source: edge.source.toString(),
        target: edge.target.toString(),
        animated: true,
        style: { stroke: edgeColor, strokeWidth: edgeWidth },
        label: edge.label || '',
        data: { type: edge.type, ip: edge.ip },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColor,
          width: 20,
          height: 20,
        },
      };
    });

    const layoutResult = createForceLayout(flowNodes, flowEdges, {
      width,
      height,
    });

    // ✅ ИСПРАВЛЕНИЕ: Используем layoutResult.nodes напрямую
    setLayoutedNodes(layoutResult.nodes);
    setLayoutedEdges(flowEdges);
  }, [loading, rawNodes, rawEdges, setLayoutedNodes, setLayoutedEdges]);

  const onInit = useCallback((reactFlowInstance) => {
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.2, duration: 800 });
    }, 100);
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', marginTop: '150px' }}>
        Загрузка графа...
      </div>
    );
  }

  if (error || (!loading && rawNodes.length === 0)) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', marginTop: '150px' }}>
        <h2>{error || 'Нет данных для отображения.'}</h2>
        <p>Попробуйте запустить сканирование снова.</p>
        <Button type='primary' onClick={() => navigate('/')}>
          Вернуться на главную
        </Button>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100vh', position: 'relative' }}
    >
      <ReactFlow
        nodes={layoutedNodes}
        edges={layoutedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView
        minZoom={0.2}
        maxZoom={4}
        attributionPosition='top-left'
      >
        <Background gap={16} size={1} color='#E6E6E6' />
        <Controls />
      </ReactFlow>
      {/* Легенда */}
      <div
        style={{
          position: 'absolute',
          bottom: 20,
          left: 20,
          background: 'white',
          padding: '15px',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          zIndex: 10,
          fontSize: '12px',
        }}
      >
        <div style={{ marginBottom: '10px', fontWeight: 'bold' }}>Легенда:</div>
        <div style={{ display: 'flex', gap: '15px', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div
              style={{
                width: '20px',
                height: '20px',
                background: '#38BDF8',
                borderRadius: '4px',
              }}
            />
            <span>Домен</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div
              style={{
                width: '20px',
                height: '20px',
                background: '#FF9900',
                borderRadius: '4px',
              }}
            />
            <span>IP адрес</span>
          </div>
        </div>
        <div style={{ marginBottom: '5px' }}>
          <span style={{ color: '#ff4d4f', fontWeight: 'bold' }}>───</span>
          <span> Прямая связь</span>
        </div>
        <div>
          <span style={{ color: '#1890ff', fontWeight: 'bold' }}>───</span>
          <span> Связь через IP</span>
        </div>
      </div>
    </div>
  );
}

export default () => (
  <ReactFlowProvider>
    <GraphPage />
  </ReactFlowProvider>
);
