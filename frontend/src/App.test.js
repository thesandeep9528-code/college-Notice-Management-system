import React, { act } from 'react';
import ReactDOM from 'react-dom/client';
import { Simulate } from 'react-dom/test-utils';
import App from './App';

const notice = {
  id: 42,
  title: 'Exam schedule',
  description: 'The final examination is on December 12.',
  category: 'Examination',
  department: 'Computer Science',
  semester: '3',
  status: 'approved',
  has_file: true,
  file_name: 'exam-schedule.pdf',
};

const jsonResponse = (payload) => ({
  ok: true,
  json: async () => payload,
});

const unauthorizedResponse = () => ({
  ok: false,
  status: 401,
  json: async () => ({ detail: 'Invalid or expired token' }),
});

const imageResponse = (pageCount) => ({
  ok: true,
  headers: {
    get: (name) => (name.toLowerCase() === 'x-pdf-page-count' ? String(pageCount) : null),
  },
  blob: async () => new Blob(['preview image'], { type: 'image/png' }),
});

it('sends chatbot questions scoped to the notice selected from the board', async () => {
  const previousFetch = global.fetch;
  const previousActEnvironment = global.IS_REACT_ACT_ENVIRONMENT;
  const previousToken = localStorage.getItem('notice-token');
  const previousCreateObjectURL = URL.createObjectURL;
  const previousRevokeObjectURL = URL.revokeObjectURL;
  localStorage.removeItem('notice-token');
  global.IS_REACT_ACT_ENVIRONMENT = true;
  URL.createObjectURL = jest.fn(() => 'blob:notice-page');
  URL.revokeObjectURL = jest.fn();
  const fetchMock = jest.fn(async (url) => {
    if (url.endsWith('/login')) return jsonResponse({ access_token: 'test-token' });
    if (url.endsWith('/me')) {
      return jsonResponse({
        id: 7,
        name: 'Student',
        email: 'student@example.edu',
        role: 'student',
        department: 'Computer Science',
        semester: '3',
      });
    }
    if (url.includes('/notices?')) return jsonResponse([notice]);
    if (url.endsWith(`/notices/${notice.id}`)) return jsonResponse(notice);
    if (url.includes(`/notices/${notice.id}/pages/`)) return imageResponse(2);
    if (url.endsWith('/rag')) {
      return jsonResponse({
        question: 'What date is the exam?',
        answer: '1. **Exam date**: December 12 [Source 1]. 2. **Result date**: December 20 [Source 1].',
        sources: [{
          notice_id: notice.id,
          title: notice.title,
          file_name: notice.file_name,
          page_number: 1,
          has_file: true,
          excerpt: 'The final examination is on December 12.',
        }],
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  global.fetch = fetchMock;

  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = ReactDOM.createRoot(container);

  try {
    await act(async () => {
      root.render(<App />);
    });

    const studentRole = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent.includes('Student'));
    act(() => Simulate.click(studentRole));

    act(() => {
      Simulate.change(container.querySelector('#login-email'), {
        target: { value: 'student@example.edu' },
      });
      Simulate.change(container.querySelector('#login-password'), {
        target: { value: 'test-password' },
      });
    });
    await act(async () => {
      Simulate.submit(container.querySelector('.login-form'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 220));
    });

    const askAboutNotice = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent.includes('Ask AI'));
    expect(askAboutNotice).toBeTruthy();
    act(() => Simulate.click(askAboutNotice));
    expect(container.textContent).toContain('Using this notice only');
    expect(container.textContent).toContain('Exam schedule');

    const questionInput = container.querySelector('[aria-label="Ask about notices"]');
    act(() => Simulate.change(questionInput, {
      target: { value: 'What date is the exam?' },
    }));
    await act(async () => {
      Simulate.submit(container.querySelector('.assistant-form'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const ragRequest = fetchMock.mock.calls.find(([url]) => url.endsWith('/rag'));
    expect(ragRequest).toBeTruthy();
    expect(JSON.parse(ragRequest[1].body).notice_id).toBe(notice.id);
    const answerPoints = container.querySelectorAll('.chat-answer-point');
    expect(answerPoints).toHaveLength(2);
    expect(answerPoints[0].querySelector('strong').textContent).toBe('1. Exam date');
    expect(answerPoints[0].querySelector('span').textContent).toBe(': December 12 [Source 1].');
    expect(answerPoints[1].querySelector('strong').textContent).toBe('2. Result date');
    expect(answerPoints[1].querySelector('span').textContent).toBe(': December 20 [Source 1].');
    expect(container.querySelector('.chat-source .source-link').textContent.trim()).toBe('Open notice');
    expect(container.querySelector('.chat-source small').textContent).toBe('exam-schedule.pdf · Page 1');
    expect(container.textContent).not.toContain('The final examination is on December 12.');

    await act(async () => {
      Simulate.click(container.querySelector('.chat-source'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(container.querySelector('.pdf-preview-page img').alt).toBe('exam-schedule.pdf, page 1');
    expect(container.textContent).toContain('Page 1 of 2');

    await act(async () => {
      Simulate.click(Array.from(container.querySelectorAll('button'))
        .find((button) => button.textContent.includes('Next page')));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(container.querySelector('.pdf-preview-page img').alt).toBe('exam-schedule.pdf, page 2');
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith(`/notices/${notice.id}/pages/2`))).toBe(true);
  } finally {
    await act(async () => root.unmount());
    container.remove();
    global.fetch = previousFetch;
    URL.createObjectURL = previousCreateObjectURL;
    URL.revokeObjectURL = previousRevokeObjectURL;
    global.IS_REACT_ACT_ENVIRONMENT = previousActEnvironment;
    if (previousToken === null) localStorage.removeItem('notice-token');
    else localStorage.setItem('notice-token', previousToken);
  }
});

it('offers only student and faculty workspaces and keeps student registration role-scoped', async () => {
  const previousFetch = global.fetch;
  const previousActEnvironment = global.IS_REACT_ACT_ENVIRONMENT;
  const previousToken = localStorage.getItem('notice-token');
  localStorage.removeItem('notice-token');
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const fetchMock = jest.fn(async (url) => {
    if (url.endsWith('/register')) return jsonResponse({ id: 8, role: 'student' });
    throw new Error(`Unexpected request: ${url}`);
  });
  global.fetch = fetchMock;

  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = ReactDOM.createRoot(container);

  try {
    await act(async () => root.render(<App />));

    expect(container.querySelectorAll('.role-option')).toHaveLength(2);
    expect(container.textContent).not.toContain('Admin');
    const studentRole = Array.from(container.querySelectorAll('.role-option'))
      .find((button) => button.textContent.includes('Student'));
    act(() => Simulate.click(studentRole));
    act(() => Simulate.click(
      Array.from(container.querySelectorAll('button'))
        .find((button) => button.textContent.includes('New student?')),
    ));

    const fields = {
      '#registration-name': 'New Student',
      '#registration-department': 'Computer Science',
      '#registration-semester': '2',
      '#login-email': 'new-student@example.edu',
      '#login-password': 'secure-pass-123',
    };
    act(() => {
      Object.entries(fields).forEach(([selector, value]) => {
        Simulate.change(container.querySelector(selector), { target: { value } });
      });
    });
    await act(async () => {
      Simulate.submit(container.querySelector('.login-form'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const registrationRequest = fetchMock.mock.calls.find(([url]) => url.endsWith('/register'));
    expect(registrationRequest).toBeTruthy();
    expect(JSON.parse(registrationRequest[1].body)).toEqual({
      email: 'new-student@example.edu',
      password: 'secure-pass-123',
      name: 'New Student',
      department: 'Computer Science',
      semester: '2',
    });
    expect(container.textContent).toContain('Student account created.');
  } finally {
    await act(async () => root.unmount());
    container.remove();
    global.fetch = previousFetch;
    global.IS_REACT_ACT_ENVIRONMENT = previousActEnvironment;
    if (previousToken === null) localStorage.removeItem('notice-token');
    else localStorage.setItem('notice-token', previousToken);
  }
});

it('clears an expired session and prompts the user to sign in again', async () => {
  const previousFetch = global.fetch;
  const previousActEnvironment = global.IS_REACT_ACT_ENVIRONMENT;
  const previousToken = localStorage.getItem('notice-token');
  localStorage.setItem('notice-token', 'expired-token');
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const fetchMock = jest.fn(async () => unauthorizedResponse());
  global.fetch = fetchMock;

  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = ReactDOM.createRoot(container);

  try {
    await act(async () => {
      root.render(<App />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(container.querySelector('.login-form')).toBeTruthy();
    expect(container.textContent).toContain('Your session expired. Please sign in again.');
    expect(localStorage.getItem('notice-token')).toBeNull();
  } finally {
    await act(async () => root.unmount());
    container.remove();
    global.fetch = previousFetch;
    global.IS_REACT_ACT_ENVIRONMENT = previousActEnvironment;
    if (previousToken === null) localStorage.removeItem('notice-token');
    else localStorage.setItem('notice-token', previousToken);
  }
});
