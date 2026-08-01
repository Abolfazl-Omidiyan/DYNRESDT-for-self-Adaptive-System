# DYNRESDT-for-self-Adaptive-System
# DYNRESDT: Self-Adaptive Digital Twin for Emergency Observation Wards 🏥⚡

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20JS%20%7C%20TailwindCSS-orange.svg)
![Architecture](https://img.shields.io/badge/Architecture-MAPE--K%20Loop-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

An adaptive, real-time Digital Twin framework designed to dynamically scale capacity, optimize resource allocation, and preserve clinical safety in hospital Emergency Observation Wards using a closed-loop MAPE-K (Monitor-Analyze-Plan-Execute-Knowledge) feedback control system.

---

## 📌 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture (MAPE-K)](#-system-architecture-mape-k)
- [Mathematical Model & Optimization](#-mathematical-model--optimization)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Deployment Modes](#-deployment-modes)
- [Recent Innovation & Future Work](#-recent-innovation--future-work)
- [Author & Acknowledgments](#-author--acknowledgments)

---

## 🌟 Overview

Emergency observation wards face highly unpredictable patient arrival surges. Traditional static capacity management leads to two critical operational bottlenecks:
1. Under-utilization: Excessive idle beds causing steep standing operational expenses.
2. Over-saturation: Severe ward congestion, long queue delays, and clinical safety risks.

DYNRESDT acts as a Self-Adaptive Digital Twin operating on the Models@run.time paradigm. It continuously monitors bed utilization and queue lengths, dynamically bringing secondary overflow zones (e.g., converted administrative offices, emergency corridors) online during peak surges and consolidating resources as demand subsides.

---

## 🚀 Key Features

* Closed-Loop Self-Adaptation: Built strictly around the classical MAPE-K feedback loop model.
* Dynamic Severity-Based Triage Queue: Prioritizes bed allocations dynamically based on clinical urgency (HIGH, MEDIUM, LOW) rather than relying on standard FIFO queues.
* Interactive Floor Plan & Actuators: Real-time visual ward dashboard allowing manual bed blocking to simulate physical disruptions (e.g., equipment failures, maintenance).
* Live Telemetry & Analytics: Integrated Chart.js dashboards tracking utilization rates, queue lengths, and financial/risk trade-offs.
* Zero External Backend Dependencies: Uses Python's native http.server for lightweight development and custom WSGI integration for cPanel production hosting.
* Telemetry Data Export: Built-in CSV dataset generator (/api/export-excel) for 48-hour post-simulation statistical analysis.

---

## 🏗 System Architecture (MAPE-K)

1. Knowledge (K): Maintains state models (Models@run.time), ward topology (4 Standard Rooms, 2 Overflow Offices, 1 Emergency Corridor), and control thresholds (Gamma_high = 0.80, Gamma_critical = 0.92).
2. Monitor (M): Calculates live utilization rates and queue telemetry metrics.
3. Analyze (A): Evaluates operational states (NORMAL_LOAD, HIGH_LOAD, CRISIS_MODE).
4.
Plan (P): Executes penalty-guided state space search to identify optimal topology adaptations.
5. Execute (E): Enacts physical changes (activating/deactivating zones, transferring patients).

---

## 🧮 Mathematical Model & Optimization

The adaptation engine minimizes an overall objective cost function C_total(s) per hourly cycle:

C_total(s) = C_op(s) + C_penalty(s) + Omega_transition(s)

### Cost Components Breakdown

| Zone / Room Type | Hourly Operational Cost (C_op) | Sub-optimal Placement Penalty (Psi_suboptimal) |
| :--- | :---: | :---: |
| Standard Room | $15 / hr | $0 / hr |
| Overflow Office | $25 / hr | $80 / hr |
| Emergency Corridor | $35 / hr | $160 / hr |

* Queue Penalty (Psi_queue): $300 / hr per waiting patient (weighted dynamically by clinical severity and wait time).
* Anti-Thrashing Penalty (Omega_transition): Temporary penalty ($150 - $450) applied during room toggle actions to prevent rapid, unnecessary adaptation cycles.

---

## 📁 Project Structure

DYNRESDT/
├── app.py                 # Core domain engine, MAPE-K logic, & standalone HTTP server
├── passenger_wsgi.py      # WSGI entry point for cPanel / Phusion Passenger hosting
├── index.html             # Single Page Application (SPA) frontend dashboard
├── static/
│   ├── css/               # Tailwind CSS visual styling
│   └── js/                # Chart.js live charts & API polling logic
├── README.md              # Documentation
└── LICENSE                # License information

---

## 💻 Getting Started

### Prerequisites
* Python 3.8+ (Zero third-party library installations required for core backend execution)

---

## 🌐 Deployment Modes

* Standalone Development Mode: Uses Python's native http.server running on 0.0.0.0:3000.
* Production Mode (WSGI / cPanel): Configured via passenger_wsgi.py with embedded exception catching (passenger_error.log) to ensure seamless execution on shared cPanel hosting setups.

---

## 🔬 Recent Innovation & Future Work

* Dynamic Triage Priority Queue (Implemented): Replaced default FIFO queues with a risk-weighted queue function (Severity x WaitTime) to ensure critical patients are prioritized immediately when secondary beds open up.
* Future Work:
  * Predictive MAPE-K: Integrating machine learning forecasting models (e.g., XGBoost, LSTM) in the Analyze phase for proactive surge preparation.
  * Staffing Optimization: Extending the mathematical model to account for Nurse-to-Patient ratios during zone activations.
  * HIS Interoperability: Adding support for HL7/FHIR protocols to integrate directly with live hospital admission systems.

---

## 👤 Author

* Abolfazl Omidiyan
  * Email: realomidiyan@gmail.com
  * LinkedIn : https://www.linkedin.com/in/abolfazl-omidiyan/
  * Live Portal: deepsek.ir 
  * Institution: Shahid Beheshti University — Master’s in Information Technology (Enterprise Architecture)
  * Course: Self-Adaptive Systems
