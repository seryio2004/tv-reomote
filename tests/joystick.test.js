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
      style: {
        values: {},
        setProperty(name, value) { this.values[name] = value; },
      },
      classList: {add() {}, remove() {}},
      dataset: {},
      offsetWidth: id === 'joystick-knob' ? 76 : 0,
      getBoundingClientRect: () => ({left: 0, top: 0, width: 210, height: 210}),
      setPointerCapture(pointerId) { captured = pointerId; },
      hasPointerCapture(pointerId) { return captured === pointerId; },
      releasePointerCapture(pointerId) { if (captured === pointerId) captured = null; },
    });
    return elements.get(id);
  };
  const context = {
    document: {
      getElementById: element,
      querySelectorAll: () => [],
      addEventListener: () => {},
    },
    fetch: (url, options) => {
      if (url === '/api/status') {
        return Promise.resolve({ok: true, json: async () => ({connected: true})});
      }
      return new Promise((resolve, reject) => {
        requests.push({
          url,
          body: JSON.parse(options.body),
          complete: () => resolve({ok: true, json: async () => ({})}),
          fail: () => reject(new Error('Sin conexión')),
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
    frame(timestamp) {
      const scheduled = [...frames.values()];
      frames.clear();
      scheduled.forEach(callback => callback(timestamp));
    },
  };
}

const pointer = (pointerId, clientX, clientY, other = {}) => ({
  pointerId, clientX, clientY, isPrimary: true, button: 0,
  preventDefault() {},
  ...other,
});
const settle = () => new Promise(resolve => setImmediate(resolve));

test('the joystick dead zone does not move or click', () => {
  const app = remote();
  const stick = app.element('joystick');
  stick.onpointerdown(pointer(1, 105, 105));
  app.frame(0);
  app.frame(33);
  stick.onpointerup(pointer(1, 105, 105));
  app.frame(66);
  assert.equal(app.requests.length, 0);
  assert.equal(stick.style.values['--stick-x'], '0px');
});

test('holding the stick moves continuously, then release discards pending movement', async () => {
  const app = remote();
  const stick = app.element('joystick');
  stick.onpointerdown(pointer(1, 200, 105));
  app.frame(0);
  assert.equal(app.requests[0].url, '/api/mouse/move');
  assert.ok(app.requests[0].body.dx > 0);
  app.frame(16);
  app.frame(33);
  assert.equal(app.requests.length, 1);
  stick.onpointerup(pointer(1, 200, 105));
  app.requests[0].complete();
  await settle();
  app.frame(66);
  assert.equal(app.requests.length, 1);
});

test('pushing farther from the center moves faster', () => {
  const near = remote();
  near.element('joystick').onpointerdown(pointer(1, 130, 105));
  near.frame(0);
  const far = remote();
  far.element('joystick').onpointerdown(pointer(1, 200, 105));
  far.frame(0);
  assert.ok(far.requests[0].body.dx > near.requests[0].body.dx);
});

test('a click waits for an in-flight movement', async () => {
  const app = remote();
  const stick = app.element('joystick');
  stick.onpointerdown(pointer(1, 200, 105));
  app.frame(0);
  stick.onpointerup(pointer(1, 200, 105));
  app.element('left-click').onclick();
  assert.equal(app.requests.length, 1);
  app.requests[0].complete();
  await settle();
  assert.equal(app.requests[1].url, '/api/mouse/click');
});

test('a failed mouse request stops the joystick', async () => {
  const app = remote();
  const stick = app.element('joystick');
  stick.onpointerdown(pointer(1, 200, 105));
  app.frame(0);
  app.requests[0].fail();
  await settle();
  app.frame(33);
  assert.equal(app.requests.length, 1);
  assert.equal(stick.style.values['--stick-x'], '0px');
});

test('a second pointer cannot change the active direction', () => {
  const app = remote();
  const stick = app.element('joystick');
  stick.onpointerdown(pointer(1, 200, 105));
  stick.onpointerdown(pointer(2, 0, 105, {isPrimary: false}));
  stick.onpointermove(pointer(2, 0, 105, {isPrimary: false}));
  app.frame(0);
  assert.ok(app.requests[0].body.dx > 0);
});
