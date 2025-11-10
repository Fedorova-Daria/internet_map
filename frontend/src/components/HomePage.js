import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/store'; // Импортируем стор
import { Input, Button, Typography, Space, Spin, Alert } from 'antd';

const { Title } = Typography;

function HomePage() {
  const [domain, setDomain] = useState('tyuiu.ru'); // Вместо subnet теперь domain
  // ✅ Получаем нужные данные и функции из Zustand
  const { startScan, loading, error } = useStore();
  const navigate = useNavigate();

  const handleScan = async () => {
    const success = await startScan(domain);
    // Если сканирование и загрузка прошли успешно, переходим на страницу графа
    if (success) {
      navigate('/graph');
    }
    // Если была ошибка, она автоматически отобразится через Alert
  };

  return (
    <div
      style={{ maxWidth: '500px', margin: '150px auto', textAlign: 'center' }}
    >
      <Title style={{ color: 'white', marginBottom: '24px' }}>Карта Сети</Title>

      {/* Отображение ошибки, если она есть */}
      {error && (
        <Alert
          message={error}
          type='error'
          style={{ marginBottom: '20px', textAlign: 'left' }}
        />
      )}

      <Space.Compact style={{ width: '100%' }}>
        <Input
          size='large'
          value={domain}
          disabled={loading}
          onChange={(e) => setDomain(e.target.value)}
          placeholder='Введите домен, например, tyuiu.ru'
          onPressEnter={handleScan} // Добавим сканирование по нажатию Enter
        />

        <Button
          type='primary'
          size='large'
          onClick={handleScan}
          loading={loading} // Используем встроенный loading у кнопки Ant Design
        >
          {loading ? 'Сканирование...' : 'Сканировать'}
        </Button>
      </Space.Compact>
    </div>
  );
}

export default HomePage;
