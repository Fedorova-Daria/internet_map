import { create } from 'zustand';

export const useStore = create((set) => ({
  // Изначально данные пустые
  nodes: [],
  edges: [],

  // Экшен для обновления данных графа (заглушка)
  // Теперь он просто получает данные и устанавливает их
  fetchGraphData: () => {
    // --- ДАННЫЕ-ЗАГЛУШКИ, КОТОРЫЕ РАНЬШЕ ПРИСЫЛАЛ БЭКЕНД ---
    const mockApiData = {
      nodes: [
        {
          id: 'ip-192.168.1.1',
          type: 'customIpNode',
          position: { x: 100, y: 100 },
          data: {
            ip: '192.168.1.1',
            domains: ['router.local', 'my-gateway.home'],
          },
        },
        {
          id: 'ip-192.168.1.10',
          type: 'customIpNode',
          position: { x: 400, y: 250 },
          data: {
            ip: '192.168.1.10',
            domains: ['fileserver.local'],
          },
        },
        {
          id: 'ip-192.168.1.12',
          type: 'customIpNode',
          position: { x: 150, y: 400 },
          data: {
            ip: '192.168.1.12',
            domains: [],
          },
        },
      ],
      edges: [
        {
          id: 'edge-subnet-1-10',
          source: 'ip-192.168.1.1',
          target: 'ip-192.168.1.10',
          data: {
            type: 'subnet',
          },
        },
        {
          id: 'edge-domain-10-12',
          source: 'ip-192.168.1.10',
          target: 'ip-192.168.1.12',
          data: {
            type: 'domain',
          },
        },
      ],
    };
    // --------------------------------

    // Устанавливаем полученные данные в состояние
    set({
      nodes: mockApiData.nodes,
      edges: mockApiData.edges,
    });
  },
}));
