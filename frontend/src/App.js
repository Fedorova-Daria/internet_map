import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './components/HomePage';
import GraphPage from './components/GraphPage';
import 'reactflow/dist/style.css'; // Обязательные стили для React Flow
import { ConfigProvider, theme } from 'antd'; // Для темной темы, если захотите

function App() {
  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
      <div style={{ padding: '1px', height: '100vh', background: '#1F1F1F' }}>
        <Router>
          <Routes>
            <Route path='/' element={<HomePage />} />
            <Route path='/graph' element={<GraphPage />} />
          </Routes>
        </Router>
      </div>
    </ConfigProvider>
  );
}

export default App;
