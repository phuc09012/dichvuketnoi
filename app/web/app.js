const state = {
  runtime: null,
  latestResponse: null,
  latestTrigger: null,
  monitoring: false,
  monitorTimer: null,
  monitorBusy: false,
  autoSendBusy: false,
};

const $ = (id) => document.getElementById(id);

const els = {
  statusPill: $("statusPill"),
  noticeBar: $("noticeBar"),
  localIp: $("localIp"),
  cameraId: $("cameraId"),
  aiStatus: $("aiStatus"),
  motionThreshold: $("motionThreshold"),
  cooldown: $("cooldown"),
  publicBase: $("publicBase"),
  mqttBadge: $("mqttBadge"),
  motionBadge: $("motionBadge"),
  lastEvent: $("lastEvent"),
  snapshotImg: $("snapshotImg"),
  snapshotEmpty: $("snapshotEmpty"),
  snapshotLink: $("snapshotLink"),
  runtimeJson: $("runtimeJson"),
  responseJson: $("responseJson"),
  snapshotGrid: $("snapshotGrid"),
  snapshotCount: $("snapshotCount"),
  peersInput: $("peersInput"),
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setResponse(value) {
  state.latestResponse = value;
  els.responseJson.textContent = typeof value === "string" ? value : pretty(value);
}

function setStatus(text, kind = "ok") {
  els.statusPill.textContent = text;
  els.statusPill.classList.toggle("error", kind === "error");
}

function setNotice(text, kind = "info") {
  els.noticeBar.textContent = text;
  els.noticeBar.classList.toggle("success", kind === "success");
  els.noticeBar.classList.toggle("error", kind === "error");
  els.noticeBar.classList.toggle("info", kind === "info");
}

function setLatestSnapshot(url, label) {
  if (!url) {
    els.snapshotLink.textContent = "-";
    els.snapshotLink.href = "#";
    els.lastEvent.textContent = "-";
    return;
  }
  els.snapshotLink.textContent = url;
  els.snapshotLink.href = url;
  els.lastEvent.textContent = label || "-";
}

function buildDetectPayload(trigger) {
  const fallback = state.runtime?.snapshots?.recent?.[0];
  const snapshotUrl = trigger?.snapshot_url || fallback?.public_url || fallback?.url;
  const snapshotPath = trigger?.snapshot_path || trigger?.probe?.snapshot_path || null;
  return {
    request_id: trigger?.request_id || "vision-request-demo",
    camera_id: trigger?.camera_id || state.runtime?.camera?.id || "cam-gate-a",
    timestamp: trigger?.timestamp || new Date().toISOString(),
    location: trigger?.location || state.runtime?.camera?.location || "Main Gate A",
    motion_detected: true,
    motion_score: trigger?.motion_score ?? trigger?.probe?.motion_score ?? 0.0,
    snapshot_url: snapshotUrl,
    snapshot_path: snapshotPath,
  };
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

function updateRuntime(runtime) {
  state.runtime = runtime;
  els.runtimeJson.textContent = pretty(runtime);
  els.localIp.textContent = runtime.local_ip || "-";
  els.cameraId.textContent = runtime.camera?.id || "-";
  els.aiStatus.textContent = runtime.ai?.service_url || "-";
  els.motionThreshold.textContent = runtime.camera?.motion_threshold ?? "-";
  els.cooldown.textContent = runtime.ai?.cooldown_seconds ?? "-";
  els.publicBase.textContent = runtime.network?.public_base_url || "-";
  els.mqttBadge.textContent = runtime.mqtt?.enabled
    ? `MQTT: ${runtime.mqtt.broker_host || "-"}:${runtime.mqtt.broker_port}`
    : "MQTT: off";
  const snap = runtime.snapshots?.recent?.[0];
  if (snap) {
    const url = snap.public_url || snap.url;
    setLatestSnapshot(url, snap.name);
  }
  els.motionBadge.textContent = runtime.camera?.motion_threshold != null
    ? `Threshold ${runtime.camera.motion_threshold}`
    : "Motion: -";
}

async function loadRuntime() {
  const runtime = await requestJson("/api/runtime");
  updateRuntime(runtime);
  return runtime;
}

async function loadHealth() {
  const health = await requestJson("/health");
  setStatus(`Healthy: ${health.service}`, "ok");
  setNotice("Service đang hoạt động bình thường.", "info");
  setResponse(health);
}

async function loadSnapshots() {
  const payload = await requestJson("/api/snapshots?limit=12");
  const items = payload.items || [];
  els.snapshotCount.textContent = `${items.length} items`;
  els.snapshotGrid.innerHTML = "";
  if (!items.length) {
    els.snapshotGrid.innerHTML = `<div class="muted">Chưa có snapshot.</div>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const link = document.createElement("a");
    link.className = "snap";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.innerHTML = `
      <img src="${item.url}" alt="${item.name}" loading="lazy" />
      <div class="snap-meta">
        <strong>${item.name}</strong>
        <span>${item.modified_at}</span>
      </div>
    `;
    link.addEventListener("click", () => setLatestSnapshot(item.url, item.name));
    fragment.appendChild(link);
  }
  els.snapshotGrid.appendChild(fragment);
}

async function captureCamera() {
  setStatus("Capturing...", "ok");
  setNotice("Đang chụp ảnh từ camera...", "info");
  const trigger = await requestJson("/camera/trigger");
  state.latestTrigger = trigger;
  setResponse(trigger);
  const snapshotUrl = trigger.snapshot_url || trigger.probe?.snapshot_path;
  setLatestSnapshot(snapshotUrl, `${trigger.event_type} • ${trigger.request_id}`);
  const motionDetected = trigger.motion_detected ?? trigger.probe?.motion_detected;
  const score = trigger.motion_score ?? trigger.probe?.motion_score;
  els.motionBadge.textContent = motionDetected === undefined
    ? "Motion: -"
    : motionDetected
      ? `Motion: yes (${score})`
      : `Motion: no (${score})`;
  await loadRuntime();
}

async function runMotionScan() {
  setStatus("Scanning motion...", "ok");
  setNotice("Đang quét motion...", "info");
  const result = await requestJson("/camera/motion");
  setResponse(result);
  if (result.snapshot_path) {
    setLatestSnapshot(`/snapshots/${result.snapshot_path.replace(/\\/g, "/").replace(/^snapshots\//, "")}`, "camera.motion");
  }
  els.motionBadge.textContent = result.motion_detected
    ? `Motion: yes (${result.motion_score})`
    : `Motion: no (${result.motion_score})`;
  await loadRuntime();
}

async function sendToAi(triggerOverride = null) {
  const trigger = triggerOverride || state.latestTrigger || await requestJson("/camera/trigger");
  const payload = buildDetectPayload(trigger);
  setStatus("Sending to AI...", "ok");
  setNotice("Đang gửi ảnh sang AI Vision...", "info");
  const result = await requestJson("/detect", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setResponse(result);
  setStatus("Sent successfully", "ok");
  setNotice("Đã gửi thành công sang AI Vision.", "success");
  return result;
}

async function monitorMotionOnce() {
  if (state.monitorBusy) return;
  state.monitorBusy = true;
  try {
    const result = await requestJson("/camera/motion");
    state.latestTrigger = result;
    setResponse(result);
    if (result.snapshot_path) {
      setLatestSnapshot(`/snapshots/${result.snapshot_path.replace(/\\/g, "/").replace(/^snapshots\//, "")}`, "camera.motion");
    }
    els.motionBadge.textContent = result.motion_detected
      ? `Motion: yes (${result.motion_score})`
      : `Motion: no (${result.motion_score})`;
    if (result.motion_detected) {
      setStatus("Motion detected", "ok");
      setNotice("Phát hiện motion, đang gửi sang AI Vision...", "info");
      if (!state.autoSendBusy) {
        state.autoSendBusy = true;
        try {
          await sendToAi(result);
        } finally {
          state.autoSendBusy = false;
        }
      }
    }
  } catch (error) {
    setStatus("Request failed", "error");
    setNotice("Không quét được motion.", "error");
    setResponse({ error: String(error.message || error) });
  } finally {
    state.monitorBusy = false;
  }
}

function startLiveMonitor() {
  if (state.monitoring) return;
  state.monitoring = true;
  setStatus("Live", "ok");
  setNotice("Camera đang chạy live, tự quét motion và tự gửi khi có chuyển động.", "info");
  monitorMotionOnce();
  state.monitorTimer = setInterval(() => {
    monitorMotionOnce();
  }, 5000);
}

async function peerCheck() {
  const peers = JSON.parse(els.peersInput.value || "[]");
  const result = await requestJson("/peer-check", {
    method: "POST",
    body: JSON.stringify({ peers }),
  });
  setResponse(result);
  setNotice("Peer check đã chạy xong.", "success");
}

function copyJson() {
  navigator.clipboard.writeText(els.responseJson.textContent).catch(() => {});
}

function wireButton(id, handler) {
  const btn = $(id);
  if (!btn) return;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await handler();
    } catch (error) {
      setStatus("Request failed", "error");
      setNotice("Có lỗi khi gửi hoặc gọi API.", "error");
      setResponse({ error: String(error.message || error) });
    } finally {
      btn.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  els.snapshotImg.src = "/camera/live";
  els.snapshotImg.addEventListener("load", () => {
    els.snapshotImg.style.display = "block";
    els.snapshotEmpty.style.display = "none";
  });
  els.snapshotImg.addEventListener("error", () => {
    els.snapshotEmpty.style.display = "block";
    els.snapshotEmpty.innerHTML = "Live feed chưa tải được. Kiểm tra camera stream hoặc refresh lại trang.";
  });

  wireButton("captureBtn", captureCamera);
  wireButton("motionBtn", runMotionScan);
  wireButton("sendAiBtn", sendToAi);
  wireButton("refreshBtn", async () => {
    await loadRuntime();
    await loadHealth();
    await loadSnapshots();
  });
  wireButton("peerCheckBtn", peerCheck);
  wireButton("loadSnapshotsBtn", loadSnapshots);
  wireButton("copyResultBtn", copyJson);

  try {
    await loadRuntime();
    await loadHealth();
    await loadSnapshots();
    setLatestSnapshot("/camera/live", "Live feed");
    startLiveMonitor();
  } catch (error) {
    setStatus("Startup failed", "error");
    setNotice("Không khởi động được dashboard.", "error");
    setResponse({ error: String(error.message || error) });
  }

  setInterval(() => {
    loadRuntime().catch(() => {});
  }, 30000);
});
