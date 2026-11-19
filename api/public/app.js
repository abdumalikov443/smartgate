const $ = (s) => document.querySelector(s);
const COLORS = { car: '#10B981', truck: '#F59E0B', bus: '#3B82F6', motorcycle: '#A855F7' };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const kstToday = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const time = (d) => new Date(d).toLocaleTimeString('en-GB', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit' });
const mins = (m) => (m == null ? '–' : m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`);
const get = (url) => fetch(url).then((r) => r.json());

$('#date').value = kstToday();
const isToday = () => $('#date').value === kstToday();

const hourly = new Chart($('#hourly'), {
  type: 'bar',
  data: { labels: [...Array(24).keys()].map((h) => `${h}`), datasets: [
    { label: 'IN', data: [], backgroundColor: '#16A34A', borderRadius: 4 },
    { label: 'OUT', data: [], backgroundColor: '#2563EB', borderRadius: 4 },
  ] },
  options: { maintainAspectRatio: false, plugins: { legend: { position: 'top', align: 'end' } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 } } } },
});
const types = new Chart($('#types'), {
  type: 'doughnut',
  data: { labels: Object.keys(COLORS), datasets: [{ data: [], backgroundColor: Object.values(COLORS), borderWidth: 0 }] },
  options: { maintainAspectRatio: false, cutout: '62%', plugins: { legend: { position: 'bottom' } } },
});

async function loadStats() {
  const s = await get(`/api/stats/vehicles?date=${$('#date').value}`);
  $('#k-in').textContent = s.totals.IN;
  $('#k-out').textContent = s.totals.OUT;
  $('#k-inside').textContent = s.insideNow;
  $('#k-dwell').textContent = mins(s.avgDwellMinutes);
  // any plate information counts: a full plate or, when the letter was unreadable, the last 4 digits
  const events = s.totals.IN + s.totals.OUT, withPlate = s.platesRead + (s.plateDigitsOnly ?? 0);
  $('#k-plates').textContent = events ? `${Math.round((withPlate / events) * 100)}%` : '–';
  $('#k-in-sub').textContent = `${s.byType.truck.IN} trucks · ${s.byType.car.IN} cars`;
  $('#k-out-sub').textContent = `${s.byType.truck.OUT} trucks · ${s.byType.car.OUT} cars`;
  $('#k-inside-sub').textContent = `${s.insideByType.truck} trucks inside`;
  $('#k-dwell-sub').textContent = `trucks ${mins(s.avgDwellByType.truck)}`;
  $('#k-plates-sub').textContent = `${s.platesRead} full · ${s.plateDigitsOnly ?? 0} by last 4 digits`;
  hourly.data.datasets[0].data = s.hourly.map((h) => h.IN);
  hourly.data.datasets[1].data = s.hourly.map((h) => h.OUT);
  hourly.update();
  types.data.datasets[0].data = Object.keys(COLORS).map((t) => s.byType[t].IN);
  types.update();
}

const typeCell = (t) => `<span class="type"><i style="background:${COLORS[t]}"></i>${esc(t)}</span>`;
const plateCell = (p, digits) => (p ? `<span class="plate">${esc(p)}</span>`
  : digits ? `<span class="plate partial" title="letter unreadable - last 4 digits">··${esc(digits)}</span>`
  : '<small style="color:#9CA3AF">unread</small>');

async function loadEvents(flashFirst = false) {
  const rows = await get('/api/vehicle-events?limit=40');
  $('#events').innerHTML = rows.length ? rows.map((e, i) => `<tr class="${flashFirst && i === 0 ? 'new' : ''}">
      <td>${time(e.occurredAt)}</td><td><span class="dir ${e.direction}">${e.direction}</span></td>
      <td>${typeCell(e.vehicleType)}</td><td>${plateCell(e.plate, e.plateDigits)}</td>
      <td>${e.snapshotUrl ? `<img class="snap" src="${esc(e.snapshotUrl)}" alt="">` : '<span class="snap"></span>'}</td></tr>`).join('')
    : '<tr><td class="empty" colspan="5">No events yet</td></tr>';
}

async function loadInside() {
  const rows = await get('/api/vehicles/inside');
  $('#inside').innerHTML = rows.length ? rows.map((v) => `<li><div>${typeCell(v.vehicleType)} ${plateCell(v.plate, v.plateDigits)}</div>
      <small>since ${time(v.inAt)} · ${mins(Math.round((Date.now() - new Date(v.inAt)) / 60000))}</small></li>`).join('')
    : '<li class="empty">Nobody inside</li>';
}

async function loadAttendance() {
  const { rows } = await get(`/api/attendance?date=${$('#date').value}`);
  $('#attendance').innerHTML = rows.length ? rows.map((r) => `<tr><td><b>${esc(r.name)}</b></td>
      <td>${time(r.firstSeen)}</td><td>${time(r.lastSeen)}</td><td>${mins(r.workMinutes)}</td>
      <td><span class="badge ${r.status}">${r.status === 'present' ? 'present' : 'checked in'}</span>${r.late ? '<span class="badge late">late</span>' : ''}</td></tr>`).join('')
    : '<tr><td class="empty" colspan="5">No attendance yet</td></tr>';
}

async function loadAlerts() {
  const rows = await get('/api/alerts?limit=15');
  $('#alerts').innerHTML = rows.length ? rows.map((a) => `<li class="alert"><div><b>Unknown person</b><br>
      <small>${esc(a.cameraId)} · ${time(a.occurredAt)} · similarity ${a.similarity}</small></div>
      ${a.snapshotUrl ? `<img src="${esc(a.snapshotUrl)}" alt="">` : ''}</li>`).join('')
    : '<li class="empty">No alerts</li>';
}

const loadAll = () => Promise.all([loadStats(), loadEvents(), loadInside(), loadAttendance(), loadAlerts()]);
$('#date').addEventListener('change', loadAll);
loadAll();

const socket = io();
socket.on('connect', () => { $('#live').className = 'live on'; $('#live').lastChild.textContent = 'live'; });
socket.on('disconnect', () => { $('#live').className = 'live'; $('#live').lastChild.textContent = 'offline'; });
socket.on('vehicle', () => { if (isToday()) { loadStats(); loadEvents(true); loadInside(); } });
socket.on('attendance', () => isToday() && loadAttendance());
socket.on('alert', loadAlerts);
