import { useState } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

function App() {
  const [loggedIn, setLoggedIn] = useState(!!sessionStorage.getItem('token'));

  return loggedIn
    ? <Dashboard onLogout={() => setLoggedIn(false)} />
    : <Login onLogin={() => setLoggedIn(true)} />;
}

export default App;
