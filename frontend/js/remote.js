const c = document.getElementById('connection');
const ic = document.getElementById('input-connection');
const m = document.getElementById('message');
const pt = document.getElementById('page-title');
const pu = document.getElementById('page-url');
const u = document.getElementById('url');
const ti = document.getElementById('text-input');
const stick = document.getElementById('joystick');
const knob = document.getElementById('joystick-knob');
let mt = null;
const app = document.querySelector('.app');
const keyboard = document.getElementById('keyboard-dialog');
const tabs = [...document.querySelectorAll('[role="tab"]')];

function selectMenu(tab) {
  stopJoystick();
  u.blur();
  tabs.forEach(item => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
  });
}

tabs.forEach((tab, index) => {
  tab.onclick = () => selectMenu(tab);
  tab.onkeydown = event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    selectMenu(tabs[next]);
    tabs[next].focus();
  };
});

document.getElementById('open-keyboard').onclick = () => {
  stopJoystick();
  document.getElementById('keyboard-hint').textContent = 'Selecciona primero un campo en la TV.';
  keyboard.showModal();
  ti.focus({preventScroll: true});
};
document.getElementById('close-keyboard').onclick = () => keyboard.close();
keyboard.addEventListener('close', () => {
  ti.blur();
  document.getElementById('open-keyboard').focus({preventScroll: true});
});
u.addEventListener('focus', () => app.classList.add('editing-url'));
u.addEventListener('blur', () => app.classList.remove('editing-url'));

// Fit the visible area, including mobile browser bars and the on-screen keyboard.
function fitViewport() {
  stopJoystick();
  document.documentElement.style.setProperty('--app-height',
    (window.visualViewport ? window.visualViewport.height : window.innerHeight) + 'px');
}
window.addEventListener('resize', fitViewport);
window.visualViewport?.addEventListener('resize', fitViewport);
window.addEventListener('blur', () => stopJoystick());
// Prevent browser gestures while keeping the TV scroll buttons independent.
document.addEventListener('touchmove', event => event.preventDefault(), {passive: false});
document.addEventListener('gesturestart', event => event.preventDefault(), {passive: false});
document.addEventListener('wheel', event => event.preventDefault(), {passive: false});

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
  if (keyboard.open) document.getElementById('keyboard-hint').textContent = text;
  m.textContent = text;
  m.style.color = error ? '#d75b5b' : '';
  mt = setTimeout(() => { m.textContent = ''; m.style.color = ''; }, 2600);
}

function connectionState(element, label, online, description) {
  element.textContent = label;
  element.className = online ? 'status online' : 'status offline';
  element.title = description || label + (online ? ' conectado' : ' desconectado');
  element.setAttribute('aria-label', element.title);
}

async function status() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    if (data.connected) {
      connectionState(c, 'Chrome', true);
      pt.textContent = data.title || 'Sin título';
      pu.textContent = data.url || '—';
    } else {
      connectionState(c, 'Chrome', false);
      pt.textContent = pu.textContent = '—';
    }
    connectionState(ic, 'Control', data.input_connected);
  } catch {
    connectionState(c, 'Chrome', false, 'Servidor no disponible');
    connectionState(ic, 'Control', false);
    pt.textContent = pu.textContent = '—';
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
  u.blur();
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
  try { await api('/api/type', {text: ti.value}); ti.value = ''; msg('Texto enviado a la TV.'); }
  catch (error) { msg(error.message, true); }
};
document.getElementById('toggle-fullscreen').onclick = async () => {
  try {
    const data = await api('/api/fullscreen');
    msg(data.fullscreen ? 'Chrome en pantalla completa.' : 'Chrome en modo ventana.');
  } catch (error) { msg(error.message, true); }
};
document.getElementById('close-popups').onclick = async () => {
  try {
    const data = await api('/api/close-popups');
    await status();
    msg(data.closed ? `Ventanas emergentes cerradas: ${data.closed}.` : 'No hay ventanas emergentes abiertas.');
  } catch (error) { msg(error.message, true); }
};
document.getElementById('refresh-status').onclick = status;

// Keep mouse requests in order. While the host handles a movement, combine
// further movements instead of building up a backlog of stale positions.
const mouseQueue = [];
let mouseSending = false;

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
    stopJoystick();
    msg(error.message, true);
    status();
  } finally {
    mouseSending = false;
  }
}

function move(dx, dy) {
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

function click(button) {
  mouseQueue.push({kind: 'click', button});
  sendMouseQueue();
}

function scroll(dy) {
  mouseQueue.push({kind: 'scroll', dy});
  sendMouseQueue();
}

document.getElementById('left-click').onclick = () => click('left');
document.getElementById('right-click').onclick = () => click('right');
document.getElementById('scroll-up').onclick = () => scroll(-550);
document.getElementById('scroll-down').onclick = () => scroll(550);

let pointerId = null;
let joystickFrame = null;
let lastTick = null;
let axisX = 0;
let axisY = 0;

function updateJoystick(event) {
  if (event.pointerId !== pointerId) return;
  const rect = stick.getBoundingClientRect();
  const travel = Math.max(1, (Math.min(rect.width, rect.height) - knob.offsetWidth) / 2 - 8);
  const rawX = event.clientX - rect.left - rect.width / 2;
  const rawY = event.clientY - rect.top - rect.height / 2;
  const scale = Math.min(1, travel / (Math.hypot(rawX, rawY) || 1));
  const x = rawX * scale;
  const y = rawY * scale;
  axisX = x / travel;
  axisY = y / travel;
  stick.style.setProperty('--stick-x', x + 'px');
  stick.style.setProperty('--stick-y', y + 'px');
}

function joystickTick(timestamp) {
  if (pointerId === null) return;
  const elapsed = lastTick === null ? 0.033 : (timestamp - lastTick) / 1000;
  if (lastTick === null || elapsed >= 0.03) {
    lastTick = timestamp;
    const strength = Math.hypot(axisX, axisY);
    if (strength > 0.12) {
      const amount = (strength - 0.12) / 0.88;
      const speed = 90 + 650 * amount * amount;
      const distance = speed * Math.min(elapsed, 0.06);
      move(axisX / strength * distance, axisY / strength * distance);
    }
  }
  joystickFrame = requestAnimationFrame(joystickTick);
}

function stopJoystick() {
  if (pointerId === null) return;
  const id = pointerId;
  pointerId = null;
  if (joystickFrame !== null) cancelAnimationFrame(joystickFrame);
  joystickFrame = null;
  lastTick = null;
  axisX = axisY = 0;
  stick.style.setProperty('--stick-x', '0px');
  stick.style.setProperty('--stick-y', '0px');
  stick.classList.remove('active');
  // A released joystick must not keep moving through queued requests.
  for (let index = mouseQueue.length - 1; index >= 0; index--) {
    if (mouseQueue[index].kind === 'move') mouseQueue.splice(index, 1);
  }
  if (stick.hasPointerCapture(id)) stick.releasePointerCapture(id);
}

stick.onpointerdown = event => {
  if (pointerId !== null || !event.isPrimary || event.button !== 0) return;
  event.preventDefault();
  pointerId = event.pointerId;
  stick.setPointerCapture(pointerId);
  stick.classList.add('active');
  updateJoystick(event);
  joystickFrame = requestAnimationFrame(joystickTick);
};
stick.onpointermove = updateJoystick;
stick.onpointerup = event => {
  if (event.pointerId === pointerId) stopJoystick();
};
stick.onpointercancel = event => {
  if (event.pointerId === pointerId) stopJoystick();
};
stick.onlostpointercapture = event => {
  if (event.pointerId === pointerId) stopJoystick();
};
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopJoystick();
});

fitViewport();
status();
setInterval(status, 5000);
