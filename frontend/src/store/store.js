// store.js
import { create } from 'zustand';
import axios from 'axios';

// Функция-помощник для поллинга.
const pollGraph = async (domain, sessionId, resolve, reject) => {
  try {
    const response = await axios.get(
      `/api/links/graph/?domain=${domain}&session_id=${sessionId}`
    );

    if (
      response.status === 200 &&
      response.data.nodes &&
      response.data.nodes.length > 0
    ) {
      resolve(response.data);
    } else {
      setTimeout(() => pollGraph(domain, sessionId, resolve, reject), 5000);
    }
  } catch (error) {
    console.error('Ошибка при опросе графа:', error);
    reject(error);
  }
};

export const useStore = create((set) => ({
  nodes: [],
  edges: [],
  loading: false,
  error: null,
  scanStatusMessage: '',

  startScanAndPoll: async (domain, depth) => {
    set({
      loading: true,
      error: null,
      nodes: [],
      edges: [],
      scanStatusMessage: 'Проверяем существующие сканы...',
    });

    try {
      const scanResponse = await axios.post('/api/domains/scan/', {
        domain,
        depth,
      });
      const { session_id } = scanResponse.data;

      if (scanResponse.status === 200) {
        set({
          scanStatusMessage: `Найден готовый скан (ID: ${session_id}). Загружаем граф...`,
        });
        const graphResponse = await axios.get(
          `/api/links/graph/?domain=${domain}&session_id=${session_id}`
        );
        set({
          nodes: graphResponse.data.nodes || [],
          edges: graphResponse.data.edges || [],
          loading: false,
          scanStatusMessage: 'Граф успешно загружен.',
        });
        return { success: true, domain };
      }

      if (scanResponse.status === 202) {
        set({
          scanStatusMessage: `Запущен новый скан (ID: ${session_id}). Ожидаем завершения...`,
        });

        const graphData = await new Promise((resolve, reject) => {
          // ✅ ИСПРАВЛЕНИЕ: Передаем 'domain' и 'session_id' в функцию поллинга
          pollGraph(domain, session_id, resolve, reject);
        });

        set({
          nodes: graphData.nodes || [],
          edges: graphData.edges || [],
          loading: false,
          scanStatusMessage: 'Скан завершен. Граф загружен.',
        });
        return { success: true, domain };
      }
    } catch (error) {
      console.error('Ошибка в процессе сканирования:', error);
      // Важно! Используем error.message, чтобы увидеть ReferenceError
      const errorMessage =
        error.response?.data?.error ||
        error.message ||
        'Произошла неизвестная ошибка.';
      set({ error: errorMessage, loading: false, scanStatusMessage: '' });
      return { success: false };
    }
  },
}));
