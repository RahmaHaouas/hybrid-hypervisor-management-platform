const API_BASE = "";

let authToken = null;

const loginScreen = document.getElementById("login-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const logoutButton = document.getElementById("logout-button");
const hypervisorsGrid = document.getElementById("hypervisors-grid");
const vmsList = document.getElementById("vms-list");

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.textContent = "";

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    try {
        const response = await fetch(`${API_BASE}/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData,
        });

        if (!response.ok) {
            loginError.textContent = "Identifiants invalides";
            return;
        }

        const data = await response.json();
        authToken = data.access_token;

        loginScreen.classList.add("hidden");
        dashboardScreen.classList.remove("hidden");

        loadDashboard();
    } catch (error) {
        loginError.textContent = "Impossible de contacter le serveur";
    }
});

async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${authToken}`,
        },
    });

    if (response.status === 401) {
        logout();
        throw new Error("Session expirée");
    }

    return response.json();
}

async function loadHypervisors() {
    const hypervisors = await apiFetch("/hypervisors");

    hypervisorsGrid.innerHTML = "";

    for (const hv of hypervisors) {
        const card = document.createElement("div");
        card.className = `hypervisor-card ${hv.reachable ? "online" : "offline"}`;
        card.innerHTML = `
            <div class="name">${hv.hypervisor}</div>
            <div class="status">
                <span class="status-dot ${hv.reachable ? "online" : "offline"}"></span>
                ${hv.reachable ? "En ligne" : "Hors ligne"}
            </div>
        `;
        hypervisorsGrid.appendChild(card);
    }
}

async function loadVMs() {
    const vms = await apiFetch("/vms");

    vmsList.innerHTML = "";

    for (const vm of vms) {
        const row = document.createElement("div");
        row.className = "vm-row";

        const isRunning = vm.state === "running";
        const actionLabel = isRunning ? "Stop" : "Start";
        const actionClass = isRunning ? "" : "start";
        const actionEndpoint = isRunning ? "stop" : "start";

        row.innerHTML = `
            <div>
                <div class="vm-name">${vm.name}</div>
                <div class="vm-meta">${vm.hypervisor}${vm.ip_address ? " &middot; " + vm.ip_address : ""}</div>
            </div>
            <div class="vm-actions">
                <span class="badge ${vm.state}">${vm.state}</span>
                <button class="action-button ${actionClass}" data-hypervisor="${vm.hypervisor}" data-vmid="${vm.id}" data-action="${actionEndpoint}">
                    ${actionLabel}
                </button>
            </div>
        `;
        vmsList.appendChild(row);
    }

    document.querySelectorAll(".action-button").forEach((button) => {
        button.addEventListener("click", handleVmAction);
    });
}

async function handleVmAction(event) {
    const button = event.currentTarget;
    const { hypervisor, vmid, action } = button.dataset;

    button.disabled = true;
    button.textContent = "...";

    try {
        await apiFetch(`/vms/${hypervisor}/${vmid}/${action}`, { method: "POST" });
        await loadVMs();
    } catch (error) {
        button.disabled = false;
        button.textContent = action === "start" ? "Start" : "Stop";
    }
}

async function loadUptime() {
    const points = await apiFetch("/uptime");
    const chartContainer = document.getElementById("uptime-chart");

    if (points.length === 0) {
        chartContainer.innerHTML = `<p class="uptime-summary">Pas encore assez de données. L'historique se construit automatiquement toutes les 60 secondes.</p>`;
        return;
    }

    const width = 600;
    const height = 80;
    const padding = 6;

    const byTime = {};
    for (const point of points) {
        if (!byTime[point.checked_at]) byTime[point.checked_at] = [];
        byTime[point.checked_at].push(point.reachable);
    }

    const timestamps = Object.keys(byTime).sort();
    const ratios = timestamps.map((t) => {
        const values = byTime[t];
        return values.filter(Boolean).length / values.length;
    });

    const stepX = (width - padding * 2) / Math.max(ratios.length - 1, 1);

    const coords = ratios.map((ratio, i) => {
        const x = padding + i * stepX;
        const y = height - padding - ratio * (height - padding * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const avgAvailability = Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 100);
    const incidents = ratios.filter((r) => r < 1).length;

    const dotsSvg = ratios
        .map((ratio, i) => {
            if (ratio === 1) return "";
            const x = padding + i * stepX;
            const y = height - padding - ratio * (height - padding * 2);
            const color = ratio === 0 ? "#e24b4a" : "#e8792c";
            return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${color}" />`;
        })
        .join("");

    chartContainer.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}">
            <polyline points="${coords.join(" ")}" fill="none" stroke="#4caf7d" stroke-width="2" />
            ${dotsSvg}
        </svg>
        <p class="uptime-summary">Disponibilité moyenne : ${avgAvailability}% &middot; ${incidents} vérification(s) avec incident</p>
    `;
}


async function loadDashboard() {
    await loadHypervisors();
    await loadVMs();
     await loadUptime();
}

function logout() {
    authToken = null;
    dashboardScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    document.getElementById("username").value = "";
    document.getElementById("password").value = "";
}

logoutButton.addEventListener("click", logout);

setInterval(() => {
    if (authToken) {
        loadDashboard();
    }
}, 15000);