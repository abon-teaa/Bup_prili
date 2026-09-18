const PRESET_SCENARIOS = {
    "scenario_01": {
        scenario_id: "scenario_01_sunny_day",
        operator_notes: [
            "Cloud cover will reduce solar generation by 30% from 12 PM to 2 PM.",
            "Water the flowers at the main substation garden.",
            "Keep battery reserve at 50% between 18:00 and 22:00 for emergency backup."
        ],
        battery: {
            capacity_kwh: 200,
            initial_energy_kwh: 50,
            minimum_energy_kwh: 20,
            max_charge_kwh_per_hour: 40,
            max_discharge_kwh_per_hour: 40
        }
    },
    "scenario_02": {
        scenario_id: "scenario_02_peak_tariff",
        operator_notes: [
            "Do not charge battery from 17:00 to 21:00 due to peak grid tariff rates.",
            "Grid electricity price forecast updated for tomorrow."
        ],
        battery: {
            capacity_kwh: 250,
            initial_energy_kwh: 60,
            minimum_energy_kwh: 25,
            max_charge_kwh_per_hour: 50,
            max_discharge_kwh_per_hour: 50
        }
    },
    "scenario_03": {
        scenario_id: "scenario_03_grid_cap",
        operator_notes: [
            "Grid import cap of 35 kWh between 12:00 and 16:00.",
            "Do not discharge battery between 0:00 and 6:00 to preserve life cycle."
        ],
        battery: {
            capacity_kwh: 180,
            initial_energy_kwh: 40,
            minimum_energy_kwh: 15,
            max_charge_kwh_per_hour: 30,
            max_discharge_kwh_per_hour: 30
        }
    },
    "scenario_04": {
        scenario_id: "scenario_04_multi_directive",
        operator_notes: [
            "Inverter fault from hour 10 to 14, expect 50% reduction in solar output.",
            "Do not charge battery from 17:00 to 21:00.",
            "Maintain minimum 80 kWh battery storage from 2 PM to 6 PM."
        ],
        battery: {
            capacity_kwh: 200,
            initial_energy_kwh: 50,
            minimum_energy_kwh: 20,
            max_charge_kwh_per_hour: 40,
            max_discharge_kwh_per_hour: 40
        }
    }
};

let dispatchChartInstance = null;

function generate24HourProfiles() {
    const hours = [];
    const baseDemand = [20, 18, 15, 15, 18, 25, 40, 55, 70, 75, 70, 65, 60, 65, 70, 75, 85, 95, 100, 90, 75, 60, 45, 30];
    const baseSolar =  [0,  0,  0,  0,  0,  5, 20, 45, 70, 90, 110, 120, 125, 120, 105, 80, 50, 20, 5,  0,  0,  0,  0,  0];
    const baseTariff = [5,  5,  5,  5,  5,  7, 10, 12, 12, 12, 10,  8,   8,  8,  10, 12, 15, 18, 18, 18, 15, 10, 7,  5];

    for (let h = 0; h < 24; h++) {
        hours.push({
            hour: h,
            demand_kwh: baseDemand[h],
            solar_kwh: baseSolar[h],
            tariff_bdt_per_kwh: baseTariff[h]
        });
    }
    return hours;
}

function loadPresetScenario() {
    const selectedKey = document.getElementById("scenarioPreset").value;
    const scenario = PRESET_SCENARIOS[selectedKey];
    if (!scenario) return;

    document.getElementById("note0").value = scenario.operator_notes[0] || "";
    document.getElementById("note1").value = scenario.operator_notes[1] || "";
    document.getElementById("note2").value = scenario.operator_notes[2] || "";

    document.getElementById("batCapacity").value = scenario.battery.capacity_kwh;
    document.getElementById("batInitial").value = scenario.battery.initial_energy_kwh;
    document.getElementById("batMin").value = scenario.battery.minimum_energy_kwh;
    document.getElementById("batMaxChg").value = scenario.battery.max_charge_kwh_per_hour;
    document.getElementById("batMaxDis").value = scenario.battery.max_discharge_kwh_per_hour;
}

const API_BASE = (window.location.protocol.startsWith("http") && (window.location.port === "8000" || window.location.port === ""))
    ? ""
    : "http://localhost:8000";

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === "ok") {
            document.getElementById("healthText").innerText = "GET /health: OK";
            document.getElementById("healthBadge").style.borderColor = "rgba(16, 185, 129, 0.5)";
        }
    } catch (e) {
        document.getElementById("healthText").innerText = "GET /health: FAIL";
        document.getElementById("healthBadge").style.borderColor = "rgba(239, 68, 68, 0.5)";
    }
}

async function runOptimization() {
    const selectedKey = document.getElementById("scenarioPreset").value;
    const scenarioDef = PRESET_SCENARIOS[selectedKey];

    const notes = [];
    const n0 = document.getElementById("note0").value.trim();
    const n1 = document.getElementById("note1").value.trim();
    const n2 = document.getElementById("note2").value.trim();
    if (n0) notes.push(n0);
    if (n1) notes.push(n1);
    if (n2) notes.push(n2);
    if (notes.length === 0) notes.push("Standard operation.");

    const payload = {
        scenario_id: scenarioDef.scenario_id,
        operator_notes: notes,
        hours: generate24HourProfiles(),
        battery: {
            capacity_kwh: parseFloat(document.getElementById("batCapacity").value),
            initial_energy_kwh: parseFloat(document.getElementById("batInitial").value),
            minimum_energy_kwh: parseFloat(document.getElementById("batMin").value),
            max_charge_kwh_per_hour: parseFloat(document.getElementById("batMaxChg").value),
            max_discharge_kwh_per_hour: parseFloat(document.getElementById("batMaxDis").value)
        }
    };

    const btn = document.getElementById("btnOptimize");
    const originalBtnHTML = btn.innerHTML;
    btn.disabled = true;
    btn.style.opacity = "0.7";
    btn.innerHTML = `<svg class="icon-svg" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg> Optimizing...`;

    const startTime = performance.now();
    try {
        const response = await fetch(`${API_BASE}/optimize-energy`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const elapsed = (performance.now() - startTime).toFixed(0);
        document.getElementById("latencyText").innerText = `Latency: ${elapsed} ms`;

        if (!response.ok) {
            const err = await response.json();
            alert("Optimization Error: " + (err.detail || "Server error"));
            return;
        }

        const data = await response.json();
        renderResults(data, payload);
    } catch (err) {
        console.error(err);
        alert("Failed to connect to /optimize-energy endpoint. Ensure backend is running on port 8000.");
    } finally {
        btn.disabled = false;
        btn.style.opacity = "1";
        btn.innerHTML = originalBtnHTML;
    }
}

function renderResults(data, payload) {
    document.getElementById("valTotalCost").innerText = `${data.total_cost_bdt.toFixed(2)} BDT`;
    document.getElementById("valTotalGrid").innerText = `${data.total_grid_kwh.toFixed(2)} kWh`;
    document.getElementById("valPeakGrid").innerText = `${data.peak_grid_kwh.toFixed(2)} kWh`;
    
    const eodEnergy = data.hourly_plan[23].battery_energy_after_kwh;
    document.getElementById("valEodBattery").innerText = `${eodEnergy.toFixed(2)} kWh`;

    const dirContainer = document.getElementById("directiveList");
    dirContainer.innerHTML = "";
    
    data.directive_interpretation.forEach(interp => {
        const div = document.createElement("div");
        div.className = `directive-item ${interp.applies ? '' : 'no-op'}`;
        
        let details = "";
        if (interp.structured_adjustment) {
            details = JSON.stringify(interp.structured_adjustment);
        }

        div.innerHTML = `
            <div>
                <strong>Note #${interp.note_index + 1}:</strong> "${payload.operator_notes[interp.note_index] || ''}"
                <p class="directive-explanation">${interp.explanation}</p>
            </div>
            <div style="text-align:right;">
                <span class="directive-badge ${interp.applies ? '' : 'no-op'}">${interp.directive_type}</span>
                ${details ? `<p class="directive-details">${details}</p>` : ''}
            </div>
        `;
        dirContainer.appendChild(div);
    });

    document.getElementById("planSummaryText").innerText = data.plan_summary;
    renderChart(data.hourly_plan, payload.hours);
}

function renderChart(plan, inputHours) {
    const ctx = document.getElementById("dispatchChart").getContext("2d");

    const labels = plan.map(item => `${item.hour}:00`);
    const gridData = plan.map(item => item.grid_kwh);
    const solarUsedData = plan.map(item => item.solar_used_kwh);
    const batteryEnergyData = plan.map(item => item.battery_energy_after_kwh);
    const demandData = inputHours.map(h => h.demand_kwh);

    if (dispatchChartInstance) {
        dispatchChartInstance.destroy();
    }

    dispatchChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Grid Import (kWh)',
                    data: gridData,
                    backgroundColor: '#7dd3fc',
                    borderColor: '#1c261d',
                    borderWidth: 2,
                    order: 2
                },
                {
                    label: 'Solar Used (kWh)',
                    data: solarUsedData,
                    backgroundColor: '#fae392',
                    borderColor: '#1c261d',
                    borderWidth: 2,
                    order: 2
                },
                {
                    label: 'Demand (kWh)',
                    data: demandData,
                    type: 'line',
                    borderColor: '#dc2626',
                    backgroundColor: '#dc2626',
                    borderWidth: 2.5,
                    pointRadius: 3,
                    pointBorderColor: '#1c261d',
                    pointBorderWidth: 1.5,
                    fill: false,
                    order: 1
                },
                {
                    label: 'Battery SoC (kWh)',
                    data: batteryEnergyData,
                    type: 'line',
                    borderColor: '#15803d',
                    backgroundColor: '#15803d',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBorderColor: '#1c261d',
                    pointBorderWidth: 1.5,
                    fill: false,
                    yAxisID: 'yBattery',
                    order: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    grid: { color: 'rgba(28, 38, 29, 0.08)' },
                    ticks: {
                        color: '#1c261d',
                        font: { family: "'Space Mono', monospace", size: 10 }
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Power / Energy (kWh)',
                        color: '#1c261d',
                        font: { family: "'Space Mono', monospace", size: 11, weight: 'bold' }
                    },
                    grid: { color: 'rgba(28, 38, 29, 0.08)' },
                    ticks: {
                        color: '#1c261d',
                        font: { family: "'Space Mono', monospace", size: 10 }
                    }
                },
                yBattery: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Battery Storage (kWh)',
                        color: '#15803d',
                        font: { family: "'Space Mono', monospace", size: 11, weight: 'bold' }
                    },
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: '#15803d',
                        font: { family: "'Space Mono', monospace", size: 10 }
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#1c261d',
                        font: { family: "'Space Mono', monospace", size: 11, weight: 'bold' },
                        boxWidth: 16,
                        boxHeight: 12
                    }
                },
                tooltip: {
                    titleFont: { family: "'Space Mono', monospace" },
                    bodyFont: { family: "'Space Mono', monospace" }
                }
            }
        }
    });
}

window.addEventListener("DOMContentLoaded", () => {
    loadPresetScenario();
    checkHealth();
    runOptimization();
});
