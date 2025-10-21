// src/components/HomePage.js
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input, Button, Typography, Space, Spin } from 'antd';

const { Title } = Typography;

function HomePage() {
  const [subnet, setSubnet] = useState('192.168.1.0/24');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  // Функция для обработки сканирования
  const handleScan = () => {
    setIsLoading(true); // Включаем режим загрузки

    // Имитируем процесс сканирования (3 секунды)
    setTimeout(() => {
      // После "сканирования" переходим на страницу с графом
      navigate('/graph');
    }, 3000);
  };

  return (
    <div
      style={{ maxWidth: '500px', margin: '150px auto', textAlign: 'center' }}
    >
      <Title style={{ color: 'white' }}>Карта Сети</Title>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          size='large'
          value={subnet}
          disabled={isLoading} // Блокируем поле ввода во время загрузки
          onChange={(e) => setSubnet(e.target.value)}
          placeholder='Введите подсеть, например, 192.168.1.0/24'
        />

        {/* В зависимости от состояния isLoading показываем или кнопку, или загрузку */}
        {isLoading ? (
          <Button type='primary' size='large' disabled>
            <Spin size='small' style={{ marginRight: '8px' }} />
            Сканирование...
          </Button>
        ) : (
          <Button type='primary' size='large' onClick={handleScan}>
            Сканировать
          </Button>
        )}
      </Space.Compact>
    </div>
  );
}

export default HomePage;
