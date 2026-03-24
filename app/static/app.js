const statusEl = document.getElementById('status');

function saveToken(token) {
  localStorage.setItem('coursehub_token', token);
}

document.getElementById('register-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) return statusEl.textContent = data.detail || 'Registration failed';
  saveToken(data.access_token);
  statusEl.textContent = 'Registration successful. Now login or open your dashboard.';
});

document.getElementById('login-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const body = new URLSearchParams(form).toString();
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body,
  });
  const data = await res.json();
  if (!res.ok) return statusEl.textContent = data.detail || 'Login failed';
  saveToken(data.access_token);
  const me = await fetch('/api/me', {headers: {Authorization: `Bearer ${data.access_token}`}}).then(r => r.json());
  if (me.role === 'instructor') location.href = '/dashboard/instructor';
  else location.href = '/dashboard/student';
});
