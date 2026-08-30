const API_BASE = "";

let authToken = null;

const loginScreen = document.getElementById("login-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const logoutButton = document.getElementById("logout-button");
const hypervisorsGrid = document.getElementById("hypervisors-grid");
const vmsList = document.getElementById("vms-list");
const refreshButton = document.getElementById("refresh-button");
const activityLogButton = document.getElementById("activity-log-button");
const lastCheckLabel = document.getElementById("last-check-label");
const activityModal = document.getElementById("activity-modal");
const closeActivityModal = document.getElementById("close-activity-modal");
const activityList = document.getElementById("activity-list");
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = document.getElementById("theme-icon");

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

async function renderHypervisors(hypervisors) {
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

async function renderVMs(vms) {
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

function updateStats(hypervisors, vms) {
    document.getElementById("stat-total-vms").textContent = vms.length;
    document.getElementById("stat-running-vms").textContent = vms.filter((v) => v.state === "running").length;
    const onlineCount = hypervisors.filter((h) => h.reachable).length;
    document.getElementById("stat-hypervisors-online").textContent = `${onlineCount}/${hypervisors.length}`;
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
    const hypervisors = await apiFetch("/hypervisors");
    renderHypervisors(hypervisors);

    const vms = await apiFetch("/vms");
    renderVMs(vms);

    updateStats(hypervisors, vms);
    await loadUptime();

    lastCheckLabel.textContent = `Dernière vérification : ${new Date().toLocaleTimeString()}`;
}

function logout() {
    authToken = null;
    dashboardScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    document.getElementById("username").value = "";
    document.getElementById("password").value = "";
}

logoutButton.addEventListener("click", logout);

refreshButton.addEventListener("click", () => {
    if (authToken) {
        loadDashboard();
    }
});

activityLogButton.addEventListener("click", async () => {
    const entries = await apiFetch("/activity-log");

    activityList.innerHTML = "";

    if (entries.length === 0) {
        activityList.innerHTML = `<p class="activity-entry">Aucune action enregistrée pour l'instant.</p>`;
    } else {
        for (const entry of entries) {
            const div = document.createElement("div");
            div.className = `activity-entry ${entry.success ? "" : "failed"}`;
            const time = new Date(entry.performed_at).toLocaleString();
            div.innerHTML = `
                <div class="activity-main">${entry.username} a ${entry.action === "start" ? "démarré" : "arrêté"} ${entry.vm_id} (${entry.hypervisor}) ${entry.success ? "" : "&mdash; échec"}</div>
                <div class="activity-meta">${time}</div>
            `;
            activityList.appendChild(div);
        }
    }

    activityModal.classList.remove("hidden");
});

closeActivityModal.addEventListener("click", () => {
    activityModal.classList.add("hidden");
});

const createVmButton = document.getElementById("create-vm-button");
const createVmModal = document.getElementById("create-vm-modal");
const closeCreateVmModal = document.getElementById("close-create-vm-modal");
const createVmForm = document.getElementById("create-vm-form");
const createVmError = document.getElementById("create-vm-error");
const createVmSubmit = document.getElementById("create-vm-submit");
const vmHypervisorSelect = document.getElementById("vm-hypervisor");
const kvmFields = document.getElementById("kvm-fields");
const openstackFields = document.getElementById("openstack-fields");
const unsupportedMessage = document.getElementById("unsupported-message");

const SUPPORTED_CREATE_HYPERVISORS = ["kvm", "openstack"];

createVmButton.addEventListener("click", () => {
    createVmForm.reset();
    createVmError.textContent = "";
    kvmFields.classList.add("hidden");
    openstackFields.classList.add("hidden");
    unsupportedMessage.classList.add("hidden");
    createVmModal.classList.remove("hidden");
});

closeCreateVmModal.addEventListener("click", () => {
    createVmModal.classList.add("hidden");
});

vmHypervisorSelect.addEventListener("change", () => {
    const selected = vmHypervisorSelect.value;

    kvmFields.classList.add("hidden");
    openstackFields.classList.add("hidden");
    unsupportedMessage.classList.add("hidden");

    if (selected === "kvm") {
        kvmFields.classList.remove("hidden");
    } else if (selected === "openstack") {
        openstackFields.classList.remove("hidden");
    } else if (selected === "esxi" || selected === "hyperv") {
        unsupportedMessage.classList.remove("hidden");
    }
});

createVmForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    createVmError.textContent = "";

    const hypervisor = vmHypervisorSelect.value;
    const name = document.getElementById("vm-name").value.trim();

    if (!SUPPORTED_CREATE_HYPERVISORS.includes(hypervisor)) {
        createVmError.textContent = "La création n'est pas disponible pour cet hyperviseur.";
        return;
    }

    const payload = { name };

    if (hypervisor === "kvm") {
        const ram = document.getElementById("kvm-ram").value;
        const vcpus = document.getElementById("kvm-vcpus").value;
        if (ram) payload.ram_mb = parseInt(ram, 10);
        if (vcpus) payload.vcpus = parseInt(vcpus, 10);
    } else if (hypervisor === "openstack") {
        payload.image = document.getElementById("os-image").value;
        payload.flavor = document.getElementById("os-flavor").value;
        payload.network = document.getElementById("os-network").value;
    }

    createVmSubmit.disabled = true;
    createVmSubmit.textContent = "Création...";

    try {
        const response = await fetch(`${API_BASE}/vms/${hypervisor}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify(payload),
        });

        if (response.status === 401) {
            logout();
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            createVmError.textContent = errorData.detail || "Échec de la création de la VM.";
            return;
        }

        const result = await response.json();

        if (!result.success) {
            createVmError.textContent = "La création a échoué côté hyperviseur. Vérifiez les paramètres.";
            return;
        }

        createVmModal.classList.add("hidden");
        await loadDashboard();
    } catch (error) {
        createVmError.textContent = "Impossible de contacter le serveur.";
    } finally {
        createVmSubmit.disabled = false;
        createVmSubmit.textContent = "Créer";
    }
});

setInterval(() => {
    if (authToken) {
        loadDashboard();
    }
}, 15000);

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    themeIcon.className = theme === "light" ? "ti ti-sun" : "ti ti-moon";
    localStorage.setItem("theme", theme);
}

const savedTheme = localStorage.getItem("theme") || "dark";
applyTheme(savedTheme);

themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    applyTheme(current === "light" ? "dark" : "light");
});