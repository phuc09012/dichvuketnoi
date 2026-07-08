const state = {
  runtime: null,
  latestResponse: null,
  latestTrigger: null,
  monitoring: false,
  monitorTimer: null,
  monitorBusy: false,
  autoSendBusy: false,
  liveFallbackTimer: null,
  motionAlertTimer: null,
  motionAlertMode: null,
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
  motionAlert: $("motionAlert"),
  motionAlertState: $("motionAlertState"),
  motionAlertTitle: $("motionAlertTitle"),
  motionAlertText: $("motionAlertText"),
  motionAlertLink: $("motionAlertLink"),
  motionAlertMeta: $("motionAlertMeta"),
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

function describeError(error) {
  const message = String(error?.message || error || "");
  if (message.toLowerCase().includes("timeout")) return "Request timeout, service phản hồi chậm.";
  if (message.includes("404")) return "Không thấy API, có thể sai route hoặc service chưa bật.";
  if (message.includes("503")) return "Service chưa sẵn sàng hoặc chưa cấu hình.";
  return message || "Có lỗi không xác định.";
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

function latestSnapshotUrl() {
  const snap = state.runtime?.snapshots?.recent?.[0];
  return snap?.public_url || snap?.url || null;
}

function liveStreamUrl() {
  return state.runtime?.camera?.stream_url || "/camera/live";
}

function showFallbackSnapshot(reason) {
  const fallbackUrl = latestSnapshotUrl();
  if (!fallbackUrl || els.snapshotImg.src === fallbackUrl) return;
  clearTimeout(state.liveFallbackTimer);
  els.snapshotImg.src = fallbackUrl;
  els.snapshotEmpty.style.display = "none";
  els.snapshotImg.style.display = "block";
  setStatus("Live unavailable", "error");
  setNotice(reason || "Live stream chưa phản hồi, đang hiển thị snapshot gần nhất.", "error");
  setLatestSnapshot(fallbackUrl, "Latest snapshot");
}

function showMotionAlert({ title, text, url, stateText, timeoutMs = 10000 } = {}) {
  clearTimeout(state.motionAlertTimer);
  els.motionAlert.hidden = false;
  els.motionAlertState.textContent = stateText || "Motion detected";
  els.motionAlertTitle.textContent = title || "Phát hiện chuyển động";
  els.motionAlertText.textContent = text || "Hệ thống vừa ghi nhận chuyển động và đang xử lý tiếp.";
  els.motionAlertLink.href = url || latestSnapshotUrl() || "#";
  els.motionAlertLink.textContent = url ? "Open snapshot" : "Snapshot";
  els.motionAlertMeta.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  state.motionAlertMode = stateText || "Motion detected";
  if (timeoutMs > 0) {
    state.motionAlertTimer = setTimeout(() => {
      els.motionAlert.hidden = true;
      state.motionAlertMode = null;
    }, timeoutMs);
  }
}

function updateMotionAlert({ title, text, url, stateText } = {}) {
  if (els.motionAlert.hidden) {
    showMotionAlert({ title, text, url, stateText });
    return;
  }
  if (stateText) {
    els.motionAlertState.textContent = stateText;
    state.motionAlertMode = stateText;
  }
  if (title) els.motionAlertTitle.textContent = title;
  if (text) els.motionAlertText.textContent = text;
  if (url) {
    els.motionAlertLink.href = url;
    els.motionAlertLink.textContent = "Open snapshot";
  }
  els.motionAlertMeta.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function scheduleMotionAlertHide(timeoutMs = 5000) {
  clearTimeout(state.motionAlertTimer);
  state.motionAlertTimer = setTimeout(() => {
    hideMotionAlert();
  }, timeoutMs);
}

function hideMotionAlert() {
  clearTimeout(state.motionAlertTimer);
  els.motionAlert.hidden = true;
  els.motionAlertState.textContent = "Cleared";
  els.motionAlertMeta.textContent = "--";
  state.motionAlertMode = null;
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

function buildManualTriggerFromLatestSnapshot() {
  const fallback = state.runtime?.snapshots?.recent?.[0];
  const snapshotUrl = fallback?.public_url || fallback?.url || latestSnapshotUrl();
  if (!snapshotUrl) return null;
  return {
    request_id: `vision-request-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`,
    camera_id: state.runtime?.camera?.id || "cam-gate-a",
    timestamp: new Date().toISOString(),
    location: state.runtime?.camera?.location || "Main Gate A",
    motion_detected: true,
    motion_score: 1.0,
    snapshot_url: snapshotUrl,
    snapshot_path: fallback?.path ? `snapshots/${fallback.path}` : null,
  };
}

async function requestJson(url, options = {}) {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 12000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      signal: controller.signal,
      ...options,
    });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      throw new Error(typeof payload === "string" ? payload : pretty(payload));
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`Request timeout after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function updateRuntime(runtime) {
  state.runtime = runtime;
  els.runtimeJson.textContent = pretty(runtime);
  els.localIp.textContent = runtime.local_ip || "-";
  els.cameraId.textContent = runtime.camera?.id || "-";
  const a4Service = runtime.a4?.service_url || runtime.ai?.service_url || "-";
  const a4Path = runtime.a4?.detect_path || runtime.ai?.detect_path || "/api/v1/detect";
  els.aiStatus.textContent = `${a4Service}${a4Path.startsWith("/") ? "" : "/"}${a4Path}`;
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
  if (!state.monitoring) {
    els.snapshotImg.src = liveStreamUrl();
  }
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
  const result = await requestJson("/camera/motion", { timeoutMs: 60000 });
  setResponse(result);
  if (result.snapshot_path) {
    const snapshotUrl = `/snapshots/${result.snapshot_path.replace(/\\/g, "/").replace(/^snapshots\//, "")}`;
    setLatestSnapshot(snapshotUrl, "camera.motion");
  }
  els.motionBadge.textContent = result.motion_detected
    ? `Motion: yes (${result.motion_score})`
    : `Motion: no (${result.motion_score})`;
  if (result.motion_detected) {
    showMotionAlert({
      title: "Phát hiện chuyển động",
      text: `Camera ${result.camera_id || state.runtime?.camera?.id || "-"} vừa ghi nhận motion score ${result.motion_score}.`,
      url: result.snapshot_path ? `/snapshots/${String(result.snapshot_path).replace(/\\/g, "/").replace(/^snapshots\//, "")}` : latestSnapshotUrl(),
    });
    setNotice("Phát hiện chuyển động.", "success");
  } else {
    hideMotionAlert();
    setNotice("Không phát hiện chuyển động.", "info");
  }
  await loadRuntime();
}

async function sendToAi(triggerOverride = null) {
  let trigger = triggerOverride || state.latestTrigger;
  if (!trigger) {
    trigger = buildManualTriggerFromLatestSnapshot();
  }
  if (!trigger) {
    setNotice("Chưa có snapshot sẵn, đang chụp lại từ camera...", "info");
    trigger = await requestJson("/camera/trigger", { timeoutMs: 90000 });
    state.latestTrigger = trigger;
  }
  const payload = buildDetectPayload(trigger);
  setStatus("Sending to A4...", "ok");
  setNotice("Đang gửi ảnh sang A4 AI Vision, chờ phản hồi...", "info");
  const result = await requestJson("/api/a4/detect", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: 60000,
  });
  setResponse(result);
  setStatus("Sent successfully", "ok");
  setNotice("Đã gửi thành công sang A4 AI Vision.", "success");
  return result;
}

async function monitorMotionOnce() {
  if (state.monitorBusy) return;
  state.monitorBusy = true;
  try {
    const result = await requestJson("/camera/motion", { timeoutMs: 60000 });
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
      setNotice("Phát hiện motion, đang gửi sang A4 AI Vision...", "info");
      showMotionAlert({
        stateText: "Motion detected",
        title: "Phát hiện chuyển động",
        text: `Camera ${result.camera_id || state.runtime?.camera?.id || "-"} vừa phát hiện chuyển động. Đang chuyển sang A4.`,
        url: result.snapshot_path ? `/snapshots/${String(result.snapshot_path).replace(/\\/g, "/").replace(/^snapshots\//, "")}` : latestSnapshotUrl(),
        timeoutMs: 0,
      });
      if (!state.autoSendBusy) {
        state.autoSendBusy = true;
        try {
          updateMotionAlert({
            stateText: "SENDING",
            title: "Đang gửi đến A4",
            text: "Hệ thống đang chuyển ảnh sang nhóm A4 AI Vision...",
            url: result.snapshot_path ? `/snapshots/${String(result.snapshot_path).replace(/\\/g, "/").replace(/^snapshots\//, "")}` : latestSnapshotUrl(),
          });
          const aiResult = await sendToAi(result);
          updateMotionAlert({
            stateText: "SUCCESS",
            title: "Gửi thành công đến AI Vision",
            text: `A4 AI Vision đã nhận ảnh và phản hồi với detection_id ${aiResult.detection_id || aiResult.request_id || "-"}.`,
            url: result.snapshot_path ? `/snapshots/${String(result.snapshot_path).replace(/\\/g, "/").replace(/^snapshots\//, "")}` : latestSnapshotUrl(),
          });
          scheduleMotionAlertHide(7000);
        } catch (error) {
          updateMotionAlert({
            stateText: "A4 error",
            title: "Đã phát hiện motion nhưng gửi A4 lỗi",
            text: String(error.message || error),
            url: result.snapshot_path ? `/snapshots/${String(result.snapshot_path).replace(/\\/g, "/").replace(/^snapshots\//, "")}` : latestSnapshotUrl(),
          });
          setNotice("Phát hiện motion nhưng gửi sang A4 bị lỗi.", "error");
        } finally {
          state.autoSendBusy = false;
        }
      }
    } else {
      if (!state.autoSendBusy) {
        hideMotionAlert();
      }
      setNotice("Không phát hiện chuyển động.", "info");
    }
  } catch (error) {
    setStatus("Request failed", "error");
    setNotice(String(error.message || error).includes("timeout")
      ? "Camera phản hồi chậm, thử lại sau."
      : "Không quét được motion.", "error");
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
      setNotice(describeError(error), "error");
      setResponse({ error: String(error.message || error) });
    } finally {
      btn.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const fallbackToSnapshot = (reason) => {
    const fallbackUrl = latestSnapshotUrl();
    if (fallbackUrl) {
      showFallbackSnapshot(reason);
    } else {
      els.snapshotEmpty.style.display = "grid";
      els.snapshotEmpty.textContent = reason || "Live feed chưa tải được. Kiểm tra camera stream hoặc refresh lại trang.";
    }
  };

  els.snapshotImg.addEventListener("load", () => {
    clearTimeout(state.liveFallbackTimer);
    els.snapshotImg.style.display = "block";
    els.snapshotEmpty.style.display = "none";
  });
  els.snapshotImg.addEventListener("error", () => {
    fallbackToSnapshot("Live feed chưa tải được. Kiểm tra camera stream hoặc refresh lại trang.");
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

  setStatus("Loading dashboard...", "ok");
  setNotice("Dashboard đang mở, các dữ liệu nạp sau trong nền.", "info");
  hideMotionAlert();

  loadRuntime()
    .catch((error) => {
      setStatus("Runtime unavailable", "error");
      setNotice(describeError(error), "error");
      setResponse({ error: `runtime: ${String(error.message || error)}` });
    })
    .then(() => {
      if (state.runtime) {
        els.snapshotImg.src = liveStreamUrl();
        setLatestSnapshot(liveStreamUrl(), "Live feed");
      }
    });

  loadHealth().catch((error) => {
    setNotice(describeError(error), "error");
  });

  loadSnapshots().catch((error) => {
    setNotice(`Snapshots chưa sẵn sàng: ${describeError(error)}`, "error");
  });

  startLiveMonitor();
  state.liveFallbackTimer = setTimeout(() => {
    const liveStillPending = els.snapshotImg.getAttribute("src") === liveStreamUrl() && !els.snapshotImg.naturalWidth;
    if (liveStillPending) {
      fallbackToSnapshot("Camera stream chưa phản hồi, đang hiển thị ảnh snapshot gần nhất.");
    }
  }, 7000);

  setInterval(() => {
    loadRuntime().catch(() => {});
  }, 30000);
});
