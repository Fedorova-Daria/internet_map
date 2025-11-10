import { create } from 'zustand';
import axios from 'axios';

export const useStore = create((set, get) => ({
  nodes: [],
  edges: [],
  loading: false,
  error: null,

  // Эта функция теперь просто получает уже готовые данные графа
  fetchGraphData: async (domain) => {
    set({ loading: true, error: null });
    try {
      const response = await axios.get(`/api/links/graph/?domain=${domain}`);
      set({
        nodes: response.data.nodes || [],
        edges: response.data.edges || [],
        loading: false,
      });
    } catch (error) {
      console.error('Ошибка загрузки графа:', error);
      set({ error: 'Не удалось загрузить данные графа.', loading: false });
    }
  },

  // ✅ НОВАЯ ФУНКЦИЯ: для запуска сканирования
  startScan: async (domain, depth = 3) => {
    set({ loading: true, error: null, nodes: [], edges: [] }); // Сбрасываем все перед новым сканированием
    try {
      // Шаг 1: Отправляем запрос на сканирование
      await axios.post('/api/domains/scan/', {
        domain: domain,
        depth: depth,
      });

      // Шаг 2: После успешного сканирования, вызываем загрузку данных графа
      // Используем get() для доступа к другим экшенам стора
      await get().fetchGraphData(domain);
    } catch (error) {
      console.error('Ошибка сканирования домена:', error);
      const errorMessage =
        error.response?.data?.detail || 'Произошла ошибка при сканировании.';
      set({ error: errorMessage, loading: false });
      // Возвращаем false, чтобы компонент знал, что произошла ошибка
      return false;
    }
    // Возвращаем true при успехе
    return true;
  },
}));
