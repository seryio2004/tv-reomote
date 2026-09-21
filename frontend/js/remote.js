const c = document.getElementById('connection');
const m = document.getElementById('message');
const pt = document.getElementById('page-title');
const pu = document.getElementById('page-url');
const u = document.getElementById('url');
const ti = document.getElementById('text-input');
const tp = document.getElementById('touchpad');
let mt = null;

async function api(path, body = null) {
  const options = {method: 'POST', headers: {}};
  if (body !== null) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) throw new Error(data.detail || 'HTTP ' + response.status);
  return data;
}

function msg(text, error = false) {
  clearTimeout(mt);
  m.textContent = text;
  m.style.color = error ? '#d75b5b' : '';
  mt = setTimeout(() => { m.textContent = ''; m.style.color = ''; }, 2600);
}

async function status() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    if (data.connected) {
      c.textContent = 'Chrome conectado';
      c.className = 'status online';
      pt.textContent = data.title || 'Sin título';
      pu.textContent = data.url || '—';
    } else {
      c.textContent = 'Chrome desconectado';
      c.className = 'status offline';
      pt.textContent = pu.textContent = '—';
    }
  } catch {
    c.textContent = 'Servidor no disponible';
    c.className = 'status offline';
  }
}

async function action(name) {
  try { await api('/api/' + name); setTimeout(status, 300); }
  catch (error) { msg(error.message, true); }
}

async function nav(url) {
  if (!url.trim()) return msg('Introduce una URL.', true);
  try {
    const data = await api('/api/navigate', {url});
    u.value = data.url || url;
    await status();
    msg('Abierto en la TV.');
  } catch (error) { msg(error.message, true); }
}

document.getElementById('url-form').onsubmit = event => {
  event.preventDefault();
  nav(u.value);
};
document.querySelectorAll('[data-action]').forEach(button => {
  button.onclick = () => action(button.dataset.action);
});
document.querySelectorAll('[data-url]').forEach(button => {
  button.onclick = () => nav(button.dataset.url);
});
document.querySelectorAll('[data-key]').forEach(button => {
  button.onclick = async () => {
    try { await api('/api/key', {key: button.dataset.key}); }
    catch (error) { msg(error.message, true); }
  };
});
document.getElementById('type-form').onsubmit = async event => {
  event.preventDefault();
  if (!ti.value) return;
  try { await api('/api/type', {text: ti.value}); ti.value = ''; }
  catch (error) { msg(error.message, true); }
};
document.getElementById('refresh-status').onclick = status;

// Keep mouse requests in order. While Chrome handles a movement, combine
// further movements instead of building up a backlog of stale positions.
const mouseQueue = [];
let mouseSending = false;
let frame = null;
let frameX = 0;
let frameY = 0;

async function sendMouseQueue() {
  if (mouseSending) return;
  mouseSending = true;
  try {
    while (mouseQueue.length) {
      const item = mouseQueue[0];
      if (item.kind === 'move') {
        // The API accepts at most 1000 px on either axis per request.
        const dx = Math.max(-1000, Math.min(1000, item.dx));
        const dy = Math.max(-1000, Math.min(1000, item.dy));
        item.dx -= dx;
        item.dy -= dy;
        if (item.dx === 0 && item.dy === 0) mouseQueue.shift();
        if (dx !== 0 || dy !== 0) await api('/api/mouse/move', {dx, dy});
      } else {
        mouseQueue.shift();
        if (item.kind === 'click') await api('/api/mouse/click', {button: item.button});
        else await api('/api/mouse/scroll', {dx: 0, dy: item.dy});
      }
    }
  } catch (error) {
    mouseQueue.length = 0;
    msg(error.message, true);
  } finally {
    mouseSending = false;
  }
}

function flushMove() {
  if (frame !== null) cancelAnimationFrame(frame);
  frame = null;
  const dx = frameX;
  const dy = frameY;
  frameX = frameY = 0;
  if (dx === 0 && dy === 0) return;
  const last = mouseQueue[mouseQueue.length - 1];
  if (last && last.kind === 'move') {
    last.dx += dx;
    last.dy += dy;
  } else {
    mouseQueue.push({kind: 'move', dx, dy});
  }
  sendMouseQueue();
}

function move(dx, dy) {
  frameX += dx * 1.6;
  frameY += dy * 1.6;
  if (frame === null) frame = requestAnimationFrame(flushMove);
}

function click(button) {
  flushMove();
  mouseQueue.push({kind: 'click', button});
  sendMouseQueue();
}

function scroll(dy) {
  flushMove();
  mouseQueue.push({kind: 'scroll', dy});
  sendMouseQueue();
}

document.getElementById('left-click').onclick = () => click('left');
document.getElementById('right-click').onclick = () => click('right');
document.getElementById('scroll-up').onclick = () => scroll(-550);
document.getElementById('scroll-down').onclick = () => scroll(550);

const TAP_SLOP = 6;
let pointerId = null;
let startX = 0;
let startY = 0;
let lastX = 0;
let lastY = 0;
let dragging = false;

function updatePointer(event) {
  if (event.pointerId !== pointerId) return;
  if (!dragging && Math.hypot(event.clientX - startX, event.clientY - startY) <= TAP_SLOP) return;
  dragging = true;
  move(event.clientX - lastX, event.clientY - lastY);
  lastX = event.clientX;
  lastY = event.clientY;
}

tp.onpointerdown = event => {
  if (pointerId !== null || !event.isPrimary || event.button !== 0) return;
  pointerId = event.pointerId;
  dragging = false;
  startX = lastX = event.clientX;
  startY = lastY = event.clientY;
  tp.setPointerCapture(event.pointerId);
};
tp.onpointermove = updatePointer;
tp.onpointerup = event => {
  if (event.pointerId !== pointerId) return;
  updatePointer(event);
  pointerId = null;
  if (tp.hasPointerCapture(event.pointerId)) tp.releasePointerCapture(event.pointerId);
  if (dragging) flushMove();
  else click('left');
};
tp.onpointercancel = event => {
  if (event.pointerId === pointerId) {
    pointerId = null;
    flushMove();
  }
};
tp.onlostpointercapture = event => {
  if (event.pointerId === pointerId) {
    pointerId = null;
    flushMove();
  }
};

status();
setInterval(status, 5000);
