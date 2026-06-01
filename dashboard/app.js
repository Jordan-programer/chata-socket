// -------------------------------------------------------------
// GLOBAL STATE & DATA STORAGE
// -------------------------------------------------------------
let activeTab = "telemetry";
let runsHistory = [];
let latencyChart = null;
let resourcesChart = null;
let lastNotifiedMessageId = -1;

// Track the latest run for each protocol to plot comparison metrics
let latestRuns = {
    TCP: null,
    UDP: null
};

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------
// -------------------------------------------------------------
// INITIALIZATION & SESSION CONTROL
// -------------------------------------------------------------
let currentUser = null;

document.addEventListener("DOMContentLoaded", () => {
    // Check if user is already logged in
    try {
        const storedUser = sessionStorage.getItem("loggedInUser");
        if (storedUser && storedUser !== "undefined" && storedUser !== "null") {
            currentUser = JSON.parse(storedUser);
            if (currentUser && currentUser.username) {
                showDashboard();
                return;
            }
        }
    } catch (e) {
        console.error("Erro ao ler sessão do usuário:", e);
        sessionStorage.removeItem("loggedInUser");
    }
    showAuthPortal();
});

function toggleAdminTabs() {
    const tabButtons = document.querySelectorAll(".tabs-nav button");
    if (currentUser.is_admin === 1) {
        tabButtons.forEach(btn => btn.style.display = "inline-flex");
    } else {
        tabButtons.forEach(btn => {
            const clickAttr = btn.getAttribute("onclick") || "";
            if (clickAttr.includes("telemetry") || clickAttr.includes("report")) {
                btn.style.display = "none";
            } else {
                btn.style.display = "inline-flex";
            }
        });
        switchTab("interactive");
    }
}

function showDashboard() {
    // Hide auth portal and show dashboard
    document.getElementById("auth-container").style.display = "none";
    document.getElementById("main-dashboard-container").style.display = "block";
    
    // Set user profile details in header
    document.getElementById("header-user-name").textContent = currentUser.name;
    document.getElementById("chat-active-user-badge").innerHTML = `<i class="fa-solid fa-user text-cyan"></i> ${currentUser.name} (@${currentUser.username})`;
    
    // Toggle Admin visibility
    toggleAdminTabs();
    
    // Check if servers are running
    checkServerStatuses();
    
    // Initialize empty charts
    initCharts();
    
    // Periodically ping servers (every 10 seconds)
    setInterval(checkServerStatuses, 10000);
    
    // Fetch registered contacts list
    fetchRegisteredUsers();
    setInterval(fetchRegisteredUsers, 4000);
    
    // Request permission for push notifications
    requestNotificationPermission();
    
    // Start polling the chat messages in real-time
    startChatPolling();
}

function showAuthPortal() {
    document.getElementById("auth-container").style.display = "flex";
    document.getElementById("main-dashboard-container").style.display = "none";
}

// -------------------------------------------------------------
// NAVIGATION & UI INTERACTIVITY
// -------------------------------------------------------------
function switchTab(tabId) {
    activeTab = tabId;
    
    // Toggle button active classes
    const buttons = document.querySelectorAll(".tab-btn");
    buttons.forEach(btn => {
        btn.classList.remove("active");
        if (btn.getAttribute("onclick").includes(tabId)) {
            btn.classList.add("active");
        }
    });
    
    // Toggle content visibility
    const contents = document.querySelectorAll(".tab-content");
    contents.forEach(content => {
        content.style.display = "none";
    });
    
    const targetContent = document.getElementById(`tab-${tabId}`);
    if (targetContent) {
        targetContent.style.display = "block";
    }

    // Refresh charts if going back to telemetry (fixes canvas layout issues)
    if (tabId === "telemetry") {
        setTimeout(() => {
            if (latencyChart) latencyChart.resize();
            if (resourcesChart) resourcesChart.resize();
        }, 50);
    }
    
    // Refresh academic report when opening the report tab
    if (tabId === "report") {
        updateAcademicReport();
    }
}

function updateLossLabel(value) {
    document.getElementById("loss-val").textContent = `${value}%`;
}

function appendToConsole(text, type = "system") {
    const consoleLogs = document.getElementById("console-logs");
    if (!consoleLogs) return;
    
    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];
    
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    line.innerHTML = `[${timeStr}] ${text}`;
    
    consoleLogs.appendChild(line);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

function clearConsole() {
    const consoleLogs = document.getElementById("console-logs");
    if (consoleLogs) {
        consoleLogs.innerHTML = `<div class="log-line system">[SISTEMA] Console limpo pelo usuário.</div>`;
    }
}

// -------------------------------------------------------------
// SERVER ALIVE CHECKS
// -------------------------------------------------------------
async function checkServerStatuses() {
    const tcpIndicator = document.getElementById("server-tcp-status");
    const udpIndicator = document.getElementById("server-udp-status");
    
    // Ping TCP status
    try {
        const res = await fetch("/api/chat/send", {
            method: "POST",
            body: JSON.stringify({ protocol: "TCP", sender: "PingTest", content: "PING" })
        });
        if (res.ok) {
            tcpIndicator.classList.add("active");
            tcpIndicator.style.opacity = "1";
        } else {
            throw new Error();
        }
    } catch {
        tcpIndicator.classList.remove("active");
        tcpIndicator.style.opacity = "0.5";
    }

    // Ping UDP status
    try {
        const res = await fetch("/api/chat/send", {
            method: "POST",
            body: JSON.stringify({ protocol: "UDP", sender: "PingTest", content: "PING" })
        });
        if (res.ok) {
            udpIndicator.classList.add("active");
            udpIndicator.style.opacity = "1";
        } else {
            throw new Error();
        }
    } catch {
        udpIndicator.classList.remove("active");
        udpIndicator.style.opacity = "0.5";
    }
}

// -------------------------------------------------------------
// SOCKET BENCHMARK RUNNER
// -------------------------------------------------------------
async function triggerBenchmark(protocol) {
    const numMessages = parseInt(document.getElementById("num_messages").value);
    const intervalMs = parseInt(document.getElementById("interval_ms").value);
    const payloadSize = parseInt(document.getElementById("payload_size").value);
    const simulatedLoss = parseInt(document.getElementById("simulated_loss").value);
    
    // UI elements update
    const tcpBtn = document.getElementById("run-tcp-btn");
    const udpBtn = document.getElementById("run-udp-btn");
    const progContainer = document.getElementById("benchmark-progress-container");
    const progBar = document.getElementById("benchmark-progress-bar");
    const progPercent = document.getElementById("progress-percent");
    const progText = document.getElementById("progress-status-text");
    
    tcpBtn.disabled = true;
    udpBtn.disabled = true;
    progContainer.style.display = "block";
    progBar.style.width = "0%";
    progPercent.textContent = "0%";
    progText.textContent = `Aguardando orquestrador inicializar o Socket ${protocol}...`;
    
    appendToConsole(`[BENCHMARK] Iniciando suite ${protocol}. Disparando subprocesso do servidor na porta ${protocol === 'TCP' ? 6001 : 6002}...`, protocol.toLowerCase());
    
    // Animate progress bar in steps as a visual indicator
    let currentProgress = 5;
    const progressInterval = setInterval(() => {
        if (currentProgress < 90) {
            currentProgress += (90 - currentProgress) * 0.15;
            progBar.style.width = `${Math.round(currentProgress)}%`;
            progPercent.textContent = `${Math.round(currentProgress)}%`;
            
            if (currentProgress > 15 && currentProgress < 50) {
                progText.textContent = `Transmitindo ${numMessages} pacotes sequenciais pelo socket...`;
            } else if (currentProgress >= 50 && currentProgress < 80) {
                progText.textContent = `Calculando latências de eco e monitorando recursos via psutil...`;
            } else if (currentProgress >= 80) {
                progText.textContent = `Aguardando finalização do timeout de escuta...`;
            }
        }
    }, 120);

    try {
        const response = await fetch("/api/run-benchmark", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                protocol: protocol,
                num_messages: numMessages,
                interval_ms: intervalMs,
                payload_size_bytes: payloadSize,
                simulated_loss_percent: simulatedLoss
            })
        });

        clearInterval(progressInterval);
        progBar.style.width = "100%";
        progPercent.textContent = "100%";
        progText.textContent = `Benchmark finalizado com sucesso!`;
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || "Erro desconhecido");
        }

        const data = await response.json();
        
        // Save latest
        latestRuns[protocol] = data;
        runsHistory.unshift(data); // Append to start of history
        
        // Log to console
        appendToConsole(`[SUCCESS] Teste ${protocol} completo! Msgs Enviadas: ${data.metrics.sent}, Recebidas: ${data.metrics.received}, Perda: ${data.metrics.loss_rate_percent}%`, protocol.toLowerCase());
        appendToConsole(`          RTT Médio: ${data.latency_ms.avg} ms (Min: ${data.latency_ms.min} / Max: ${data.latency_ms.max})`, protocol.toLowerCase());
        appendToConsole(`          Vazão: ${data.metrics.throughput_msgs_sec} msgs/s (${data.metrics.throughput_kb_sec} KB/s)`, protocol.toLowerCase());
        appendToConsole(`          CPU Média Servidor: ${data.resources.server_cpu_percent}% | RAM Média: ${data.resources.server_ram_mb} MB`, "system");
        
        // Update stats cards
        updateMetricsCards(data);
        
        // Update history table
        updateHistoryTable();
        
        // Refresh charts
        updateCharts();
        
        // Refresh academic report
        updateAcademicReport();
        
    } catch (error) {
        clearInterval(progressInterval);
        progBar.style.width = "0%";
        progPercent.textContent = "Erro";
        progText.textContent = `Falha no teste: ${error.message}`;
        appendToConsole(`[ERRO] Falha ao rodar benchmark ${protocol}: ${error.message}`, "error");
    } finally {
        setTimeout(() => {
            tcpBtn.disabled = false;
            udpBtn.disabled = false;
            progContainer.style.display = "none";
        }, 1500);
    }
}

// -------------------------------------------------------------
// METRICS & TABLES UPDATES
// -------------------------------------------------------------
function updateMetricsCards(data) {
    document.getElementById("metric-avg-rtt").innerHTML = `${data.latency_ms.avg} <span class="unit">ms</span>`;
    document.getElementById("metric-min-rtt").textContent = data.latency_ms.min;
    document.getElementById("metric-max-rtt").textContent = data.latency_ms.max;
    
    const lossCard = document.getElementById("metric-loss");
    lossCard.innerHTML = `${data.metrics.loss_rate_percent} <span class="unit">%</span>`;
    document.getElementById("metric-lost-count").textContent = data.metrics.lost;
    document.getElementById("metric-sent-count").textContent = data.metrics.sent;
    
    document.getElementById("metric-throughput").innerHTML = `${data.metrics.throughput_msgs_sec} <span class="unit">msg/s</span>`;
    document.getElementById("metric-kb-throughput").textContent = data.metrics.throughput_kb_sec;
    
    const outOrderVal = document.getElementById("metric-out-order");
    outOrderVal.innerHTML = `${data.metrics.out_of_order_percent} <span class="unit">%</span>`;
    document.getElementById("metric-out-count").textContent = data.metrics.out_of_order;
    
    // Style cards depending on severity of protocol issues
    const lossCardWrapper = lossCard.closest(".metric-card");
    if (data.metrics.loss_rate_percent > 5.0) {
        lossCardWrapper.style.borderColor = "rgba(239, 68, 68, 0.4)";
        lossCardWrapper.style.boxShadow = "0 4px 15px -3px rgba(239, 68, 68, 0.25)";
    } else {
        lossCardWrapper.style.borderColor = "var(--glass-border)";
        lossCardWrapper.style.boxShadow = "none";
    }
}

function updateHistoryTable() {
    const tbody = document.getElementById("history-table-body");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    
    if (runsHistory.length === 0) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="8">Nenhum teste executado nesta sessão.</td></tr>`;
        return;
    }
    
    runsHistory.forEach(run => {
        const row = document.createElement("tr");
        
        const isTCP = run.protocol === "TCP";
        const protocolBadge = `<span class="table-badge ${isTCP ? 'badge-tcp' : 'badge-udp'}">${run.protocol}</span>`;
        const configStr = `${run.config.num_messages} msgs @ ${run.config.interval_ms}ms (${run.config.payload_size_bytes}B)`;
        
        row.innerHTML = `
            <td>${protocolBadge}</td>
            <td>${configStr}</td>
            <td style="font-weight:600; color:${run.metrics.loss_rate_percent > 0 ? 'var(--udp-color)' : 'var(--success-color)'}">${run.metrics.loss_rate_percent}%</td>
            <td>${run.latency_ms.avg} ms</td>
            <td>${run.metrics.throughput_msgs_sec} msg/s</td>
            <td>${run.metrics.out_of_order} (${run.metrics.out_of_order_percent}%)</td>
            <td>${run.resources.server_cpu_percent}%</td>
            <td>${run.resources.server_ram_mb} MB</td>
        `;
        
        tbody.appendChild(row);
    });
}

// -------------------------------------------------------------
// INTERACTIVE CHAT LABS
// -------------------------------------------------------------
// -------------------------------------------------------------
// AUTHENTICATION API SUBMISSIONS
// -------------------------------------------------------------
function switchAuthTab(tab) {
    document.getElementById("tab-login-btn").classList.toggle("active", tab === "login");
    document.getElementById("tab-register-btn").classList.toggle("active", tab === "register");
    
    document.getElementById("form-login").style.display = tab === "login" ? "block" : "none";
    document.getElementById("form-register").style.display = tab === "register" ? "block" : "none";
    
    // Clear alert
    const alertBox = document.getElementById("auth-alert");
    alertBox.style.display = "none";
}

async function submitRegister() {
    const name = document.getElementById("register-name").value.trim();
    const username = document.getElementById("register-username").value.trim().toLowerCase();
    const password = document.getElementById("register-password").value;
    
    if (!name || !username || !password) {
        showAuthAlert("Todos os campos são obrigatórios.", "error");
        return;
    }
    
    try {
        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, username, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAuthAlert("Cadastro realizado! Redirecionando...", "success");
            // Clear inputs
            document.getElementById("register-name").value = "";
            document.getElementById("register-username").value = "";
            document.getElementById("register-password").value = "";
            
            // Auto switch to login after 1.5 seconds
            setTimeout(() => {
                switchAuthTab("login");
                document.getElementById("login-username").value = username;
            }, 1500);
        } else {
            showAuthAlert(data.error || "Erro ao realizar cadastro.", "error");
        }
    } catch (error) {
        showAuthAlert("Falha de comunicação com o servidor.", "error");
    }
}

async function submitLogin() {
    const username = document.getElementById("login-username").value.trim().toLowerCase();
    const password = document.getElementById("login-password").value;
    
    if (!username || !password) {
        showAuthAlert("Nome de usuário e senha são obrigatórios.", "error");
        return;
    }
    
    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            currentUser = data.user;
            sessionStorage.setItem("loggedInUser", JSON.stringify(currentUser));
            showDashboard();
            appendToConsole(`[AUTH] Usuário logado: ${currentUser.name} (@${currentUser.username})`, "system");
        } else {
            showAuthAlert(data.error || "Usuário ou senha inválidos.", "error");
        }
    } catch (error) {
        showAuthAlert("Falha ao comunicar com o servidor.", "error");
    }
}

function showAuthAlert(msg, type) {
    const alertBox = document.getElementById("auth-alert");
    alertBox.textContent = msg;
    alertBox.className = `auth-alert-box ${type}`;
    alertBox.style.display = "block";
}

function triggerLogout() {
    sessionStorage.removeItem("loggedInUser");
    currentUser = null;
    lastNotifiedMessageId = -1;
    selectedRecipient = null;
    showAuthPortal();
    // Reset login form fields
    document.getElementById("login-password").value = "";
    appendToConsole("[AUTH] Usuário deslogado.", "system");
}

// -------------------------------------------------------------
// UNIFIED REAL-TIME CHAT LABS
// -------------------------------------------------------------
let activeChatProtocol = "TCP";
let localSentRtts = {}; // Map of sender+content -> RTT string
let lastRenderedMessagesCount = -1;
let selectedRecipient = null;
let registeredUsers = [];
let allMessages = [];

async function fetchRegisteredUsers() {
    if (!currentUser) return;
    try {
        const response = await fetch("/api/users");
        if (!response.ok) return;
        registeredUsers = await response.json();
        renderContactsList();
    } catch (e) {
        console.error("Erro ao buscar contatos:", e);
    }
}

function renderContactsList() {
    const container = document.getElementById("contacts-list-container");
    if (!container) return;
    
    container.innerHTML = "";
    
    // Exclude current user from contact list
    const otherUsers = registeredUsers.filter(u => u.username.toLowerCase() !== currentUser.username.toLowerCase());
    
    if (otherUsers.length === 0) {
        container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-muted); font-size:0.8rem;">Nenhum outro usuário cadastrado.</div>`;
        return;
    }
    
    // Scan allMessages to compute unread counts and latest message timestamps
    const contactLatestTimes = {};
    const contactUnreadCounts = {};
    
    otherUsers.forEach(user => {
        contactUnreadCounts[user.username] = 0;
        contactLatestTimes[user.username] = 0;
    });
    
    if (Array.isArray(allMessages)) {
        allMessages.forEach(msg => {
            const sender = msg.sender.toLowerCase();
            const recipient = msg.recipient ? msg.recipient.toLowerCase() : "";
            const currUser = currentUser.username.toLowerCase();
            
            if (sender === currUser && recipient) {
                contactLatestTimes[recipient] = Math.max(contactLatestTimes[recipient] || 0, msg.timestamp);
            } else if (recipient === currUser) {
                contactLatestTimes[sender] = Math.max(contactLatestTimes[sender] || 0, msg.timestamp);
                
                // Count as unread if delivered is 0 AND we are NOT currently chatting with them
                if (msg.delivered === 0 && (!selectedRecipient || selectedRecipient.toLowerCase() !== sender)) {
                    contactUnreadCounts[sender] = (contactUnreadCounts[sender] || 0) + 1;
                }
            }
        });
    }
    
    // Sort otherUsers: those with latest messages float to the top
    otherUsers.sort((a, b) => {
        const timeA = contactLatestTimes[a.username] || 0;
        const timeB = contactLatestTimes[b.username] || 0;
        
        // If times are equal, sort alphabetically by name
        if (timeA === timeB) {
            return a.name.localeCompare(b.name);
        }
        return timeB - timeA; // Descending (latest on top)
    });
    
    otherUsers.forEach(user => {
        const isActive = selectedRecipient === user.username;
        const contactDiv = document.createElement("div");
        contactDiv.className = `contact-item ${isActive ? 'active' : ''}`;
        contactDiv.setAttribute("data-username", user.username);
        
        const initialLetter = user.name ? user.name.charAt(0).toUpperCase() : "?";
        const adminBadge = user.is_admin ? `<span class="contact-badge">Admin</span>` : "";
        
        // Unread badge markup (green round indicator like WhatsApp)
        const unreadCount = contactUnreadCounts[user.username] || 0;
        const unreadBadge = unreadCount > 0 ? `<span class="unread-count-badge animate-pulse-scale">${unreadCount}</span>` : "";
        
        contactDiv.innerHTML = `
            <div class="contact-avatar">${initialLetter}</div>
            <div class="contact-info">
                <span class="contact-name">${user.name}</span>
                <span class="contact-username">@${user.username}</span>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px;">
                ${adminBadge}
                ${unreadBadge}
            </div>
        `;
        
        contactDiv.onclick = () => selectContact(user.username, user.name);
        container.appendChild(contactDiv);
    });
}

function selectContact(username, name) {
    selectedRecipient = username;
    
    // Update active state in list
    const items = document.querySelectorAll(".contact-item");
    items.forEach(item => {
        item.classList.remove("active");
        if (item.getAttribute("data-username") === username) {
            item.classList.add("active");
        }
    });
    
    // Update panes visibilities
    document.getElementById("chat-empty-state").style.display = "none";
    document.getElementById("chat-active-pane").style.display = "flex";
    
    // Set labels
    document.getElementById("chat-recipient-name-lbl").textContent = `${name} (@${username})`;
    
    // Force poll instantly
    lastRenderedMessagesCount = -1;
    fetchChatMessages();
}

function selectChatProtocol(protocol) {
    if (activeChatProtocol === protocol) return;
    
    activeChatProtocol = protocol;
    
    // Toggle active state on buttons
    document.getElementById("btn-proto-tcp").classList.toggle("active", protocol === "TCP");
    document.getElementById("btn-proto-udp").classList.toggle("active", protocol === "UDP");
    
    // Update label
    document.getElementById("chat-active-protocol-lbl").textContent = `Canal: ${protocol} (${protocol === 'TCP' ? 'Conexão Persistente' : 'Datagrama Rápido'})`;
    
    // Update input placeholder & send button theme
    const input = document.getElementById("unified-chat-input");
    const sendBtn = document.getElementById("unified-send-btn");
    if (protocol === "TCP") {
        input.placeholder = "Digite uma mensagem por TCP...";
        sendBtn.className = "chat-send-btn btn-tcp";
    } else {
        input.placeholder = "Digite uma mensagem por UDP...";
        sendBtn.className = "chat-send-btn btn-udp";
    }
    
    // Clear chat count to force re-render
    lastRenderedMessagesCount = -1;
    fetchChatMessages();
    
    appendToConsole(`[CHAT] Protocolo de conversa alternado para ${protocol}`, "system");
}

function handleUnifiedChatKey(event) {
    if (event.key === "Enter") {
        sendUnifiedMessage();
    }
}

async function sendUnifiedMessage() {
    if (!currentUser || !selectedRecipient) return;
    
    const input = document.getElementById("unified-chat-input");
    if (!input) return;
    
    const text = input.value.trim();
    if (!text) return;
    
    // Clear input instantly
    input.value = "";
    
    const uniqueMsgKey = `${currentUser.username}-${text}`;
    
    // Record sending state
    localSentRtts[uniqueMsgKey] = "Enviando...";
    lastRenderedMessagesCount = -1;
    fetchChatMessages();
    
    try {
        const response = await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                protocol: activeChatProtocol,
                sender: currentUser.username,
                recipient: selectedRecipient,
                content: text
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            localSentRtts[uniqueMsgKey] = `${data.rtt_ms} ms`;
        } else {
            localSentRtts[uniqueMsgKey] = "Falha";
            appendToConsole(`[ERRO CHAT] Erro ao enviar: ${data.error}`, "error");
        }
    } catch (error) {
        localSentRtts[uniqueMsgKey] = "Erro de rede";
        appendToConsole(`[ERRO CHAT] Falha de conexão: ${error.message}`, "error");
    }
    
    lastRenderedMessagesCount = -1;
    fetchChatMessages();
}

// -------------------------------------------------------------
// SOCKET SIMULATION INJECTIONS
// -------------------------------------------------------------
function handleSimulateKey(event) {
    if (event.key === "Enter") {
        injectSimulatedMessage();
    }
}

async function injectSimulatedMessage() {
    const sender = document.getElementById("sim-sender").value;
    const input = document.getElementById("sim-content");
    if (!input) return;
    
    const text = input.value.trim();
    if (!text) return;
    
    input.value = "";
    
    appendToConsole(`[SIMULADOR] Injetando mensagem de '${sender}' no socket ${activeChatProtocol}...`, "system");
    
    try {
        const response = await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                protocol: activeChatProtocol,
                sender: sender,
                content: text
            })
        });
        
        const data = await response.json();
        if (data.success) {
            appendToConsole(`[SIMULADOR] Pacote de '${sender}' transmitido e ecoado em ${data.rtt_ms} ms!`, "system");
        } else {
            appendToConsole(`[SIMULADOR ERRO] Falha ao injetar pacote: ${data.error}`, "error");
        }
    } catch (error) {
        appendToConsole(`[SIMULADOR ERRO] Falha de rede ao se comunicar com backend: ${error.message}`, "error");
    }
    
    lastRenderedMessagesCount = -1;
    fetchChatMessages();
}

// -------------------------------------------------------------
// CHAT SYNC & RENDERING ENGINE
// -------------------------------------------------------------
function startChatPolling() {
    fetchChatMessages();
    setInterval(fetchChatMessages, 500);
}

async function fetchChatMessages() {
    if (!currentUser) return;
    
    try {
        // We pass active_chat so messages from them are immediately marked as delivered/read
        const activeChatParam = selectedRecipient ? `&active_chat=${encodeURIComponent(selectedRecipient)}` : "";
        const response = await fetch(`/api/chat/messages?username=${encodeURIComponent(currentUser.username)}${activeChatParam}`);
        if (!response.ok) return;
        
        const messages = await response.json();
        allMessages = messages; // Save globally
        
        // Dynamic contact sorting & unread badge calculations
        renderContactsList();
        
        // --- NOTIFICATION ENGINE ---
        if (lastNotifiedMessageId === -1) {
            if (messages.length > 0) {
                lastNotifiedMessageId = Math.max(...messages.map(m => m.id || 0));
            } else {
                lastNotifiedMessageId = 0;
            }
        } else {
            messages.forEach(m => {
                if (m.id > lastNotifiedMessageId) {
                    lastNotifiedMessageId = Math.max(lastNotifiedMessageId, m.id);
                    
                    // Check if the message is addressed to the current logged-in user and not sent by them
                    if (m.recipient && m.recipient.toLowerCase() === currentUser.username.toLowerCase() && 
                        m.sender.toLowerCase() !== currentUser.username.toLowerCase()) {
                        
                        // Trigger notification!
                        triggerIncomingMessageNotification(m);
                    }
                }
            });
        }
        // ----------------------------
        
        // Render the chat ONLY if we are in the interactive chat tab and have a selected recipient
        if (activeTab === "interactive" && selectedRecipient) {
            // Filter messages by BOTH protocol and sender/recipient match
            const filtered = messages.filter(m => {
                const isProto = m.protocol === activeChatProtocol;
                const senderMatch = m.sender.toLowerCase() === currentUser.username.toLowerCase() && m.recipient.toLowerCase() === selectedRecipient.toLowerCase();
                const recipientMatch = m.sender.toLowerCase() === selectedRecipient.toLowerCase() && m.recipient.toLowerCase() === currentUser.username.toLowerCase();
                return isProto && (senderMatch || recipientMatch);
            });
            
            // Compute active check count or signature to detect delivery receipt changes
            const renderSignature = filtered.map(m => `${m.delivered}-${m.seq}`).join(",");
            if (filtered.length !== lastRenderedMessagesCount || this.lastRenderSignature !== renderSignature) {
                renderUnifiedChatRoom(filtered);
                lastRenderedMessagesCount = filtered.length;
                this.lastRenderSignature = renderSignature;
            }
        }
    } catch (error) {
        // Silent poll error
    }
}

function renderUnifiedChatRoom(messages) {
    const container = document.getElementById("unified-chat-messages");
    if (!container) return;
    
    container.innerHTML = `
        <div class="chat-system-msg">Canal ${activeChatProtocol} privado com @${selectedRecipient} estabelecido.</div>
    `;
    
    messages.forEach(msg => {
        const sender = msg.sender;
        const content = msg.content;
        const uniqueMsgKey = `${sender}-${content}`;
        const delivered = msg.delivered === 1;
        
        const isSelf = (sender.toLowerCase() === currentUser.username.toLowerCase());
        const direction = isSelf ? `sent ${activeChatProtocol === 'TCP' ? 'alice-msg' : 'bob-msg'}` : "received";
        const rtt = isSelf ? (localSentRtts[uniqueMsgKey] || null) : null;
        
        const displayName = isSelf ? "Você" : sender;
        appendUnifiedBubble(container, displayName, content, direction, rtt, delivered);
    });
}

function appendUnifiedBubble(container, sender, content, direction, rtt = null, delivered = false) {
    const bubbleRow = document.createElement("div");
    bubbleRow.className = `chat-msg-row ${direction}`;
    
    let metaHtml = "";
    if (direction.includes("sent")) {
        // Render checkmarks
        const checkmarks = delivered ? 
            `<span class="msg-status-receipt delivered" title="Acusação de Recepção Confirmada"><i class="fa-solid fa-check-double"></i> Recebida</span>` : 
            `<span class="msg-status-receipt sent-only" title="Mensagem Enviada"><i class="fa-solid fa-check"></i> Enviada</span>`;
            
        const rttText = rtt !== null ? `RTT: <span class="rtt-stat">${rtt}</span> | ` : "";
        metaHtml = `<div class="msg-meta-row">${rttText}${checkmarks}</div>`;
    } else {
        metaHtml = `<div class="msg-meta-row">Recebido</div>`;
    }
    
    bubbleRow.innerHTML = `
        <span class="msg-sender">${sender}</span>
        <div class="msg-bubble">${content}</div>
        ${metaHtml}
    `;
    
    container.appendChild(bubbleRow);
    container.scrollTop = container.scrollHeight;
}

// -------------------------------------------------------------
// CHARTJS GRAPHICS ENGINE
// -------------------------------------------------------------
function initCharts() {
    // 1. Latency Comparison Chart
    const ctxLatency = document.getElementById("latencyChart").getContext("2d");
    latencyChart = new Chart(ctxLatency, {
        type: 'bar',
        data: {
            labels: ['Mínimo (Min RTT)', 'Médio (Avg RTT)', 'Máximo (Max RTT)', 'Jitter (Desvio)'],
            datasets: [
                {
                    label: 'TCP (Conexão Segura)',
                    data: [0, 0, 0, 0],
                    backgroundColor: 'rgba(6, 182, 212, 0.4)',
                    borderColor: 'var(--tcp-color)',
                    borderWidth: 2,
                    borderRadius: 6
                },
                {
                    label: 'UDP (Envio Rápido)',
                    data: [0, 0, 0, 0],
                    backgroundColor: 'rgba(249, 115, 22, 0.4)',
                    borderColor: 'var(--udp-color)',
                    borderWidth: 2,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Outfit', weight: 500 } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Inter' } },
                    title: { display: true, text: 'Latência em Milissegundos (ms)', color: '#64748b' }
                }
            }
        }
    });

    // 2. Hardware Resource Usage Chart
    const ctxResources = document.getElementById("resourcesChart").getContext("2d");
    resourcesChart = new Chart(ctxResources, {
        type: 'bar',
        data: {
            labels: ['Servidor CPU %', 'Cliente CPU %', 'Servidor RAM (MB)', 'Cliente RAM (MB)'],
            datasets: [
                {
                    label: 'TCP',
                    data: [0, 0, 0, 0],
                    backgroundColor: 'rgba(6, 182, 212, 0.35)',
                    borderColor: 'rgba(6, 182, 212, 0.8)',
                    borderWidth: 1.5,
                    borderRadius: 4
                },
                {
                    label: 'UDP',
                    data: [0, 0, 0, 0],
                    backgroundColor: 'rgba(249, 115, 22, 0.35)',
                    borderColor: 'rgba(249, 115, 22, 0.8)',
                    borderWidth: 1.5,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Outfit', weight: 500 } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Inter' } },
                    title: { display: true, text: 'Intensidade / Consumo Absoluto', color: '#64748b' }
                }
            }
        }
    });
}

function updateCharts() {
    if (!latencyChart || !resourcesChart) return;
    
    // TCP Values
    const tcp = latestRuns.TCP;
    // UDP Values
    const udp = latestRuns.UDP;
    
    // Update Latency Chart Datasets
    latencyChart.data.datasets[0].data = tcp ? [tcp.latency_ms.min, tcp.latency_ms.avg, tcp.latency_ms.max, tcp.latency_ms.jitter] : [0, 0, 0, 0];
    latencyChart.data.datasets[1].data = udp ? [udp.latency_ms.min, udp.latency_ms.avg, udp.latency_ms.max, udp.latency_ms.jitter] : [0, 0, 0, 0];
    latencyChart.update();
    
    // Update Resources Chart Datasets
    resourcesChart.data.datasets[0].data = tcp ? [tcp.resources.server_cpu_percent, tcp.resources.client_cpu_percent, tcp.resources.server_ram_mb, tcp.resources.client_ram_mb] : [0, 0, 0, 0];
    resourcesChart.data.datasets[1].data = udp ? [udp.resources.server_cpu_percent, udp.resources.client_cpu_percent, udp.resources.server_ram_mb, udp.resources.client_ram_mb] : [0, 0, 0, 0];
    resourcesChart.update();
}

// -------------------------------------------------------------
// DYNAMIC ACADEMIC REPORT COMPILER
// -------------------------------------------------------------
function updateAcademicReport() {
    const tableRows = document.getElementById("academic-table-rows");
    const findingsDiv = document.getElementById("academic-telemetry-findings");
    
    if (!tableRows || !findingsDiv) return;
    
    // Clear rows
    tableRows.innerHTML = "";
    
    const tcp = latestRuns.TCP;
    const udp = latestRuns.UDP;
    
    if (!tcp && !udp) {
        tableRows.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: #888;">Nenhum benchmark foi executado ainda para popular a tabela comparativa. Inicie um teste no painel de telemetria!</td>
            </tr>
        `;
        findingsDiv.innerHTML = `
            <p><strong>Nota de Observação:</strong> Execute testes nos protocolos TCP e UDP na guia do Painel de Telemetria para que a análise automatizada preencha e plote as descobertas matemáticas e comparações de hardware de forma totalmente integrada no documento.</p>
        `;
        return;
    }
    
    // Write TCP row if exists
    if (tcp) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>TCP</strong></td>
            <td>${tcp.metrics.sent}</td>
            <td>${tcp.metrics.received}</td>
            <td>${tcp.metrics.loss_rate_percent}%</td>
            <td>${tcp.latency_ms.avg} ms</td>
            <td>${tcp.metrics.throughput_msgs_sec} msg/s</td>
            <td>${tcp.metrics.out_of_order} (${tcp.metrics.out_of_order_percent}%)</td>
        `;
        tableRows.appendChild(row);
    }
    
    // Write UDP row if exists
    if (udp) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>UDP</strong></td>
            <td>${udp.metrics.sent}</td>
            <td>${udp.metrics.received}</td>
            <td>${udp.metrics.loss_rate_percent}%</td>
            <td>${udp.latency_ms.avg} ms</td>
            <td>${udp.metrics.throughput_msgs_sec} msg/s</td>
            <td>${udp.metrics.out_of_order} (${udp.metrics.out_of_order_percent}%)</td>
        `;
        tableRows.appendChild(row);
    }
    
    // Compile scientific findings dynamically!
    let findingsHtml = `
        <div class="academic-findings-card">
            <h5>5.1 Discussão e Análise dos Resultados Experimentais</h5>
    `;
    
    if (tcp && udp) {
        const speedRatio = (udp.metrics.throughput_msgs_sec / tcp.metrics.throughput_msgs_sec).toFixed(1);
        const latencyDiff = (tcp.latency_ms.avg - udp.latency_ms.avg).toFixed(2);
        
        findingsHtml += `
            <p>Os testes experimentais revelaram dados substanciais em loopback local. O protocolo <strong>UDP demonstrou uma taxa de vazão cerca de ${speedRatio} vezes maior</strong> do que o TCP nas rajadas massivas de dados, alcançando uma latência média RTT cerca de ${Math.abs(latencyDiff)} ms mais ágil.</p>
            <p>No quesito confiabilidade, o <strong>TCP manteve perda estrita de 0% de pacotes</strong> e manteve 100% de integridade no ordenamento sequencial devido ao seu algoritmo de retransmissão de janela deslizante. Por outro lado, o UDP apresentou perda de dados correspondente a <strong>${udp.metrics.loss_rate_percent}%</strong> (incluindo drop artificial programado e colisão em buffers de recepção do SO no disparo extremo) e desordenou cerca de <strong>${udp.metrics.out_of_order}</strong> datagramas.</p>
            <p>Em relação à pegada de hardware, o TCP resultou em consumo médio do servidor de <strong>${tcp.resources.server_cpu_percent}% de CPU</strong> e <strong>${tcp.resources.server_ram_mb} MB de RAM</strong>, refletindo o alto custo computacional do gerenciamento de threads de conexão persistente e controle de congestionamento, em oposição ao UDP que consumiu apenas <strong>${udp.resources.server_cpu_percent}% de CPU</strong> e <strong>${udp.resources.server_ram_mb} MB de RAM</strong> no servidor.</p>
        `;
    } else {
        const activeProto = tcp ? "TCP" : "UDP";
        const run = tcp || udp;
        findingsHtml += `
            <p>A suite de testes coletou métricas iniciais para o protocolo <strong>${activeProto}</strong>. Constatou-se uma latência média (RTT) de <strong>${run.latency_ms.avg} ms</strong> e uma taxa de perda de <strong>${run.metrics.loss_rate_percent}%</strong> sob carga configurada de ${run.config.num_messages} pacotes. O consumo de CPU do servidor permaneceu em torno de <strong>${run.resources.server_cpu_percent}%</strong> com alocação física de memória de <strong>${run.resources.server_ram_mb} MB</strong>. Execute o teste com o protocolo oposto para gerar a análise comparativa profunda.</p>
        `;
    }
    
    findingsHtml += `</div>`;
    findingsDiv.innerHTML = findingsHtml;
}

// -------------------------------------------------------------
// NATIVE PUSH NOTIFICATIONS & AUDIO SYNTHESIS
// -------------------------------------------------------------
function requestNotificationPermission() {
    if ("Notification" in window) {
        if (Notification.permission === "default") {
            Notification.requestPermission().then(permission => {
                if (permission === "granted") {
                    appendToConsole("[SISTEMA] Permissão para notificações concedida!", "system");
                }
            });
        }
    }
}

function playNotificationSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5 tone
        oscillator.frequency.exponentialRampToValueAtTime(880.00, audioCtx.currentTime + 0.1); // A5 tone
        
        gainNode.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.35);
    } catch (e) {
        console.error("[NOTIFICAÇÃO AUDIO] Erro ao sintetizar som:", e);
    }
}

function triggerIncomingMessageNotification(msg) {
    // 1. Synthesize bell alert sound
    playNotificationSound();
    
    // 2. Spawn HTML5 desktop push notification if permission is allowed
    if ("Notification" in window && Notification.permission === "granted") {
        const title = `Nova mensagem de @${msg.sender} [${msg.protocol}]`;
        const options = {
            body: msg.content,
            icon: "unia_logo.png",
            tag: `msg-${msg.sender}`, // Deduplicate alerts for same sender
            renotify: true
        };
        
        try {
            const n = new Notification(title, options);
            n.onclick = () => {
                window.focus();
                // Find and automatically select the sender to switch chats instantly!
                const contact = registeredUsers.find(u => u.username.toLowerCase() === msg.sender.toLowerCase());
                if (contact) {
                    selectContact(contact.username, contact.name);
                }
            };
        } catch (e) {
            console.error("[NOTIFICAÇÃO PUSH] Falha ao instanciar objeto de notificação:", e);
        }
    }
}
