import assert from "node:assert/strict";
import { test } from "node:test";
import { mountPointerLight } from "../src/utils/pointer-light.ts";

class Events {
    listeners = new Map();
    addEventListener(name, listener) {
        if (!this.listeners.has(name)) this.listeners.set(name, new Set());
        this.listeners.get(name).add(listener);
    }
    removeEventListener(name, listener) {
        this.listeners.get(name)?.delete(listener);
    }
    emit(name, event = {}) {
        for (const listener of this.listeners.get(name) || []) listener(event);
    }
}

function fixture({ fine = true, reduced = false, focused = true } = {}) {
    const view = new Events();
    const doc = new Events();
    const pointer = Object.assign(new Events(), { matches: fine });
    const motion = Object.assign(new Events(), { matches: reduced });
    const frames = new Map();
    let nextFrame = 0;
    doc.documentElement = new Events();
    doc.hidden = false;
    doc.hasFocus = () => focused;
    view.matchMedia = (query) => query.includes("reduced-motion") ? motion : pointer;
    view.requestAnimationFrame = (callback) => {
        const id = ++nextFrame;
        frames.set(id, callback);
        return id;
    };
    view.cancelAnimationFrame = (id) => frames.delete(id);
    const target = { dataset: {}, style: {} };
    const cleanup = mountPointerLight(target, { view, doc });
    const move = (x = 40, y = 70, pointerType = "mouse") =>
        view.emit("pointermove", { clientX: x, clientY: y, pointerType });
    const flush = () => {
        const pending = [...frames.values()];
        frames.clear();
        pending.forEach((callback) => callback());
    };
    return { view, doc, pointer, motion, frames, target, cleanup, move, flush };
}

test("pointer moves coalesce into one frame using the latest coordinates", () => {
    const f = fixture();
    assert.equal(f.target.dataset.active, "false");
    assert.equal(f.view.listeners.get("pointermove").size, 1);
    f.move(10, 20);
    f.move(30, 50);
    assert.equal(f.frames.size, 1);
    assert.equal(f.target.style.transform, undefined);
    f.flush();
    assert.equal(f.target.style.transform, "translate3d(30px, 50px, 0) translate(-50%, -50%)");
    assert.equal(f.target.dataset.active, "true");
    f.cleanup();
});

test("touch, coarse pointers, reduced motion and unfocused pages stay inactive", () => {
    for (const options of [{ fine: false }, { reduced: true }, { focused: false }]) {
        const f = fixture(options);
        f.move();
        assert.equal(f.frames.size, 0);
        assert.equal(f.target.dataset.active, "false");
        f.cleanup();
    }
    const f = fixture();
    f.move(10, 20, "touch");
    assert.equal(f.frames.size, 0);
    f.doc.hidden = true;
    f.move();
    assert.equal(f.frames.size, 0);
    f.cleanup();
});

test("leaving, blurring, hiding or changing preferences cancels pending light", () => {
    const triggers = [
        (f) => f.doc.documentElement.emit("pointerleave"),
        (f) => f.view.emit("blur"),
        (f) => { f.doc.hidden = true; f.doc.emit("visibilitychange"); },
        (f) => { f.pointer.matches = false; f.pointer.emit("change"); },
        (f) => { f.motion.matches = true; f.motion.emit("change"); },
    ];
    for (const trigger of triggers) {
        const f = fixture();
        f.move();
        f.flush();
        assert.equal(f.target.dataset.active, "true");
        f.move(80, 90);
        trigger(f);
        assert.equal(f.frames.size, 0);
        assert.equal(f.target.dataset.active, "false");
        f.flush();
        assert.equal(f.target.dataset.active, "false");
        f.cleanup();
    }
});

test("focus loss before a frame is rendered does not reveal the light", () => {
    const f = fixture();
    f.move();
    f.doc.hasFocus = () => false;
    f.flush();
    assert.equal(f.target.dataset.active, "false");
    f.cleanup();
});

test("cleanup removes every listener and cancels work", () => {
    const f = fixture();
    f.move();
    f.cleanup();
    assert.equal(f.frames.size, 0);
    assert.equal(f.target.dataset.active, "false");
    for (const events of [f.view, f.doc, f.doc.documentElement, f.pointer, f.motion]) {
        for (const listeners of events.listeners.values()) assert.equal(listeners.size, 0);
    }
    f.move();
    assert.equal(f.frames.size, 0);
});
