// HomePage.js
import React, { useState, useMemo } from 'react'; // Добавляем useMemo
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/store';
import { Input, Button, Typography, Space, Alert, Slider } from 'antd'; // Импортируем Slider

const { Title, Text } = Typography; // Добавляем Text для подсказок

// Определяем метки для слайдера
const depthMarks = {
  1: {
    style: { color: '#a0a0a0' },
    label: <strong>1</strong>,
  },
  2: {
    style: { color: '#7aff76ff' },
    label: <strong>2</strong>,
  },
  3: {
    style: { color: '#f5a623' },
    label: <strong>3</strong>,
  },
};

// Описания для каждого уровня глубины
const depthDescriptions = {
  1: 'Первый круг: найти IP-адреса цели, их подсети и все поддомены цели.',
  2: 'Второй круг: для всех найденных на первом круге поддоменов повторить полный цикл (поиск IP, подсетей и уже их поддоменов).',
  3: 'Третий круг: для всех результатов второго круга повторить полный цикл. Максимальная глубина, очень долго.',
};

function HomePage() {
  const [domain, setDomain] = useState('tyuiu.ru');
  const [depth, setDepth] = useState(2); // Глубина по умолчанию

  const { startScanAndPoll, loading, error, scanStatusMessage } = useStore();
  const navigate = useNavigate();

  const handleScan = async () => {
    const result = await startScanAndPoll(domain, depth);
    if (result.success) {
      navigate(`/graph?domain=${result.domain}`);
    }
  };

  // Используем useMemo, чтобы текст подсказки не пересчитывался при каждом рендере
  const currentDepthDescription = useMemo(() => {
    return depthDescriptions[depth];
  }, [depth]);

  return (
    <div
      style={{ maxWidth: '500px', margin: '150px auto', textAlign: 'center' }}
    >
      <Title style={{ color: 'white', marginBottom: '24px' }}>Карта Сети</Title>

      {/* Отображение статуса или ошибки */}
      {(loading || error) && (
        <Alert
          message={loading ? scanStatusMessage : error}
          type={loading ? 'info' : 'error'}
          style={{ marginBottom: '20px' }}
          showIcon
        />
      )}

      {/* Поле ввода домена */}
      <Input
        size='large'
        value={domain}
        disabled={loading}
        onChange={(e) => setDomain(e.target.value)}
        placeholder='Введите домен, например, tyuiu.ru'
        onPressEnter={handleScan}
        style={{ marginBottom: '30px' }} // Добавим отступ снизу
      />

      {/* Наш новый слайдер для выбора глубины */}
      <div style={{ padding: '0 10px', marginBottom: '10px' }}>
        <Slider
          min={1}
          max={3}
          marks={depthMarks}
          value={depth}
          onChange={setDepth}
          disabled={loading}
          step={1} // Шаг слайдера
        />
      </div>

      {/* Динамическое описание для выбранной глубины */}
      <Text type='secondary' style={{ marginBottom: '30px', display: 'block' }}>
        {currentDepthDescription}
      </Text>

      {/* Кнопка запуска */}
      <Button
        type='primary'
        size='large'
        onClick={handleScan}
        loading={loading}
        block // Растянем кнопку на всю ширину
      >
        {loading ? 'Выполняется...' : 'Анализ'}
      </Button>
    </div>
  );
}

export default HomePage;
