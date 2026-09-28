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
  const windowEvents = {};
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '',
      style: {
        values: {},
        setProperty(name, value) { this.values[name] = value; },
      },
      classList: {
        values: new Set(),
        add(value) { this.values.add(value); },
        remove(value) { this.values.delete(value); },
      },
      attributes: {},
      events: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      getAttribute(name) { return this.attributes[name]; },
      addEventListener(name, callback) { this.events[name] = callback; },
      focus() { this.events.focus?.(); },
      blur() { this.events.blur?.(); },
      showModal() { this.open = true; },
      close() { this.open = false; this.events.close?.(); },
      dataset: {},
      offsetWidth: id === 'joystick-knob' ? 76 : 0,
      getBoundingClientRect: () => ({left: 0, top: 0, width: 210, height: 210}),
      setPointerCapture(pointerId) { captured = pointerId; },
      hasPointerCapture(pointerId) { return captured === pointerId; },
      releasePointerCapture(pointerId) { if (captured === pointerId) captured = null; },
    });
    return elements.get(id);
  };
  const tabs = [element('joystick-tab'), element('shortcuts-tab')];
  tabs[0].setAttribute('aria-controls', 'joystick-panel');
  tabs[1].setAttribute('aria-controls', 'shortcuts-panel');
  const context = {
    window: {
      innerHeight: 640,
      addEventListener: (name, callback) => { windowEvents[name] = callback; },
    },
    document: {
      getElementById: element,
      querySelector: selector => element(selector),
      querySelectorAll: selector => selector === '[role="tab"]' ? tabs : [],
      documentElement: element('html'),
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
    windowEvents,
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


test('switching menus stops movement and selects only the requested panel', () => {
  const app = remote();
  app.element('joystick').onpointerdown(pointer(1, 200, 105));
  app.frame(0);
  app.element('shortcuts-tab').onclick();
  app.frame(33);
  assert.equal(app.requests.length, 1);
  assert.equal(app.element('joystick').style.values['--stick-x'], '0px');
  assert.equal(app.element('joystick-panel').hidden, true);
  assert.equal(app.element('shortcuts-panel').hidden, false);
  assert.equal(app.element('shortcuts-tab').getAttribute('aria-selected'), 'true');
  assert.equal(app.element('joystick-tab').tabIndex, -1);
  app.element('joystick-tab').onclick();
  assert.equal(app.element('shortcuts-panel').hidden, true);
  assert.equal(app.element('joystick-panel').hidden, false);
});

test('arrow keys move focus and selection between menus', () => {
  const app = remote();
  app.element('joystick-tab').onkeydown({key: 'ArrowRight', preventDefault() {}});
  assert.equal(app.element('shortcuts-tab').tabIndex, 0);
  assert.equal(app.element('shortcuts-panel').hidden, false);
});

test('opening the keyboard stops the joystick and closing it preserves the menu', () => {
  const app = remote();
  app.element('joystick-tab').onclick();
  app.element('joystick').onpointerdown(pointer(1, 200, 105));
  app.element('open-keyboard').onclick();
  app.frame(0);
  assert.equal(app.requests.length, 0);
  assert.equal(app.element('keyboard-dialog').open, true);
  app.element('close-keyboard').onclick();
  assert.equal(app.element('keyboard-dialog').open, false);
  assert.equal(app.element('joystick-panel').hidden, false);
});

test('viewport changes and lost window focus stop cursor movement', () => {
  for (const event of ['resize', 'blur']) {
    const app = remote();
    app.element('joystick').onpointerdown(pointer(1, 200, 105));
    app.windowEvents[event]();
    app.frame(0);
    assert.equal(app.requests.length, 0);
    assert.equal(app.element('joystick').style.values['--stick-x'], '0px');
  }
});
