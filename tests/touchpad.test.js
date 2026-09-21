const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../frontend/js/remote.js'), 'utf8');

function remote() {
  const elements = new Map();
  const requests = [];
  const frames = new Map();
  let nextFrame = 0;
  let captured = null;
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '',
      style: {},
      dataset: {},
      setPointerCapture(id) { captured = id; },
      hasPointerCapture(id) { return captured === id; },
      releasePointerCapture(id) { if (captured === id) captured = null; },
    });
    return elements.get(id);
  };
  const context = {
    document: {
      getElementById: element,
      querySelectorAll: () => [],
    },
    fetch: (url, options) => {
      if (url === '/api/status') {
        return Promise.resolve({ok: true, json: async () => ({connected: true})});
      }
      return new Promise(resolve => {
        requests.push({
          url,
          body: JSON.parse(options.body),
          complete: () => resolve({ok: true, json: async () => ({})}),
        });
      });
    },
    requestAnimationFrame: callback => {
      frames.set(++nextFrame, callback);
      return nextFrame;
    },
    cancelAnimationFrame: id => frames.delete(id),
    setInterval: () => {},
    setTimeout: () => 1,
    clearTimeout: () => {},
  };
  vm.runInNewContext(script, context);
  return {
    element,
    requests,
    flushFrame() {
      const scheduled = [...frames.values()];
      frames.clear();
      scheduled.forEach(callback => callback());
    },
  };
}

const pointer = (pointerId, clientX, clientY, other = {}) => ({
  pointerId, clientX, clientY, isPrimary: true, button: 0, ...other,
});
const settle = () => new Promise(resolve => setImmediate(resolve));

test('a small finger movement remains a click without moving the cursor', () => {
  const app = remote();
  const pad = app.element('touchpad');
  pad.onpointerdown(pointer(1, 20, 20));
  pad.onpointermove(pointer(1, 23, 24));
  pad.onpointerup(pointer(1, 23, 24));
  assert.deepEqual(app.requests.map(request => request.url), ['/api/mouse/click']);
});

test('pointer release includes its final position and does not click after a drag', () => {
  const app = remote();
  const pad = app.element('touchpad');
  pad.onpointerdown(pointer(1, 0, 0));
  pad.onpointerup(pointer(1, 10, 0));
  assert.deepEqual(app.requests.map(request => request.url), ['/api/mouse/move']);
  assert.equal(app.requests[0].body.dx, 16);
});

test('movement is combined while a request is pending and the click follows it', async () => {
  const app = remote();
  const pad = app.element('touchpad');
  pad.onpointerdown(pointer(1, 0, 0));
  pad.onpointermove(pointer(1, 10, 0));
  app.flushFrame();
  assert.equal(app.requests.length, 1);
  assert.equal(app.requests[0].body.dx, 16);

  pad.onpointermove(pointer(1, 15, 0));
  app.flushFrame();
  pad.onpointermove(pointer(1, 20, 0));
  app.flushFrame();
  pad.onpointerup(pointer(1, 20, 0));
  app.element('left-click').onclick();
  assert.equal(app.requests.length, 1);

  app.requests[0].complete();
  await settle();
  assert.equal(app.requests[1].url, '/api/mouse/move');
  assert.equal(app.requests[1].body.dx, 16);
  app.requests[1].complete();
  await settle();
  assert.equal(app.requests[2].url, '/api/mouse/click');
});

test('other pointers cannot move or click the active gesture', () => {
  const app = remote();
  const pad = app.element('touchpad');
  pad.onpointerdown(pointer(1, 0, 0));
  pad.onpointerdown(pointer(2, 100, 100, {isPrimary: false}));
  pad.onpointermove(pointer(2, 200, 200, {isPrimary: false}));
  pad.onpointerup(pointer(2, 200, 200, {isPrimary: false}));
  pad.onpointercancel(pointer(1, 0, 0));
  app.flushFrame();
  assert.equal(app.requests.length, 0);
});
