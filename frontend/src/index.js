import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css'; // Ваш главный файл стилей
import App from './App'; // Ваш главный компонент приложения

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
