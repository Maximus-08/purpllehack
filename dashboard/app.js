document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const storeId = urlParams.get("store_id") || "STORE_BLR_002";
    const apiBase = ""; // relative routes are served from FastAPI
    
    const storeTitleEl = document.getElementById("store-title-id");
    if (storeTitleEl) {
        storeTitleEl.textContent = `(${storeId})`;
    }
    
    function updateMetrics() {
        // 1. Fetch Metrics
        fetch(`${apiBase}/stores/${storeId}/metrics`)
            .then(res => {
                if (!res.ok) throw new Error("API error");
                return res.json();
            })
            .then(data => {
                document.getElementById("metric-visitors").textContent = data.unique_visitors;
                document.getElementById("metric-conversion").textContent = (data.conversion_rate * 100).toFixed(1) + "%";
                document.getElementById("metric-queue").textContent = data.current_queue_depth;
                document.getElementById("metric-abandonment").textContent = (data.abandonment_rate * 100).toFixed(1) + "%";
                
                document.getElementById("connection-status").className = "status-dot connected";
                document.getElementById("connection-text").textContent = "Connected";
            })
            .catch(err => {
                console.error("Error fetching metrics:", err);
                document.getElementById("connection-status").className = "status-dot disconnected";
                document.getElementById("connection-text").textContent = "Disconnected";
            });
            
        // 2. Fetch Funnel
        fetch(`${apiBase}/stores/${storeId}/funnel`)
            .then(res => {
                if (!res.ok) throw new Error("Funnel API error");
                return res.json();
            })
            .then(data => {
                const container = document.getElementById("funnel-container");
                container.innerHTML = "";
                
                const list = document.createElement("div");
                list.className = "funnel-list";
                
                data.stages.forEach(stage => {
                    const row = document.createElement("div");
                    row.className = "funnel-row";
                    row.innerHTML = `
                        <div class="funnel-label">${stage.stage}</div>
                        <div class="funnel-bar-container">
                            <div class="funnel-bar" style="width: ${stage.percentage}%"></div>
                        </div>
                        <div class="funnel-value">${stage.count} (${stage.percentage}%)</div>
                    `;
                    list.appendChild(row);
                });
                container.appendChild(list);
            })
            .catch(err => console.error("Error fetching funnel:", err));
            
        // 3. Fetch Heatmap
        fetch(`${apiBase}/stores/${storeId}/heatmap`)
            .then(res => {
                if (!res.ok) throw new Error("Heatmap API error");
                return res.json();
            })
            .then(data => {
                const container = document.getElementById("heatmap-container");
                container.innerHTML = "";
                
                data.zones.forEach(zone => {
                    const card = document.createElement("div");
                    card.className = "heatmap-card";
                    
                    const opacity = Math.max(0.1, zone.score / 100);
                    card.style.borderColor = `rgba(217, 70, 239, ${opacity})`;
                    card.style.backgroundColor = `rgba(217, 70, 239, ${opacity * 0.15})`;
                    
                    card.innerHTML = `
                        <div class="zone-name">${zone.name}</div>
                        <div class="zone-score">${zone.score.toFixed(0)}</div>
                        <div class="zone-metrics">
                            <span>Visits: ${zone.visit_count}</span>
                            <span>Dwell: ${(zone.avg_dwell_ms / 1000).toFixed(0)}s</span>
                        </div>
                    `;
                    container.appendChild(card);
                });
            })
            .catch(err => console.error("Error fetching heatmap:", err));
            
        // 4. Fetch Anomalies
        fetch(`${apiBase}/stores/${storeId}/anomalies`)
            .then(res => {
                if (!res.ok) throw new Error("Anomalies API error");
                return res.json();
            })
            .then(data => {
                const container = document.getElementById("anomalies-container");
                container.innerHTML = "";
                
                if (!data || data.length === 0) {
                    container.innerHTML = '<div class="anomaly-placeholder">No active anomalies detected.</div>';
                    return;
                }
                
                data.forEach(anomaly => {
                    const item = document.createElement("div");
                    item.className = `anomaly-item ${anomaly.severity.toLowerCase()}`;
                    
                    const dtStr = anomaly.detected_at;
                    let displayTime = "";
                    try {
                        displayTime = new Date(dtStr).toLocaleTimeString();
                    } catch (e) {
                        displayTime = dtStr;
                    }
                    
                    item.innerHTML = `
                        <div class="anomaly-header">
                            <span class="anomaly-badge ${anomaly.severity.toLowerCase()}">${anomaly.severity}</span>
                            <span class="anomaly-type">${anomaly.type}</span>
                            <span class="anomaly-time">${displayTime}</span>
                        </div>
                        <div class="anomaly-message">${anomaly.message}</div>
                        <div class="anomaly-action"><strong>Suggested Action:</strong> ${anomaly.suggested_action}</div>
                    `;
                    container.appendChild(item);
                });
            })
            .catch(err => console.error("Error fetching anomalies:", err));
    }
    
    // Initial load and start interval polling
    updateMetrics();
    setInterval(updateMetrics, 3000);
});

