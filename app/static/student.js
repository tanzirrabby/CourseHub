const token = localStorage.getItem('coursehub_token');
const listEl = document.getElementById('course-list');
const certEl = document.getElementById('cert-list');

async function loadCourses() {
  const courses = await fetch('/api/courses').then(r => r.json());
  listEl.innerHTML = courses.map(c => `<li><strong>${c.title}</strong>
    <button onclick="enroll(${c.id})">Enroll</button>
  </li>`).join('');
}

async function loadCerts() {
  const res = await fetch('/api/certificates', {headers: {Authorization: `Bearer ${token}`}});
  if (!res.ok) return;
  const certs = await res.json();
  certEl.innerHTML = certs.map(c => `<li>Certificate #${c.id} for course ${c.course_id} (${c.issued_at})</li>`).join('');
}

window.enroll = async (courseId) => {
  await fetch(`/api/courses/${courseId}/enroll`, {method: 'POST', headers: {Authorization: `Bearer ${token}`}});
  alert('Enrolled! Complete lessons and quizzes via API to earn certificate.');
};

loadCourses();
loadCerts();
