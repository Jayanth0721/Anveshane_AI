const API_BASE = "/api";
const SUPPORT_TICKETS_KEY = "anveshane_support_tickets";
const SIDEBAR_STATE_KEY = "anveshane_sidebar_collapsed";
const THEME_STATE_KEY = "anveshane_theme";
const TROUBLESHOOT_STATUS_KEY = "anveshane_troubleshoot_status";
const SESSION_LOGS_KEY = "anveshane_session_logs";
const SESSION_STARTED_AT_KEY = "anveshane_session_started_at";
const RECENT_FEATURES_KEY = "anveshane_recent_features";
const SESSION_LOG_LIMIT = 400;

let currentToken = null;
let currentUser = null;
let currentPage = "dashboard";
let cachedTenders = [];
let cachedCitizenTenders = [];
let cachedCitizenStatsFilters = null;
let currentEvaluationsTenderId = "";
let sidebarCollapsed = false;
let currentTheme = "light";
let contractorAnalysisState = {
    fileId: "",
    fileName: "",
    result: null,
    isUploading: false,
    isAnalyzing: false,
};

let sessionPagination = {
    currentPage: 0,
    pageSize: 10
};

function el(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatDate(value) {
    if (!value) return "Not specified";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatDecision(decision) {
    const text = (decision || "pending").replace(/_/g, " ").toLowerCase();
    return text.replace(/\b\w/g, char => char.toUpperCase());
}

function formatCurrencyINR(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0) return "Not available";
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
    }).format(amount);
}

function formatDurationFromMs(durationMs) {
    const totalMinutes = Math.max(0, Math.floor(Number(durationMs || 0) / 60000));
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    const parts = [];

    if (days) parts.push(`${days}d`);
    if (hours) parts.push(`${hours}h`);
    if (minutes || !parts.length) parts.push(`${minutes}m`);

    return parts.join(" ");
}

function decisionBadgeClass(decision) {
    const map = {
        ELIGIBLE: "badge-eligible",
        NOT_ELIGIBLE: "badge-not-eligible",
        MANUAL_REVIEW: "badge-manual-review",
        pending: "badge-pending",
        active: "badge-active",
        closed: "badge-manual-review",
        published: "badge-eligible",
    };
    return map[decision] || map[String(decision || "").toLowerCase()] || "badge-pending";
}

function showToast(title, body = "") {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
        <div class="toast-title">${escapeHtml(title)}</div>
        <div class="toast-body">${escapeHtml(body)}</div>
        <button class="toast-dismiss" type="button">Dismiss</button>
    `;
    toast.querySelector(".toast-dismiss").addEventListener("click", () => toast.remove());
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3800);
}

function tok() {
    return currentToken || localStorage.getItem("access_token") || "";
}

function apiUrl(path) {
    return `${API_BASE}${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(tok())}`;
}

function handleAuthFailure() {
    if (!tok()) return;
    logout();
    setFormError("login-form", "Your session expired. Please sign in again.");
}

async function apiFetch(path, options = {}) {
    const response = await fetch(apiUrl(path), options);
    if (response.status === 401) handleAuthFailure();
    return response;
}

async function parseApiResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        return response.json();
    }
    return response.text();
}

function formatApiError(payload) {
    if (!payload) return "Request failed";
    if (typeof payload === "string") return payload;
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
        return payload.detail.map(item => `${item.loc.join(".")}: ${item.msg}`).join("\n");
    }
    return payload.message || JSON.stringify(payload);
}

async function apiGet(path) {
    const response = await apiFetch(path);
    const payload = await parseApiResponse(response);
    if (!response.ok) throw new Error(formatApiError(payload));
    return payload;
}

async function apiPostJson(path, body) {
    const response = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const payload = await parseApiResponse(response);
    if (!response.ok) throw new Error(formatApiError(payload));
    return payload;
}

async function apiPutJson(path, body) {
    const response = await apiFetch(path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const payload = await parseApiResponse(response);
    if (!response.ok) throw new Error(formatApiError(payload));
    return payload;
}

async function apiPostForm(path, formData) {
    const response = await apiFetch(path, {
        method: "POST",
        body: formData,
    });
    const payload = await parseApiResponse(response);
    if (!response.ok) throw new Error(formatApiError(payload));
    return payload;
}

document.addEventListener("DOMContentLoaded", () => {
    initEventListeners();
    initApp();
});

function initEventListeners() {
    el("login-form")?.addEventListener("submit", doLogin);
    el("register-form")?.addEventListener("submit", doRegister);
    el("submit-form")?.addEventListener("submit", doSubmitBid);
    el("create-tender-form")?.addEventListener("submit", doCreateTender);
    el("profile-settings-form")?.addEventListener("submit", saveProfileSettings);
    el("theme-settings-form")?.addEventListener("submit", saveThemeSettings);
    el("settings-theme")?.addEventListener("change", event => applyTheme(event.target.value));
    el("global-search-input")?.addEventListener("input", handleGlobalSearchInput);
    el("global-search-input")?.addEventListener("focus", handleGlobalSearchInput);
    el("global-search-input")?.addEventListener("keydown", handleGlobalSearchKeydown);
    el("submit-file")?.addEventListener("change", event => {
        const fileName = event.target.files?.[0]?.name || "No file chosen";
        el("submit-file-name").textContent = fileName;
    });
    el("tender-file")?.addEventListener("change", event => {
        const fileName = event.target.files?.[0]?.name || "No file chosen";
        el("tender-file-name").textContent = fileName;
    });
    document.addEventListener("click", event => {
        if (event.target.classList.contains("modal-overlay")) {
            closeModal(event.target.id);
        }
        if (!event.target.closest(".topbar-search")) {
            hideGlobalSearchResults();
        }
    });
}

function setCurrentUser(user, token) {
    currentUser = user || null;
    currentToken = token || currentToken;

    if (user && token) {
        localStorage.setItem("access_token", token);
        localStorage.setItem("user_data", JSON.stringify(user));
    }

    if (!user) return;

    if (el("user-name")) el("user-name").textContent = user.full_name || user.username || user.email || "User";
    if (el("user-role")) el("user-role").textContent = formatDecision(user.role);
    if (el("user-role-note")) {
        el("user-role-note").textContent = user.company_name || (
            user.role === "admin" ? "Admin workspace" :
            user.role === "citizen" ? "Citizen access" :
            "Contractor workspace"
        );
    }
    if (el("user-avatar")) {
        el("user-avatar").innerHTML = getRoleAvatar(user.role);
    }
    populateProfileSettingsForm();
}

function clearLoginFields() {
    const email = el("login-email");
    const pass = el("login-password");
    if (email) email.value = "";
    if (pass) pass.value = "";
}

function setupAuthAnimation() {
    const container = document.querySelector(".auth-form-side");
    const inputs = document.querySelectorAll("#login-form input, #register-form input, #register-form select");
    
    if (!container) return;

    inputs.forEach(input => {
        input.addEventListener("input", () => {
            container.classList.add("is-typing");
            // Remove after a short delay of inactivity
            if (input.typingTimeout) clearTimeout(input.typingTimeout);
            input.typingTimeout = setTimeout(() => {
                container.classList.remove("is-typing");
            }, 1000);
        });
        
        input.addEventListener("focus", () => {
            container.classList.add("is-typing");
        });
        
        input.addEventListener("blur", () => {
            container.classList.remove("is-typing");
        });
    });
}

async function initApp() {
    const storedToken = localStorage.getItem("access_token");
    if (!storedToken) {
        showAuth();
        return;
    }

    currentToken = storedToken;
    
    // Clear login fields on load
    clearLoginFields();
    // Setup Auth Typing Animation
    setupAuthAnimation();

    const storedUser = localStorage.getItem("user_data");
    if (storedUser) {
        try {
            setCurrentUser(JSON.parse(storedUser), storedToken);
        } catch (_error) {
            localStorage.removeItem("user_data");
        }
    }

    try {
        const user = await apiGet("/auth/me");
        setCurrentUser(user, storedToken);
        ensureSessionStart();
        logSessionEvent("session_restored", "Session history loaded from existing sign-in.");
    } catch (_error) {
        logout();
        return;
    }

    applySidebarState(localStorage.getItem(SIDEBAR_STATE_KEY) === "true");
    applyTheme(localStorage.getItem(THEME_STATE_KEY) || "light");
    setupUIForRole(currentUser.role);
    showDashboard();
    await refreshCurrentPage();
}

function getRoleAvatar(role) {
    const icons = {
        admin: `<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        contractor: `<svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/></svg>`,
        citizen: `<svg viewBox="0 0 24 24"><path d="M12 2l8 4v6c0 5.2-3.4 8.8-8 10-4.6-1.2-8-4.8-8-10V6l8-4z"/><circle cx="12" cy="10" r="2.5"/><path d="M8.5 16a4.5 4.5 0 0 1 7 0"/></svg>`,
    };
    return icons[role] || icons.contractor;
}

function showAuth() {
    el("auth-container")?.classList.remove("hidden");
    el("dashboard-container")?.classList.add("hidden");
    el("login-page")?.classList.remove("hidden");
    el("register-page")?.classList.add("hidden");
}

function showDashboard() {
    el("auth-container")?.classList.add("hidden");
    el("dashboard-container")?.classList.remove("hidden");
    activatePage(currentPage || getDefaultPageForRole(currentUser?.role));
}

function toggleAuthPage() {
    el("login-page")?.classList.toggle("hidden");
    el("register-page")?.classList.toggle("hidden");
    return false;
}

async function doLogin(event) {
    event.preventDefault();
    clearFormError("login-form");
    try {
        const payload = await apiPostJson("/auth/login", {
            email: el("login-email").value,
            password: el("login-password").value,
        });
        setCurrentUser(payload.user, payload.access_token);
        startSessionTimer();
        logSessionEvent("login", "User signed in successfully.");
        setupUIForRole(currentUser.role);
        showDashboard();
        await refreshCurrentPage();
    } catch (error) {
        setFormError("login-form", error.message || "Login failed");
    }
}

async function doRegister(event) {
    event.preventDefault();
    clearFormError("register-form");
    try {
        const payload = await apiPostJson("/auth/register", {
            email: el("register-email").value,
            username: el("register-username").value,
            password: el("register-password").value,
            full_name: el("register-name").value,
            company_name: el("register-company").value,
            role: el("register-role").value,
        });
        setCurrentUser(payload.user, payload.access_token);
        startSessionTimer();
        logSessionEvent("register", "New user registered and started a session.");
        setupUIForRole(currentUser.role);
        showDashboard();
        await refreshCurrentPage();
    } catch (error) {
        setFormError("register-form", error.message || "Registration failed");
    }
}

function logout() {
    logSessionEvent("logout", "User signed out from the workspace.");
    localStorage.removeItem("access_token");
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
    localStorage.removeItem("user_data");
    currentToken = null;
    currentUser = null;
    currentPage = "dashboard";
    hideGlobalSearchResults();
    showAuth();
}

function setFormError(formId, message) {
    const form = el(formId);
    if (!form) return;
    let errorNode = form.querySelector(".form-error");
    if (!errorNode) {
        errorNode = document.createElement("p");
        errorNode.className = "error form-error";
        form.prepend(errorNode);
    }
    errorNode.textContent = message;
}

function clearFormError(formId) {
    const form = el(formId);
    const errorNode = form?.querySelector(".form-error");
    if (errorNode) errorNode.remove();
}

function getDefaultPageForRole(role) {
    if (role === "citizen") return "citizen";
    if (role === "admin") return "dashboard";
    return "dashboard";
}

function setupUIForRole(role) {
    el("admin-menu")?.classList.toggle("hidden", role !== "admin");
    el("citizen-menu")?.classList.toggle("hidden", role !== "citizen");
    el("help-menu")?.classList.toggle("hidden", false);
    document.querySelectorAll(".support-help-link").forEach(node => {
        node.style.display = role === "admin" ? "none" : "";
    });

    document.querySelectorAll(".contractor-only").forEach(node => {
        node.style.display = (role === "contractor" || role === "admin") ? "" : "none";
    });
    document.querySelectorAll(".bidder-only").forEach(node => {
        node.style.display = role === "contractor" ? "" : "none";
    });
    document.querySelectorAll(".admin-only").forEach(node => {
        const isContractorOnly = node.classList.contains("contractor-only");
        if (isContractorOnly) {
            node.style.display = (role === "contractor" || role === "admin") ? "" : "none";
        } else {
            node.style.display = role === "admin" ? "" : "none";
        }
    });


    const helpSubtitle = el("help-subtitle");
    if (helpSubtitle) {
        helpSubtitle.textContent =
            role === "citizen" ? "Ask for more details or report a concern" :
            "Raise a ticket or ask a question";
    }

    el("help-contractor")?.classList.toggle("hidden", role !== "contractor");
    el("help-citizen")?.classList.toggle("hidden", role !== "citizen");

    renderRoleWorkspace(role);
}

function activatePage(pageName) {
    currentPage = pageName;
    document.querySelectorAll(".page").forEach(node => node.classList.remove("active"));
    document.querySelectorAll(".sb-link").forEach(node => {
        node.classList.toggle("active", node.dataset.page === pageName);
    });
    const page = el(`${pageName}-page`);
    if (page) page.classList.add("active");
}

function showPage(pageName) {
    if (pageName === "logs" && currentUser?.role !== "admin") {
        showToast("Access Denied", "Only administrators can view session logs.");
        return false;
    }
    activatePage(pageName);
    refreshCurrentPage();
    return false;
}

async function refreshCurrentPage() {
    if (!currentUser) return;

    await fetchStats();

    if (currentUser.role === "admin") {
        await fetchAdminAnalytics();
        await fetchAdminUsers();
        await renderAdminSupport();
    }

    switch (currentPage) {
    case "dashboard":
        await fetchTenders();
        await fetchRecentActivity();
        if (currentUser.role === "contractor") {
            await renderContractorRecentSubmissions();
        }
        break;

    case "tenders":
        await fetchTenders();
        break;
    case "submissions":
        await fetchTenders();
        await fetchSubmissionViews();
        break;

    case "audit":
        await fetchAuditStats();
        break;
    case "orderbook":
        await fetchOrderbook();
        break;
    case "evaluations":
        await fetchEvaluationsView();
        break;
    case "admin":
        await fetchTenders();
        showAdminTab("analytics");
        break;
    case "help":
        await renderSupportViews();
        break;
    case "inbox":
        await renderInboxPage();
        break;
    case "citizen":
        await fetchCitizenTenders();
        break;
    case "sectors":
        await fetchSectorDashboard();
        await fetchCitizenAmountStats();
        showCitizenSectorTab("sectors");
        break;
    case "settings":
        populateProfileSettingsForm();
        break;
    case "timeline":
        await fetchTimelinePageData();
        break;
    case "logs":
        renderSessionLogs();
        break;
    case "troubleshoot":
        renderTroubleshootState();
        break;
    default:
        break;
    }
}

function populateProfileSettingsForm() {
    if (!currentUser) return;
    if (el("settings-full-name")) el("settings-full-name").value = currentUser.full_name || "";
    if (el("settings-username")) el("settings-username").value = currentUser.username || "";
    if (el("settings-email")) el("settings-email").value = currentUser.email || "";
    if (el("settings-company")) el("settings-company").value = currentUser.company_name || "";
    if (el("settings-role")) el("settings-role").value = formatDecision(currentUser.role || "");
    if (el("settings-theme")) el("settings-theme").value = currentTheme;
}

async function saveProfileSettings(event) {
    event.preventDefault();
    if (!currentUser) return;

    try {
        const updatedProfile = {
            ...currentUser,
            full_name: el("settings-full-name").value.trim(),
            username: el("settings-username").value.trim(),
            email: el("settings-email").value.trim(),
            company_name: el("settings-company").value.trim(),
        };
        const payload = await apiPutJson("/auth/profile", {
            full_name: updatedProfile.full_name,
            username: updatedProfile.username,
            email: updatedProfile.email,
            company_name: updatedProfile.company_name,
        });
        setCurrentUser({ ...updatedProfile, ...payload.user }, currentToken);
        logSessionEvent("profile_updated", "Profile details were updated.");
        populateProfileSettingsForm();
        showToast("Profile updated", "Your account details were saved.");
    } catch (error) {
        showToast("Unable to update profile", error.message);
    }
}

function saveThemeSettings(event) {
    event.preventDefault();
    applyTheme(el("settings-theme")?.value || "light");
    logSessionEvent("theme_changed", `Theme changed to ${currentTheme}.`);
    showToast("Theme updated", `Using ${formatDecision(currentTheme)} mode.`);
}

function getFeatureSearchIndex() {
    const items = [
        { page: "about", label: "About", desc: "Overview of the platform", tags: "about platform introduction workflow procurement intelligence", roles: ["admin", "contractor", "citizen"] },
        { page: "settings", label: "Profile Settings", desc: "Edit your account details", tags: "settings profile account theme dark light name email username company", roles: ["admin", "contractor", "citizen"] },
        { page: "settings", label: "Theme Settings", desc: "Switch between light and dark mode", tags: "theme appearance dark light display mode preferences", roles: ["admin", "contractor", "citizen"] },
        { page: "timeline", label: "Timeline", desc: "Tender lifecycle and explainability timeline", tags: "timeline tender lifecycle explainability audit events history flow", roles: ["admin", "contractor", "citizen"] },
        { page: "help", label: "Help & Support", desc: "Tickets, questions, and concerns", tags: "help support ticket concern question request", roles: ["contractor", "citizen"] },
        { page: "inbox", label: "Inbox", desc: "Sent tickets and received replies", tags: "inbox mailbox messages sent received replies support", roles: ["admin", "contractor", "citizen"] },
        { page: "dashboard", label: "Overview", desc: "Procurement activity summary", tags: "overview dashboard stats summary procurement", roles: ["admin", "contractor"] },
        { page: "dashboard", label: "Dashboard Stats", desc: "Quick procurement totals and activity snapshot", tags: "dashboard overview totals stats summary widgets cards", roles: ["admin", "contractor"] },
        { page: "tenders", label: "Tenders", desc: "Browse and manage tenders", tags: "tender tenders tendering procurement bids opportunities manage", roles: ["admin", "contractor"] },
        { page: "tenders", label: "Tender Opportunities", desc: "View available tenders and tender details", tags: "opportunities listings browse tender details procurement", roles: ["admin", "contractor"] },
        { page: "submissions", label: "Submissions", desc: "Track tender submissions", tags: "submission submissions bid bids upload documents", roles: ["contractor", "admin"] },
        { page: "submissions", label: "Bid Uploads", desc: "Upload and track bid documents", tags: "upload files documents bids submission contractor", roles: ["contractor", "admin"] },

        { page: "evaluations", label: "Evaluations", desc: "AI-generated eligibility decisions", tags: "evaluations review ai decisions eligibility scoring", roles: ["admin"] },
        { page: "evaluations", label: "Eligibility Review", desc: "See automated evaluation outcomes", tags: "eligibility evaluation review ai scoring decisions confidence", roles: ["admin"] },
        { page: "admin", label: "Control Panel", desc: "Analytics, tenders, and support inbox", tags: "admin control panel analytics users tenders support inbox", roles: ["admin"] },
        { page: "admin", label: "Admin Analytics", desc: "Open procurement analytics and totals", tags: "analytics charts totals admin control panel", roles: ["admin"] },
        { page: "admin", label: "Support Inbox", desc: "Review submitted support tickets", tags: "support inbox tickets concerns help admin", roles: ["admin"] },
        { page: "citizen", label: "Awarded Tenders", desc: "Public view of published awards", tags: "citizen awarded tenders awards public winners contracts", roles: ["citizen"] },
        { page: "sectors", label: "Sector Dashboard", desc: "Sector analytics and amount stats", tags: "sector dashboard statistics stats amount tender analytics filters", roles: ["citizen"] },
        { page: "sectors", label: "Tender Amount Stats", desc: "Explore awarded tender amounts and filters", tags: "amount stats sector awarded analytics filters dashboard", roles: ["citizen"] },
        { page: "logs", label: "Session History", desc: "Review login time, logout time, duration, and device details", tags: "session logs history login logout duration device timezone browser", roles: ["admin", "contractor", "citizen"] },
        { page: "troubleshoot", label: "Page Troubleshoot", desc: "Clear saved app data and reload the page", tags: "troubleshoot reset refresh clear cache reload recovery", roles: ["admin", "contractor", "citizen"] },
        { page: "dashboard", label: "Contractor PDF Analyzer", desc: "Run a self-check on contractor PDF documents", tags: "pdf analyzer contractor self check analysis upload document", roles: ["contractor"] },
        { action: "logout", label: "Log Out", desc: "Sign out from the workspace", tags: "logout sign out session exit", roles: ["admin", "contractor", "citizen"] },
    ];
    const roleItems = items.filter(item => item.roles.includes(currentUser?.role));
    const sidebarItems = Array.from(document.querySelectorAll(".sidebar .sb-link"))
        .filter(node => node.offsetParent !== null)
        .map(node => {
            const label = node.querySelector(".nav-label")?.textContent?.trim() || "";
            const page = node.dataset.page || "";
            const action = page ? "" : (label.toLowerCase().includes("log out") ? "logout" : "");
            if (!label || (!page && !action)) return null;
            return {
                page: page || undefined,
                action: action || undefined,
                label,
                desc: "Sidebar navigation",
                tags: `${label.toLowerCase()} sidebar navigation menu`,
                roles: [currentUser?.role].filter(Boolean),
            };
        })
        .filter(Boolean);

    const deduped = new Map();
    [...roleItems, ...sidebarItems].forEach(item => {
        const key = `${item.page || ""}:${item.action || ""}:${item.label}`;
        if (!deduped.has(key)) deduped.set(key, item);
    });
    return Array.from(deduped.values());
}

function getRecentFeatures() {
    try {
        return JSON.parse(localStorage.getItem(RECENT_FEATURES_KEY) || "[]");
    } catch (_error) {
        return [];
    }
}

function rememberFeatureUse(pageName = "", actionName = "") {
    const featureKey = actionName ? `action:${actionName}` : `page:${pageName}`;
    if (!featureKey || featureKey === "page:") return;
    const recent = getRecentFeatures().filter(item => item !== featureKey);
    recent.unshift(featureKey);
    localStorage.setItem(RECENT_FEATURES_KEY, JSON.stringify(recent.slice(0, 8)));
}

function getRecommendedSearchResults(items) {
    const recommendations = [];
    const roleSpecific = items.find(item => {
        if (!item.roles?.includes(currentUser?.role)) return false;
        if (item.action === "logout" || item.page === "about" || item.page === "settings" || item.page === "logs") return false;
        return item.roles.length === 1;
    });
    if (roleSpecific) {
        recommendations.push({
            ...roleSpecific,
            desc: `Recommended for ${formatDecision(currentUser?.role || "your role")}`,
        });
    }

    const recentKeys = getRecentFeatures();
    const recentItem = recentKeys
        .map(key => items.find(item => key === (item.action ? `action:${item.action}` : `page:${item.page}`)))
        .find(Boolean);
    if (recentItem) {
        recommendations.push({
            ...recentItem,
            desc: `Recently used: ${recentItem.label}`,
        });
    }

    const deduped = new Map();
    recommendations.forEach(item => {
        const key = `${item.page || ""}:${item.action || ""}:${item.label}`;
        if (!deduped.has(key)) deduped.set(key, item);
    });
    return Array.from(deduped.values()).slice(0, 2);
}

function renderGlobalSearchResults(results) {
    const container = el("global-search-results");
    if (!container) return;
    if (!results.length) {
        container.innerHTML = `<div class="search-empty">No matching features</div>`;
    } else {
        container.innerHTML = results.map((item, index) => `
            <button class="search-result-item" type="button" data-page="${escapeHtml(item.page || "")}" data-action="${escapeHtml(item.action || "")}" ${index === 0 ? 'data-active="true"' : ""} onclick="goToSearchFeature('${escapeHtml(item.page || "")}', '${escapeHtml(item.action || "")}')">
                <span class="search-result-title">${escapeHtml(item.label)}</span>
                <span class="search-result-desc">${escapeHtml(item.desc)}</span>
            </button>
        `).join("");
    }
    container.classList.remove("hidden");
}

function hideGlobalSearchResults() {
    const container = el("global-search-results");
    if (!container) return;
    container.classList.add("hidden");
    container.innerHTML = "";
}

function handleGlobalSearchInput() {
    const query = (el("global-search-input")?.value || "").trim().toLowerCase();
    const items = getFeatureSearchIndex();
    const results = query
        ? items.filter(item => `${item.label} ${item.desc} ${item.page || ""} ${item.action || ""} ${item.tags || ""}`.toLowerCase().includes(query)).slice(0, 20)
        : getRecommendedSearchResults(items);
    renderGlobalSearchResults(results);
}

function handleGlobalSearchKeydown(event) {
    if (event.key === "Escape") {
        hideGlobalSearchResults();
        return;
    }
    if (event.key !== "Enter") return;
    event.preventDefault();
    const firstResult = el("global-search-results")?.querySelector(".search-result-item");
    if (firstResult?.dataset.page || firstResult?.dataset.action) {
        goToSearchFeature(firstResult.dataset.page || "", firstResult.dataset.action || "");
    }
}

function goToSearchFeature(pageName, actionName = "") {
    if (el("global-search-input")) el("global-search-input").value = "";
    hideGlobalSearchResults();
    rememberFeatureUse(pageName, actionName);
    if (actionName === "logout") {
        logout();
        return;
    }
    showPage(pageName);
}

function toggleSidebar() {
    applySidebarState(!sidebarCollapsed);
}

function applySidebarState(nextState) {
    sidebarCollapsed = !!nextState;
    document.querySelector(".app-shell")?.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    localStorage.setItem(SIDEBAR_STATE_KEY, String(sidebarCollapsed));
}

function applyTheme(themeName) {
    currentTheme = themeName === "dark" ? "dark" : "light";
    document.body.classList.toggle("theme-dark", currentTheme === "dark");
    localStorage.setItem(THEME_STATE_KEY, currentTheme);
}

function renderTroubleshootState() {
    const status = localStorage.getItem(TROUBLESHOOT_STATUS_KEY) || "ready";
    const visual = el("troubleshoot-visual");
    const text = el("troubleshoot-status-text");
    if (!visual || !text) return;

    visual.classList.toggle("running", status === "running");
    if (status === "running") {
        text.textContent = "Clearing saved app data and preparing a clean reload...";
    } else if (status === "done") {
        text.textContent = "Cleanup completed. The page was reloaded with fresh app data.";
        localStorage.removeItem(TROUBLESHOOT_STATUS_KEY);
    } else {
        text.textContent = "No cleanup is running right now.";
    }
}

async function runPageTroubleshoot() {
    const visual = el("troubleshoot-visual");
    const text = el("troubleshoot-status-text");
    if (visual) visual.classList.add("running");
    if (text) text.textContent = "Clearing saved app data and preparing a clean reload...";

    const preservedToken = localStorage.getItem("access_token");
    localStorage.setItem(TROUBLESHOOT_STATUS_KEY, "running");

    const keysToKeep = new Set(["access_token", TROUBLESHOOT_STATUS_KEY]);
    const snapshot = {};
    for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (key && keysToKeep.has(key)) {
            snapshot[key] = localStorage.getItem(key);
        }
    }

    localStorage.clear();
    sessionStorage.clear();

    Object.entries(snapshot).forEach(([key, value]) => {
        if (value !== null) localStorage.setItem(key, value);
    });
    if (preservedToken) localStorage.setItem("access_token", preservedToken);
    localStorage.setItem(TROUBLESHOOT_STATUS_KEY, "done");
    logSessionEvent("troubleshoot_run", "Page troubleshoot cleared local app data and forced a reload.");

    if ("caches" in window) {
        try {
            const cacheNames = await window.caches.keys();
            await Promise.all(cacheNames.map(name => window.caches.delete(name)));
        } catch (_error) {
            // Ignore cache API failures and continue with reload.
        }
    }

    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("_refresh", String(Date.now()));
    window.location.replace(nextUrl.toString());
}

function getDeviceProfile() {
    const platform = navigator.userAgentData?.platform || navigator.platform || "Unknown platform";
    const browser = navigator.userAgent || "Unknown browser";
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Unknown timezone";
    const language = navigator.language || "Unknown language";
    const screenSize = window.screen ? `${window.screen.width}x${window.screen.height}` : "Unknown screen";
    const estimatedLocation = `${language} / ${timezone}`;
    return { platform, browser, timezone, language, screenSize, estimatedLocation };
}

function getSessionLogs() {
    try {
        return JSON.parse(localStorage.getItem(SESSION_LOGS_KEY) || "[]");
    } catch (_error) {
        return [];
    }
}

function setSessionLogs(logs) {
    localStorage.setItem(SESSION_LOGS_KEY, JSON.stringify(logs.slice(0, SESSION_LOG_LIMIT)));
}

function startSessionTimer() {
    localStorage.setItem(SESSION_STARTED_AT_KEY, new Date().toISOString());
}

function ensureSessionStart() {
    const existing = localStorage.getItem(SESSION_STARTED_AT_KEY);
    if (existing) return existing;
    const now = new Date().toISOString();
    localStorage.setItem(SESSION_STARTED_AT_KEY, now);
    return now;
}

function getSessionStart() {
    return localStorage.getItem(SESSION_STARTED_AT_KEY) || "";
}

function logSessionEvent(type, detail) {
    const logs = getSessionLogs();
    const device = getDeviceProfile();
    const sessionStartedAt = currentUser ? ensureSessionStart() : getSessionStart();
    logs.unshift({
        id: crypto.randomUUID(),
        type,
        detail,
        timestamp: new Date().toISOString(),
        session_started_at: sessionStartedAt,
        page: currentPage,
        user: currentUser ? {
            id: currentUser.id,
            username: currentUser.username,
            role: currentUser.role,
            company_name: currentUser.company_name || "",
        } : null,
        device,
    });
    setSessionLogs(logs);
}

function renderSessionLogs() {
    const target = el("session-logs-list");
    if (!target) return;
    const allSessions = buildSessionHistory(getSessionLogs());
    const timezones = Array.from(new Set(allSessions.map(s => s.timezone))).filter(Boolean).sort();

    // Store filter values if they exist
    const filterUser = el("session-filter-user")?.value?.toLowerCase() || "";
    const filterRole = el("session-filter-role")?.value?.toLowerCase() || "";
    const filterDevice = el("session-filter-device")?.value?.toLowerCase() || "";
    const filterTz = el("session-filter-timezone")?.value?.toLowerCase() || "";

    const filtered = allSessions.filter(s => {
        if (filterUser && !s.userName.toLowerCase().includes(filterUser)) return false;
        if (filterRole && s.role.toLowerCase() !== filterRole) return false;
        if (filterDevice && s.device.toLowerCase() !== filterDevice) return false;
        if (filterTz && s.timezone.toLowerCase() !== filterTz) return false;
        return true;
    });

    const total = filtered.length;
    const start = sessionPagination.currentPage * sessionPagination.pageSize;
    const end = start + sessionPagination.pageSize;
    const pageItems = filtered.slice(start, end);

    target.innerHTML = `
        <div class="session-filter-bar">
            <button type="button" class="btn-ghost btn-sm" onclick="toggleSessionFilterPanel()">
                Filter Session Logs
            </button>
        </div>
        <div class="session-filter-grid hidden" id="session-filter-panel">
            <label class="field">
                <span>User</span>
                <input type="text" id="session-filter-user" placeholder="Filter by user" value="${escapeHtml(filterUser)}">
            </label>
            <label class="field">
                <span>Role</span>
                <select id="session-filter-role">
                    <option value="">All roles</option>
                    <option value="admin" ${filterRole === 'admin' ? 'selected' : ''}>Admin</option>
                    <option value="contractor" ${filterRole === 'contractor' ? 'selected' : ''}>Contractor</option>
                    <option value="citizen" ${filterRole === 'citizen' ? 'selected' : ''}>Citizen</option>
                </select>
            </label>
            <label class="field">
                <span>Device</span>
                <select id="session-filter-device">
                    <option value="">All devices</option>
                    <option value="windows" ${filterDevice === 'windows' ? 'selected' : ''}>Windows</option>
                    <option value="android" ${filterDevice === 'android' ? 'selected' : ''}>Android</option>
                    <option value="mac" ${filterDevice === 'mac' ? 'selected' : ''}>Mac</option>
                    <option value="linux" ${filterDevice === 'linux' ? 'selected' : ''}>Linux</option>
                    <option value="tablet" ${filterDevice === 'tablet' ? 'selected' : ''}>Tablet</option>
                </select>
            </label>
            <label class="field">
                <span>Timezone</span>
                <select id="session-filter-timezone">
                    <option value="">All timezones</option>
                    ${timezones.map(tz => `<option value="${escapeHtml(tz.toLowerCase())}" ${filterTz === tz.toLowerCase() ? 'selected' : ''}>${escapeHtml(tz)}</option>`).join("")}
                </select>
            </label>
        </div>

        <div class="session-table-wrapper">
            <table class="session-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Role</th>
                        <th>Login Time</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Device</th>
                        <th>Timezone</th>
                    </tr>
                </thead>
                <tbody>
                    ${pageItems.map(s => `
                        <tr>
                            <td>${escapeHtml(s.userName)}</td>
                            <td>${escapeHtml(formatDecision(s.role))}</td>
                            <td>${escapeHtml(formatDate(s.loginTime))}</td>
                            <td><span class="badge ${!s.logoutTime ? 'badge-active' : 'badge-manual-review'}">${s.logoutTime ? 'Closed' : 'Active'}</span></td>
                            <td>${escapeHtml(s.duration)}</td>
                            <td>${escapeHtml(s.device)}</td>
                            <td>${escapeHtml(s.timezone)}</td>
                        </tr>
                    `).join("")}
                    ${!pageItems.length ? '<tr><td colspan="7" style="text-align:center;padding:40px">No logs found.</td></tr>' : ''}
                </tbody>
            </table>
        </div>
        <div class="pagination-footer">
            <button class="btn-ghost btn-sm" onclick="changeSessionPage(-1)" ${sessionPagination.currentPage === 0 ? 'disabled' : ''}>Previous</button>
            <span>Page ${sessionPagination.currentPage + 1} of ${Math.ceil(total / sessionPagination.pageSize) || 1}</span>
            <button class="btn-ghost btn-sm" onclick="changeSessionPage(1)" ${end >= total ? 'disabled' : ''}>Next</button>
        </div>
    `;

    bindSessionLogFilters();
}

function changeSessionPage(delta) {
    sessionPagination.currentPage += delta;
    renderSessionLogs();
}

function bindSessionLogFilters() {
    el("session-filter-toggle")?.addEventListener("click", toggleSessionFilterPanel);
    const filterIds = [
        "session-filter-user",
        "session-filter-role",
        "session-filter-login",
        "session-filter-logout",
        "session-filter-duration",
        "session-filter-device",
        "session-filter-timezone",
    ];
    filterIds.forEach(id => {
        el(id)?.addEventListener("input", applySessionLogFilters);
        el(id)?.addEventListener("change", applySessionLogFilters);
    });
}

function toggleSessionFilterPanel() {
    el("session-filter-panel")?.classList.toggle("hidden");
}

function applySessionLogFilters() {
    const rows = document.querySelectorAll("#session-history-rows tr");
    const filters = {
        user: (el("session-filter-user")?.value || "").trim().toLowerCase(),
        role: (el("session-filter-role")?.value || "").trim().toLowerCase(),
        login: (el("session-filter-login")?.value || "").trim().toLowerCase(),
        logout: (el("session-filter-logout")?.value || "").trim().toLowerCase(),
        duration: (el("session-filter-duration")?.value || "").trim().toLowerCase(),
        device: (el("session-filter-device")?.value || "").trim().toLowerCase(),
        timezone: (el("session-filter-timezone")?.value || "").trim().toLowerCase(),
    };

    rows.forEach(row => {
        const matches = Object.entries(filters).every(([key, value]) => !value || (row.dataset[key] || "").includes(value));
        row.style.display = matches ? "" : "none";
    });
}

function buildSessionHistory(logs) {
    const relevantLogs = logs.filter(log => ["login", "register", "logout", "session_restored"].includes(log.type));
    const sessions = new Map();

    relevantLogs.forEach(log => {
        const sessionKey = log.session_started_at || `${log.user?.id || "guest"}-${log.timestamp}`;
        const existing = sessions.get(sessionKey) || {
            userName: log.user?.username || "Guest",
            role: formatDecision(log.user?.role || "unknown"),
            loginTime: log.session_started_at || log.timestamp,
            logoutTime: "",
            duration: "0m",
            device: log.device?.platform || "Unknown",
            timezone: log.device?.timezone || "Unknown",
        };

        if (!existing.loginTime || new Date(log.timestamp).getTime() < new Date(existing.loginTime).getTime()) {
            existing.loginTime = log.session_started_at || log.timestamp;
        }
        if (log.type === "logout") {
            existing.logoutTime = log.timestamp;
        }
        existing.userName = log.user?.username || existing.userName;
        existing.role = formatDecision(log.user?.role || existing.role);
        existing.device = log.device?.platform || existing.device;
        existing.timezone = log.device?.timezone || existing.timezone;
        sessions.set(sessionKey, existing);
    });

    return Array.from(sessions.values())
        .map(session => {
            const start = new Date(session.loginTime);
            const end = session.logoutTime ? new Date(session.logoutTime) : new Date();
            const duration = !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())
                ? formatDurationFromMs(end.getTime() - start.getTime())
                : "Unknown";
            return {
                ...session,
                duration,
            };
        })
        .sort((a, b) => new Date(b.loginTime).getTime() - new Date(a.loginTime).getTime());
}

async function fetchStats() {
    try {
        const payload = await apiGet("/dashboard/stats");
        const stats = payload.stats || {};
        if (el("stat-tenders")) el("stat-tenders").textContent = stats.active_tenders ?? 0;
        if (el("stat-submissions")) el("stat-submissions").textContent = stats.total_submissions ?? 0;
        if (el("stat-pending")) el("stat-pending").textContent = stats.pending_evaluations ?? 0;
        if (el("stat-approved")) el("stat-approved").textContent = stats.approved_bidders ?? 0;
    } catch (_error) {
        if (el("stat-tenders")) el("stat-tenders").textContent = "-";
        if (el("stat-submissions")) el("stat-submissions").textContent = "-";
        if (el("stat-pending")) el("stat-pending").textContent = "-";
        if (el("stat-approved")) el("stat-approved").textContent = "-";
    }
}

async function fetchAdminAnalytics() {
    try {
        const payload = await apiGet("/dashboard/admin/analytics");
        const analytics = payload.analytics || {};
        if (el("analytics-users")) el("analytics-users").textContent = analytics.total_users ?? 0;
        if (el("analytics-tenders")) el("analytics-tenders").textContent = analytics.total_tenders ?? 0;
        if (el("analytics-evaluations")) el("analytics-evaluations").textContent = analytics.total_evaluations ?? 0;
        if (el("analytics-confidence")) el("analytics-confidence").textContent = analytics.average_confidence ?? "-";
        if (el("analytics-review")) el("analytics-review").textContent = analytics.manual_review_rate ?? "-";
    } catch (_error) {
        if (el("analytics-users")) el("analytics-users").textContent = "-";
    }
}

async function fetchTenders() {
    try {
        const payload = await apiGet("/tenders");
        cachedTenders = payload.tenders || [];
        renderTenderLists(cachedTenders);
        populateSubmitTenderOptions(cachedTenders);
        if (currentUser?.role === "admin") {
            renderAdminTenderSectors();
        } else {
            const elDashboard = el("admin-tenders-sector-dashboard");
            if (elDashboard) elDashboard.style.display = "none";
        }
    } catch (error) {
        renderListState("tenders-list", error.message);
        renderListState("admin-tenders-list", error.message);
    }
}

async function fetchRecentActivity() {
    const target = el("activity-feed");
    if (!target) return;
    
    if (currentUser?.role !== 'admin') {
        el("dashboard-recent-activity")?.classList.add("hidden");
        return;
    }
    
    el("dashboard-recent-activity")?.classList.remove("hidden");
    
    try {
        const payload = await apiGet("/audit/all");
        const logs = payload.logs || [];
        
        if (logs.length === 0) {
            target.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--gray-400);">No recent activity recorded yet.</div>`;
            return;
        }
        
        target.innerHTML = logs.map(log => {
            const icon = log.action.includes("AWARD") ? '🏆' : 
                         log.action.includes("TIE") ? '⚖️' : 
                         log.action.includes("REOPEN") ? '🔓' :
                         log.action.includes("RECALL") ? '🔄' : '📝';
            return `
                <div class="activity-item" style="display: flex; gap: 12px; padding: 12px; background: white; border-radius: 8px; border: 1px solid var(--gray-100); transition: transform 0.2s ease;">
                    <div style="background: var(--blue-lt); color: var(--blue); width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 14px;">
                        ${icon}
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                            <span style="font-weight: 600; font-size: 13px; color: var(--gray-900);">${escapeHtml(log.action.replace(/_/g, ' '))}</span>
                            <span style="font-size: 11px; color: var(--gray-400);">${formatDate(log.timestamp)}</span>
                        </div>
                        <p style="font-size: 12px; color: var(--gray-600); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(log.reason)}</p>
                        <div style="font-size: 10px; color: var(--gray-400); margin-top: 4px;">Tender ID: ${escapeHtml(log.tender_id)} | Actor: ${escapeHtml(log.user_id)}</div>
                    </div>
                </div>
            `;
        }).join("");
    } catch (error) {
        target.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--red);">Failed to load activity: ${escapeHtml(error.message)}</div>`;
    }
}


function renderTenderLists(tenders) {
    const contractorList = el("tenders-list");
    const adminList = el("admin-tenders-list");

    if (contractorList) {
        if (tenders.length === 0) {
            contractorList.innerHTML = emptyState("No tenders available yet.");
        } else {
            contractorList.innerHTML = tenders.map(tender => renderTenderCard(tender, false)).join("");
        }
    }

    if (adminList) {
        if (tenders.length === 0) {
            adminList.innerHTML = emptyState("No tenders have been created yet.");
        } else {
            adminList.innerHTML = tenders.map(tender => renderTenderCard(tender, true)).join("");
        }
    }
}

function renderTenderCard(tender, adminView) {
    const deadline = tender.application_deadline ? formatDate(tender.application_deadline) : "Open until closed";
    const actions = [];

    if (adminView) {
        actions.push(`<button class="btn-ghost" type="button" onclick="startEditTender('${escapeHtml(tender.id)}')">Edit</button>`);
        if (tender.status === "active") {
            actions.push(`<button class="btn-ghost" type="button" onclick="closeTender('${escapeHtml(tender.id)}')">Close</button>`);
        }
        if (tender.status === "closed") {
            actions.push(`<button class="btn-ghost" type="button" onclick="reopenTender('${escapeHtml(tender.id)}')">Reopen</button>`);
            actions.push(`<button class="btn-solid btn-sm" type="button" onclick="publishTender('${escapeHtml(tender.id)}')">Publish Result</button>`);
        }
        if (tender.status === "published") {
            actions.push(`<button class="btn-ghost" type="button" onclick="recallTenderResult('${escapeHtml(tender.id)}')">Recall Result</button>`);
            actions.push(`<button class="btn-ghost" type="button" onclick="reopenTender('${escapeHtml(tender.id)}')">Reopen</button>`);
        }
        actions.push(`<button class="btn-ghost" type="button" onclick="openTenderEvaluations('${escapeHtml(tender.id)}')">Evaluations</button>`);
    } else if (currentUser?.role === "contractor" && tender.status === "active") {
        actions.push(`<button class="btn-solid btn-sm" type="button" onclick="showSubmitModal('${escapeHtml(tender.id)}')">Submit Bid</button>`);
    }

    return `
        <article class="item-card tender-card">
            <div class="item-card-top">
                <div>
                    <div class="item-card-title">${escapeHtml(tender.title)}</div>
                    <div class="item-card-desc">${escapeHtml(tender.description || "No description provided.")}</div>
                </div>
                <span class="badge ${decisionBadgeClass(tender.status)}">${escapeHtml(formatDecision(tender.status))}</span>
            </div>
            <div class="item-card-meta">
                <span>${escapeHtml(tender.department || "Procurement Department")}</span>
                <span>${escapeHtml(tender.work_location || "Location not specified")}</span>
                <span>${escapeHtml(tender.investment_amount || "Value not specified")}</span>
                <span>${escapeHtml(deadline)}</span>
                <span>${escapeHtml(String(tender.submissions ?? 0))} submissions</span>
            </div>
            ${tender.status === 'published' ? `
            <div style="margin-top: 12px; padding: 10px; background: rgba(16, 185, 129, 0.05); border-left: 4px solid var(--green-500); border-radius: 4px;">
                <div style="font-weight:600; color:var(--green-700); margin-bottom: ${tender.runner_up ? '4px' : '0'};">🏆 Awarded to: ${escapeHtml(tender.awarded_to)}</div>
                ${tender.runner_up ? `<div style="font-size:12px; color:var(--gray-600); margin-bottom: ${tender.second_runner_up ? '2px' : '0'};">🥈 1st Runner-Up: ${escapeHtml(tender.runner_up)}</div>` : ''}
                ${tender.second_runner_up ? `<div style="font-size:12px; color:var(--gray-600);">🥉 2nd Runner-Up: ${escapeHtml(tender.second_runner_up)}</div>` : ''}
            </div>` : ''}
            ${actions.length ? `<div class="item-card-actions">${actions.join("")}</div>` : ""}
        </article>
    `;
}

function populateSubmitTenderOptions(tenders) {
    const select = el("submit-tender");
    if (!select) return;
    const activeTenders = tenders.filter(tender => tender.status === "active");
    select.innerHTML = `
        <option value="">Select a tender...</option>
        ${activeTenders.map(tender => `<option value="${escapeHtml(tender.id)}">${escapeHtml(tender.title)}</option>`).join("")}
    `;
}

function showSubmitModal(preselectedTenderId = "") {
    populateSubmitTenderOptions(cachedTenders);
    if (preselectedTenderId && el("submit-tender")) {
        el("submit-tender").value = preselectedTenderId;
    }
    if (currentUser?.company_name && el("submit-company-name")) {
        el("submit-company-name").value = currentUser.company_name;
    }
    openModal("submit-modal");
}

function showCreateTenderModal() {
    resetTenderForm();
    openModal("create-tender-modal");
}

function resetTenderForm() {
    el("create-tender-form")?.reset();
    if (el("tender-edit-id")) el("tender-edit-id").value = "";
    if (el("tender-modal-title")) el("tender-modal-title").textContent = "Create Tender";
    if (el("tender-submit-btn")) el("tender-submit-btn").textContent = "Create Tender";
    if (el("tender-file-name")) el("tender-file-name").textContent = "No file chosen";
    if (el("tender-sector")) el("tender-sector").value = "Infrastructure";
    if (el("admin-tender-department")) el("admin-tender-department").value = "";
}

function startEditTender(tenderId) {
    const tender = cachedTenders.find(item => item.id === tenderId);
    if (!tender) return;
    el("tender-edit-id").value = tender.id;
    el("tender-title").value = tender.title || "";
    el("tender-description").value = tender.description || "";
    el("tender-sector").value = tender.sector || "Infrastructure";
    el("admin-tender-department").value = tender.department || "";
    el("tender-investment").value = tender.investment_amount || "";
    el("tender-duration").value = tender.duration_days || "";
    el("tender-location").value = tender.work_location || "";
    el("tender-penalty").value = tender.penalty_per_day || "";
    el("tender-penalty-days").value = tender.penalty_max_days || 180;
    el("tender-deadline").value = tender.application_deadline ? tender.application_deadline.slice(0, 16) : "";
    if (el("tender-modal-title")) el("tender-modal-title").textContent = "Edit Tender";
    if (el("tender-submit-btn")) el("tender-submit-btn").textContent = "Save Changes";
    if (el("tender-file-name")) el("tender-file-name").textContent = "Keep current document";
    openModal("create-tender-modal");
}

async function doCreateTender(event) {
    event.preventDefault();
    const editId = el("tender-edit-id").value;
    const formData = new FormData();
    formData.append("title", el("tender-title").value);
    formData.append("description", el("tender-description").value);
    formData.append("sector", el("tender-sector").value);
    formData.append("department", el("admin-tender-department").value);
    formData.append("duration_days", el("tender-duration").value);
    formData.append("investment_amount", el("tender-investment").value);
    formData.append("penalty_per_day", el("tender-penalty").value);
    formData.append("penalty_max_days", el("tender-penalty-days").value || "180");
    formData.append("work_location", el("tender-location").value);
    formData.append("application_deadline", el("tender-deadline").value);

    try {
        if (editId) {
            await apiPostForm(`/tenders/${editId}/update`, formData);
            showToast("Tender updated", "The tender details were saved.");
        } else {
            const file = el("tender-file").files?.[0];
            if (!file) {
                showToast("Document required", "Please attach a tender file.");
                return;
            }
            formData.append("file", file);
            await apiPostForm("/tenders/create", formData);
            showToast("Tender created", "The new tender is now available.");
        }
        closeModal("create-tender-modal");
        resetTenderForm();
        await fetchTenders();
        await fetchStats();
    } catch (error) {
        showToast("Unable to save tender", error.message);
    }
}

async function closeTender(tenderId) {
    try {
        await apiPostForm(`/tenders/${tenderId}/close`, new FormData());
        showToast("Tender closed", "Applications are no longer accepted.");
        await fetchTenders();
        await fetchStats();
    } catch (error) {
        showToast("Unable to close tender", error.message);
    }
}

async function reopenTender(tenderId) {
    try {
        const payload = await apiPostForm(`/tenders/${tenderId}/reopen`, new FormData());
        showToast("Tender reopened", payload.application_deadline
            ? `Applications reopened until ${formatDate(payload.application_deadline)}.`
            : "Applications are open again.");
        await fetchTenders();
        await fetchStats();
        await fetchCitizenTenders();
    } catch (error) {
        showToast("Unable to reopen", error.message);
    }
}

async function publishTender(tenderId) {
    try {
        const payload = await apiPostForm(`/tenders/${tenderId}/publish`, new FormData());
        showToast("Result published", payload.winner ? `Winner: ${payload.winner}` : "Tender result is now public.");
        await fetchTenders();
        await fetchStats();
        await fetchCitizenTenders();
    } catch (error) {
        if (error.message.includes("Tie detected")) {
            showToast("Tie Detected", "Please pick a winner from the evaluation analysis.");
            openTenderEvaluations(tenderId);
        } else {
            showToast("Unable to publish", error.message);
        }
    }
}

async function recallTenderResult(tenderId) {
    try {
        await apiPostForm(`/tenders/${tenderId}/recall`, new FormData());
        showToast("Result recalled", "The tender has been moved back to a closed review state.");
        await fetchTenders();
        await fetchStats();
        await fetchCitizenTenders();
    } catch (error) {
        showToast("Unable to recall result", error.message);
    }
}

async function doSubmitBid(event) {
    event.preventDefault();
    const file = el("submit-file").files?.[0];
    if (!file) {
        showToast("Document required", "Please attach your bid document.");
        return;
    }

    const formData = new FormData();
    formData.append("tender_id", el("submit-tender").value);
    formData.append("bidder_name", el("submit-bidder-name").value);
    formData.append("company_name", el("submit-company-name").value);
    formData.append("file", file);

    try {
        await apiPostForm("/submissions/submit", formData);
        closeModal("submit-modal");
        el("submit-form")?.reset();
        if (el("submit-file-name")) el("submit-file-name").textContent = "No file chosen";
        showToast("Bid submitted", "Your document was received successfully.");
        await fetchSubmissionViews();
        await fetchStats();
    } catch (error) {
        showToast("Submission failed", error.message);
    }
}

async function fetchSubmissionViews() {
    if (currentUser?.role === "admin") {
        await renderAdminSubmissions();
        return;
    }

    // Contractor logic - use history endpoint to see all submissions regardless of tender status
    const target = el("submissions-list");
    if (!target) return;

    target.innerHTML = `<div class="loading-state" style="padding: 40px; text-align: center; color: var(--gray-500);">Loading your submissions...</div>`;

    try {
        const payload = await apiGet("/contractor/history");
        const history = payload.history || [];
        
        if (!history.length) {
            target.innerHTML = emptyState("You have not submitted any bids yet.");
            return;
        }

        const cards = history.map(item => {
            const decision = item.result_status.replace(/ /g, '_').toUpperCase();
            return `
                <article class="item-card submission-card">
                    <div class="item-card-top">
                        <div>
                            <div class="item-card-title">${escapeHtml(item.tender_title)}</div>
                            <div class="item-card-desc">${escapeHtml(item.company_name || item.bidder_name)}</div>
                        </div>
                        <span class="badge ${decisionBadgeClass(decision)}">${escapeHtml(item.result_status)}</span>
                    </div>
                    <div class="item-card-meta">
                        <span>${escapeHtml(item.bidder_name)}</span>
                        <span>${escapeHtml(formatDate(item.submitted_at))}</span>
                        <span>${escapeHtml(item.published ? "Published" : "Under Review")}</span>
                    </div>
                    <div style="margin-top: 16px; display: flex; gap: 8px;">
                        <a href="/api/submissions/document/${item.submission_id}?token=${encodeURIComponent(tok())}" target="_blank" class="btn-ghost btn-sm" style="font-size: 11px;">View Document</a>
                        ${item.published ? `<button onclick="showTenderTimeline('${item.tender_id}')" class="btn-ghost btn-sm" style="font-size: 11px;">View Timeline</button>` : ""}
                    </div>
                </article>
            `;
        });

        target.innerHTML = cards.join("");
    } catch (error) {
        target.innerHTML = emptyState("Failed to load submissions: " + error.message);
    }
}

function renderAdminTenderSectors() {
    const target = el("admin-tenders-sector-dashboard");
    if (!target) return;
    target.style.display = "block";

    const totalTenders = cachedTenders.length;
    if (totalTenders === 0) {
        target.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--gray-400); border: 1px dashed var(--gray-200); border-radius: 12px;">Create your first tender to see sector analytics.</div>`;
        return;
    }

    const sectors = [
        { name: "Infrastructure", desc: "Roads, construction, water supply", icon: "🏗️" },
        { name: "TECH", desc: "Manpower, digital systems, hardware", icon: "💻" },
        { name: "Education", desc: "School development, books, uniforms", icon: "🎓" },
        { name: "Agriculture", desc: "Watershed, farming equipment", icon: "🚜" },
        { name: "Insurance", desc: "Mediclaim policies", icon: "🛡️" },
        { name: "General", desc: "Other miscellaneous tenders", icon: "📦" }
    ];

    const tenderCounts = {};
    cachedTenders.forEach(t => {
        const s = t.sector || "General";
        tenderCounts[s] = (tenderCounts[s] || 0) + 1;
    });

    target.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="color: var(--gray-900); font-size: 20px; font-weight: 700;">Sector Analytics</h2>
            <div style="font-size: 13px; color: var(--gray-500); background: var(--gray-50); padding: 4px 12px; border-radius: 20px; border: 1px solid var(--gray-100);">${totalTenders} Total Tenders</div>
        </div>
        <div class="sector-grid">
            ${sectors.map(item => {
                const count = tenderCounts[item.name] || 0;
                const percentage = totalTenders > 0 ? Math.round((count / totalTenders) * 100) : 0;
                return `
                    <button class="sector-card" type="button" onclick="filterTendersBySector('${escapeHtml(item.name)}')">
                        <div class="sector-card-top">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 20px;">${item.icon}</span>
                                <h3 style="font-size: 15px; font-weight: 600; color: var(--gray-900);">${escapeHtml(item.name)}</h3>
                            </div>
                            <span class="badge ${percentage > 0 ? 'badge-eligible' : 'badge-pending'}" style="font-size: 10px; padding: 2px 8px;">${percentage}%</span>
                        </div>
                        <p style="font-size: 12px; color: var(--gray-500); margin: 10px 0; text-align: left; line-height: 1.4;">${escapeHtml(item.desc)}</p>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
                            <div class="sector-card-meta" style="font-weight: 700; color: var(--gray-900); font-size: 13px;">${count} <span style="font-weight:400; color:var(--gray-500)">tenders</span></div>
                            <div style="font-size: 10px; color: var(--blue); font-weight: 600;">VIEW LIST →</div>
                        </div>
                        <div style="height: 4px; background: var(--gray-100); border-radius: 2px; margin-top: 12px; overflow: hidden;">
                            <div style="height: 100%; width: ${percentage}%; background: var(--blue); border-radius: 2px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);"></div>
                        </div>
                    </button>
                `;
            }).join("")}
            <button class="sector-card" type="button" onclick="filterTendersBySector('All')" style="justify-content: center; align-items: center; background: var(--blue-lt); border: 1px dashed var(--blue); box-shadow: none;">
                <div style="text-align: center;">
                    <h3 style="color: var(--blue); font-size: 15px; font-weight: 600; margin-bottom: 4px;">View All</h3>
                    <p style="font-size: 11px; color: var(--blue); opacity: 0.7;">Clear all filters</p>
                </div>
            </button>
        </div>
    `;
}


function filterTendersBySector(sector) {
    if (sector === 'All') {
        renderTenderLists(cachedTenders);
    } else {
        const filtered = cachedTenders.filter(t => (t.sector || "General") === sector);
        renderTenderLists(filtered);
    }
    el("tenders-list").scrollIntoView({ behavior: "smooth" });
}

async function renderAdminSubmissions(filterSector = "All") {
    const target = el("submissions-list");
    const filterTarget = el("admin-submissions-filter");
    if (!target || !filterTarget) return;

    filterTarget.style.display = "block";
    target.innerHTML = `<div class="loading-state" style="padding: 40px; text-align: center; color: var(--gray-500);">Loading submissions...</div>`;

    let activeTenders = cachedTenders;
    if (filterSector !== "All") {
        activeTenders = cachedTenders.filter(t => (t.sector || "General") === filterSector);
    }

    // Render filter buttons
    const sectors = ["All", "Infrastructure", "TECH", "Education", "Agriculture", "Insurance", "General"];
    filterTarget.innerHTML = `
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            ${sectors.map(s => `
                <button class="btn-${s === filterSector ? 'solid' : 'ghost'} btn-sm" onclick="renderAdminSubmissions('${escapeHtml(s)}')">${escapeHtml(s)}</button>
            `).join('')}
        </div>
    `;

    if (!activeTenders.length) {
        target.innerHTML = emptyState(`No tenders found for sector: ${filterSector}`);
        return;
    }

    const payloads = await Promise.all(
        activeTenders.map(tender =>
            apiGet(`/submissions/${tender.id}`)
                .then(payload => ({ tender, submissions: payload.submissions || [] }))
                .catch(() => ({ tender, submissions: [] }))
        )
    );

    let html = "";
    payloads.forEach(({ tender, submissions }) => {
        // Even if 0 submissions, show the tender so admin knows it exists
        html += `
            <div class="submission-group" style="margin-top: 24px; padding: 24px; background: rgba(255,255,255,0.03); border-radius: 16px; border: 1px solid rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <h3 style="font-size: 18px; color: var(--gray-700); margin-bottom: 4px;">${escapeHtml(tender.title)}</h3>
                        <span style="font-size: 12px; color: var(--gray-500);">${escapeHtml(tender.sector || "General")}</span>
                    </div>
                    <span class="badge">${submissions.length} Submissions</span>
                </div>
                <div class="card-list">
                    ${submissions.length ? submissions.map(sub => renderSubmissionCard(tender, sub)).join("") : `<div class="empty-state-mini" style="padding: 20px; text-align: center; color: var(--gray-400); border: 1px dashed var(--gray-200); border-radius: 8px;">No submissions for this tender yet.</div>`}
                </div>
            </div>
        `;
    });

    target.innerHTML = html;
}

function renderSubmissionCard(tender, submission) {
    const decision = submission.evaluation?.decision || "pending";
    return `
        <article class="item-card submission-card">
            <div class="item-card-top">
                <div>
                    <div class="item-card-title">${escapeHtml(tender.title)}</div>
                    <div class="item-card-desc">${escapeHtml(submission.company_name || submission.bidder_name)}</div>
                </div>
                <span class="badge ${decisionBadgeClass(decision)}">${escapeHtml(formatDecision(decision))}</span>
            </div>
            <div class="item-card-meta">
                <span>${escapeHtml(submission.bidder_name)}</span>
                <span>${escapeHtml(formatDate(submission.submitted_at))}</span>
                <span>${escapeHtml(formatDecision(submission.status))}</span>
            </div>
            <div style="margin-top: 16px; display: flex; gap: 8px;">
                <a href="/api/submissions/document/${submission.id}?token=${encodeURIComponent(tok())}" target="_blank" class="btn-ghost btn-sm" style="font-size: 11px;">View Document</a>
            </div>
        </article>
    `;
}

async function renderContractorRecentSubmissions() {
    const target = el("contractor-recent-submissions");
    if (!target || currentUser?.role !== "contractor") return;

    try {
        const payload = await apiGet("/contractor/history");
        const history = (payload.history || []).slice(0, 3); // Show top 3 recent

        if (!history.length) {
            target.innerHTML = "";
            return;
        }

        target.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="font-size: 18px; font-weight: 700; color: var(--gray-900);">Recent Submissions</h3>
                <button class="btn-ghost btn-sm" onclick="showPage('submissions')">View All</button>
            </div>
            <div class="item-grid" style="grid-template-columns: 1fr; gap: 12px;">
                ${history.map(item => {
                    const decision = item.result_status.replace(/ /g, '_').toUpperCase();
                    return `
                        <div class="item-card" style="padding: 16px; border: 1px solid var(--gray-200); border-radius: 12px; cursor: pointer; transition: all 0.2s ease;" 
                             onclick="showPage('submissions')"
                             onmouseover="this.style.borderColor='var(--primary-300)'; this.style.backgroundColor='var(--primary-50)'" 
                             onmouseout="this.style.borderColor='var(--gray-200)'; this.style.backgroundColor='white'">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-weight: 600; color: var(--gray-900); font-size: 15px;">${escapeHtml(item.tender_title)}</div>
                                    <div style="font-size: 12px; color: var(--gray-500); margin-top: 2px;">Submitted on ${escapeHtml(formatDate(item.submitted_at))}</div>
                                </div>
                                <span class="badge ${decisionBadgeClass(decision)}" style="font-size: 11px;">${escapeHtml(item.result_status)}</span>
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    } catch (error) {
        console.error("Failed to render contractor recent submissions", error);
    }
}



async function fetchOrderbook() {
    const target = el("orderbook-list");
    if (!target || currentUser?.role !== "contractor") return;
    
    target.innerHTML = `<div class="loading-state">Fetching your awarded contracts...</div>`;
    
    try {
        const payload = await apiGet("/contractor/orderbook");
        const orders = payload.orderbook || [];
        
        target.innerHTML = orders.length ? orders.map(tender => `
            <article class="item-card tender-card">
                <div class="item-card-top">
                    <div>
                        <div class="item-card-title" style="display:flex; align-items:center; gap: 8px;">
                            ${escapeHtml(tender.title)}
                            <span class="badge badge-eligible" style="font-size: 10px;">Smart Score Winner</span>
                        </div>
                        <div class="item-card-desc">${escapeHtml(tender.department || "General")} | Awarded on ${tender.awarded_at ? escapeHtml(formatDate(tender.awarded_at)) : escapeHtml(formatDate(tender.created_at))}</div>
                    </div>
                    <span class="badge badge-eligible">Awarded</span>
                </div>
                <div class="item-card-meta">
                    <span>${escapeHtml(tender.work_location || "Various Locations")}</span>
                    <span>${escapeHtml(tender.investment_amount || "Budget TBD")}</span>
                    <button class="btn-ghost btn-sm" onclick="showToast('Project Dashboard', 'Full project tracking for ${escapeHtml(tender.title)} is coming soon.')">Track Progress</button>
                </div>
            </article>
        `).join("") : emptyState("You don't have any awarded contracts in your orderbook yet.");
    } catch (error) {
        target.innerHTML = emptyState(error.message);
    }
}

async function openTenderEvaluations(tenderId) {
    activatePage("evaluations");
    await fetchEvaluationsView(tenderId);
}

async function fetchAuditStats() {
    const target = el("audit-table-body");
    if (!target || currentUser?.role !== "admin") return;
    
    target.innerHTML = `<tr><td colspan="6" class="loading-state">Loading contractor performance data...</td></tr>`;
    
    try {
        const payload = await apiGet("/admin/contractor-stats");
        const stats = payload.stats || [];
        
        target.innerHTML = stats.length ? stats.map((s, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>
                    <div style="font-weight:600">${escapeHtml(s.full_name)}</div>
                    <div style="font-size:11px;color:var(--gray-500)">${escapeHtml(s.company_name)}</div>
                </td>
                <td>${s.total_projects}</td>
                <td style="color:var(--green-600);font-weight:600">${s.merit_points}</td>
                <td style="color:var(--red-600);font-weight:600">${s.demerit_points}</td>
                <td>
                    <div class="progress-bar-small">
                        <div class="progress-fill" style="width: ${s.success_rate}%; background: ${s.success_rate > 70 ? 'var(--green-500)' : 'var(--amber-500)'}"></div>
                    </div>
                    <span style="font-size:11px">${s.success_rate}%</span>
                </td>
            </tr>
        `).join("") : `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--gray-400)">No contractor performance data available.</td></tr>`;

        renderCommandCenter(stats);
    } catch (error) {
        target.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--red-500)">${escapeHtml(error.message)}</td></tr>`;
    }
}

function switchAuditTab(tabName) {
    document.querySelectorAll(".capsule-tab").forEach(btn => {
        btn.classList.toggle("active", btn.textContent.toLowerCase().includes(tabName));
    });
    document.querySelectorAll(".audit-section").forEach(sec => {
        sec.classList.toggle("active", sec.id.includes(tabName));
    });
}

function renderCommandCenter(contractors) {
    const target = el("command-center-body");
    if (!target) return;

    target.innerHTML = contractors.length ? contractors.map(c => `
        <tr>
            <td style="font-family:monospace;font-size:12px">${escapeHtml(c.id.substring(0,8))}</td>
            <td><strong>${escapeHtml(c.full_name)}</strong></td>
            <td>${escapeHtml(c.id)}</td> <!-- Assuming ID is email or has email -->
            <td>${escapeHtml(c.company_name)}</td>
            <td style="text-align: right;">
                <button class="btn-ghost btn-sm" style="color:var(--red-600)" onclick="deleteContractor('${escapeHtml(c.id)}')">
                    <svg viewBox="0 0 24 24" style="width:14px;height:14px;margin-right:4px"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    Delete
                </button>
            </td>
        </tr>
    `).join("") : `<tr><td colspan="5" style="text-align:center;padding:40px">No contractors found.</td></tr>`;
}

async function deleteContractor(userId) {
    if (!confirm("Are you sure you want to permanently remove this contractor and all their bid history?")) return;
    
    try {
        await apiPost(`/admin/delete-user?user_id=${encodeURIComponent(userId)}`, {});
        showToast("Contractor deleted successfully.");
        fetchAuditStats();
    } catch (error) {
        showToast("Error", error.message);
    }
}

async function resolveTicketDirectly(ticketId) {
    if (!ticketId) return;

    try {
        await apiPostJson(`/support/tickets/${ticketId}/resolve`, {});
        showToast("Ticket marked as resolved.");
        await renderAdminSupport();
    } catch (error) {
        showToast("Unable to resolve ticket", error.message);
    }
}

async function fetchEvaluationsView(preferredTenderId = "") {
    const target = el("evaluations-list");
    if (!target) return;

    const tenders = cachedTenders.length ? cachedTenders : ((await apiGet("/tenders")).tenders || []);
    
    const aiTenderSelect = el("ai-analysis-tender-select");
    if (aiTenderSelect && (!aiTenderSelect.options.length || aiTenderSelect.options[0].value === "")) {
        aiTenderSelect.innerHTML = tenders.map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(t.title)}</option>`).join("");
    }

    const tenderId = preferredTenderId || tenders[0]?.id;
    currentEvaluationsTenderId = tenderId || "";
    
    const selectedTender = tenders.find(t => t.id === tenderId);
    if (el("evaluation-tender-title")) {
        el("evaluation-tender-title").textContent = selectedTender ? selectedTender.title : "No tender selected";
    }
    if (aiTenderSelect) {
        aiTenderSelect.value = tenderId || "";
    }

    if (!tenderId) {
        target.innerHTML = emptyState("No tenders are available for evaluation yet.");
        return;
    }

    const payload = await apiGet(`/evaluations/${tenderId}`).catch(error => ({ evaluations: [], error: error.message }));
    const evaluations = payload.evaluations || [];
    if (!evaluations.length) {
        target.innerHTML = emptyState(payload.error || "No evaluations found for this tender yet.");
        return;
    }

    const maxScore = Math.max(...evaluations.map(e => e.confidence || 0));
    const topScorers = evaluations.filter(e => e.confidence === maxScore);
    const isTie = topScorers.length > 1;
    const isAwarded = !!(selectedTender?.status === 'published' || selectedTender?.awarded_to);

    let tieBanner = "";
    if (isTie && !isAwarded) {
        tieBanner = `
            <div class="tie-detected-banner" style="margin-bottom: 20px; padding: 16px; background: rgba(245, 158, 11, 0.1); border: 1px solid var(--amber); border-radius: 12px; display: flex; align-items: center; gap: 16px;">
                <div style="background: var(--amber); color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 20px;">!</div>
                <div>
                    <h4 style="color: #92400e; margin-bottom: 4px;">Tie Detected</h4>
                    <p style="font-size: 14px; color: #b45309;">Multiple bidders have the same top score (${(maxScore * 100).toFixed(1)}%). Please manually select a winner using the buttons below.</p>
                </div>
            </div>
        `;
    }

    target.innerHTML = tieBanner + evaluations.map(item => {
        const isTop = item.confidence === maxScore && item.confidence > 0;
        const canAward = !isAwarded && currentUser?.role === "admin";

        return `
        <article class="item-card evaluation-card" ${isTop ? 'style="border: 2px solid var(--blue); background: rgba(59, 130, 246, 0.05);"' : ''}>
            <div class="item-card-top">
                <div>
                    <div class="item-card-title">
                        ${escapeHtml(item.bidder_name)}
                        ${isTie && isTop ? '<span style="color:var(--amber);font-size:12px;margin-left:8px;font-weight:bold;">★ Tied for Top Score</span>' : (isTop ? '<span style="color:var(--blue);font-size:12px;margin-left:8px;font-weight:bold;">★ Highest Score</span>' : '')}
                    </div>
                    <div class="item-card-desc">Tender ID: ${escapeHtml(tenderId)}</div>
                </div>
                <span class="badge ${decisionBadgeClass(item.decision)}">${escapeHtml(formatDecision(item.decision))}</span>
            </div>
            <div class="item-card-meta">
                <span style="font-weight: 600; color: var(--blue-dk);">Score: ${((item.confidence || 0) * 100).toFixed(1)}%</span>
                <span>${escapeHtml(formatDate(item.evaluated_at))}</span>
                <span>${escapeHtml(item.audit_id || "No audit id")}</span>
            </div>
            <div class="item-card-actions">
                <button class="btn-ghost" type="button" onclick="showEvaluationDetail('${escapeHtml(item.id)}')">View Report</button>
                ${canAward ? `<button class="btn-solid btn-sm" style="margin-left: 8px;" type="button" onclick="manuallyAwardTender('${escapeHtml(tenderId)}', '${escapeHtml(item.bidder_name).replace(/'/g, "\\'")}')">Award Winner</button>` : ''}
            </div>
        </article>
    `}).join("");
}

window.manuallyAwardTender = async function(tenderId, bidderName) {
    if (!confirm(`Are you sure you want to manually award this tender to ${bidderName} to resolve the tie?`)) return;
    try {
        await apiPostForm(`/tenders/${tenderId}/publish?manual_winner=${encodeURIComponent(bidderName)}`, new FormData());
        showToast("Success", `Tender awarded to ${bidderName}`);
        await fetchTenders(); // Refresh tenders to update selectedTender state
        await fetchEvaluationsView(tenderId);
    } catch (error) {
        showToast("Error", error.message);
    }
};

function updateWeightSum() {
    const st = parseFloat(el("ai-st-weight").value) || 0;
    const sob = parseFloat(el("ai-sob-weight").value) || 0;
    const sp = parseFloat(el("ai-sp-weight").value) || 0;
    const sum = st + sob + sp;
    
    const display = el("ai-total-sum-value");
    const warning = el("weight-sum-warning");
    
    if (display) {
        display.innerText = sum.toFixed(1);
        if (Math.abs(sum - 10.0) < 0.01) {
            display.style.color = "var(--green)";
            warning?.classList.add("hidden");
        } else {
            display.style.color = "var(--red)";
            warning?.classList.remove("hidden");
        }
        
        // Simple pulse animation
        display.style.transform = "scale(1.1)";
        setTimeout(() => {
            display.style.transform = "scale(1)";
        }, 200);
    }
}

async function runAiAnalysis() {
    const model = el("ai-model-select").value;
    const tenderId = el("ai-analysis-tender-select")?.value || currentEvaluationsTenderId;
    const resultContainer = el("ai-analysis-result");
    
    if (!tenderId) {
        resultContainer.classList.remove("hidden");
        resultContainer.innerHTML = `<p class="error">No tender selected for analysis.</p>`;
        return;
    }
    
    resultContainer.classList.remove("hidden");
    resultContainer.innerHTML = `<div class="loading-state" style="padding: 12px; color: var(--gray-600); text-align: center;">Running analysis with ${model}...</div>`;
    
    try {
        const payload = await apiPostJson(`/evaluations/${tenderId}/ai-analysis`, { 
            model: model,
            st_weight: parseFloat(el("ai-st-weight").value),
            sob_weight: parseFloat(el("ai-sob-weight").value),
            sp_weight: parseFloat(el("ai-sp-weight").value)
        });
        resultContainer.innerHTML = `
            <h3 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                Analysis Result (${model.toUpperCase()})
            </h3>
            <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.6; color: var(--gray-700);">${escapeHtml(payload.analysis).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>')}</div>
        `;
        
        // Fetch evaluations to properly detect ties based on real database scores
        const evalPayload = await apiGet(`/evaluations/${tenderId}`).catch(() => ({ evaluations: [] }));
        const evaluations = evalPayload.evaluations || [];
        
        if (evaluations.length > 0) {
            resultContainer.innerHTML += `
                <div class="tie-alert" style="margin-top: 24px; padding: 20px; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--gray-200); border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                    <h4 style="color: var(--gray-800); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; font-size: 16px;">
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        Finalize & Award Winner
                    </h4>
                    <p style="font-size: 14px; margin-bottom: 20px; color: var(--gray-600);">Based on the AI analysis above and calculated scores, you can now manually award the tender. This will publish the result and notify the bidders.</p>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        ${evaluations.map(ev => `
                            <div style="display: flex; justify-content: space-between; align-items: center; background: var(--gray-50); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--gray-100);">
                                <div style="display: flex; flex-direction: column;">
                                    <span style="font-weight: 600; color: var(--gray-800);">${escapeHtml(ev.bidder_name)}</span>
                                    <span style="font-size: 11px; color: var(--gray-500);">Score: ${((ev.confidence || 0) * 100).toFixed(1)}% | Status: ${formatDecision(ev.decision)}</span>
                                </div>
                                <div style="display: flex; gap: 8px;">
                                    <button class="btn-ghost btn-sm" onclick="window.open('/api/submissions/document/${escapeHtml(ev.submission_id)}?token=${encodeURIComponent(tok())}', '_blank')">
                                        View Document
                                    </button>
                                    <button class="btn-solid btn-sm" style="background: var(--blue); color: white;" onclick="manuallyAwardTender('${escapeHtml(tenderId)}', '${escapeHtml(ev.bidder_name).replace(/'/g, "\\'")}')">Award Winner</button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

    } catch (error) {
        resultContainer.innerHTML = `<p class="error">Analysis failed: ${escapeHtml(error.message)}</p>`;
    }
}

async function showEvaluationDetail(evaluationId) {
    try {
        const payload = await apiGet(`/evaluations/detail/${evaluationId}`);
        const evaluation = payload.evaluation;
        const breakdown = Array.isArray(evaluation.criteria_breakdown) ? evaluation.criteria_breakdown : [];
        const adminReviewControls = currentUser?.role === "admin" ? `
            <div class="criterion-row">
                <div class="criterion-row-top">
                    <div class="criterion-name">Admin reconsideration</div>
                    <span class="badge ${decisionBadgeClass(evaluation.decision)}">${escapeHtml(formatDecision(evaluation.decision))}</span>
                </div>
                <div class="field" style="margin-top:12px">
                    <label>Change application decision</label>
                    <select id="evaluation-override-decision">
                        <option value="MANUAL_REVIEW">Manual Review</option>
                        <option value="ELIGIBLE">Eligible</option>
                        <option value="NOT_ELIGIBLE">Not Eligible</option>
                    </select>
                </div>
                <div class="field" style="margin-top:12px">
                    <label>Reason</label>
                    <textarea id="evaluation-override-reason" rows="4" placeholder="Explain why this application is being reconsidered or updated."></textarea>
                </div>
                <div class="item-card-actions" style="margin-top:12px">
                    <button class="btn-solid btn-sm" type="button" onclick="submitEvaluationOverride('${escapeHtml(evaluation.id)}')">Save Reconsideration</button>
                </div>
            </div>
        ` : "";
        el("evaluation-details").innerHTML = `
            <div class="eval-header">
                <h3>${escapeHtml(evaluation.bidder_name)}</h3>
                <span class="badge ${decisionBadgeClass(evaluation.decision)}">${escapeHtml(formatDecision(evaluation.decision))}</span>
            </div>
            <div class="eval-meta-grid">
                <div class="eval-meta-box">
                    <div class="label">Evaluated</div>
                    <div class="value" style="font-size:14px">${escapeHtml(formatDate(evaluation.evaluated_at))}</div>
                </div>
                <div class="eval-meta-box">
                    <div class="label">Audit ID</div>
                    <div class="value mono">${escapeHtml(evaluation.audit_id || "Not available")}</div>
                </div>
            </div>
            ${breakdown.map(item => `
                <div class="criterion-row">
                    <div class="criterion-row-top">
                        <div class="criterion-name">${escapeHtml(item.criterion_name || item.criterion_id || "Criterion")}</div>
                        <span class="badge ${decisionBadgeClass(item.status)}">${escapeHtml(formatDecision(item.status))}</span>
                    </div>
                    <div class="criterion-reason">${escapeHtml(item.reason || "No reason provided")}</div>
                </div>
            `).join("")}
            <div class="summary-box">${escapeHtml(evaluation.summary || "No summary available.")}</div>
            ${adminReviewControls}
        `;
        if (currentUser?.role === "admin") {
            const decisionSelect = el("evaluation-override-decision");
            if (decisionSelect) decisionSelect.value = evaluation.decision || "MANUAL_REVIEW";
        }
        openModal("evaluation-modal");
    } catch (error) {
        showToast("Unable to load report", error.message);
    }
}

async function submitEvaluationOverride(evaluationId) {
    const newDecision = el("evaluation-override-decision")?.value || "";
    const reason = (el("evaluation-override-reason")?.value || "").trim();

    if (!newDecision) {
        showToast("Decision required", "Please choose the updated application decision.");
        return;
    }

    if (!reason) {
        showToast("Reason required", "Please add a short reason for the reconsideration.");
        return;
    }

    try {
        await apiPostJson(`/evaluations/${evaluationId}/override`, {
            new_decision: newDecision,
            reason,
        });
        showToast("Application updated", "The tender application decision has been reconsidered.");
        await fetchTenders();
        await fetchStats();
        if (currentPage === "evaluations" && currentEvaluationsTenderId) {
            await fetchEvaluationsView(currentEvaluationsTenderId);
        }
        await showEvaluationDetail(evaluationId);
    } catch (error) {
        showToast("Unable to reconsider application", error.message);
    }
}

async function fetchCitizenTenders() {
    const target = el("citizen-list");
    if (!target) return;
    try {
        const payload = await apiGet("/citizen/tenders");
        cachedCitizenTenders = payload.tenders || [];
        
        // Calculate KPIs
        const publishedCount = cachedCitizenTenders.length;
        const awardedCount = cachedCitizenTenders.filter(t => t.status === "completed").length;
        // Basic amount extraction for KPI
        let totalValue = 0;
        cachedCitizenTenders.forEach(t => {
            const match = (t.investment_amount || "").match(/[\d,]+/);
            if (match) {
                totalValue += parseInt(match[0].replace(/,/g, '')) || 0;
            }
        });

        if (el("citizen-stat-tenders")) el("citizen-stat-tenders").textContent = publishedCount;
        if (el("citizen-stat-awarded")) el("citizen-stat-awarded").textContent = awardedCount;
        if (el("citizen-stat-value")) el("citizen-stat-value").textContent = totalValue > 0 ? `₹${(totalValue/10000000).toFixed(1)} Cr` : "TBD";

        target.innerHTML = cachedCitizenTenders.length ? cachedCitizenTenders.map(item => `

            <article class="item-card">
                <div class="item-card-top">
                    <div>
                        <div class="item-card-title">${escapeHtml(item.title)}</div>
                        <div class="item-card-desc">${escapeHtml(item.department || "Procurement Department")}</div>
                    </div>
                    <span class="badge ${decisionBadgeClass(item.status)}">${escapeHtml(formatDecision(item.status))}</span>
                </div>
                <div class="item-card-meta" style="margin: 12px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; border-top: 1px solid var(--gray-50); padding-top: 12px;">
                    <div style="font-size: 12px; color: var(--gray-500);">
                        <strong>Sector:</strong> ${escapeHtml(item.sector || "General")}
                    </div>
                    <div style="font-size: 12px; color: var(--gray-500);">
                        <strong>Deadline:</strong> ${item.deadline ? escapeHtml(formatDate(item.deadline)) : "Closed"}
                    </div>
                </div>
                <div class="item-card-actions">
                    <button class="btn-ghost" type="button" onclick="showCitizenTenderDetail('${escapeHtml(item.tender_id)}')">View Details</button>
                    <button class="btn-ghost" type="button" onclick="showTenderTimeline('${escapeHtml(item.tender_id)}')">View Timeline</button>
                </div>
            </article>

        `).join("") : emptyState("No published tenders are available for citizens yet.");
    } catch (error) {
        target.innerHTML = emptyState(error.message);
    }
}

async function showCitizenTenderDetail(tenderId) {
    try {
        const [detailPayload, explanationPayload] = await Promise.all([
            apiGet(`/citizen/tender/${tenderId}`),
            apiGet(`/citizen/tender/${tenderId}/explanation`),
        ]);
        const tender = detailPayload.tender;
        const explanation = explanationPayload.explanation;
        const comparisonRows = tender.comparative_table || [];
        el("citizen-detail-content").innerHTML = `
            <div class="citizen-detail-layout">
                <section class="citizen-section">
                    <h4>${escapeHtml(tender.title)}</h4>
                    <div class="citizen-chip-row">
                        <span class="citizen-chip">Winner: ${escapeHtml(tender.winning_bidder)}</span>
                        <span class="citizen-chip">Value: ${escapeHtml(tender.contract_value)}</span>
                        <span class="citizen-chip">Duration: ${escapeHtml(tender.duration)}</span>
                    </div>
                    <div class="citizen-status-note ${tender.verified_decision ? "ok" : "risk"}">
                        ${escapeHtml(explanation.winner)} was selected for public award view.
                    </div>
                </section>
                <section class="citizen-section">
                    <h4>Why this bidder won</h4>
                    <ul class="citizen-reasons">
                        ${(explanation.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}
                    </ul>
                    <div class="confidence-track">
                        <div class="confidence-fill" style="width:${Math.max(0, Math.min(100, (Number(explanation.confidence) || 0) * 100))}%"></div>
                    </div>
                </section>
                <section class="citizen-section">
                    <h4>Top comparison</h4>
                    <div class="citizen-table-wrap">
                        <table class="citizen-table">
                            <thead>
                                <tr><th>Bidder</th><th>Status</th><th>Key strength</th></tr>
                            </thead>
                            <tbody>
                                ${comparisonRows.map(row => `
                                    <tr>
                                        <td>${escapeHtml(row.bidder)}</td>
                                        <td>${escapeHtml(row.status)}</td>
                                        <td>${escapeHtml(row.key_strength)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        `;
        openModal("citizen-detail-modal");
    } catch (error) {
        showToast("Unable to load tender detail", error.message);
    }
}

async function showTenderTimeline(tenderId) {
    const target = el("timeline-details");
    if (!target) return;
    target.innerHTML = `<div class="empty-state"><p>Loading timeline...</p></div>`;
    openModal("timeline-modal");
    try {
        const payload = await apiGet(`/tenders/${tenderId}/timeline`);
        target.innerHTML = renderTimelineMarkup(payload);
    } catch (error) {
        target.innerHTML = emptyState(error.message);
    }
}

function renderTimelineMarkup(payload) {
    const items = payload.timeline || [];
    return `
        <div class="timeline-shell">
            <div class="timeline-head">
                <h3>${escapeHtml(payload.title || "Tender timeline")}</h3>
                <p class="page-sub">A step-by-step view of how this tender moved through the workflow.</p>
            </div>
            <div class="timeline-list">
                ${items.length ? items.map(item => `
                    <article class="timeline-item">
                        <div class="timeline-marker ${escapeHtml(item.type || "update")}"></div>
                        <div class="timeline-card">
                            <div class="timeline-meta">${escapeHtml(formatDate(item.at))}</div>
                            <h4>${escapeHtml(item.title)}</h4>
                            <p>${escapeHtml(item.description)}</p>
                        </div>
                    </article>
                `).join("") : `<div class="empty-state"><p>No timeline events are available yet.</p></div>`}
            </div>
        </div>
    `;
}

async function fetchTimelinePageData() {
    const listTarget = el("timeline-page-list");
    const detailTarget = el("timeline-page-detail");
    if (!listTarget || !detailTarget || !currentUser) return;

    try {
        const items = currentUser.role === "citizen"
            ? ((await apiGet("/citizen/tenders")).tenders || []).map(item => ({
                id: item.tender_id,
                title: item.title,
                subtitle: item.department || "Procurement Department",
                status: item.status,
            }))
            : ((cachedTenders.length ? cachedTenders : ((await apiGet("/tenders")).tenders || []))).map(item => ({
                id: item.id,
                title: item.title,
                subtitle: item.department || "Procurement Department",
                status: item.status,
            }));

        if (!items.length) {
            listTarget.innerHTML = emptyState("No tenders are available for timeline view yet.");
            detailTarget.innerHTML = emptyState("A tender timeline will appear here once records are available.");
            return;
        }

        listTarget.innerHTML = items.map((item, index) => `
            <button class="timeline-list-item ${index === 0 ? "active" : ""}" type="button" onclick="showTimelinePageDetail('${escapeHtml(item.id)}', this)">
                <div class="timeline-list-title">${escapeHtml(item.title)}</div>
                <div class="timeline-list-sub">${escapeHtml(item.subtitle)}</div>
                <span class="badge ${decisionBadgeClass(item.status)}">${escapeHtml(formatDecision(item.status))}</span>
            </button>
        `).join("");

        await showTimelinePageDetail(items[0].id);
    } catch (error) {
        listTarget.innerHTML = emptyState(error.message);
        detailTarget.innerHTML = emptyState(error.message);
    }
}

async function showTimelinePageDetail(tenderId, triggerButton = null) {
    const detailTarget = el("timeline-page-detail");
    if (!detailTarget) return;
    document.querySelectorAll(".timeline-list-item").forEach(node => {
        node.classList.toggle("active", node === triggerButton || node.getAttribute("onclick")?.includes(`'${tenderId}'`));
    });
    detailTarget.innerHTML = `<div class="empty-state"><p>Loading timeline...</p></div>`;
    try {
        const payload = await apiGet(`/tenders/${tenderId}/timeline`);
        detailTarget.innerHTML = renderTimelineMarkup(payload);
    } catch (error) {
        detailTarget.innerHTML = emptyState(error.message);
    }
}

async function fetchSectorDashboard() {
    const target = el("sector-dashboard");
    if (!target) return;
    try {
        const payload = await apiGet("/citizen/sectors");
        const sectors = payload.sectors || [];
        target.innerHTML = `
            <div class="sector-grid">
                ${sectors.map(item => `
                    <button class="sector-card" type="button" onclick="showSectorDetail('${escapeHtml(item.sector)}')">
                        <div class="sector-card-top">
                            <h3>${escapeHtml(item.sector)}</h3>
                            <span class="badge badge-active">${escapeHtml(String(item.percentage))}%</span>
                        </div>
                        <p>${escapeHtml(item.description)}</p>
                        <div class="sector-card-meta">${escapeHtml(String(item.tender_count))} tenders</div>
                    </button>
                `).join("")}
            </div>
            <div id="sector-detail-panel"></div>
        `;
    } catch (error) {
        target.innerHTML = emptyState(error.message);
    }
}

function showCitizenSectorTab(tabName) {
    document.querySelectorAll(".citizen-sector-tab").forEach(node => {
        node.classList.toggle("active", node.dataset.citizenTab === tabName);
    });
    document.querySelectorAll(".citizen-sector-panel").forEach(node => node.classList.remove("active"));
    el(`citizen-${tabName}-tab`)?.classList.add("active");
}

function populateCitizenStatsFilter(selectId, values, selectedValue, defaultLabel, formatter = value => value) {
    const select = el(selectId);
    if (!select) return;
    select.innerHTML = `
        <option value="">${escapeHtml(defaultLabel)}</option>
        ${(values || []).map(value => `
            <option value="${escapeHtml(value)}" ${value === selectedValue ? "selected" : ""}>${escapeHtml(formatter(value))}</option>
        `).join("")}
    `;
}

function renderCitizenStatsOptions(filters) {
    cachedCitizenStatsFilters = filters || null;
    populateCitizenStatsFilter("citizen-stats-sector", filters?.available_sectors || [], filters?.sector || "", "All sectors");
    populateCitizenStatsFilter("citizen-stats-department", filters?.available_departments || [], filters?.department || "", "All departments");
    populateCitizenStatsFilter("citizen-stats-status", filters?.available_statuses || [], filters?.tender_status || "", "All statuses", formatDecision);
}

async function fetchCitizenAmountStats() {
    const summaryTarget = el("citizen-stats-summary");
    const breakdownTarget = el("citizen-stats-breakdown");
    if (!summaryTarget || !breakdownTarget) return;

    const params = new URLSearchParams();
    const sector = el("citizen-stats-sector")?.value || "";
    const department = el("citizen-stats-department")?.value || "";
    const tenderStatus = el("citizen-stats-status")?.value || "";
    if (sector) params.set("sector", sector);
    if (department) params.set("department", department);
    if (tenderStatus) params.set("tender_status", tenderStatus);

    try {
        const query = params.toString();
        const payload = await apiGet(`/citizen/stats${query ? `?${query}` : ""}`);
        const summary = payload.summary || {};
        const breakdown = payload.breakdown || [];
        renderCitizenStatsOptions(payload.filters || {});

        summaryTarget.innerHTML = `
            <div class="citizen-stats-grid">
                <article class="kpi-card">
                    <div><p class="kpi-label">Matching Tenders</p><p class="kpi-value">${escapeHtml(String(summary.total_tenders ?? 0))}</p></div>
                </article>
                <article class="kpi-card">
                    <div><p class="kpi-label">Amounts Found</p><p class="kpi-value">${escapeHtml(String(summary.tenders_with_amount ?? 0))}</p></div>
                </article>
                <article class="kpi-card">
                    <div><p class="kpi-label">Total Amount</p><p class="kpi-value citizen-kpi-value">${escapeHtml(formatCurrencyINR(summary.total_amount_rupees))}</p></div>
                </article>
                <article class="kpi-card">
                    <div><p class="kpi-label">Average Amount</p><p class="kpi-value citizen-kpi-value">${escapeHtml(formatCurrencyINR(summary.average_amount_rupees))}</p></div>
                </article>
            </div>
            <section class="sector-insight-card" style="margin-top:16px">
                <p class="sector-insight-label">Highest Value Tender</p>
                <p class="sector-insight-text">${escapeHtml(summary.highest_amount_tender || "No matching tender")}</p>
                <p class="page-sub" style="margin-top:8px">${escapeHtml(formatCurrencyINR(summary.highest_amount_rupees))}</p>
            </section>
        `;

        breakdownTarget.innerHTML = `
            <section class="sector-chart-card">
                <h3>Amount breakdown</h3>
                <table class="sector-table">
                    <thead>
                        <tr><th>Tender ID</th><th>Title</th><th>Sector</th><th>Department</th><th>Status</th><th>Amount</th></tr>
                    </thead>
                    <tbody>
                        ${breakdown.length ? breakdown.map(item => `
                            <tr>
                                <td>${escapeHtml(item.tender_id)}</td>
                                <td>${escapeHtml(item.title)}</td>
                                <td>${escapeHtml(item.sector)}</td>
                                <td>${escapeHtml(item.department)}</td>
                                <td>${escapeHtml(formatDecision(item.status))}</td>
                                <td>${escapeHtml(item.amount || "Not disclosed")}</td>
                            </tr>
                        `).join("") : `<tr><td colspan="6">No tenders matched the selected filters.</td></tr>`}
                    </tbody>
                </table>
            </section>
        `;
    } catch (error) {
        summaryTarget.innerHTML = emptyState(error.message);
        breakdownTarget.innerHTML = "";
    }
}

function resetCitizenAmountStatsFilters() {
    if (el("citizen-stats-sector")) el("citizen-stats-sector").value = "";
    if (el("citizen-stats-department")) el("citizen-stats-department").value = "";
    if (el("citizen-stats-status")) el("citizen-stats-status").value = "";
    fetchCitizenAmountStats();
}

async function showSectorDetail(sectorName) {
    const detailPanelId = "sector-detail-panel";
    const panel = el(detailPanelId);
    if (!panel) return;
    try {
        const payload = await apiGet(`/citizen/sectors/${encodeURIComponent(sectorName)}`);
        const tenders = payload.tenders || [];
        panel.innerHTML = `
            <section class="sector-chart-card" style="margin-top:16px">
                <h3>${escapeHtml(payload.sector)} sector tenders</h3>
                <table class="sector-table">
                    <thead>
                        <tr><th>Tender ID</th><th>Title</th><th>Department</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        ${tenders.map(item => `
                            <tr>
                                <td>${escapeHtml(item.tender_id)}</td>
                                <td>${escapeHtml(item.title)}</td>
                                <td>${escapeHtml(item.department)}</td>
                                <td>${escapeHtml(formatDecision(item.status))}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </section>
        `;
    } catch (error) {
        panel.innerHTML = emptyState(error.message);
    }
}

function renderRoleWorkspace(role) {
    const workspace = el("role-workspace");
    const contractorModule = el("contractor-analysis-module");
    if (!workspace || !contractorModule) return;

    if (role === "admin") {
        workspace.innerHTML = `
            <section class="workspace-shell">
                <div class="workspace-hero">
                    <div>
                        <p class="workspace-eyebrow">Admin Control</p>
                        <h2 class="workspace-title">Run procurement from intake to public outcome</h2>
                        <p class="workspace-copy">Create tenders, control review workflows, compare evaluations, and publish defensible results from one decision workspace.</p>
                    </div>
                    <div class="workspace-action-grid">
                        <button class="workspace-action" type="button" onclick="showCreateTenderModal()">Create Tender</button>
                        <button class="workspace-action" type="button" onclick="showPage('admin')">Open Admin Panel</button>
                    </div>
                </div>
            </section>
        `;
        contractorModule.innerHTML = "";
        return;
    }

    if (role === "citizen") {
        workspace.innerHTML = `
            <section class="workspace-shell">
                <div class="workspace-hero">
                    <div>
                        <p class="workspace-eyebrow">Citizen View</p>
                        <h2 class="workspace-title">Explore public procurement outcomes with clarity</h2>
                        <p class="workspace-copy">See finalized tenders, contract amounts, winning bidders, and plain-language summaries without exposing internal review data.</p>
                    </div>
                    <div class="workspace-action-grid">
                        <button class="workspace-action" type="button" onclick="showPage('citizen')">Awarded Tenders</button>
                        <button class="workspace-action" type="button" onclick="showPage('sectors')">Sector Dashboard</button>
                    </div>
                </div>
            </section>
        `;
        contractorModule.innerHTML = "";
        return;
    }

    workspace.innerHTML = `
        <section class="workspace-shell">
            <div class="workspace-hero">
                <div>
                    <p class="workspace-eyebrow">Contractor Workspace</p>
                    <h2 class="workspace-title">Prepare stronger bids before submission</h2>
                    <p class="workspace-copy">Track opportunities, review your bid submissions, and run a quick document self-check before you submit to a tender.</p>
                </div>
                <div class="workspace-action-grid">
                    <button class="workspace-action" type="button" onclick="showSubmitModal()">Submit Bid</button>
                    <button class="workspace-action" type="button" onclick="showPage('submissions')">Open Submissions</button>
                </div>
            </div>
            <div id="contractor-recent-submissions" class="recent-activity-section" style="margin-top: 32px;"></div>
        </section>
    `;

    contractorModule.innerHTML = `
        <section class="workspace-shell">
            <div class="workspace-card">
                <div class="workspace-card-head">
                    <div>
                        <p class="workspace-eyebrow">PDF Analyzer</p>
                        <h3 class="workspace-card-title">Contractor self-check</h3>
                    </div>
                    <span class="analysis-status review" id="analysis-status-pill">Waiting for document</span>
                </div>
                <div class="contractor-analysis-controls">
                    <label class="analysis-upload-box">
                        <input id="analysis-upload-input" type="file" accept=".pdf">
                        <span class="analysis-upload-title">Choose a PDF to analyze</span>
                        <span class="analysis-upload-sub" id="analysis-upload-sub">Only PDF files are supported for this quick check.</span>
                        <span class="analysis-file-meta" id="analysis-file-meta">No file selected</span>
                    </label>
                    <div class="contractor-analysis-actions">
                        <button class="btn-solid btn-sm" type="button" id="analysis-upload-btn">Upload PDF</button>
                        <button class="btn-ghost" type="button" id="analysis-run-btn">Run Analysis</button>
                    </div>
                    <div id="analysis-result-slot"></div>
                </div>
            </div>
        </section>
    `;

    el("analysis-upload-input")?.addEventListener("change", event => {
        const file = event.target.files?.[0];
        contractorAnalysisState.fileName = file?.name || "";
        if (el("analysis-file-meta")) {
            el("analysis-file-meta").textContent = file?.name || "No file selected";
        }
    });
    el("analysis-upload-btn")?.addEventListener("click", uploadContractorDocument);
    el("analysis-run-btn")?.addEventListener("click", analyzeContractorDocument);
}

async function uploadContractorDocument() {
    const file = el("analysis-upload-input")?.files?.[0];
    if (!file) {
        showToast("Select a PDF", "Choose a file before uploading.");
        return;
    }

    contractorAnalysisState.isUploading = true;
    updateContractorAnalysisStatus("Uploading...", "review");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const payload = await apiPostForm("/contractor/upload", formData);
        contractorAnalysisState.fileId = payload.file_id;
        contractorAnalysisState.fileName = payload.file_name;
        contractorAnalysisState.result = null;
        updateContractorAnalysisStatus("Ready to analyze", "review");
        renderContractorAnalysisResult();
        showToast("Upload complete", payload.file_name);
    } catch (error) {
        updateContractorAnalysisStatus("Upload failed", "not-eligible");
        showToast("Upload failed", error.message);
    } finally {
        contractorAnalysisState.isUploading = false;
    }
}

async function analyzeContractorDocument() {
    if (!contractorAnalysisState.fileId) {
        showToast("Upload first", "Please upload a PDF before starting analysis.");
        return;
    }

    contractorAnalysisState.isAnalyzing = true;
    updateContractorAnalysisStatus("Analyzing...", "review");

    try {
        const payload = await apiPostForm(`/contractor/analyze/${contractorAnalysisState.fileId}`, new FormData());
        contractorAnalysisState.result = payload;
        const statusClass =
            payload.eligibility_status === "ELIGIBLE" ? "eligible" :
            payload.eligibility_status === "NOT_ELIGIBLE" ? "not-eligible" :
            "review";
        updateContractorAnalysisStatus(formatDecision(payload.eligibility_status), statusClass);
        renderContractorAnalysisResult();
    } catch (error) {
        updateContractorAnalysisStatus("Analysis failed", "not-eligible");
        showToast("Analysis failed", error.message);
    } finally {
        contractorAnalysisState.isAnalyzing = false;
    }
}

function updateContractorAnalysisStatus(text, statusClass) {
    const pill = el("analysis-status-pill");
    if (!pill) return;
    pill.className = `analysis-status ${statusClass}`;
    pill.textContent = text;
}

function renderContractorAnalysisResult() {
    const slot = el("analysis-result-slot");
    if (!slot) return;
    const result = contractorAnalysisState.result;
    if (!result) {
        slot.innerHTML = emptyState("Upload a PDF and run analysis to see extracted insights.");
        return;
    }

    const extracted = result.extracted_data || {};
    const confidencePercent = Math.round((Number(result.confidence) || 0) * 100);
    const certifications = Array.isArray(extracted.certifications) ? extracted.certifications.join(", ") : extracted.certifications;
    slot.innerHTML = `
        <div class="contractor-result-grid">
            <div class="eval-meta-box">
                <div class="label">Bidder</div>
                <div class="value" style="font-size:16px">${escapeHtml(extracted.bidder_name || "Not found")}</div>
            </div>
            <div class="eval-meta-box">
                <div class="label">Turnover</div>
                <div class="value" style="font-size:16px">${escapeHtml(extracted.turnover || "Not found")}</div>
            </div>
            <div class="eval-meta-box sector-highlight">
                <div class="label">Sector</div>
                <div class="value" style="font-size:16px">${escapeHtml(result.sector || "General")}</div>
            </div>
            <div class="eval-meta-box">
                <div class="label">Certifications</div>
                <div class="value" style="font-size:14px">${escapeHtml(certifications || "Not found")}</div>
            </div>
        </div>
        <div class="analysis-projects-block">
            <p><strong>Projects:</strong> ${escapeHtml(extracted.projects || "Not found")}</p>
            <p><strong>Summary:</strong> ${escapeHtml(result.summary || "No summary available.")}</p>
        </div>
        <div class="analysis-confidence-block">
            <div class="analysis-confidence-head">
                <strong>Confidence</strong>
                <span>${confidencePercent}%</span>
            </div>
            <div class="analysis-confidence-track">
                <div class="analysis-confidence-fill" style="width:${confidencePercent}%"></div>
            </div>
        </div>
    `;
}

async function fetchAdminUsers() {
    const target = el("users-list");
    if (!target || currentUser?.role !== "admin") return;
    try {
        const payload = await apiGet("/admin/users");
        renderAdminUsers(payload.users || []);
    } catch (error) {
        target.innerHTML = emptyState(error.message || "Unable to load users.");
    }
}

function renderAdminUsers(users) {
    const target = el("users-list");
    if (!target) return;
    if (!users.length) {
        target.innerHTML = emptyState("No users found.");
        return;
    }

    target.innerHTML = users.map(user => `
        <article class="item-card">
            <div class="item-card-top">
                <div>
                    <div class="item-card-title">${escapeHtml(user.full_name || user.username || "Unnamed User")}</div>
                    <div class="item-card-desc">${escapeHtml(user.email || "No email available")}</div>
                </div>
                <span class="badge ${user.is_active ? "badge-eligible" : "badge-not-eligible"}">${escapeHtml(user.is_active ? "Active" : "Inactive")}</span>
            </div>
            <div class="item-card-meta">
                <span>Username: ${escapeHtml(user.username || "-")}</span>
                <span>Role: ${escapeHtml(formatDecision(user.role || "-"))}</span>
                <span>Company: ${escapeHtml(user.company_name || "Not provided")}</span>
                <span>Joined: ${escapeHtml(formatDate(user.created_at))}</span>
            </div>
        </article>
    `).join("");
}

function showAdminTab(tabName) {
    document.querySelectorAll(".tab").forEach(node => {
        node.classList.toggle("active", node.dataset.tab === tabName);
    });
    document.querySelectorAll(".admin-tab").forEach(node => node.classList.remove("active"));
    el(`${tabName}-tab`)?.classList.add("active");
}

function openModal(id) {
    const node = el(id);
    if (!node) return;
    node.classList.remove("hidden");
    node.style.display = "flex";
}

function closeModal(id) {
    const node = el(id);
    if (!node) return;
    node.classList.add("hidden");
    node.style.display = "";
}

function emptyState(message) {
    return `<div class="empty-state"><p>${escapeHtml(message)}</p></div>`;
}

function renderListState(id, message) {
    if (el(id)) el(id).innerHTML = emptyState(message);
}

function getSupportTickets() {
    try {
        const raw = localStorage.getItem(SUPPORT_TICKETS_KEY);
        if (!raw) {
            const welcome = [{
                id: "welcome-1",
                userName: "System",
                userRole: "admin",
                subject: "Welcome to Anveshane AI Support",
                message: "This is your communication hub. All inquiries from citizens and bidders will appear here.",
                status: "active",
                is_read: false,
                timestamp: new Date().toISOString()
            }];
            localStorage.setItem(SUPPORT_TICKETS_KEY, JSON.stringify(welcome));
            return welcome;
        }
        const tickets = JSON.parse(raw);
        // Ensure legacy tickets have is_read defined
        tickets.forEach(t => {
            if (typeof t.is_read === 'undefined') t.is_read = true;
        });
        return tickets;
    } catch (error) {
        return [];
    }
}

function setSupportTickets(tickets) {
    localStorage.setItem(SUPPORT_TICKETS_KEY, JSON.stringify(tickets));
}

function openTicketModal(type) {
    if (el("ticket-type")) el("ticket-type").value = type;
    if (el("ticket-modal-title")) {
        el("ticket-modal-title").textContent = {
            contractor: "Raise a Support Ticket",
            evaluation: "Request Evaluation Review",
            document: "Report a Document Issue",
            info: "Request More Details",
            general: "Ask a Question",
            concern: "Report a Concern",
        }[type] || "Raise a Ticket";
    }
    el("ticket-form")?.reset();
    if (el("ticket-type")) el("ticket-type").value = type;
    openModal("ticket-modal");
}

async function submitTicket(event) {
    event.preventDefault();
    if (!currentUser) return;

    try {
        const payload = {
            subject: el("ticket-subject").value,
            message: el("ticket-message").value,
            priority: el("ticket-priority").value,
        };
        await apiPostJson("/support/tickets", payload);
        closeModal("ticket-modal");
        await renderSupportViews();
        showToast("Ticket submitted", "Your request has been saved.");
    } catch (error) {
        showToast("Failed to submit ticket", error.message);
    }
}

async function renderSupportViews() {
    if (!currentUser) return;

    try {
        const payload = await apiGet("/support/tickets");
        const tickets = payload || [];
        const ownTickets = tickets.filter(ticket => ticket.user_id === currentUser.id);

        if (currentUser.role === "contractor") {
            renderTicketList("tickets-list", ownTickets, "No tickets raised yet.");
        }

        if (currentUser.role === "citizen") {
            renderTicketList("citizen-tickets-list", ownTickets, "No requests submitted yet.");
        }
    } catch (error) {
        console.error("Failed to render support views", error);
    }
}

async function renderInboxPage() {
    if (!currentUser) return;
    try {
        const payload = await apiGet("/support/tickets");
        const tickets = payload || [];
        renderInboxThreadList("inbox-thread-list", tickets);
    } catch (error) {
        console.error("Failed to render inbox page", error);
    }
}

function renderTicketList(targetId, tickets, emptyText = "No tickets raised yet.") {
    const target = el(targetId);
    if (!target) return;
    target.innerHTML = tickets.length ? tickets.map(ticket => `
        <article class="ticket-card">
            <div>
                <div class="ticket-subject">${escapeHtml(ticket.subject)}</div>
                <div class="ticket-meta">${escapeHtml(formatDate(ticket.created_at))} | ${escapeHtml(formatDecision(ticket.status))}</div>
            </div>
            <span class="priority-badge ${ticket.priority === "high" ? "badge-not-eligible" : ticket.priority === "medium" ? "badge-manual-review" : "badge-pending"}">${escapeHtml(formatDecision(ticket.priority))}</span>
        </article>
    `).join("") : `<p style="color:var(--gray-400);font-size:13px;padding:20px 0">${escapeHtml(emptyText)}</p>`;
}

function renderInboxList(targetId, tickets) {
    const target = el(targetId);
    if (!target) return;
    target.innerHTML = tickets.length ? tickets.map(ticket => `
        <article class="ticket-card">
            <div>
                <div class="ticket-subject">${escapeHtml(ticket.subject)}</div>
                <div class="ticket-meta">${escapeHtml(ticket.replies[ticket.replies.length - 1].message)}</div>
            </div>
            <span class="badge badge-eligible">${escapeHtml(formatDecision(ticket.status))}</span>
        </article>
    `).join("") : `<p style="color:var(--gray-400);font-size:13px;padding:20px 0">No replies received yet.</p>`;
}

function renderInboxThreadList(targetId, tickets) {
    const target = el(targetId);
    if (!target) return;
    const messages = tickets
        .flatMap(ticket => {
            const isAdmin = currentUser?.role === "admin";
            const outgoing = [{
                direction: isAdmin ? "incoming" : "outgoing",
                subject: ticket.subject,
                status: ticket.status,
                sentAt: ticket.created_at,
                message: ticket.message,
                type: ticket.type || "request",
                priority: ticket.priority,
                is_read: ticket.is_read,
                ticket_id: ticket.id,
                owner: ticket.username || currentUser?.username || "User",
            }];
            const incoming = (ticket.replies || []).map(reply => ({
                direction: isAdmin ? "outgoing" : "incoming",
                subject: ticket.subject,
                status: ticket.status,
                sentAt: reply.sent_at,
                message: reply.message,
                type: "reply",
                priority: ticket.priority,
                owner: isAdmin ? "Admin" : (ticket.username || "User"),
            }));
            return [...outgoing, ...incoming];
        })
        .sort((a, b) => new Date(b.sentAt).getTime() - new Date(a.sentAt).getTime());

    target.innerHTML = messages.length ? messages.map(message => `
        <article class="ticket-card inbox-mail-card" onclick="markMessageRead('${message.ticket_id}'); showToast('${escapeHtml(message.subject)}', '${escapeHtml(message.message).replace(/'/g, "\\'")}')">
            <div class="inbox-direction ${message.direction}">
                ${message.direction === "outgoing"
                    ? `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>`
                    : `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H7"/><path d="M11 6l-6 6 6 6"/></svg>`}
            </div>
            <div class="inbox-mail-main">
                <div class="inbox-mail-sender" style="display: flex; align-items: center; gap: 8px;">
                    ${escapeHtml(message.owner)}
                    ${!message.is_read && message.direction === 'incoming' ? '<span style="width: 8px; height: 8px; background: var(--blue); border-radius: 50%;"></span>' : ''}
                </div>
                <div class="inbox-mail-content">
                    <span class="inbox-mail-subject" ${!message.is_read && message.direction === 'incoming' ? 'style="font-weight: 700;"' : ''}>${escapeHtml(message.subject)}</span>
                    <span class="inbox-mail-snippet"> - ${escapeHtml(message.message || "No message provided.")}</span>
                </div>
                <div class="inbox-mail-date">${escapeHtml(formatDate(message.sentAt))}</div>
                <span class="badge ${decisionBadgeClass(message.status)}">${escapeHtml(formatDecision(message.status))}</span>
            </div>
        </article>
    `).join("") : emptyState("No messages yet.");
}

async function markMessageRead(ticketId) {
    if (!ticketId) return;
    try {
        await apiPostJson(`/support/tickets/${ticketId}/read`, {});
        await renderInboxPage();
    } catch (error) {
        console.error("Failed to mark message as read", error);
    }
}

async function renderAdminSupport() {
    const target = el("admin-support-list");
    const counter = el("admin-ticket-counter");
    if (!target || !counter) return;

    try {
        const payload = await apiGet("/support/tickets");
        const tickets = (payload || []).filter(t => t.status !== 'resolved');
        counter.textContent = tickets.length;
        counter.classList.toggle("hidden", tickets.length === 0);

        target.innerHTML = tickets.length ? tickets.map(ticket => `
            <article class="ticket-card admin-ticket-card">
                <div>
                    <div class="ticket-subject">${escapeHtml(ticket.subject)}</div>
                    <div class="ticket-meta">${escapeHtml(ticket.username)} | ${escapeHtml(formatDecision(ticket.role))} | ${escapeHtml(formatDate(ticket.created_at))}</div>
                    <div class="item-card-desc" style="margin-top:8px">${escapeHtml(ticket.message)}</div>
                </div>
                <div class="admin-ticket-side">
                    <span class="priority-badge ${ticket.priority === "high" ? "badge-not-eligible" : ticket.priority === "medium" ? "badge-manual-review" : "badge-pending"}">${escapeHtml(formatDecision(ticket.priority))}</span>
                    <div class="admin-ticket-actions">
                        <button class="btn-ghost" type="button" onclick="openAdminReplyModal('${escapeHtml(ticket.id)}', 'replied')">Reply</button>
                        <button class="btn-ghost" type="button" onclick="resolveTicketDirectly('${escapeHtml(ticket.id)}')">Resolve</button>
                    </div>
                </div>
            </article>
        `).join("") : emptyState("No support tickets yet.");
    } catch (error) {
        target.innerHTML = emptyState("Failed to load tickets: " + error.message);
    }
}

async function openAdminReplyModal(ticketId, status) {
    if (!ticketId) return;
    
    try {
        const payload = await apiGet("/support/tickets");
        const tickets = payload || [];
        const ticket = tickets.find(item => item.id === ticketId);
        if (!ticket) return;
        el("admin-reply-ticket-id").value = ticketId;
        el("admin-reply-status").value = status;
        el("admin-reply-title").textContent = `Reply to ${ticket.username}`;
        el("admin-reply-message").value = "";
        openModal("admin-reply-modal");
    } catch (error) {
        showToast("Error", "Could not load ticket details.");
    }
}

async function submitAdminReply(event) {
    event.preventDefault();
    const ticketId = el("admin-reply-ticket-id").value;
    const message = el("admin-reply-message").value;

    if (!message.trim()) return;

    try {
        await apiPostJson(`/support/tickets/${ticketId}/reply`, { message });
        closeModal("admin-reply-modal");
        await renderAdminSupport();
        await renderSupportViews();
        showToast("Reply saved", "The ticket response has been recorded.");
    } catch (error) {
        showToast("Failed to send reply", error.message);
    }
}

window.toggleAuthPage = toggleAuthPage;
window.logout = logout;
window.showPage = showPage;
window.showSubmitModal = showSubmitModal;
window.showCreateTenderModal = showCreateTenderModal;
window.closeModal = closeModal;
window.showAdminTab = showAdminTab;
window.openTicketModal = openTicketModal;
window.submitTicket = submitTicket;
window.submitAdminReply = submitAdminReply;
window.openAdminReplyModal = openAdminReplyModal;
window.markMessageRead = markMessageRead;
window.resolveTicketDirectly = resolveTicketDirectly;
window.startEditTender = startEditTender;
window.closeTender = closeTender;
window.reopenTender = reopenTender;
window.publishTender = publishTender;
window.recallTenderResult = recallTenderResult;
window.openTenderEvaluations = openTenderEvaluations;
window.showEvaluationDetail = showEvaluationDetail;
window.submitEvaluationOverride = submitEvaluationOverride;
window.showCitizenTenderDetail = showCitizenTenderDetail;
window.showTenderTimeline = showTenderTimeline;
window.showTimelinePageDetail = showTimelinePageDetail;
window.showSectorDetail = showSectorDetail;
window.toggleSidebar = toggleSidebar;
window.goToSearchFeature = goToSearchFeature;
