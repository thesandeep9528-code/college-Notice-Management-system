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

it('sends chatbot questions scoped to the notice selected from the board', async () => {
  const previousFetch = global.fetch;
  const previousActEnvironment = global.IS_REACT_ACT_ENVIRONMENT;
  global.IS_REACT_ACT_ENVIRONMENT = true;
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
    if (url.endsWith('/rag')) {
      return jsonResponse({
        question: 'What date is the exam?',
        answer: 'December 12.',
        sources: [],
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
  } finally {
    await act(async () => root.unmount());
    container.remove();
    global.fetch = previousFetch;
    global.IS_REACT_ACT_ENVIRONMENT = previousActEnvironment;
  }
});
