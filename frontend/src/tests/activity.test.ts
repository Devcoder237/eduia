import { describe, expect, it } from "vitest";
import { PAGES } from "../lib/router";
import { ActiveTimeCounter, BEAT_EVERY_S, IDLE_LIMIT_MS, MAX_BEAT_S, moduleForPage } from "../utils/activity";

describe("moduleForPage", () => {
  it("rattache chaque écran privé à un module et ignore les pages publiques", () => {
    expect(moduleForPage("tutor")).toBe("tutor");
    expect(moduleForPage("quiz")).toBe("quiz");
    expect(moduleForPage("exercise")).toBe("exercise");
    expect(moduleForPage("exam")).toBe("exam");
    expect(moduleForPage("progress")).toBe("other");
    for (const page of ["landing", "login", "legal", "reset"] as const) {
      expect(moduleForPage(page)).toBeNull();
    }
  });

  it("couvre toutes les pages sans exception", () => {
    for (const page of PAGES) expect(() => moduleForPage(page)).not.toThrow();
  });
});

describe("ActiveTimeCounter", () => {
  it("ne signale qu'après 30 s d'activité réelle", () => {
    const counter = new ActiveTimeCounter();
    for (let i = 1; i < BEAT_EVERY_S; i += 1) expect(counter.tick(true, 0)).toBe(false);
    expect(counter.tick(true, 0)).toBe(true);
    expect(counter.take()).toBe(BEAT_EVERY_S);
    expect(counter.take()).toBe(0);
  });

  it("ne compte pas le temps onglet caché ni sans interaction depuis plus d'une minute", () => {
    const counter = new ActiveTimeCounter();
    for (let i = 0; i < 100; i += 1) counter.tick(false, 0);
    for (let i = 0; i < 100; i += 1) counter.tick(true, IDLE_LIMIT_MS);
    expect(counter.take()).toBe(0);
    counter.tick(true, IDLE_LIMIT_MS - 1);
    expect(counter.take()).toBe(1);
  });

  it("plafonne un signal à 60 s et conserve le reste", () => {
    const counter = new ActiveTimeCounter();
    for (let i = 0; i < 90; i += 1) counter.tick(true, 0);
    expect(counter.take()).toBe(MAX_BEAT_S);
    expect(counter.take()).toBe(30);
  });

  it("restitue les secondes d'un envoi échoué sans dépasser le plafond", () => {
    const counter = new ActiveTimeCounter();
    for (let i = 0; i < 30; i += 1) counter.tick(true, 0);
    const sent = counter.take();
    counter.restore(sent);
    expect(counter.take()).toBe(30);
    counter.restore(500);
    expect(counter.take()).toBe(MAX_BEAT_S);
  });
});