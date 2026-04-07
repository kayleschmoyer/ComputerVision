const alertList = document.getElementById("alertList");
const clipPlayer = document.getElementById("clipPlayer");
const clipMeta = document.getElementById("clipMeta");

function normalizeClipPath(path) {
  if (path.startsWith("/clips/")) return path;
  const fileName = path.split("/").pop();
  return `/clips/${fileName}`;
}

function renderAlert(alert, prepend = false) {
  const li = document.createElement("li");
  li.className = "alert-item";
  li.innerHTML = `
    <strong>${alert.event_type}</strong><br />
    <small>${alert.timestamp} | Camera: ${alert.camera_id}</small><br />
    <small>${alert.details}</small>
  `;

  li.onclick = () => {
    const clipUrl = normalizeClipPath(alert.clip_path);
    clipPlayer.src = clipUrl;
    clipPlayer.play();
    clipMeta.textContent = `${alert.event_type} @ ${alert.timestamp}`;
  };

  if (prepend) {
    alertList.prepend(li);
  } else {
    alertList.appendChild(li);
  }
}

async function loadAlerts() {
  const res = await fetch("/alerts");
  const alerts = await res.json();
  alertList.innerHTML = "";
  alerts.reverse().forEach((a) => renderAlert(a));
}

function startWebSocket() {
  const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${wsProto}://${window.location.host}/ws/alerts`);

  ws.onopen = () => ws.send("subscribe");
  ws.onmessage = (evt) => {
    const alert = JSON.parse(evt.data);
    renderAlert(alert, true);
  };
  ws.onclose = () => setTimeout(startWebSocket, 2000);
}

loadAlerts();
startWebSocket();
