import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [token, setToken] = useState(null);
  const [role, setRole] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');

  const apiBase = 'http://localhost:8000'; // FastAPI server

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error('Invalid credentials');
      const data = await res.json();
      setToken(data.access_token);
      setRole(data.role);
      setMessage('Logged in as ' + data.role);
    } catch (err) {
      setMessage(err.message);
    }
  };

  // Simple logout
  const logout = () => {
    setToken(null);
    setRole(null);
    setMessage('Logged out');
  };

  // RAG query state (for students)
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const askQuestion = async () => {
    if (!question) return;
    const res = await fetch(`${apiBase}/rag`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    setAnswer(data.answer);
  };

  // Minimal UI per role
  const renderStudent = () => (
    <div className="student-dashboard">
      <h2>Student Dashboard</h2>
      <input
        type="text"
        placeholder="Ask a question about notices"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <button onClick={askQuestion}>Get Answer</button>
      {answer && (
        <div className="answer">
          <h4>Answer:</h4>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );

  const renderFaculty = () => (
    <div className="faculty-dashboard">
      <h2>Faculty Dashboard (Create Notice)</h2>
      <p>Notice creation UI to be implemented.</p>
    </div>
  );

  const renderAdmin = () => (
    <div className="admin-dashboard">
      <h2>Admin Dashboard</h2>
      <p>User management and notice approval UI to be implemented.</p>
    </div>
  );

  if (!token) {
    return (
      <div className="login-container">
        <h2>Login</h2>
        <form onSubmit={handleLogin}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit">Login</button>
        </form>
        {message && <p>{message}</p>}
      </div>
    );
  }

  return (
    <div className="app-container">
      <header>
        <h1>AI College Notice</h1>
        <button onClick={logout}>Logout</button>
      </header>
      {message && <p>{message}</p>}
      {role === 'student' && renderStudent()}
      {role === 'faculty' && renderFaculty()}
      {role === 'admin' && renderAdmin()}
    </div>
  );
}

export default App;
