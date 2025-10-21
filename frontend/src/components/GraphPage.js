// src/components/GraphPage.js
import React, { useEffect, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
} from 'reactflow';
import { useStore } from '../store/store';
import CustomIpNode from './CustomIpNode';

function GraphPage() {
  const {
    nodes: initialNodes,
    edges: initialEdges,
    fetchGraphData,
  } = useStore();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const nodeTypes = useMemo(() => ({ customIpNode: CustomIpNode }), []);
  const { getNodes } = useReactFlow();

  const handleNodeDrag = (_, draggedNode) => {
    // --- ПАРАМЕТРЫ ФИЗИКИ ---
    const idealDistance = 150; // Идеальная длина связи
    const pullFactor = 0.05; // Сила притяжения
    const repelDistance = 270; // Дистанция, на которой начинается отталкивание
    const repelFactor = 0.06; // Сила отталкивания
    // -------------------------

    const allNodes = getNodes();

    const updatedNodes = allNodes.map((n) => {
      if (n.id === draggedNode.id) {
        return draggedNode; // Позиция главного узла контролируется пользователем
      }

      let totalForceX = 0;
      let totalForceY = 0;

      // 1. СИЛА ПРИТЯЖЕНИЯ (как в прошлый раз)
      const connectedEdges = edges.filter(
        (e) => e.source === n.id || e.target === n.id
      );
      connectedEdges.forEach((edge) => {
        const otherNodeId = edge.source === n.id ? edge.target : edge.source;
        const otherNode = allNodes.find((node) => node.id === otherNodeId);
        if (!otherNode) return;

        const dx = otherNode.position.x - n.position.x;
        const dy = otherNode.position.y - n.position.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > idealDistance) {
          const force = (distance - idealDistance) * pullFactor;
          totalForceX += (dx / distance) * force;
          totalForceY += (dy / distance) * force;
        }
      });

      // 2. СИЛА ОТТАЛКИВАНИЯ (новая логика)
      allNodes.forEach((otherNode) => {
        if (n.id === otherNode.id) return;

        const dx = otherNode.position.x - n.position.x;
        const dy = otherNode.position.y - n.position.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < repelDistance) {
          const force = (repelDistance - distance) * repelFactor;
          // Сила действует в обратном направлении (отталкивание)
          totalForceX -= (dx / distance) * force;
          totalForceY -= (dy / distance) * force;
        }
      });

      // Применяем обе силы к позиции узла
      return {
        ...n,
        position: {
          x: n.position.x + totalForceX,
          y: n.position.y + totalForceY,
        },
      };
    });

    setNodes(updatedNodes);
  };

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);
  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);
  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const coloredEdges = useMemo(() => {
    return edges.map((edge) => ({
      ...edge,
      style: {
        stroke: edge.data?.type === 'subnet' ? '#ff4d4f' : '#73d13d',
        strokeWidth: 2,
      },
      animated: true,
    }));
  }, [edges]);

  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <ReactFlow
        nodes={nodes}
        edges={coloredEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDrag={handleNodeDrag}
        fitView
        nodesConnectable={false}
        elementsSelectable={true}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

// Оборачиваем компонент в провайдер
import { ReactFlowProvider } from 'reactflow';

export default () => (
  <ReactFlowProvider>
    <GraphPage />
  </ReactFlowProvider>
);
