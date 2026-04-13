const DEFAULT_INTERVAL_MIN = 5;
const ALARM_NAME = "auto-sync";

async function getAllCookies() {
  return await chrome.cookies.getAll({ domain: "zhipin.com" });
}

function cookiesToMap(cookies) {
  const map = {};
  for (const c of cookies) {
    if (c && c.name && c.value) {
      map[c.name] = c.value;
    }
  }
  return map;
}

function cookiesToString(map) {
  const parts = [];
  for (const [k, v] of Object.entries(map)) {
    parts.push(`${k}=${v}`);
  }
  return parts.join("; ");
}

async function sendToLocal(map) {
  const resp = await fetch("http://127.0.0.1:9876/cookies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cookies: map }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  return await resp.json();
}

async function syncCookies() {
  const cookies = await getAllCookies();
  const map = cookiesToMap(cookies);
  if (Object.keys(map).length === 0) {
    await chrome.storage.local.set({ lastError: "no_cookies", lastSync: null });
    return { ok: false, error: "no_cookies" };
  }
  try {
    await sendToLocal(map);
    const now = Date.now();
    await chrome.storage.local.set({ lastSync: now, lastError: "" });
    return { ok: true, cookieCount: Object.keys(map).length, lastSync: now };
  } catch (err) {
    const msg = err && err.message ? err.message : String(err);
    await chrome.storage.local.set({ lastError: msg });
    return { ok: false, error: msg };
  }
}

async function getSettings() {
  const data = await chrome.storage.local.get(["intervalMin"]);
  return data.intervalMin || DEFAULT_INTERVAL_MIN;
}

async function scheduleAlarm() {
  const intervalMin = await getSettings();
  await chrome.alarms.create(ALARM_NAME, { periodInMinutes: intervalMin });
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({ intervalMin: DEFAULT_INTERVAL_MIN });
  await scheduleAlarm();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm && alarm.name === ALARM_NAME) {
    await syncCookies();
  }
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg && msg.type === "sync") {
      const result = await syncCookies();
      sendResponse(result);
      return;
    }
    if (msg && msg.type === "get_status") {
      const data = await chrome.storage.local.get(["lastSync", "lastError", "intervalMin"]);
      sendResponse({ ok: true, ...data });
      return;
    }
    if (msg && msg.type === "get_cookies") {
      const cookies = await getAllCookies();
      const map = cookiesToMap(cookies);
      sendResponse({ ok: true, cookies: map, cookieString: cookiesToString(map) });
      return;
    }
    if (msg && msg.type === "set_interval") {
      const intervalMin = Number(msg.intervalMin || DEFAULT_INTERVAL_MIN);
      await chrome.storage.local.set({ intervalMin });
      await scheduleAlarm();
      sendResponse({ ok: true, intervalMin });
      return;
    }
    sendResponse({ ok: false, error: "unknown_message" });
  })();
  return true;
});
