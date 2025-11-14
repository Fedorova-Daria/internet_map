import React, { useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
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

const createForceLayout = (nodes, edges, { width, height, rootDomainName }) => {
  // Находим корневой узел, чтобы зафиксировать его
  const rootNode = nodes.find((n) => n.data.label === rootDomainName);

  if (rootNode) {
    // Фиксируем корневой узел в центре
    rootNode.fx = width / 2;
    rootNode.fy = height / 2;
  }

  const graphData = {
    nodes: nodes.map((node) => ({
      ...node,
      radius: node.type === 'customIpNode' ? 40 : 60, // Уменьшим радиус для IP
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
        .distance(150)
        .strength(0.5)
    )
    // ✅ Заменяем центрирование на РАДИАЛЬНОЕ расположение
    .force(
      'r',
      d3
        .forceRadial(
          (d) => {
            // Узлы, напрямую связанные с корнем, будут ближе
            const isDirectLink = graphData.links.some(
              (l) =>
                (l.source.id === rootNode?.id && l.target.id === d.id) ||
                (l.target.id === rootNode?.id && l.source.id === d.id)
            );
            return isDirectLink ? 200 : 500;
          },
          width / 2,
          height / 2
        )
        .strength(0.8)
    )
    .force('charge', d3.forceManyBody().strength(-200)) // Уменьшаем отталкивание, т.к. радиальная сила уже расставляет узлы
    .force(
      'collision',
      d3.forceCollide().radius((d) => d.radius + 15)
    ) // Уменьшаем радиус столкновения
    .stop();

  // Запускаем достаточное количество итераций для стабилизации
  for (let i = 0, n = 300; i < n; ++i) {
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
  const location = useLocation(); // ✅ Получаем доступ к URL

  // ✅ Извлекаем домен из URL, чтобы знать, какой узел корневой
  const rootDomainName = useMemo(() => {
    const searchParams = new URLSearchParams(location.search);
    return searchParams.get('domain');
  }, [location.search]);

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
        // Уменьшаем размеры узлов, чтобы они не были громоздкими
        width: node.type === 'ip' ? 100 : 150,
        minHeight: 40,
      },
    }));

    const flowEdges = rawEdges.map((edge) => ({
      id: edge.id.toString(),
      source: edge.source.toString(),
      target: edge.target.toString(),
      animated: false,
      style: {
        stroke: edge.type === 'direct' ? '#ff4d4f' : '#1890ff',
        strokeWidth: edge.type === 'direct' ? 1.5 : 1, // Делаем линии тоньше
      },
      label: '', // Убираем метки с ребер, чтобы не загромождать
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.type === 'direct' ? '#ff4d4f' : '#1890ff',
        width: 15,
        height: 15,
      },
    }));

    const layoutResult = createForceLayout(flowNodes, flowEdges, {
      width,
      height,
      rootDomainName, // ✅ Передаем имя корневого домена
    });

    setLayoutedNodes(layoutResult.nodes);
    setLayoutedEdges(layoutResult.edges);
  }, [
    loading,
    rawNodes,
    rawEdges,
    setLayoutedNodes,
    setLayoutedEdges,
    rootDomainName,
  ]);

  const onInit = useCallback((reactFlowInstance) => {
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.1, duration: 800 });
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
