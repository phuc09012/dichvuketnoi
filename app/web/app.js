const state = {
  runtime: null,
  lastResult: null,
  lastTrigger: null,
};

const $ = (id) => document.getElementById(id);

const els = {
  statusChip: $("statusChip"),
  localIp: $("localIp"),
  cameraId: $("cameraId"),
  aiStatus: $("aiStatus"),
  mqttStatus: $("mqttStatus"),
  motionThreshold: $("motionThreshold"),
  cooldown: $("cooldown"),
  publicBase: $("publicBase"),
  lastEvent: $("lastEvent"),
  motionState: $("motionState"),
  snapshotImg: $("snapshotImg"),
  snapshotEmpty: $("snapshotEmpty"),
  snapshotLink: $("snapshotLink"),
  runtimeJson: $("runtimeJson"),
  responseJson: $("responseJson"),
  snapshotGrid: $("snapshotGrid"),
  snapshotCount: $("snapshotCount"),
  detectInput: $("detectInput"),
  peersInput: $("peersInput"),
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setResult(value) {
  state.lastResult = value;
  els.responseJson.textContent = typeof value === "string" ? value : pretty(value);
}

function setStatus(text, kind = "ok") {
  els.statusChip.textContent = text;
  els.statusChip.classList.toggle("error", kind === "error");
}

function setSnapshot(url, label = "Latest snapshot") {
  if (!url) {
    els.snapshotImg.style.display = "none";
    els.snapshotEmpty.style.display = "block";
    els.snapshotLink.textContent = "-";
    els.snapshotLink.href = "#";
    return;
  }
  els.snapshotImg.src = url;
  els.snapshotImg.style.display = "block";
  els.snapshotEmpty.style.display = "none";
  els.snapshotLink.textContent = url;
  els.snapshotLink.href = url;
  els.lastEvent.textContent = label;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(typeof payload === "string" ? payload : pretty(payload));
  }
  return payload;
}

function updateSummary(runtime) {
  state.runtime = runtime;
  els.runtimeJson.textContent = pretty(runtime);
  els.localIp.textContent = runtime.local_ip || "-";
  els.cameraId.textContent = runtime.camera?.id || "-";
  els.aiStatus.textContent = runtime.ai?.service_url || "-";
  els.mqttStatus.textContent = runtime.mqtt?.enabled ? `${runtime.mqtt.broker_host || "-"}:${runtime.mqtt.broker_port}` : "disabled";
  els.motionThreshold.textContent = runtime.camera?.motion_threshold ?? "-";
  els.cooldown.textContent = runtime.ai?.cooldown_seconds ?? "-";
  els.publicBase.textContent = runtime.network?.public_base_url || "-";
  els.detectInput.value = pretty({
    request_id: "vision-request-demo",
    camera_id: runtime.camera?.id || "cam-gate-a",
    timestamp: new Date().toISOString(),
    location: runtime.camera?.location || "Main Gate A",
    motion_detected: true,
    motion_score: 0.82,
    image_url: runtime.snapshots?.recent?.[0]?.public_url || runtime.snapshots?.recent?.[0]?.url || "",
  });
}

async function refreshRuntime() {
  const runtime = await requestJson("/api/runtime");
  updateSummary(runtime);
  await loadSnapshots();
  setStatus("Dashboard ready", "ok");
}

async function loadHealth() {
  const health = await requestJson("/health");
  setStatus(`Healthy: ${health.service}`, "ok");
  setResult(health);
}

async function loadPeers() {
  const peers = await requestJson("/peers");
  setResult(peers);
  return peers;
}

async function loadSnapshots() {
  const payload = await requestJson("/api/snapshots?limit=12");
  const items = payload.items || [];
  els.snapshotCount.textContent = `${items.length} items`;
  els.snapshotGrid.innerHTML = "";
  if (!items.length) {
    els.snapshotGrid.innerHTML = `<div class="muted">Chưa có snapshot nào.</div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const link = document.createElement("a");
    link.className = "snapshot-item";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.innerHTML = `
      <img src="${item.url}" alt="${item.name}" loading="lazy" />
      <div class="snapshot-caption">
        <strong>${item.name}</strong>
        <span>${item.modified_at}</span>
      </div>
    `;
    link.addEventListener("click", () => setSnapshot(item.url, item.name));
    fragment.appendChild(link);
  }
  els.snapshotGrid.appendChild(fragment);
}

async function triggerCamera() {
  setStatus("Triggering camera...", "ok");
  const trigger = await requestJson("/camera/trigger");
  state.lastTrigger = trigger;
  setResult(trigger);
  const snapshotUrl = trigger.snapshot_url || trigger.probe?.snapshot_path || null;
  setSnapshot(snapshotUrl, `${trigger.event_type} • ${trigger.request_id}`);
  if (trigger.motion_detected !== undefined) {
    els.motionState.textContent = trigger.motion_detected ? `Motion ${trigger.motion_score}` : `No motion (${trigger.motion_score})`;
  } else if (trigger.probe) {
    els.motionState.textContent = trigger.probe.motion_detected ? `Motion ${trigger.probe.motion_score}` : `No motion (${trigger.probe.motion_score})`;
  }
  await refreshRuntime();
}

async function cameraCheck() {
  const result = await requestJson("/camera/check");
  setResult(result);
  if (result.snapshot_path) {
    setSnapshot(`/snapshots/${result.snapshot_path.replace(/\\/g, "/").replace(/^snapshots\//, "")}`, "camera.check");
  }
  await refreshRuntime();
}

async function motionScan() {
  const result = await requestJson("/camera/motion");
  setResult(result);
  if (result.snapshot_path) {
    setSnapshot(`/snapshots/${result.snapshot_path.replace(/\\/g, "/").replace(/^snapshots\//, "")}`, "camera.motion");
  }
  els.motionState.textContent = result.motion_detected ? `Motion ${result.motion_score}` : `No motion (${result.motion_score})`;
  await refreshRuntime();
}

async function peerCheck() {
  const peers = JSON.parse(els.peersInput.value || "[]");
  const result = await requestJson("/peer-check", {
    method: "POST",
    body: JSON.stringify({ peers }),
  });
  setResult(result);
}

async function sendDetect() {
  const payload = JSON.parse(els.detectInput.value);
  if (!payload.image_url && !payload.snapshot_url && !payload.image_base64) {
    const latest = state.lastTrigger?.snapshot_url || state.runtime?.snapshots?.recent?.[0]?.public_url || state.runtime?.snapshots?.recent?.[0]?.url;
    payload.image_url = latest;
  }
  const result = await requestJson("/detect", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setResult(result);
}

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function bindButton(id, handler) {
  const element = $(id);
  if (!element) return;
  element.addEventListener("click", async () => {
    element.disabled = true;
    try {
      await handler();
    } catch (error) {
      setStatus("Request failed", "error");
      setResult({ error: String(error.message || error) });
    } finally {
      element.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindButton("refreshBtn", refreshRuntime);
  bindButton("triggerBtn", triggerCamera);
  bindButton("motionBtn", motionScan);
  bindButton("cameraCheckBtn", cameraCheck);
  bindButton("peerBtn", loadPeers);
  bindButton("runPeerCheck", peerCheck);
  bindButton("runDetect", sendDetect);
  bindButton("detectBtn", sendDetect);
  bindButton("snapshotsBtn", loadSnapshots);
  bindButton("copyPayload", () => copyText(els.detectInput.value));
  bindButton("copyResult", () => copyText(els.responseJson.textContent));

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        switch (button.dataset.action) {
          case "health":
            await loadHealth();
            break;
          case "trigger":
            await triggerCamera();
            break;
          case "motion":
            await motionScan();
            break;
          case "detect":
            await sendDetect();
            break;
          case "peercheck":
            await peerCheck();
            break;
          case "snapshots":
            await loadSnapshots();
            break;
        }
      } catch (error) {
        setStatus("Request failed", "error");
        setResult({ error: String(error.message || error) });
      } finally {
        button.disabled = false;
      }
    });
  });

  try {
    await refreshRuntime();
    await loadHealth();
    await loadPeers();
  } catch (error) {
    setStatus("Startup failed", "error");
    setResult({ error: String(error.message || error) });
  }

  setInterval(() => {
    if (state.runtime) {
      refreshRuntime().catch(() => {});
    }
  }, 30000);
});
