import React, { useCallback, useEffect, useState } from 'react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';
const EMPTY_NOTICE = { title: '', description: '', category: '', department: '', semester: '' };
const CATEGORY_OPTIONS = ['Academic', 'Examination', 'Events', 'General', 'Fees', 'Placement'];
const DEPARTMENT_OPTIONS = ['Computer Science', 'Information Technology', 'Electronics', 'Mechanical', 'Civil'];
const SEMESTER_OPTIONS = ['1', '2', '3', '4', '5', '6', '7', '8'];
const ROLE_OPTIONS = [
  { value: 'student', label: 'Student', description: 'Browse campus notices', icon: 'grid' },
  { value: 'faculty', label: 'Faculty', description: 'Post and track notices', icon: 'file' },
  { value: 'admin', label: 'Admin', description: 'Manage the platform', icon: 'shield' },
];
const DEMO_ACCOUNTS = [
  {
    role: 'admin',
    label: 'Admin',
    email: process.env.REACT_APP_DEMO_ADMIN_EMAIL,
    password: process.env.REACT_APP_DEMO_ADMIN_PASSWORD,
  },
  {
    role: 'faculty',
    label: 'Faculty',
    email: process.env.REACT_APP_DEMO_FACULTY_EMAIL,
    password: process.env.REACT_APP_DEMO_FACULTY_PASSWORD,
  },
  {
    role: 'student',
    label: 'Student',
    email: process.env.REACT_APP_DEMO_STUDENT_EMAIL,
    password: process.env.REACT_APP_DEMO_STUDENT_PASSWORD,
  },
];
const SHOW_DEMO_CREDENTIALS = process.env.NODE_ENV === 'development'
  && process.env.REACT_APP_SHOW_DEMO_CREDENTIALS === 'true'
  && DEMO_ACCOUNTS.every(({ email, password }) => email && password);

async function apiRequest(path, token, options = {}) {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function uploadFormData(path, token, body, onProgress, method = 'POST') {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(method, `${API_BASE}${path}`);
    if (token) request.setRequestHeader('Authorization', `Bearer ${token}`);
    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    });
    request.addEventListener('load', () => {
      let payload = {};
      try {
        payload = JSON.parse(request.responseText);
      } catch {
        payload = {};
      }
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(payload.detail || `Request failed (${request.status})`));
        return;
      }
      resolve(payload);
    });
    request.addEventListener('error', () => reject(new Error('Network error while uploading the notice')));
    request.send(body);
  });
}

async function fetchNoticePdf(noticeId, token, download = false) {
  const response = await fetch(`${API_BASE}/notices/${noticeId}/file${download ? '?download=true' : ''}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response.blob();
}

function Icon({ name, size = 19 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  };
  const shapes = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></>,
    spark: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2z" /><path d="m19 14 1 2.5 2.5 1-2.5 1L19 21l-1-2.5-2.5-1 2.5-1z" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="10" cy="7" r="4" /><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    check: <><path d="m5 12 4 4L19 6" /></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18" /></>,
    building: <><path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h.01M15 10h.01M9 14h.01M15 14h.01M10 21v-4h4v4" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11" /><path d="m9 12 2 2 4-4" /></>,
  };
  return <svg {...common}>{shapes[name] || shapes.grid}</svg>;
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('notice-token'));
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [selectedRole, setSelectedRole] = useState('');
  const [page, setPage] = useState('home');
  const [loginBusy, setLoginBusy] = useState(false);
  const [toast, setToast] = useState(null);
  const [mobileNav, setMobileNav] = useState(false);

  const notify = useCallback((message, type = 'success') => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('notice-token');
    setToken(null);
    setUser(null);
    setEmail('');
    setPassword('');
    setSelectedRole('');
    setPage('home');
  }, []);

  useEffect(() => {
    if (!token) return;
    apiRequest('/me', token)
      .then(setUser)
      .catch(() => logout());
  }, [token, logout]);

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!selectedRole) {
      setLoginError('Choose Student, Faculty, or Admin before signing in.');
      return;
    }
    setLoginBusy(true);
    setLoginError('');
    try {
      const data = await apiRequest('/login', null, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      const account = await apiRequest('/me', data.access_token);
      if (account.role !== selectedRole) {
        const roleLabel = ROLE_OPTIONS.find((option) => option.value === account.role)?.label || account.role;
        setLoginError(`This account belongs to the ${roleLabel} workspace. Select ${roleLabel} and try again.`);
        return;
      }
      localStorage.setItem('notice-token', data.access_token);
      setToken(data.access_token);
      setUser(account);
      setPage('home');
    } catch (error) {
      setLoginError(error.message);
    } finally {
      setLoginBusy(false);
    }
  };

  if (!token || !user) {
    return (
      <main className="login-screen">
        <section className="login-story">
          <div className="login-brand"><span className="brand-mark"><Icon name="spark" /></span> Campus<span>Notice</span></div>
          <div className="login-story-copy">
            <span className="eyebrow eyebrow-light">THE CAMPUS, IN THE KNOW</span>
            <h1>Every important update.<br /><em>Right where it belongs.</em></h1>
            <p>One trusted space for campus notices, approvals, and answers — so nobody misses what matters.</p>
            <div className="login-highlights">
              <span><Icon name="check" size={16} /> Verified campus updates</span>
              <span><Icon name="check" size={16} /> Searchable in seconds</span>
              <span><Icon name="check" size={16} /> Notice-grounded help</span>
            </div>
          </div>
          <p className="login-footer">A smarter way to stay connected to campus.</p>
        </section>
        <section className="login-panel">
          <div className="login-form-wrap">
            <span className="eyebrow">WELCOME BACK</span>
            <h2>Sign in to your campus</h2>
            <p className="muted">Choose your workspace, then sign in with its account.</p>
            <form onSubmit={handleLogin} className="login-form">
              <div className="role-picker" role="group" aria-labelledby="role-picker-label">
                <span id="role-picker-label">Choose your workspace</span>
                <div className="role-options">
                  {ROLE_OPTIONS.map((option) => <button key={option.value} type="button" className={`role-option ${selectedRole === option.value ? 'role-option-selected' : ''}`} aria-pressed={selectedRole === option.value} onClick={() => { setSelectedRole(option.value); setLoginError(''); }}>
                    <span className="role-option-icon"><Icon name={option.icon} size={17} /></span>
                    <span><strong>{option.label}</strong><small>{option.description}</small></span>
                  </button>)}
                </div>
              </div>
              <label htmlFor="login-email">College email</label>
              <div className="input-with-icon"><Icon name="mail" size={18} /><input id="login-email" type="email" placeholder="you@college.edu" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
              <label htmlFor="login-password">Password</label>
              <div className="input-with-icon"><Icon name="shield" size={18} /><input id="login-password" type="password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} required /></div>
              {loginError && <p className="form-error" role="alert">{loginError}</p>}
              <button className="button button-primary login-submit" disabled={loginBusy || !selectedRole}>{loginBusy ? 'Signing in…' : <>Sign in{selectedRole ? ` as ${ROLE_OPTIONS.find((option) => option.value === selectedRole)?.label}` : ''} <Icon name="arrow" size={17} /></>}</button>
            </form>
            {SHOW_DEMO_CREDENTIALS && <section className="demo-credentials" aria-labelledby="demo-credentials-title">
              <div className="demo-credentials-heading">
                <strong id="demo-credentials-title">Local demo accounts</strong>
                <span>For development only</span>
              </div>
              <div className="demo-account-list">
                {DEMO_ACCOUNTS.map((account) => <button
                  key={account.role}
                  type="button"
                  className="demo-account"
                  onClick={() => {
                    setSelectedRole(account.role);
                    setEmail(account.email);
                    setPassword(account.password);
                    setLoginError('');
                  }}
                  aria-label={`Fill ${account.label} demo credentials`}
                >
                  <span className="demo-account-role">{account.label}</span>
                  <span className="demo-account-email">{account.email}</span>
                  <span className="demo-account-password">Password: {account.password}</span>
                  <span className="demo-account-action">Fill sign-in form</span>
                </button>)}
              </div>
              <p>These credentials are visible to anyone using this local development app.</p>
            </section>}
            <div className="login-help"><span className="status-dot" /> Secure role-based access</div>
          </div>
          <span className="login-copyright">© CampusNotice · Built for your college community</span>
        </section>
      </main>
    );
  }

  const role = user.role;
  const navigation = role === 'student'
    ? [{ key: 'home', title: 'Notice board', icon: 'grid' }, { key: 'assistant', title: 'Ask the assistant', icon: 'spark' }]
    : role === 'faculty'
      ? [{ key: 'home', title: 'My workspace', icon: 'grid' }, { key: 'my-notices', title: 'My notices', icon: 'file' }, { key: 'create', title: 'Create a notice', icon: 'plus' }]
      : [{ key: 'home', title: 'Overview', icon: 'grid' }, { key: 'notices', title: 'All notices', icon: 'file' }, { key: 'approvals', title: 'Notice approvals', icon: 'check' }, { key: 'users', title: 'People & access', icon: 'users' }];

  const roleTitle = { student: 'Student', faculty: 'Faculty', admin: 'Administrator' }[role] || role;

  return (
    <div className="dashboard-shell">
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><span className="brand-mark"><Icon name="spark" /></span><span>Campus<em>Notice</em></span><button className="mobile-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><Icon name="close" /></button></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <button key={item.key} className={`nav-item ${page === item.key ? 'nav-active' : ''}`} onClick={() => { setPage(item.key); setMobileNav(false); }}>
              <Icon name={item.icon} size={19} /><span>{item.title}</span>{item.key === 'approvals' && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-tip">
          <span className="tip-icon"><Icon name="spark" size={17} /></span>
          <strong>Stay in the loop</strong>
          <p>Campus updates, made easier to find and understand.</p>
        </div>
        <div className="sidebar-user">
          <div className="avatar">{(user.email || 'U').charAt(0).toUpperCase()}</div>
          <div className="sidebar-user-info"><strong>{user.email.split('@')[0]}</strong><span>{roleTitle}</span></div>
          <button className="icon-button logout-button" onClick={logout} title="Sign out" aria-label="Sign out"><Icon name="logout" /></button>
        </div>
      </aside>

      {mobileNav && <button className="nav-backdrop" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}

      <main className="main-panel">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open menu"><Icon name="menu" /></button>
          <div className="breadcrumb"><span>Campus</span><span className="breadcrumb-slash">/</span><strong>{navigation.find((item) => item.key === page)?.title || 'Workspace'}</strong></div>
          <div className="topbar-right"><span className="today-label"><Icon name="calendar" size={16} /> {new Date().toLocaleDateString('en', { weekday: 'short', month: 'short', day: 'numeric' })}</span><div className="topbar-avatar">{(user.email || 'U').charAt(0).toUpperCase()}</div></div>
        </header>
        <div className="page-content">
          {role === 'student' && <StudentWorkspace page={page} setPage={setPage} token={token} user={user} />}
          {role === 'faculty' && <FacultyWorkspace page={page} setPage={setPage} token={token} notify={notify} />}
          {role === 'admin' && <AdminWorkspace page={page} setPage={setPage} token={token} user={user} notify={notify} />}
        </div>
      </main>
      {toast && <div className={`toast ${toast.type === 'error' ? 'toast-error' : ''}`} role={toast.type === 'error' ? 'alert' : 'status'}><span className={toast.type === 'error' ? 'toast-error-icon' : 'toast-check'}><Icon name={toast.type === 'error' ? 'close' : 'check'} size={15} /></span>{toast.message}</div>}
    </div>
  );
}

function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
      {action}
    </div>
  );
}

function StatCard({ icon, label, value, note, tone }) {
  return <article className="stat-card"><span className={`stat-icon ${tone}`}><Icon name={icon} size={20} /></span><div className="stat-copy"><span>{label}</span><strong>{value}</strong><small>{note}</small></div></article>;
}

function NoticeCard({ notice, admin = false, faculty = false, student = false, actionBusy = false, onApprove, onReject, onView, onDelete, onEdit, onPreview, onAskAbout }) {
  const category = notice.category || 'Campus update';
  return (
    <article className="notice-card">
      <div className="notice-card-top"><span className="notice-category"><span className="category-dot" />{category}</span><span className={`status-pill status-${notice.status || 'approved'}`}>{notice.status || 'approved'}</span></div>
      <h3>{notice.title}</h3>
      <p className="notice-description">{notice.description || 'Open this notice for more information.'}</p>
      <div className="notice-meta">
        {notice.department && <span><Icon name="building" size={15} />{notice.department}</span>}
        {notice.semester && <span><Icon name="file" size={15} />Semester {notice.semester}</span>}
        {notice.deadline && <span><Icon name="calendar" size={15} />Due {notice.deadline}</span>}
      </div>
      {faculty && notice.rejection_reason && <p className="notice-rejection-reason"><strong>Admin feedback:</strong> {notice.rejection_reason}</p>}
      {admin && <div className="notice-actions">
        {notice.status === 'pending' && <><button className="button button-approve" disabled={actionBusy} onClick={() => onApprove(notice.id)}><Icon name="check" size={16} /> Approve</button><button className="button button-reject" disabled={actionBusy} onClick={() => onReject(notice.id)}><Icon name="close" size={16} /> Reject</button></>}
        {onView && <button className="button button-soft" onClick={() => onView(notice)}>Details</button>}
        {onDelete && <button className="button button-reject" disabled={actionBusy} onClick={() => onDelete(notice)}>Delete</button>}
      </div>}
      {faculty && ((notice.has_file && onPreview) || (notice.status === 'rejected' && onEdit) || (['pending', 'rejected'].includes(notice.status) && onDelete)) && <div className="notice-actions">
        {notice.has_file && onPreview && <button className="button button-soft" onClick={() => onPreview(notice)}>Preview PDF</button>}
        {notice.status === 'rejected' && onEdit && <button className="button button-soft" onClick={() => onEdit(notice)}>Edit & resubmit</button>}
        {['pending', 'rejected'].includes(notice.status) && onDelete && <button className="button button-reject" disabled={actionBusy} onClick={() => onDelete(notice)}>Delete</button>}
      </div>}
      {student && <div className="notice-actions"><button className="button button-soft" onClick={() => onView(notice)}>View details</button><button className="button button-primary" onClick={() => onAskAbout(notice)}><Icon name="spark" size={15} /> Ask AI</button>{notice.has_file && onPreview && <button className="button button-soft" onClick={() => onPreview(notice)}>Preview PDF</button>}</div>}
    </article>
  );
}

function EmptyState({ icon = 'file', title, description, action }) {
  return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={24} /></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}

function PdfPreviewDialog({ preview, onClose }) {
  if (!preview) return null;
  return (
    <div className="modal-backdrop">
      <section className="pdf-preview-modal" role="dialog" aria-modal="true" aria-labelledby="pdf-preview-title">
        <div className="modal-heading"><div><span className="eyebrow">NOTICE ATTACHMENT</span><h2 id="pdf-preview-title">{preview.filename}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close PDF preview"><Icon name="close" /></button></div>
        <iframe title={`Preview of ${preview.filename}`} src={preview.url} />
        <div className="modal-actions"><a className="button button-primary" href={preview.url} download={preview.filename}>Download PDF</a><button className="button button-soft" onClick={onClose}>Close</button></div>
      </section>
    </div>
  );
}

function StudentNoticeDetails({ notice, onClose, onPreview, onDownload, onAskAbout }) {
  if (!notice) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="detail-modal student-detail-modal" role="dialog" aria-modal="true" aria-labelledby="student-notice-title">
        <div className="modal-heading"><div><span className="eyebrow">APPROVED NOTICE</span><h2 id="student-notice-title">{notice.title}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close notice details"><Icon name="close" /></button></div>
        <p className="notice-detail-description">{notice.description || 'No description provided.'}</p>
        <dl className="detail-list"><dt>Category</dt><dd>{notice.category || 'Not set'}</dd><dt>Department</dt><dd>{notice.department || 'All departments'}</dd><dt>Semester</dt><dd>{notice.semester || 'All semesters'}</dd><dt>Deadline</dt><dd>{notice.deadline || 'No deadline listed'}</dd><dt>Published</dt><dd>{notice.created_at || 'Not recorded'}</dd></dl>
        <div className="modal-actions"><button className="button button-primary" onClick={() => onAskAbout(notice)}><Icon name="spark" size={16} /> Ask AI about this notice</button>{notice.has_file && <><button className="button button-soft" onClick={() => onPreview(notice)}>Preview PDF</button><button className="button button-soft" onClick={() => onDownload(notice)}>Download PDF</button></>}</div>
      </section>
    </div>
  );
}

function StudentWorkspace({ page, setPage, token, user }) {
  const [notices, setNotices] = useState([]);
  const [filters, setFilters] = useState({ search: '', category: '', department: '', semester: '', sort: 'newest' });
  const [prioritizeProfile, setPrioritizeProfile] = useState(Boolean(user.department || user.semester));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [selectedNotice, setSelectedNotice] = useState(null);
  const [assistantNotice, setAssistantNotice] = useState(null);
  const [pdfPreview, setPdfPreview] = useState(null);

  useEffect(() => {
    if (page !== 'home') return undefined;
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
      apiRequest(`/notices?${params.toString()}`, token)
        .then((data) => { if (active) setNotices(data); })
        .catch((requestError) => { if (active) setError(requestError.message); })
        .finally(() => { if (active) setLoading(false); });
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [filters, page, token]);

  useEffect(() => () => {
    if (pdfPreview?.url) URL.revokeObjectURL(pdfPreview.url);
  }, [pdfPreview]);

  const openPdfPreview = async (notice, pageNumber = null) => {
    setError('');
    try {
      const blob = await fetchNoticePdf(notice.id, token);
      const url = URL.createObjectURL(blob);
      setPdfPreview({
        filename: notice.file_name || `${notice.title}.pdf`,
        url: pageNumber ? `${url}#page=${pageNumber}` : url,
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const downloadPdf = async (notice) => {
    setError('');
    try {
      const blob = await fetchNoticePdf(notice.id, token, true);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = notice.file_name || `${notice.title}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const openNotice = async (notice) => {
    setSelectedNotice(notice);
    try {
      setSelectedNotice(await apiRequest(`/notices/${notice.id}`, token));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const askAboutNotice = (notice) => {
    setAssistantNotice(notice);
    setSelectedNotice(null);
    setMessages([]);
    setError('');
    setPage('assistant');
  };

  const chooseAnotherNotice = () => {
    setAssistantNotice(null);
    setMessages([]);
    setPage('home');
  };

  const openSource = async (source) => {
    try {
      const notice = await apiRequest(`/notices/${source.notice_id}`, token);
      if (source.page_number && source.has_file) {
        await openPdfPreview(notice, source.page_number);
      } else {
        setSelectedNotice(notice);
      }
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const askQuestion = async (event) => {
    event.preventDefault();
    if (!question.trim() || !assistantNotice || asking) return;
    const userMessage = { role: 'user', content: question.trim() };
    const history = messages.slice(-8).map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, userMessage]);
    setQuestion('');
    setAsking(true);
    try {
      const response = await apiRequest('/rag', token, {
        method: 'POST',
        body: JSON.stringify({
          question: userMessage.content,
          notice_id: assistantNotice.id,
          history,
        }),
      });
      setMessages((current) => [...current, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
      }]);
    } catch (requestError) {
      setMessages((current) => [...current, {
        role: 'assistant',
        content: requestError.message,
        error: true,
        sources: [],
      }]);
    } finally {
      setAsking(false);
    }
  };

  if (page === 'assistant') {
    return (
      <div className="assistant-page">
        <PageHeading eyebrow="YOUR NOTICE ASSISTANT" title={<>Answers, without<br className="desktop-break" /> the notice hunt.</>} description="Choose a notice from your filtered notice board. The assistant will use only that notice and its PDF." action={<div className="assistant-heading-actions">{assistantNotice && <button className="button button-soft" disabled={asking} onClick={chooseAnotherNotice}>Choose another notice</button>}{messages.length > 0 && <button className="button button-soft" disabled={asking} onClick={() => setMessages([])}>Clear conversation</button>}</div>} />
        <section className="assistant-card">
          <div className="assistant-orb"><Icon name="spark" size={28} /></div>
          <span className="eyebrow">APPROVED NOTICE SEARCH</span><h2>What would you like to know?</h2><p>Try asking about exam schedules, registration deadlines, or campus events.</p>
          {assistantNotice ? <div className="assistant-selected-notice"><Icon name="file" size={16} /><span><strong>Using this notice only</strong><small>{assistantNotice.title}{assistantNotice.file_name ? ` · ${assistantNotice.file_name}` : ''}</small></span></div> : <div className="assistant-select-prompt"><p>Select a notice from the notice board first. You can filter by category, department, semester, or search.</p><button className="button button-soft" onClick={() => setPage('home')}>Browse filtered notices</button></div>}
          {assistantNotice && <div className="prompt-suggestions">{['Summarize this notice', 'What date or deadline is mentioned?', 'Explain the key requirements'].map((prompt) => <button key={prompt} onClick={() => setQuestion(prompt)}>{prompt}<Icon name="arrow" size={14} /></button>)}</div>}
          <form className="assistant-form" onSubmit={askQuestion}><input aria-label="Ask about notices" placeholder={assistantNotice ? 'Ask about this notice…' : 'Choose a notice to start'} value={question} onChange={(event) => setQuestion(event.target.value)} disabled={!assistantNotice || asking} /><button className="button button-primary" disabled={!assistantNotice || asking || !question.trim()}>{asking ? 'Searching…' : <><Icon name="send" size={16} /> Ask</>}</button></form>
          <div className="chat-transcript" aria-live="polite">
            {messages.map((message, index) => <article key={`${index}-${message.role}`} className={`chat-message chat-${message.role}`}>
              <span className="answer-label">{message.role === 'user' ? 'YOU' : <><Icon name="spark" size={15} /> NOTICE ASSISTANT</>}</span>
              <p role={message.error ? 'alert' : undefined}>{message.content}</p>
              {message.sources?.length > 0 && <div className="chat-sources"><strong>Sources</strong>{message.sources.map((source) => <button className="chat-source" key={`${source.notice_id}-${source.page_number || 'notice'}`} onClick={() => openSource(source)}><span>{source.title}{source.page_number ? ` · page ${source.page_number}` : ''}</span><small>{source.excerpt}</small><span className="source-link">Open notice <Icon name="arrow" size={13} /></span></button>)}</div>}
            </article>)}
            {asking && <div className="chat-message chat-assistant" role="status"><span className="answer-label"><Icon name="spark" size={15} /> NOTICE ASSISTANT</span><p>Searching approved notices…</p></div>}
          </div>
          <div className="assistant-disclaimer"><Icon name="shield" size={14} /> Answers are grounded only in the selected approved notice. PDF page sources are shown when available.</div>
        </section>
        {error && <div className="inline-error assistant-error" role="alert">{error}</div>}
        <StudentNoticeDetails notice={selectedNotice} onClose={() => setSelectedNotice(null)} onPreview={openPdfPreview} onDownload={downloadPdf} onAskAbout={askAboutNotice} />
        <PdfPreviewDialog preview={pdfPreview} onClose={() => setPdfPreview(null)} />
      </div>
    );
  }

  const updateFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const clearFilters = () => setFilters({ search: '', category: '', department: '', semester: '', sort: 'newest' });
  const hasFilters = Object.entries(filters).some(([key, value]) => key !== 'sort' && value);
  const displayNotices = prioritizeProfile && (user.department || user.semester)
    ? [...notices].sort((left, right) => {
      const matchesProfile = (notice) => (!user.department || !notice.department
        || notice.department.trim().toLowerCase() === user.department.trim().toLowerCase())
        && (!user.semester || !notice.semester || String(notice.semester) === String(user.semester));
      return Number(matchesProfile(right)) - Number(matchesProfile(left));
    })
    : notices;
  const currentDate = new Date();
  const today = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(currentDate.getDate()).padStart(2, '0')}`;
  const upcomingDeadlines = displayNotices
    .filter((notice) => notice.deadline && notice.deadline >= today)
    .sort((left, right) => left.deadline.localeCompare(right.deadline))
    .slice(0, 3);

  return (
    <div className="student-page">
      <PageHeading eyebrow="YOUR CAMPUS, AT A GLANCE" title={<>Good to see you.<br className="desktop-break" /> Here’s what’s happening.</>} description="The latest approved updates from your college, all in one place." action={<button className="button button-soft" onClick={() => setPage('assistant')}><Icon name="spark" size={17} /> Ask notice assistant</button>} />
      <section className="student-welcome"><div className="welcome-copy"><span className="welcome-kicker"><span className="live-dot" /> CAMPUS NOTICE BOARD</span><h2>Stay a step ahead.</h2><p>Find important updates, deadlines, and announcements from across campus.</p><button className="welcome-link" onClick={() => setPage('assistant')}>Have a question? Ask the notice assistant <Icon name="arrow" size={16} /></button></div><div className="welcome-art" aria-hidden="true"><div className="art-sun" /><div className="art-card art-card-one"><Icon name="calendar" size={17} /><span><b>Important dates</b><small>Never miss a deadline</small></span></div><div className="art-card art-card-two"><Icon name="bell" size={17} /><span><b>Campus updates</b><small>All in one place</small></span></div><div className="art-star">✳</div></div></section>
      {upcomingDeadlines.length > 0 && <section className="notice-section deadline-section"><div className="section-title-row"><div><span className="eyebrow">DON’T MISS A DATE</span><h2>Upcoming deadlines</h2></div><span className="section-caption">Based on published notice dates</span></div><div className="deadline-grid">{upcomingDeadlines.map((notice) => <button className="deadline-card" key={notice.id} onClick={() => openNotice(notice)}><span><Icon name="calendar" size={17} />{new Date(`${notice.deadline}T00:00:00`).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' })}</span><strong>{notice.title}</strong><small>{notice.category || 'Campus update'}</small></button>)}</div></section>}
      <section className="notice-section">
        <div className="section-title-row"><div><span className="eyebrow">FRESH FROM CAMPUS</span><h2>Notice board <span className="count-badge">{notices.length}</span></h2></div><span className="section-caption">Approved notices for students</span></div>
        <div className="filter-toolbar">
          <label className="search-field"><Icon name="search" size={18} /><input aria-label="Search notices" placeholder="Search notices…" value={filters.search} onChange={(event) => updateFilter('search', event.target.value)} />{filters.search && <button onClick={() => updateFilter('search', '')} aria-label="Clear search"><Icon name="close" size={16} /></button>}</label>
          <select aria-label="Filter by category" value={filters.category} onChange={(event) => updateFilter('category', event.target.value)}><option value="">All categories</option>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
          <select aria-label="Filter by department" value={filters.department} onChange={(event) => updateFilter('department', event.target.value)}><option value="">All departments</option>{DEPARTMENT_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
          <select aria-label="Filter by semester" value={filters.semester} onChange={(event) => updateFilter('semester', event.target.value)}><option value="">All semesters</option>{SEMESTER_OPTIONS.map((item) => <option key={item} value={item}>Semester {item}</option>)}</select>
          <select aria-label="Sort notices" value={filters.sort} onChange={(event) => updateFilter('sort', event.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select>
          {(user.department || user.semester) && <label className="profile-priority"><input type="checkbox" checked={prioritizeProfile} onChange={(event) => setPrioritizeProfile(event.target.checked)} /> Prioritize notices for my profile</label>}
          {hasFilters && <button className="clear-filters" onClick={clearFilters}>Clear filters</button>}
        </div>
        {error && <div className="inline-error" role="alert">{error}</div>}
        {loading ? <div className="notice-grid">{[1, 2, 3].map((item) => <div key={item} className="skeleton-card" />)}</div>
          : displayNotices.length ? <div className="notice-grid">{displayNotices.map((notice) => <NoticeCard key={notice.id} notice={notice} student onView={openNotice} onPreview={openPdfPreview} onAskAbout={askAboutNotice} />)}</div>
            : <EmptyState icon={hasFilters ? 'search' : 'file'} title={hasFilters ? 'No matching notices' : 'It’s quiet for now'} description={hasFilters ? 'Try adjusting your search or filters to find another notice.' : 'Approved campus announcements will appear here as soon as they’re published.'} action={hasFilters && <button className="text-button" onClick={clearFilters}>Clear filters</button>} />}
      </section>
      <StudentNoticeDetails notice={selectedNotice} onClose={() => setSelectedNotice(null)} onPreview={openPdfPreview} onDownload={downloadPdf} onAskAbout={askAboutNotice} />
      <PdfPreviewDialog preview={pdfPreview} onClose={() => setPdfPreview(null)} />
    </div>
  );
}

function FacultyWorkspace({ page, setPage, token, notify }) {
  const [noticeForm, setNoticeForm] = useState(EMPTY_NOTICE);
  const [editingNotice, setEditingNotice] = useState(null);
  const [selectedPdf, setSelectedPdf] = useState(null);
  const [selectedPdfUrl, setSelectedPdfUrl] = useState('');
  const [pdfPreview, setPdfPreview] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [formError, setFormError] = useState('');
  const [fileError, setFileError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState('');
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [notices, setNotices] = useState([]);
  const [noticeError, setNoticeError] = useState('');
  const [noticesLoading, setNoticesLoading] = useState(true);
  const [filters, setFilters] = useState({ search: '', status: '', category: '' });
  const [busyNoticeId, setBusyNoticeId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (page !== 'home') return undefined;
    let active = true;
    setDashboardLoading(true);
    setDashboardError('');
    apiRequest('/faculty/dashboard', token)
      .then((data) => { if (active) setDashboard(data); })
      .catch((error) => { if (active) setDashboardError(error.message); })
      .finally(() => { if (active) setDashboardLoading(false); });
    return () => { active = false; };
  }, [page, refreshKey, token]);

  useEffect(() => {
    if (page !== 'my-notices') return undefined;
    let active = true;
    const timer = window.setTimeout(() => {
      setNoticesLoading(true);
      setNoticeError('');
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
      apiRequest(`/notices?${params.toString()}`, token)
        .then((data) => { if (active) setNotices(data); })
        .catch((error) => { if (active) setNoticeError(error.message); })
        .finally(() => { if (active) setNoticesLoading(false); });
    }, 160);
    return () => { active = false; window.clearTimeout(timer); };
  }, [filters, page, refreshKey, token]);

  useEffect(() => {
    if (!selectedPdf) {
      setSelectedPdfUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(selectedPdf);
    setSelectedPdfUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedPdf]);

  useEffect(() => {
    if (page !== 'create' && editingNotice) {
      setEditingNotice(null);
      setNoticeForm(EMPTY_NOTICE);
      setSelectedPdf(null);
      setFileError('');
      setFormError('');
    }
  }, [editingNotice, page]);

  useEffect(() => () => {
    if (pdfPreview) URL.revokeObjectURL(pdfPreview.url);
  }, [pdfPreview]);

  const updateForm = (key, value) => setNoticeForm((current) => ({ ...current, [key]: value }));

  const selectPdf = (event) => {
    const file = event.target.files && event.target.files[0];
    setFileError('');
    if (!file) {
      setSelectedPdf(null);
      return;
    }
    if (!file.name.toLowerCase().endsWith('.pdf') || (file.type && !['application/pdf', 'application/octet-stream'].includes(file.type))) {
      setFileError('Choose a PDF file.');
      event.target.value = '';
      setSelectedPdf(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setFileError('The PDF must be 10 MiB or smaller.');
      event.target.value = '';
      setSelectedPdf(null);
      return;
    }
    setSelectedPdf(file);
  };

  const openPdfPreview = async (notice) => {
    try {
      const blob = await fetchNoticePdf(notice.id, token);
      setPdfPreview({
        url: URL.createObjectURL(blob),
        filename: notice.file_name || `${notice.title}.pdf`,
      });
    } catch (error) {
      notify(error.message, 'error');
    }
  };

  const editNotice = (notice) => {
    setNoticeForm({
      title: notice.title || '',
      description: notice.description || '',
      category: notice.category || '',
      department: notice.department || '',
      semester: notice.semester || '',
      deadline: notice.deadline || '',
    });
    setEditingNotice(notice);
    setSelectedPdf(null);
    setFileError('');
    setFormError('');
    setFileInputKey((current) => current + 1);
    setPage('create');
  };

  const submitNotice = async (event) => {
    event.preventDefault();
    if (!noticeForm.title.trim()) {
      setFormError('A notice title is required.');
      return;
    }
    setSubmitting(true);
    setFormError('');
    setUploadProgress(selectedPdf ? 0 : null);
    try {
      if (editingNotice || selectedPdf) {
        const body = new FormData();
        Object.entries(noticeForm).forEach(([key, value]) => body.append(key, value));
        if (selectedPdf) body.append('pdf', selectedPdf);
        const path = editingNotice ? `/notices/${editingNotice.id}/resubmit` : '/notices/upload';
        await uploadFormData(path, token, body, (progress) => {
          if (selectedPdf) setUploadProgress(progress);
        }, editingNotice ? 'PUT' : 'POST');
      } else {
        await apiRequest('/notices', token, {
          method: 'POST',
          body: JSON.stringify(noticeForm),
        });
      }
      setNoticeForm(EMPTY_NOTICE);
      setEditingNotice(null);
      setSelectedPdf(null);
      setFileError('');
      setFileInputKey((current) => current + 1);
      setRefreshKey((current) => current + 1);
      setPage('my-notices');
      notify('Notice submitted for admin review.');
    } catch (error) {
      setFormError(error.message);
      notify(error.message, 'error');
    } finally {
      setSubmitting(false);
      setUploadProgress(null);
    }
  };

  const deleteNotice = async (notice) => {
    if (!window.confirm(`Delete "${notice.title}"? This cannot be undone.`)) return;
    setBusyNoticeId(notice.id);
    try {
      await apiRequest(`/notices/${notice.id}/faculty`, token, { method: 'DELETE' });
      setRefreshKey((current) => current + 1);
      notify('Notice deleted.');
    } catch (error) {
      notify(error.message, 'error');
    } finally {
      setBusyNoticeId(null);
    }
  };

  if (page === 'create') {
    return (
      <div className="faculty-create-page">
        <PageHeading
          eyebrow={editingNotice ? 'UPDATE YOUR SUBMISSION' : 'SHARE WITH YOUR CAMPUS'}
          title={editingNotice ? 'Edit and resubmit' : 'Create a notice'}
          description="Add a clear announcement. An administrator will review it before students can see it."
          action={<button className="button button-soft" onClick={() => setPage(editingNotice ? 'my-notices' : 'home')}>Cancel</button>}
        />
        <div className="form-layout">
          <form className="notice-form-card" onSubmit={submitNotice}>
            <div className="form-section-heading"><span className="form-section-icon"><Icon name="file" /></span><div><h2>Notice details</h2><p>Fields marked with * are required. PDF attachments are optional (10 MiB max).</p></div></div>
            <label htmlFor="notice-title">Notice title <span>*</span></label>
            <input id="notice-title" className="form-control" maxLength="255" placeholder="e.g. Mid-semester examination schedule" value={noticeForm.title} onChange={(event) => updateForm('title', event.target.value)} required />
            <label htmlFor="notice-description">Description</label>
            <textarea id="notice-description" className="form-control" rows="5" maxLength="10000" placeholder="Share the key details students need to know…" value={noticeForm.description} onChange={(event) => updateForm('description', event.target.value)} />
            <div className="form-row">
              <div><label htmlFor="notice-category">Category</label><select id="notice-category" className="form-control" value={noticeForm.category} onChange={(event) => updateForm('category', event.target.value)}><option value="">Choose category</option>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select></div>
              <div><label htmlFor="notice-department">Department</label><select id="notice-department" className="form-control" value={noticeForm.department} onChange={(event) => updateForm('department', event.target.value)}><option value="">Choose department</option>{DEPARTMENT_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select></div>
            </div>
            <div className="form-row">
              <div><label htmlFor="notice-semester">Semester <span className="label-optional">OPTIONAL</span></label><select id="notice-semester" className="form-control" value={noticeForm.semester} onChange={(event) => updateForm('semester', event.target.value)}><option value="">All semesters</option>{SEMESTER_OPTIONS.map((item) => <option key={item} value={item}>Semester {item}</option>)}</select></div>
              <div><label htmlFor="notice-deadline">Deadline <span className="label-optional">OPTIONAL</span></label><input id="notice-deadline" type="date" className="form-control" value={noticeForm.deadline || ''} onChange={(event) => updateForm('deadline', event.target.value)} /></div>
            </div>
            <label htmlFor="notice-pdf">Attach a PDF <span className="label-optional">OPTIONAL</span></label>
            <input key={fileInputKey} id="notice-pdf" className="form-control" type="file" accept="application/pdf,.pdf" onChange={selectPdf} />
            {editingNotice && <p className="file-help">Leave the attachment empty to keep the current PDF.</p>}
            {fileError && <p className="form-error" role="alert">{fileError}</p>}
            {selectedPdf && selectedPdfUrl && <div className="selected-pdf-preview"><div><strong>{selectedPdf.name}</strong><button className="text-button" type="button" onClick={() => { setSelectedPdf(null); setFileInputKey((current) => current + 1); }}>Remove PDF</button></div><iframe title="Selected PDF preview" src={selectedPdfUrl} /></div>}
            {uploadProgress !== null && <div className="upload-progress" role="status"><span>Uploading PDF… {uploadProgress}%</span><progress max="100" value={uploadProgress} /></div>}
            {formError && <div className="inline-error" role="alert">{formError}</div>}
            <div className="submit-notice-row"><span><Icon name="shield" size={15} /> Submitted notices need admin approval.</span><button className="button button-primary" disabled={submitting || !noticeForm.title.trim() || Boolean(fileError)}>{submitting ? uploadProgress !== null ? `Uploading ${uploadProgress}%…` : 'Submitting…' : editingNotice ? 'Resubmit for review' : 'Submit for review'}</button></div>
          </form>
          <aside className="form-aside"><span className="aside-spark"><Icon name="spark" size={20} /></span><h3>Make it easy to scan.</h3><p>A helpful title and a few clear details make it easier for students to find the information that matters.</p><div className="review-steps"><div><span>01</span><p><b>You submit</b><small>Your notice enters the review queue.</small></p></div><div><span>02</span><p><b>Admin reviews</b><small>The campus admin checks the details.</small></p></div><div><span>03</span><p><b>Students see it</b><small>Approved notices appear on the board.</small></p></div></div></aside>
        </div>
        <PdfPreviewDialog preview={pdfPreview} onClose={() => setPdfPreview(null)} />
      </div>
    );
  }

  if (page === 'my-notices') {
    const updateFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
    const clearFilters = () => setFilters({ search: '', status: '', category: '' });
    const hasFilters = Object.values(filters).some(Boolean);
    return (
      <>
      <div className="faculty-page">
        <PageHeading eyebrow="YOUR SUBMISSIONS" title="My notices" description="Track review status, respond to feedback, and manage your submissions." action={<button className="button button-primary" onClick={() => { setEditingNotice(null); setNoticeForm(EMPTY_NOTICE); setPage('create'); }}><Icon name="plus" size={17} /> Create a notice</button>} />
        <div className="filter-toolbar faculty-filter-toolbar">
          <label className="search-field"><Icon name="search" size={18} /><input aria-label="Search my notices" placeholder="Search my notices…" value={filters.search} onChange={(event) => updateFilter('search', event.target.value)} /></label>
          <select aria-label="Filter my notices by status" value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
          <select aria-label="Filter my notices by category" value={filters.category} onChange={(event) => updateFilter('category', event.target.value)}><option value="">All categories</option>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
          {hasFilters && <button className="clear-filters" onClick={clearFilters}>Clear filters</button>}
        </div>
        {noticeError && <div className="inline-error" role="alert">{noticeError}</div>}
        {noticesLoading ? <div className="notice-grid">{[1, 2, 3].map((item) => <div key={item} className="skeleton-card" />)}</div>
          : notices.length ? <div className="notice-grid">{notices.map((notice) => <NoticeCard key={notice.id} notice={notice} faculty actionBusy={busyNoticeId === notice.id} onPreview={openPdfPreview} onEdit={editNotice} onDelete={deleteNotice} />)}</div>
            : <EmptyState icon={hasFilters ? 'search' : 'file'} title={hasFilters ? 'No matching notices' : 'No submissions yet'} description={hasFilters ? 'Try another search or status filter.' : 'Create your first notice and track its review here.'} action={<button className="text-button" onClick={() => { setEditingNotice(null); setNoticeForm(EMPTY_NOTICE); setPage('create'); }}>Create a notice <Icon name="arrow" size={15} /></button>} />}
      </div>
      <PdfPreviewDialog preview={pdfPreview} onClose={() => setPdfPreview(null)} />
      </>
    );
  }

  return (
    <div className="faculty-page">
      <PageHeading eyebrow="FACULTY WORKSPACE" title={<>Good morning.<br className="desktop-break" /> Let’s keep students informed.</>} description="Share timely campus information with the people who need it." action={<button className="button button-primary" onClick={() => { setEditingNotice(null); setNoticeForm(EMPTY_NOTICE); setPage('create'); }}><Icon name="plus" size={17} /> Create a notice</button>} />
      {dashboardError && <div className="inline-error" role="alert">{dashboardError}</div>}
      {dashboardLoading ? <div className="notice-grid">{[1, 2, 3, 4].map((item) => <div key={item} className="skeleton-card" />)}</div> : <>
        <div className="stats-grid faculty-stats-grid">
          <StatCard icon="file" label="Total notices" value={dashboard?.total || 0} note="Your submissions" tone="stat-indigo" />
          <StatCard icon="check" label="Approved" value={dashboard?.approved || 0} note="Published for students" tone="stat-green" />
          <StatCard icon="calendar" label="Pending review" value={dashboard?.pending || 0} note="Awaiting admin review" tone="stat-amber" />
          <StatCard icon="close" label="Rejected" value={dashboard?.rejected || 0} note="Feedback available" tone="stat-rose" />
        </div>
        <section className="notice-section faculty-recent-section">
          <div className="section-title-row"><div><span className="eyebrow">LATEST ACTIVITY</span><h2>Recently uploaded</h2></div><button className="text-button" onClick={() => setPage('my-notices')}>View all <Icon name="arrow" size={15} /></button></div>
          {dashboard?.recent_notices?.length ? <div className="notice-grid">{dashboard.recent_notices.map((notice) => <NoticeCard key={notice.id} notice={notice} faculty onPreview={openPdfPreview} />)}</div>
            : <EmptyState icon="file" title="No submissions yet" description="Your latest notices and their approval status will appear here." action={<button className="text-button" onClick={() => setPage('create')}>Create a notice <Icon name="arrow" size={15} /></button>} />}
        </section>
      </>}
      <PdfPreviewDialog preview={pdfPreview} onClose={() => setPdfPreview(null)} />
    </div>
  );
}

function AdminWorkspace({ page, setPage, token, user, notify }) {
  const [data, setData] = useState({ users: [], notices: [], dashboard: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', role: 'student', department: '', semester: '' });
  const [editingUserId, setEditingUserId] = useState(null);
  const [savingUser, setSavingUser] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [userRole, setUserRole] = useState('');
  const [userStatus, setUserStatus] = useState('');
  const [noticeSearch, setNoticeSearch] = useState('');
  const [noticeStatus, setNoticeStatus] = useState('');
  const [noticeCategory, setNoticeCategory] = useState('');
  const [noticeDepartment, setNoticeDepartment] = useState('');
  const [selectedNotice, setSelectedNotice] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [noticeEditForm, setNoticeEditForm] = useState(null);
  const [rejectingNoticeId, setRejectingNoticeId] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [actionBusy, setActionBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [users, notices, dashboard] = await Promise.all([
        apiRequest('/users', token),
        apiRequest('/notices', token),
        apiRequest('/admin/dashboard', token),
      ]);
      setData({ users, notices, dashboard });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

  const resetUserForm = () => {
    setEditingUserId(null);
    setUserForm({ name: '', email: '', password: '', role: 'student', department: '', semester: '' });
  };

  const saveUser = async (event) => {
    event.preventDefault();
    setSavingUser(true);
    setError('');
    const payload = { ...userForm };
    if (editingUserId && !payload.password) delete payload.password;
    try {
      await apiRequest(editingUserId ? `/users/${editingUserId}` : '/users', token, {
        method: editingUserId ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      });
      notify(editingUserId ? 'Account updated.' : 'Account created.');
      resetUserForm();
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingUser(false);
    }
  };

  const editUser = (account) => {
    setEditingUserId(account.id);
    setUserForm({
      name: account.name || '',
      email: account.email,
      password: '',
      role: account.role,
      department: account.department || '',
      semester: account.semester || '',
    });
    setSelectedUser(null);
  };

  const toggleUser = async (account) => {
    const action = account.active ? 'deactivate' : 'activate';
    if (account.active && !window.confirm(`Deactivate ${account.email}? They will lose access immediately.`)) return;
    setError('');
    try {
      await apiRequest(`/users/${account.id}/activate?active=${!account.active}`, token, { method: 'PUT' });
      notify(`Account ${action}d.`);
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const reviewNotice = async (id, status, reason = '') => {
    if (status === 'rejected') {
      setRejectingNoticeId(id);
      setRejectionReason('');
      return;
    }
    if (!window.confirm('Approve and publish this notice to students?')) return;
    setActionBusy(true);
    setError('');
    try {
      await apiRequest(`/notices/${id}/status`, token, {
        method: 'PUT',
        body: JSON.stringify({ status, rejection_reason: reason }),
      });
      notify('Notice approved and published.');
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setActionBusy(false);
    }
  };

  const submitRejection = async (event) => {
    event.preventDefault();
    if (!rejectionReason.trim() || !rejectingNoticeId) return;
    setActionBusy(true);
    setError('');
    try {
      await apiRequest(`/notices/${rejectingNoticeId}/status`, token, {
        method: 'PUT',
        body: JSON.stringify({ status: 'rejected', rejection_reason: rejectionReason.trim() }),
      });
      setRejectingNoticeId(null);
      setRejectionReason('');
      notify('Notice rejected with feedback for the faculty member.');
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setActionBusy(false);
    }
  };

  const removeNotice = async (notice) => {
    if (!window.confirm(`Delete “${notice.title}”? This cannot be undone.`)) return;
    setActionBusy(true);
    setError('');
    try {
      await apiRequest(`/notices/${notice.id}`, token, { method: 'DELETE' });
      setSelectedNotice(null);
      notify('Notice deleted.');
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setActionBusy(false);
    }
  };

  const saveNotice = async (event) => {
    event.preventDefault();
    if (!selectedNotice) return;
    setActionBusy(true);
    setError('');
    try {
      const updated = await apiRequest(`/notices/${selectedNotice.id}`, token, {
        method: 'PUT',
        body: JSON.stringify(noticeEditForm),
      });
      setSelectedNotice(updated);
      setNoticeEditForm(null);
      notify('Notice details updated.');
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setActionBusy(false);
    }
  };

  const dashboard = data.dashboard || { notices: {}, recent_activity: [] };
  const noticeCounts = dashboard.notices || {};
  const visibleUsers = data.users.filter((account) => {
    const query = userSearch.trim().toLowerCase();
    const matchesSearch = !query || [account.name, account.email, account.department]
      .some((value) => (value || '').toLowerCase().includes(query));
    const matchesRole = !userRole || account.role === userRole;
    const matchesStatus = !userStatus || String(Boolean(account.active)) === userStatus;
    return matchesSearch && matchesRole && matchesStatus;
  });
  const visibleNotices = data.notices.filter((notice) => {
    const query = noticeSearch.trim().toLowerCase();
    const matchesSearch = !query || [notice.title, notice.description, notice.department, notice.category]
      .some((value) => (value || '').toLowerCase().includes(query));
    return matchesSearch
      && (!noticeStatus || notice.status === noticeStatus)
      && (!noticeCategory || notice.category === noticeCategory)
      && (!noticeDepartment || notice.department === noticeDepartment);
  });
  const pendingNotices = data.notices.filter((notice) => notice.status === 'pending');

  if (page === 'users') {
    return (
      <div className="admin-users-page">
        <PageHeading eyebrow="CAMPUS DIRECTORY" title="People & access" description="Search accounts, review their campus details, and manage role-based access." action={<button className="button button-soft" onClick={refresh}>Refresh</button>} />
        {error && <div className="inline-error" role="alert">{error}</div>}
        <div className="people-layout">
          <section className="directory-card">
            <div className="section-title-row"><div><span className="eyebrow">ACCOUNT DIRECTORY</span><h2>Campus accounts <span className="count-badge">{loading ? '—' : visibleUsers.length}</span></h2></div></div>
            <div className="filter-toolbar admin-filter-toolbar">
              <label className="search-field"><Icon name="search" size={17} /><input aria-label="Search users" placeholder="Search name, email, department…" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} /></label>
              <select aria-label="Filter users by role" value={userRole} onChange={(event) => setUserRole(event.target.value)}><option value="">All roles</option><option value="student">Students</option><option value="faculty">Faculty</option><option value="admin">Admins</option></select>
              <select aria-label="Filter users by status" value={userStatus} onChange={(event) => setUserStatus(event.target.value)}><option value="">All statuses</option><option value="true">Active</option><option value="false">Inactive</option></select>
            </div>
            {loading ? <div className="loading-row">Loading accounts…</div> : <div className="table-scroll"><table className="data-table"><thead><tr><th>ACCOUNT</th><th>DEPARTMENT</th><th>ROLE</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>{visibleUsers.map((account) => <tr key={account.id}><td><span className="table-avatar">{(account.name || account.email).charAt(0).toUpperCase()}</span><span className="account-cell"><strong>{account.name || 'Name not provided'}</strong><small>{account.email}</small></span></td><td>{account.department || '—'}</td><td><span className={`role-tag role-${account.role}`}>{account.role}</span></td><td><span className={`status-pill ${account.active ? 'status-approved' : 'status-rejected'}`}>{account.active ? 'Active' : 'Inactive'}</span></td><td><div className="table-actions"><button className="table-action" onClick={() => setSelectedUser(account)}>Details</button><button className="table-action" onClick={() => editUser(account)}>Edit</button><button className={`table-action ${account.active ? 'deactivate-action' : ''}`} disabled={account.id === user.id} onClick={() => toggleUser(account)}>{account.active ? 'Deactivate' : 'Activate'}</button></div></td></tr>)}</tbody></table>{!visibleUsers.length && <EmptyState title="No matching accounts" description="Try changing the search or filters." />}</div>}
          </section>
          <form className="create-user-card" onSubmit={saveUser}>
            <span className="aside-spark"><Icon name="users" size={19} /></span>
            <h2>{editingUserId ? 'Edit campus account' : 'Add a campus account'}</h2>
            <p>{editingUserId ? 'Update profile details and access role.' : 'Create a student, faculty, or administrator login.'}</p>
            <label htmlFor="account-name">Full name</label><input id="account-name" className="form-control" maxLength="120" value={userForm.name} onChange={(event) => setUserForm({ ...userForm, name: event.target.value })} />
            <label htmlFor="account-email">College email</label><input id="account-email" className="form-control" type="email" placeholder="name@college.edu" value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} required />
            <label htmlFor="account-department">Department</label><input id="account-department" className="form-control" maxLength="120" value={userForm.department} onChange={(event) => setUserForm({ ...userForm, department: event.target.value })} />
            <label htmlFor="account-semester">Semester</label><input id="account-semester" className="form-control" maxLength="20" value={userForm.semester} onChange={(event) => setUserForm({ ...userForm, semester: event.target.value })} />
            <label htmlFor="account-password">{editingUserId ? 'New password (optional)' : 'Temporary password'}</label><input id="account-password" className="form-control" type="password" minLength="8" placeholder={editingUserId ? 'Leave blank to keep current password' : 'At least 8 characters'} value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} required={!editingUserId} />
            <label htmlFor="account-role">Role</label><select id="account-role" className="form-control" value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Admin</option></select>
            <div className="user-form-actions"><button className="button button-primary full-button" disabled={savingUser}>{savingUser ? 'Saving…' : <><Icon name={editingUserId ? 'check' : 'plus'} size={17} /> {editingUserId ? 'Save changes' : 'Create account'}</>}</button>{editingUserId && <button className="button button-soft full-button" type="button" onClick={resetUserForm}>Cancel editing</button>}</div>
          </form>
        </div>
        {selectedUser && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedUser(null); }}><section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="user-detail-title"><div className="modal-heading"><div><span className="eyebrow">CAMPUS ACCOUNT</span><h2 id="user-detail-title">{selectedUser.name || selectedUser.email}</h2></div><button className="icon-button" onClick={() => setSelectedUser(null)} aria-label="Close account details"><Icon name="close" /></button></div><dl className="detail-list"><dt>Email</dt><dd>{selectedUser.email}</dd><dt>Role</dt><dd>{selectedUser.role}</dd><dt>Status</dt><dd>{selectedUser.active ? 'Active' : 'Inactive'}</dd><dt>Department</dt><dd>{selectedUser.department || 'Not set'}</dd><dt>Semester</dt><dd>{selectedUser.semester || 'Not set'}</dd><dt>Account ID</dt><dd>{selectedUser.id}</dd></dl><button className="button button-primary" onClick={() => editUser(selectedUser)}>Edit account</button></section></div>}
      </div>
    );
  }

  if (page === 'notices') {
    return (
      <div className="admin-notices-page">
        <PageHeading eyebrow="CAMPUS NOTICE ARCHIVE" title="All notices" description="Search notices across every review status, inspect metadata, and manage published content." action={<button className="button button-soft" onClick={refresh}>Refresh notices</button>} />
        {error && <div className="inline-error" role="alert">{error}</div>}
        <div className="filter-toolbar admin-filter-toolbar">
          <label className="search-field"><Icon name="search" size={17} /><input aria-label="Search notices" placeholder="Search title, description, or department…" value={noticeSearch} onChange={(event) => setNoticeSearch(event.target.value)} /></label>
          <select aria-label="Filter notices by status" value={noticeStatus} onChange={(event) => setNoticeStatus(event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
          <select aria-label="Filter notices by category" value={noticeCategory} onChange={(event) => setNoticeCategory(event.target.value)}><option value="">All categories</option>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
          <select aria-label="Filter notices by department" value={noticeDepartment} onChange={(event) => setNoticeDepartment(event.target.value)}><option value="">All departments</option>{DEPARTMENT_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
        </div>
        {loading ? <div className="notice-grid">{[1, 2, 3].map((item) => <div key={item} className="skeleton-card" />)}</div> : visibleNotices.length ? <div className="notice-grid">{visibleNotices.map((notice) => <NoticeCard key={notice.id} notice={notice} admin actionBusy={actionBusy} onApprove={(id) => reviewNotice(id, 'approved')} onReject={(id) => reviewNotice(id, 'rejected')} onView={setSelectedNotice} onDelete={removeNotice} />)}</div> : <EmptyState title="No matching notices" description="Try another search or status filter." />}
        {selectedNotice && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) { setSelectedNotice(null); setNoticeEditForm(null); } }}><section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="notice-detail-title">
          <div className="modal-heading"><div><span className="eyebrow">NOTICE DETAILS</span><h2 id="notice-detail-title">{noticeEditForm ? 'Edit notice details' : selectedNotice.title}</h2></div><button className="icon-button" onClick={() => { setSelectedNotice(null); setNoticeEditForm(null); }} aria-label="Close notice details"><Icon name="close" /></button></div>
          {noticeEditForm ? <form className="notice-edit-form" onSubmit={saveNotice}>
            <label htmlFor="edit-notice-title">Title</label><input id="edit-notice-title" className="form-control" maxLength="255" required value={noticeEditForm.title} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, title: event.target.value })} />
            <label htmlFor="edit-notice-description">Description</label><textarea id="edit-notice-description" className="form-control" rows="4" maxLength="10000" value={noticeEditForm.description} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, description: event.target.value })} />
            <label htmlFor="edit-notice-category">Category</label><input id="edit-notice-category" className="form-control" maxLength="100" value={noticeEditForm.category} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, category: event.target.value })} />
            <label htmlFor="edit-notice-department">Department</label><input id="edit-notice-department" className="form-control" maxLength="120" value={noticeEditForm.department} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, department: event.target.value })} />
            <label htmlFor="edit-notice-semester">Semester</label><input id="edit-notice-semester" className="form-control" maxLength="20" value={noticeEditForm.semester} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, semester: event.target.value })} />
            <label htmlFor="edit-notice-deadline">Deadline</label><input id="edit-notice-deadline" className="form-control" type="date" value={noticeEditForm.deadline} onChange={(event) => setNoticeEditForm({ ...noticeEditForm, deadline: event.target.value })} />
            <div className="modal-actions"><button className="button button-primary" disabled={actionBusy}>{actionBusy ? 'Saving…' : 'Save metadata'}</button><button className="button button-soft" type="button" onClick={() => setNoticeEditForm(null)}>Cancel</button></div>
          </form> : <>
            <span className={`status-pill status-${selectedNotice.status}`}>{selectedNotice.status}</span>
            <p className="notice-detail-description">{selectedNotice.description || 'No description provided.'}</p>
            <dl className="detail-list"><dt>Category</dt><dd>{selectedNotice.category || 'Not set'}</dd><dt>Department</dt><dd>{selectedNotice.department || 'Not set'}</dd><dt>Semester</dt><dd>{selectedNotice.semester || 'All semesters'}</dd><dt>Deadline</dt><dd>{selectedNotice.deadline || 'Not set'}</dd><dt>Submitted by</dt><dd>{data.users.find((account) => account.id === selectedNotice.uploaded_by)?.email || `Account ${selectedNotice.uploaded_by || 'unknown'}`}</dd><dt>Created</dt><dd>{selectedNotice.created_at || 'Not recorded'}</dd>{selectedNotice.rejection_reason && <><dt>Rejection reason</dt><dd>{selectedNotice.rejection_reason}</dd></>}</dl>
            <div className="modal-actions"><button className="button button-primary" onClick={() => setNoticeEditForm({ title: selectedNotice.title || '', description: selectedNotice.description || '', category: selectedNotice.category || '', department: selectedNotice.department || '', semester: selectedNotice.semester || '', deadline: (selectedNotice.deadline || '').slice(0, 10) })}>Edit metadata</button><button className="button button-reject" disabled={actionBusy} onClick={() => removeNotice(selectedNotice)}>Delete notice</button></div>
          </>}
        </section></div>}
        {rejectingNoticeId && <div className="modal-backdrop"><form className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="rejection-title" onSubmit={submitRejection}><div className="modal-heading"><div><span className="eyebrow">NOTICE REVIEW</span><h2 id="rejection-title">Give the faculty member feedback</h2></div><button className="icon-button" type="button" onClick={() => setRejectingNoticeId(null)} aria-label="Close rejection form"><Icon name="close" /></button></div><label htmlFor="rejection-reason">Reason for rejection</label><textarea id="rejection-reason" className="form-control" rows="4" maxLength="1000" required value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} /><div className="modal-actions"><button className="button button-reject" disabled={actionBusy || !rejectionReason.trim()}>{actionBusy ? 'Submitting…' : 'Reject notice'}</button><button className="button button-soft" type="button" onClick={() => setRejectingNoticeId(null)}>Cancel</button></div></form></div>}
      </div>
    );
  }

  if (page === 'approvals') {
    return (
      <div className="admin-approvals-page">
        <PageHeading eyebrow="CONTENT MODERATION" title="Notice approvals" description="Review faculty submissions and provide clear feedback before they reach students." action={<button className="button button-soft" onClick={refresh}>Refresh queue</button>} />
        {error && <div className="inline-error" role="alert">{error}</div>}
        <div className="queue-summary"><span className="queue-number">{loading ? '—' : pendingNotices.length}</span><div><strong>Waiting for review</strong><p>Approved notices become visible to students immediately.</p></div><span className="queue-icon"><Icon name="check" size={22} /></span></div>
        {loading ? <div className="notice-grid">{[1, 2].map((item) => <div key={item} className="skeleton-card" />)}</div> : pendingNotices.length ? <div className="notice-grid">{pendingNotices.map((notice) => <NoticeCard key={notice.id} notice={notice} admin actionBusy={actionBusy} onApprove={(id) => reviewNotice(id, 'approved')} onReject={(id) => reviewNotice(id, 'rejected')} onView={setSelectedNotice} onDelete={removeNotice} />)}</div> : <EmptyState icon="check" title="You’re all caught up" description="There are no notices waiting for review right now." />}
        {selectedNotice && <div className="modal-backdrop"><section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="approval-detail-title"><div className="modal-heading"><div><span className="eyebrow">NOTICE DETAILS</span><h2 id="approval-detail-title">{selectedNotice.title}</h2></div><button className="icon-button" onClick={() => setSelectedNotice(null)} aria-label="Close notice details"><Icon name="close" /></button></div><p className="notice-detail-description">{selectedNotice.description || 'No description provided.'}</p><dl className="detail-list"><dt>Category</dt><dd>{selectedNotice.category || 'Not set'}</dd><dt>Department</dt><dd>{selectedNotice.department || 'Not set'}</dd><dt>Semester</dt><dd>{selectedNotice.semester || 'All semesters'}</dd><dt>Submitted by</dt><dd>{data.users.find((account) => account.id === selectedNotice.uploaded_by)?.email || `Account ${selectedNotice.uploaded_by || 'unknown'}`}</dd><dt>Submitted</dt><dd>{selectedNotice.created_at || 'Not recorded'}</dd></dl></section></div>}
        {rejectingNoticeId && <div className="modal-backdrop"><form className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="rejection-title" onSubmit={submitRejection}><div className="modal-heading"><div><span className="eyebrow">NOTICE REVIEW</span><h2 id="rejection-title">Give the faculty member feedback</h2></div><button className="icon-button" type="button" onClick={() => setRejectingNoticeId(null)} aria-label="Close rejection form"><Icon name="close" /></button></div><label htmlFor="rejection-reason">Reason for rejection</label><textarea id="rejection-reason" className="form-control" rows="4" maxLength="1000" required value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} /><div className="modal-actions"><button className="button button-reject" disabled={actionBusy || !rejectionReason.trim()}>{actionBusy ? 'Submitting…' : 'Reject notice'}</button><button className="button button-soft" type="button" onClick={() => setRejectingNoticeId(null)}>Cancel</button></div></form></div>}
      </div>
    );
  }

  const summaryStats = [
    { icon: 'users', label: 'Students', value: dashboard.students, note: 'Registered accounts', tone: 'stat-indigo' },
    { icon: 'building', label: 'Faculty', value: dashboard.faculty, note: 'Campus contributors', tone: 'stat-cyan' },
    { icon: 'file', label: 'Total notices', value: noticeCounts.total, note: 'Across all statuses', tone: 'stat-indigo' },
    { icon: 'check', label: 'Pending', value: noticeCounts.pending, note: 'Awaiting review', tone: 'stat-amber' },
    { icon: 'check', label: 'Approved', value: noticeCounts.approved, note: 'Visible to students', tone: 'stat-green' },
    { icon: 'close', label: 'Rejected', value: noticeCounts.rejected, note: 'Feedback provided', tone: 'stat-cyan' },
  ];

  return (
    <div className="admin-page">
      <PageHeading eyebrow="CAMPUS OVERVIEW" title="A clear view of campus." description="Monitor accounts, notice approvals, and recent platform activity." action={<button className="button button-soft" onClick={refresh}>Refresh overview</button>} />
      {error && <div className="inline-error" role="alert">{error}</div>}
      <section className="admin-banner"><div><span className="welcome-kicker"><span className="live-dot" /> ADMIN OVERVIEW</span><h2>Good work keeps everyone informed.</h2><p>Review announcements and keep campus accounts up to date.</p></div><div className="admin-banner-art"><span><Icon name="shield" size={31} /></span></div></section>
      <div className="stats-grid">{summaryStats.map((item) => <StatCard key={item.label} {...item} value={loading ? '—' : (item.value ?? 0)} />)}</div>
      <div className="admin-lower-grid">
        <section className="quick-actions-card"><div className="section-title-row"><div><span className="eyebrow">KEEP THINGS MOVING</span><h2>Quick actions</h2></div></div><button className="quick-action" onClick={() => setPage('approvals')}><span className="quick-action-icon quick-amber"><Icon name="check" /></span><span><b>Review pending notices</b><small>{loading ? 'Loading queue…' : `${noticeCounts.pending || 0} waiting for your review`}</small></span><Icon name="arrow" size={18} /></button><button className="quick-action" onClick={() => setPage('users')}><span className="quick-action-icon quick-indigo"><Icon name="users" /></span><span><b>Manage campus accounts</b><small>{loading ? 'Loading accounts…' : `${dashboard.total_users || 0} accounts in the directory`}</small></span><Icon name="arrow" size={18} /></button><button className="quick-action" onClick={() => setPage('notices')}><span className="quick-action-icon quick-indigo"><Icon name="file" /></span><span><b>Browse all notices</b><small>{loading ? 'Loading notices…' : `${noticeCounts.total || 0} notices across campus`}</small></span><Icon name="arrow" size={18} /></button></section>
        <section className="recent-card"><div className="section-title-row"><div><span className="eyebrow">AUDIT TRAIL</span><h2>Recent platform activity</h2></div></div>{loading ? <div className="loading-row">Loading activity…</div> : dashboard.recent_activity?.length ? dashboard.recent_activity.map((activity) => <div className="activity-item" key={activity.id}><span className="recent-file"><Icon name={activity.entity_type === 'notice' ? 'file' : 'users'} size={16} /></span><div><strong>{activity.actor_name || activity.actor_email || 'System'} {activity.action} {activity.entity_type}</strong><small>{activity.details || `${activity.entity_type} ${activity.entity_id || ''}`}</small></div><time>{activity.created_at}</time></div>) : <EmptyState title="No activity recorded yet" description="Account and notice changes will appear here." />}</section>
      </div>
    </div>
  );
}

export default App;
