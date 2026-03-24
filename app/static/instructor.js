const token = localStorage.getItem('coursehub_token');
const listEl = document.getElementById('course-list');

async function loadCourses() {
  const courses = await fetch('/api/courses').then(r => r.json());
  listEl.innerHTML = courses.map(c => `<li><strong>${c.title}</strong> - ${c.description} (ID: ${c.id})</li>`).join('');
}


document.getElementById('course-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  const res = await fetch('/api/courses', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    e.target.reset();
    loadCourses();
  }
});

loadCourses();
