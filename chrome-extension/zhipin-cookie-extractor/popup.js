const statusEl = document.getElementById("status");
const intervalSelect = document.getElementById("interval");
const tokenInput = document.getElementById("token");

function setStatus(text) {
  statusEl.textContent = text;
}

function sendMessage(msg) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(msg, (response) => resolve(response));
  });
}

function formatTime(ts) {
  if (!ts) return "never";
  const d = new Date(ts);
  return d.toLocaleString();
}

async function refreshStatus() {
  const resp = await sendMessage({ type: "get_status" });
  if (!resp || !resp.ok) {
    setStatus("status: unavailable");
    return;
  }
  const lastSync = formatTime(resp.lastSync);
  const error = resp.lastError ? `error: ${resp.lastError}` : "error: none";
  setStatus(`last sync: ${lastSync}\n${error}`);
  if (resp.intervalMin) {
    intervalSelect.value = String(resp.intervalMin);
  }
  if (resp.token) {
    tokenInput.value = resp.token;
  }
}

document.getElementById("sync").addEventListener("click", async () => {
  setStatus("syncing...");
  const resp = await sendMessage({ type: "sync" });
  if (resp && resp.ok) {
    setStatus(`synced: ${resp.cookieCount} cookies\nlast sync: ${formatTime(resp.lastSync)}`);
  } else {
    setStatus(`sync failed: ${resp && resp.error ? resp.error : "unknown"}`);
  }
});

document.getElementById("copy").addEventListener("click", async () => {
  const resp = await sendMessage({ type: "get_cookies" });
  if (!resp || !resp.ok) {
    setStatus("copy failed: no cookies");
    return;
  }
  await navigator.clipboard.writeText(resp.cookieString || "");
  setStatus("cookie copied to clipboard");
});

document.getElementById("export").addEventListener("click", async () => {
  const resp = await sendMessage({ type: "get_cookies" });
  if (!resp || !resp.ok) {
    setStatus("export failed: no cookies");
    return;
  }
  const blob = new Blob([JSON.stringify({ cookies: resp.cookies }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download({
    url,
    filename: "zhipin-cookies.json",
    saveAs: true,
  });
  setStatus("exported cookies as JSON");
});

intervalSelect.addEventListener("change", async (e) => {
  const val = Number(e.target.value);
  await sendMessage({ type: "set_interval", intervalMin: val });
  setStatus(`auto-refresh set to ${val} min`);
});

tokenInput.addEventListener("change", async (e) => {
  const val = e.target.value || "";
  await sendMessage({ type: "set_token", token: val });
  setStatus("token updated");
});

tokenInput.addEventListener("keyup", async (e) => {
  if (e.key !== "Enter") return;
  const val = e.target.value || "";
  await sendMessage({ type: "set_token", token: val });
  setStatus("token updated");
});

refreshStatus();
