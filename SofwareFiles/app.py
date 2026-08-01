import os
import sys
import json
import random
import uuid
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ==========================================
# 1. CORE SIMULATION CLASSES & CONFIGURATIONS
# ==========================================

class RoomType:
    STANDARD = 'STANDARD'
    OVERFLOW_OFFICE = 'OVERFLOW_OFFICE'
    OVERFLOW_CORRIDOR = 'OVERFLOW_CORRIDOR'

class BedStatus:
    AVAILABLE = 'AVAILABLE'
    OCCUPIED = 'OCCUPIED'
    BLOCKED = 'BLOCKED'

class OperationalPhase:
    NORMAL_LOAD = 'NORMAL_LOAD'
    HIGH_LOAD = 'HIGH_LOAD'
    CRISIS_MODE = 'CRISIS_MODE'

class Patient:
    def __init__(self, id, name, severity, arrival_time, discharge_time, assigned_bed_id=None, assigned_room_id=None):
        self.id = id
        self.name = name
        self.severity = severity
        self.arrival_time = arrival_time
        self.discharge_time = discharge_time
        self.assigned_bed_id = assigned_bed_id
        self.assigned_room_id = assigned_room_id

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'severity': self.severity,
            'arrivalTime': self.arrival_time,
            'dischargeTime': self.discharge_time,
            'assignedBedId': self.assigned_bed_id,
            'assignedRoomId': self.assigned_room_id
        }

class Bed:
    def __init__(self, id, room_id, name, status, patient_id=None):
        self.id = id
        self.room_id = room_id
        self.name = name
        self.status = status
        self.patient_id = patient_id

    def to_dict(self):
        return {
            'id': self.id,
            'roomId': self.room_id,
            'name': self.name,
            'status': self.status,
            'patientId': self.patient_id
        }

class Room:
    def __init__(self, id, name, room_type, is_active, beds, base_capacity, operational_cost_per_hour, safety_penalty_per_hour):
        self.id = id
        self.name = name
        self.type = room_type
        self.is_active = is_active
        self.beds = beds
        self.base_capacity = base_capacity
        self.operational_cost_per_hour = operational_cost_per_hour
        self.safety_penalty_per_hour = safety_penalty_per_hour

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'isActive': self.is_active,
            'beds': [b.to_dict() for b in self.beds],
            'baseCapacity': self.base_capacity,
            'operationalCostPerHour': self.operational_cost_per_hour,
            'safetyPenaltyPerHour': self.safety_penalty_per_hour
        }

class WardState:
    def __init__(self, id, name, rooms):
        self.id = id
        self.name = name
        self.rooms = rooms

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'rooms': [r.to_dict() for r in self.rooms]
        }

INITIAL_ROOMS_CONFIG = [
    {'id': 'rm-std-1', 'name': 'Standard Room A', 'type': RoomType.STANDARD, 'bedsCount': 4, 'operationalCost': 15, 'penalty': 0},
    {'id': 'rm-std-2', 'name': 'Standard Room B', 'type': RoomType.STANDARD, 'bedsCount': 4, 'operationalCost': 15, 'penalty': 0},
    {'id': 'rm-std-3', 'name': 'Standard Room C', 'type': RoomType.STANDARD, 'bedsCount': 4, 'operationalCost': 15, 'penalty': 0},
    {'id': 'rm-std-4', 'name': 'Standard Room D', 'type': RoomType.STANDARD, 'bedsCount': 4, 'operationalCost': 15, 'penalty': 0},
    {'id': 'rm-off-1', 'name': 'Overflow Office Zone 1', 'type': RoomType.OVERFLOW_OFFICE, 'bedsCount': 3, 'operationalCost': 25, 'penalty': 80},
    {'id': 'rm-off-2', 'name': 'Overflow Office Zone 2', 'type': RoomType.OVERFLOW_OFFICE, 'bedsCount': 3, 'operationalCost': 25, 'penalty': 80},
    {'id': 'rm-cor-1', 'name': 'Overflow Corridor Zone A', 'type': RoomType.OVERFLOW_CORRIDOR, 'bedsCount': 4, 'operationalCost': 35, 'penalty': 160},
]

def initialize_ward_state():
    rooms = []
    for cfg in INITIAL_ROOMS_CONFIG:
        beds = []
        for i in range(cfg['bedsCount']):
            beds.append(Bed(
                id=f"{cfg['id']}-bed-{i + 1}",
                room_id=cfg['id'],
                name=f"Bed {i + 1}",
                status=BedStatus.AVAILABLE
            ))
        rooms.append(Room(
            id=cfg['id'],
            name=cfg['name'],
            room_type=cfg['type'],
            is_active=(cfg['type'] == RoomType.STANDARD),
            beds=beds,
            base_capacity=cfg['bedsCount'],
            operational_cost_per_hour=cfg['operationalCost'],
            safety_penalty_per_hour=cfg['penalty']
        ))
    return WardState(id='ward-main', name='Emergency Response & Observation Ward', rooms=rooms)

# ==========================================
# 2. MAPE-K SELF-ADAPTATION CONTROLLER LOGIC
# ==========================================

def monitor_system(ward, waiting_queue, arrival_rate, discharge_rate, current_sim_hour):
    active_beds_count = 0
    occupied_beds_count = 0
    blocked_beds_count = 0
    operational_cost_rate = 0
    penalty_cost_rate = 0

    for room in ward.rooms:
        if room.is_active:
            operational_cost_rate += room.operational_cost_per_hour
            if room.type != RoomType.STANDARD:
                occupied_in_room = sum(1 for b in room.beds if b.status == BedStatus.OCCUPIED)
                penalty_cost_rate += room.safety_penalty_per_hour * occupied_in_room

            for bed in room.beds:
                active_beds_count += 1
                if bed.status == BedStatus.OCCUPIED:
                    occupied_beds_count += 1
                elif bed.status == BedStatus.BLOCKED:
                    blocked_beds_count += 1

    effective_active_beds = max(1, active_beds_count - blocked_beds_count)
    utilization_rate = occupied_beds_count / effective_active_beds
    waiting_queue_penalty = len(waiting_queue) * 300
    penalty_cost_rate += waiting_queue_penalty
    total_cost_rate = operational_cost_rate + penalty_cost_rate

    return {
        'timestamp': current_sim_hour,
        'activeBedsCount': active_beds_count,
        'occupiedBedsCount': occupied_beds_count,
        'blockedBedsCount': blocked_beds_count,
        'utilizationRate': utilization_rate,
        'waitingQueueCount': len(waiting_queue),
        'arrivalRate': arrival_rate,
        'dischargeRate': discharge_rate,
        'operationalCostRate': operational_cost_rate,
        'penaltyCostRate': penalty_cost_rate,
        'totalCostRate': total_cost_rate
    }

def analyze_system(metrics, current_phase):
    gamma_high = 0.80
    gamma_critical = 0.92
    gamma_low = 0.40

    target_phase = OperationalPhase.NORMAL_LOAD
    analysis_message = ''
    adaptation_required = False

    if metrics['waitingQueueCount'] > 0 or metrics['utilizationRate'] >= gamma_critical:
        target_phase = OperationalPhase.CRISIS_MODE
        analysis_message = f"CRITICAL STATE: Bed utilization at {metrics['utilizationRate'] * 100:.1f}% exceeds limit of {gamma_critical * 100:.0f}%, or waiting list ({metrics['waitingQueueCount']}) is active. Capacity scaling triggered."
        adaptation_required = True
    elif metrics['utilizationRate'] >= gamma_high:
        target_phase = OperationalPhase.HIGH_LOAD
        analysis_message = f"ALERT STATE: High load detected at {metrics['utilizationRate'] * 100:.1f}% (Threshold: {gamma_high * 100:.0f}%). Proactive scale suggested."
        adaptation_required = True
    elif metrics['utilizationRate'] <= gamma_low and metrics['activeBedsCount'] > 16:
        target_phase = OperationalPhase.NORMAL_LOAD
        analysis_message = f"LOW LOAD STATE: Ward load at {metrics['utilizationRate'] * 100:.1f}% is below consolidation threshold. Recommending resource consolidation."
        adaptation_required = True
    else:
        target_phase = OperationalPhase.NORMAL_LOAD
        analysis_message = f"STABLE STATE: Bed utilization at {metrics['utilizationRate'] * 100:.1f}% is nominal. No adaptation needed."
        adaptation_required = False

    if target_phase != current_phase:
        adaptation_required = True

    return {
        'phase': target_phase,
        'analysisMessage': analysis_message,
        'adaptationRequired': adaptation_required
    }

def plan_adaptation(ward, metrics, analysis_phase, waiting_queue):
    candidates = []
    current_total_cost = metrics['totalCostRate']

    candidates.append({
        'id': 'act-no-action',
        'type': 'NO_ACTION',
        'utilityCost': current_total_cost,
        'reason': 'Maintain current configuration.'
    })

    def estimate_hypothetical_cost(activate_room_id=None, deactivate_room_id=None):
        active_beds = 0
        operational_cost = 0
        safety_penalty = 0

        for room in ward.rooms:
            is_room_active = room.is_active
            if room.id == activate_room_id:
                is_room_active = True
            if room.id == deactivate_room_id:
                is_room_active = False

            if is_room_active:
                operational_cost += room.operational_cost_per_hour
                if room.type != RoomType.STANDARD:
                    safety_penalty += room.safety_penalty_per_hour * room.base_capacity
                for b in room.beds:
                    active_beds += 1

        added_beds = 0
        if activate_room_id:
            for r in ward.rooms:
                if r.id == activate_room_id:
                    added_beds = r.base_capacity

        estimated_waiting_count = max(0, len(waiting_queue) - added_beds)
        waiting_penalty = estimated_waiting_count * 300
        
        reconfig_overhead = 0
        if activate_room_id:
            room_to_open = next((r for r in ward.rooms if r.id == activate_room_id), None)
            if room_to_open:
                if room_to_open.type == RoomType.OVERFLOW_CORRIDOR:
                    reconfig_overhead = 450
                elif room_to_open.type == RoomType.OVERFLOW_OFFICE:
                    reconfig_overhead = 250
                else:
                    reconfig_overhead = 100
        if deactivate_room_id:
            reconfig_overhead = 150

        return operational_cost + safety_penalty + waiting_penalty + reconfig_overhead

    inactive_rooms = [r for r in ward.rooms if not r.is_active]
    for room in inactive_rooms:
        cost = estimate_hypothetical_cost(activate_room_id=room.id)
        candidates.append({
            'id': f"act-activate-{room.id}",
            'type': 'ACTIVATE_ROOM',
            'targetRoomId': room.id,
            'utilityCost': cost,
            'reason': f"Activate {room.name}. Score: ${cost:.0f}/hr."
        })

    if analysis_phase == OperationalPhase.NORMAL_LOAD and metrics['utilizationRate'] < 0.40:
        active_overflow_rooms = [r for r in ward.rooms if r.is_active and r.type != RoomType.STANDARD]
        for room in active_overflow_rooms:
            total_avail = sum(sum(1 for b in r.beds if b.status == BedStatus.AVAILABLE) for r in ward.rooms if r.is_active and r.id != room.id)
            occupied_in_room = sum(1 for b in room.beds if b.status == BedStatus.OCCUPIED)
            if total_avail >= occupied_in_room:
                cost = estimate_hypothetical_cost(deactivate_room_id=room.id)
                candidates.append({
                    'id': f"act-deactivate-{room.id}",
                    'type': 'DEACTIVATE_ROOM',
                    'targetRoomId': room.id,
                    'utilityCost': cost,
                    'reason': f"Deactivate {room.name} to save operational cost."
                })

    active_overflow_with_p = any(b.status == BedStatus.OCCUPIED for r in ward.rooms if r.is_active and r.type != RoomType.STANDARD for b in r.beds)
    active_std_with_v = any(b.status == BedStatus.AVAILABLE for r in ward.rooms if r.is_active and r.type == RoomType.STANDARD for b in r.beds)

    if active_overflow_with_p and active_std_with_v:
        candidates.append({
            'id': 'act-consolidate',
            'type': 'CONSOLIDATE_PATIENTS',
            'utilityCost': current_total_cost - 50,
            'reason': 'Consolidate overflow patients back to standard rooms.'
        })

    candidates.sort(key=lambda x: x['utilityCost'])
    best_action = candidates[0]
    no_action = next(c for c in candidates if c['type'] == 'NO_ACTION')

    if len(waiting_queue) > 0 and best_action['type'] == 'ACTIVATE_ROOM':
        return best_action

    if best_action['utilityCost'] < no_action['utilityCost'] * 0.95:
        return best_action

    return no_action

def execute_adaptation(ward, action, waiting_queue, current_sim_hour, phase, metrics):
    updated_queue = list(waiting_queue)
    logs_text = ''

    if action['type'] == 'ACTIVATE_ROOM':
        room = next((r for r in ward.rooms if r.id == action.get('targetRoomId')), None)
        if room:
            room.is_active = True
            logs_text = f"Activated zone: {room.name} ({room.type}). Added {room.base_capacity} beds."
            avail_beds = [b for b in room.beds if b.status == BedStatus.AVAILABLE]
            filled_count = 0
            for bed in avail_beds:
                if len(updated_queue) == 0:
                    break
                p = updated_queue.pop(0)
                bed.status = BedStatus.OCCUPIED
                bed.patient_id = p.id
                p.assigned_bed_id = bed.id
                p.assigned_room_id = room.id
                filled_count += 1
            if filled_count > 0:
                logs_text += f" Allocated {filled_count} waiting patient(s) immediately."

    elif action['type'] == 'DEACTIVATE_ROOM':
        room = next((r for r in ward.rooms if r.id == action.get('targetRoomId')), None)
        if room:
            occupied = [b for b in room.beds if b.status == BedStatus.OCCUPIED]
            relocated_count = 0
            for bed in occupied:
                pid = bed.patient_id
                for r in ward.rooms:
                    if r.is_active and r.type == RoomType.STANDARD and r.id != room.id:
                        v_bed = next((b for b in r.beds if b.status == BedStatus.AVAILABLE), None)
                        if v_bed:
                            v_bed.status = BedStatus.OCCUPIED
                            v_bed.patient_id = pid
                            bed.status = BedStatus.AVAILABLE
                            bed.patient_id = None
                            relocated_count += 1
                            break
            room.is_active = False
            logs_text = f"Deactivated zone: {room.name}. Relocated {relocated_count} patients."

    elif action['type'] == 'CONSOLIDATE_PATIENTS':
        consolidate_count = 0
        for s_room in ward.rooms:
            if s_room.is_active and s_room.type != RoomType.STANDARD:
                for s_bed in s_room.beds:
                    if s_bed.status == BedStatus.OCCUPIED:
                        pid = s_bed.patient_id
                        for t_room in ward.rooms:
                            if t_room.is_active and t_room.type == RoomType.STANDARD:
                                t_bed = next((b for b in t_room.beds if b.status == BedStatus.AVAILABLE), None)
                                if t_bed:
                                    t_bed.status = BedStatus.OCCUPIED
                                    t_bed.patient_id = pid
                                    s_bed.status = BedStatus.AVAILABLE
                                    s_bed.patient_id = None
                                    consolidate_count += 1
                                    break
        logs_text = f"Consolidated {consolidate_count} patient(s) from overflow to standard rooms."

    else:
        logs_text = "Ward state stable. No adjustments executed."

    log_entry = {
        'id': f"log-{int(time.time()*1000)}-{str(uuid.uuid4())[:4]}",
        'timestamp': current_sim_hour,
        'phase': phase,
        'metrics': {
            'utilization': metrics['utilizationRate'],
            'waitingCount': metrics['waitingQueueCount']
        },
        'analysis': logs_text,
        'actionTaken': action['type'] + (f" ({action.get('targetRoomId')})" if action.get('targetRoomId') else ''),
        'costImpact': {
            'operational': metrics['operationalCostRate'],
            'penalty': metrics['penaltyCostRate']
        }
    }

    return ward, updated_queue, log_entry

def assign_waiting_queue_to_beds(ward, queue):
    updated_queue = list(queue)
    rooms_sorted = sorted([r for r in ward.rooms if r.is_active], key=lambda r: 0 if r.type == RoomType.STANDARD else 1)

    for room in rooms_sorted:
        v_beds = [b for b in room.beds if b.status == BedStatus.AVAILABLE]
        for bed in v_beds:
            if len(updated_queue) == 0:
                break
            p = updated_queue.pop(0)
            bed.status = BedStatus.OCCUPIED
            bed.patient_id = p.id
            p.assigned_bed_id = bed.id
            p.assigned_room_id = room.id

    return ward, updated_queue

def process_discharges(ward, current_hour, patients_map):
    discharged_ids = []
    for room in ward.rooms:
        for bed in room.beds:
            if bed.status == BedStatus.OCCUPIED and bed.patient_id:
                p = patients_map.get(bed.patient_id)
                if p and current_hour >= p.discharge_time:
                    discharged_ids.append(bed.patient_id)
                    bed.status = BedStatus.AVAILABLE
                    bed.patient_id = None

    return ward, discharged_ids

# ==========================================
# 3. WEB SERVER STATE ENGINE & FLOW LOGIC
# ==========================================

PATIENT_NAMES = [
    'Ali Rezaei', 'Maryam Hosseini', 'Mohammad Karimi', 'Zahra Ghasemi', 'Amir Soltani',
    'Fatemeh Rahimi', 'Mehdi Ahmadi', 'Sara Ebadi', 'Reza Mousavi', 'Neda Tehrani',
    'Pouya Alizadeh', 'Yasaman Salehi', 'Arash Sadeghi', 'Elnaz Shakeri', 'Sina Moradi',
    'Taraneh Alidoosti', 'Babak Radmanesh', 'Pegah Faraji', 'Kaveh Behdad', 'Shirin Yazdani',
    'Nima Yousefi', 'Sohrab Sepehri', 'Mitra Mansouri', 'Farzaneh Kabiri', 'Mani Farhadi',
    'Saman Jalili', 'Anahita Nemati', 'Dariush Mehrjui', 'Rostam Samadi', 'Soraya Ghasemi'
]

class AppState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.ward_state = initialize_ward_state()
        self.waiting_queue = []
        self.patients_map = {}
        self.current_sim_hour = 0
        self.is_playing = False
        self.speed = 1500
        self.metrics = monitor_system(self.ward_state, self.waiting_queue, 0, 0, 0)
        self.metrics_history = [self.metrics]
        self.history_logs = []
        self.operational_phase = OperationalPhase.NORMAL_LOAD
        self.analysis_message = 'System initialized. Waiting for simulation stream.'
        self.current_action = None
        self.seed_initial_patients()

    def seed_initial_patients(self):
        initial_patients_count = 12
        active_rooms = [r for r in self.ward_state.rooms if r.is_active]
        patient_index = 0

        for room in active_rooms:
            for bed in room.beds:
                if patient_index < initial_patients_count:
                    p_name = PATIENT_NAMES[patient_index % len(PATIENT_NAMES)]
                    p_id = f"pat-init-{patient_index}"
                    patient = Patient(
                        id=p_id,
                        name=p_name,
                        severity='MEDIUM' if random.random() > 0.8 else 'LOW',
                        arrival_time=0,
                        discharge_time=random.randint(4, 9),
                        assigned_bed_id=bed.id,
                        assigned_room_id=room.id
                    )
                    bed.status = BedStatus.OCCUPIED
                    bed.patient_id = p_id
                    self.patients_map[p_id] = patient
                    patient_index += 1

        self.metrics = monitor_system(self.ward_state, self.waiting_queue, 1, 0, 0)
        self.metrics_history = [self.metrics]
        self.analysis_message = 'Ward initialized with baseline population (12 patients: 75% utilization, close to warning threshold Gamma_high=80%).'

    def step(self):
        next_hour = self.current_sim_hour + 1
        self.current_sim_hour = next_hour

        self.ward_state, discharged_ids = process_discharges(
            self.ward_state,
            next_hour,
            self.patients_map
        )

        curve_hour = next_hour % 24
        if 0 <= curve_hour <= 4:
            base_arrivals = 1 if random.random() > 0.6 else 0
        elif 5 <= curve_hour <= 11:
            base_arrivals = random.randint(2, 4)
        elif 12 <= curve_hour <= 17:
            base_arrivals = random.randint(1, 2)
        else:
            base_arrivals = 1 if random.random() > 0.5 else 0

        new_arrivals = []
        for i in range(base_arrivals):
            r_name = random.choice(PATIENT_NAMES)
            r_id = f"pat-{next_hour}-{i}-{str(random.randint(1000, 9999))}"
            rand_sev = random.random()
            severity = 'HIGH' if rand_sev > 0.85 else ('MEDIUM' if rand_sev > 0.6 else 'LOW')
            duration = random.randint(3, 7) if severity != 'HIGH' else random.randint(6, 11)

            p = Patient(
                id=r_id,
                name=r_name,
                severity=severity,
                arrival_time=next_hour,
                discharge_time=next_hour + duration
            )
            new_arrivals.append(p)
            self.patients_map[r_id] = p

        next_queue = self.waiting_queue + new_arrivals
        self.ward_state, final_queue = assign_waiting_queue_to_beds(self.ward_state, next_queue)
        self.waiting_queue = final_queue

        monitored_metrics = monitor_system(
            self.ward_state,
            self.waiting_queue,
            len(new_arrivals),
            len(discharged_ids),
            next_hour
        )
        self.metrics = monitored_metrics

        analysis = analyze_system(monitored_metrics, self.operational_phase)
        plan = plan_adaptation(self.ward_state, monitored_metrics, analysis['phase'], self.waiting_queue)

        updated_ward, updated_queue, log_entry = execute_adaptation(
            self.ward_state,
            plan,
            self.waiting_queue,
            next_hour,
            analysis['phase'],
            monitored_metrics
        )

        self.ward_state = updated_ward
        self.waiting_queue = updated_queue
        self.operational_phase = analysis['phase']
        self.analysis_message = analysis['analysisMessage']
        self.current_action = plan

        self.metrics_history.append(monitored_metrics)
        if len(self.metrics_history) > 48:
            self.metrics_history.pop(0)

        if plan['type'] != 'NO_ACTION' or analysis['phase'] != self.operational_phase:
            self.history_logs.insert(0, log_entry)

    def toggle_block_bed(self, room_id, bed_id):
        room = next((r for r in self.ward_state.rooms if r.id == room_id), None)
        if not room:
            return

        bed = next((b for b in room.beds if b.id == bed_id), None)
        if not bed:
            return

        next_queue = list(self.waiting_queue)

        if bed.status == BedStatus.BLOCKED:
            bed.status = BedStatus.AVAILABLE
        else:
            if bed.status == BedStatus.OCCUPIED and bed.patient_id:
                patient = self.patients_map.get(bed.patient_id)
                if patient:
                    patient.assigned_bed_id = None
                    patient.assigned_room_id = None
                    next_queue.insert(0, patient)
                bed.patient_id = None
            bed.status = BedStatus.BLOCKED

        self.ward_state, final_queue = assign_waiting_queue_to_beds(self.ward_state, next_queue)
        self.waiting_queue = final_queue

        monitored_metrics = monitor_system(self.ward_state, self.waiting_queue, 0, 0, self.current_sim_hour)
        self.metrics = monitored_metrics

        analysis = analyze_system(monitored_metrics, self.operational_phase)
        plan = plan_adaptation(self.ward_state, monitored_metrics, analysis['phase'], self.waiting_queue)

        updated_ward, updated_queue, log_entry = execute_adaptation(
            self.ward_state,
            plan,
            self.waiting_queue,
            self.current_sim_hour,
            analysis['phase'],
            monitored_metrics
        )

        self.ward_state = updated_ward
        self.waiting_queue = updated_queue
        self.operational_phase = analysis['phase']
        self.analysis_message = analysis['analysisMessage']
        self.current_action = plan

        if plan['type'] != 'NO_ACTION':
            self.history_logs.insert(0, log_entry)

    def inject_patients(self, count, is_severe=False):
        new_patients = []
        for i in range(count):
            r_name = random.choice(PATIENT_NAMES)
            r_id = f"pat-manual-{self.current_sim_hour}-{i}-{str(random.randint(1000, 9999))}"
            severity = 'HIGH' if is_severe else ('MEDIUM' if random.random() > 0.7 else 'LOW')
            duration = random.randint(6, 11) if is_severe else random.randint(3, 7)

            p = Patient(
                id=r_id,
                name=r_name,
                severity=severity,
                arrival_time=self.current_sim_hour,
                discharge_time=self.current_sim_hour + duration
            )
            new_patients.append(p)
            self.patients_map[r_id] = p

        next_queue = self.waiting_queue + new_patients
        self.ward_state, final_queue = assign_waiting_queue_to_beds(self.ward_state, next_queue)
        self.waiting_queue = final_queue

        monitored_metrics = monitor_system(
            self.ward_state,
            self.waiting_queue,
            len(new_patients),
            0,
            self.current_sim_hour
        )
        self.metrics = monitored_metrics

        analysis = analyze_system(monitored_metrics, self.operational_phase)
        plan = plan_adaptation(self.ward_state, monitored_metrics, analysis['phase'], self.waiting_queue)

        updated_ward, updated_queue, log_entry = execute_adaptation(
            self.ward_state,
            plan,
            self.waiting_queue,
            self.current_sim_hour,
            analysis['phase'],
            monitored_metrics
        )

        self.ward_state = updated_ward
        self.waiting_queue = updated_queue
        self.operational_phase = analysis['phase']
        self.analysis_message = analysis['analysisMessage']
        self.current_action = plan

        if plan['type'] != 'NO_ACTION':
            self.history_logs.insert(0, log_entry)

state = AppState()

# ==========================================
# 4. LIGHTWEIGHT SERVER & API ROUTING ENGINE
# ==========================================

class PythonTwinServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            # Smart fallback: check same directory first, then templates folder
            html_paths = [
                os.path.join(os.path.dirname(__file__), 'index.html'),
                os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
            ]
            content = b"<h1>index.html not found! Please place index.html in the same directory.</h1>"
            for p in html_paths:
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        content = f.read()
                    break
            self.wfile.write(content)
            
        elif parsed.path == '/api/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            p_map_serializable = {k: v.to_dict() for k, v in state.patients_map.items()}
            res = {
                'wardState': state.ward_state.to_dict(),
                'waitingQueue': [p.to_dict() for p in state.waiting_queue],
                'patientsMap': p_map_serializable,
                'currentSimHour': state.current_sim_hour,
                'isPlaying': state.is_playing,
                'speed': state.speed,
                'metrics': state.metrics,
                'metricsHistory': state.metrics_history,
                'historyLogs': state.history_logs,
                'operationalPhase': state.operational_phase,
                'analysisMessage': state.analysis_message,
                'currentAction': state.current_action
            }
            self.wfile.write(json.dumps(res).encode('utf-8'))
            
        elif parsed.path in ('/api/export-excel', '/api/export-csv'):
            headers = [
                'Simulated Hour',
                'Active Beds',
                'Occupied Beds',
                'Blocked Beds',
                'Utilization Rate (%)',
                'Waiting Queue Count',
                'Arrival Rate',
                'Discharge Rate',
                'Operational Cost ($/hr)',
                'Penalty Cost ($/hr)',
                'Total Cost ($/hr)'
            ]
            rows = []
            for m in state.metrics_history:
                rows.append([
                    str(m['timestamp']),
                    str(m['activeBedsCount']),
                    str(m['occupiedBedsCount']),
                    str(m['blockedBedsCount']),
                    f"{m['utilizationRate'] * 100:.1f}",
                    str(m['waitingQueueCount']),
                    str(m['arrivalRate']),
                    str(m['dischargeRate']),
                    str(m['operationalCostRate']),
                    str(m['penaltyCostRate']),
                    str(m['totalCostRate'])
                ])
            csv_data = ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', f"attachment; filename=DYNRESDT_telemetry_hour_{state.current_sim_hour}.csv")
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        body = {}
        if post_data:
            try:
                body = json.loads(post_data.decode('utf-8'))
            except:
                pass

        if parsed.path == '/api/step':
            state.step()
        elif parsed.path == '/api/play-toggle':
            state.is_playing = body.get('isPlaying', not state.is_playing)
        elif parsed.path == '/api/speed':
            state.speed = body.get('speed', 1500)
        elif parsed.path == '/api/reset':
            state.reset()
        elif parsed.path == '/api/block-bed':
            state.toggle_block_bed(body.get('roomId'), body.get('bedId'))
        elif parsed.path == '/api/inject':
            state.inject_patients(body.get('count', 3), body.get('isSevere', False))
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        p_map_serializable = {k: v.to_dict() for k, v in state.patients_map.items()}
        res = {
            'wardState': state.ward_state.to_dict(),
            'waitingQueue': [p.to_dict() for p in state.waiting_queue],
            'patientsMap': p_map_serializable,
            'currentSimHour': state.current_sim_hour,
            'isPlaying': state.is_playing,
            'speed': state.speed,
            'metrics': state.metrics,
            'metricsHistory': state.metrics_history,
            'historyLogs': state.history_logs,
            'operationalPhase': state.operational_phase,
            'analysisMessage': state.analysis_message,
            'currentAction': state.current_action
        }
        self.wfile.write(json.dumps(res).encode('utf-8'))


# ==========================================
# 5. WSGI COMPATIBILITY FOR HOSTING SERVERS (cPanel, Phusion Passenger)
# ==========================================

def application(environ, start_response):
    path = environ.get('PATH_INFO', '')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    # helper to read request body
    body = {}
    if method == 'POST':
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = environ['wsgi.input'].read(content_length)
            if post_data:
                body = json.loads(post_data.decode('utf-8'))
        except Exception:
            pass

    if method == 'GET':
        if path == '/' or path == '/index.html' or path == '':
            html_paths = [
                os.path.join(os.path.dirname(__file__), 'index.html'),
                os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
            ]
            content = b"<h1>index.html not found! Please place index.html in the same directory.</h1>"
            for p in html_paths:
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        content = f.read()
                    break
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [content]
            
        elif path == '/api/state':
            p_map_serializable = {k: v.to_dict() for k, v in state.patients_map.items()}
            res = {
                'wardState': state.ward_state.to_dict(),
                'waitingQueue': [p.to_dict() for p in state.waiting_queue],
                'patientsMap': p_map_serializable,
                'currentSimHour': state.current_sim_hour,
                'isPlaying': state.is_playing,
                'speed': state.speed,
                'metrics': state.metrics,
                'metricsHistory': state.metrics_history,
                'historyLogs': state.history_logs,
                'operationalPhase': state.operational_phase,
                'analysisMessage': state.analysis_message,
                'currentAction': state.current_action
            }
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [json.dumps(res).encode('utf-8')]
            
        elif path in ('/api/export-excel', '/api/export-csv'):
            headers = [
                'Simulated Hour', 'Active Beds', 'Occupied Beds', 'Blocked Beds',
                'Utilization Rate (%)', 'Waiting Queue Count', 'Arrival Rate',
                'Discharge Rate', 'Operational Cost ($/hr)', 'Penalty Cost ($/hr)',
                'Total Cost ($/hr)'
            ]
            rows = []
            for m in state.metrics_history:
                rows.append([
                    str(m['timestamp']),
                    str(m['activeBedsCount']),
                    str(m['occupiedBedsCount']),
                    str(m['blockedBedsCount']),
                    f"{m['utilizationRate'] * 100:.1f}",
                    str(m['waitingQueueCount']),
                    str(m['arrivalRate']),
                    str(m['dischargeRate']),
                    str(m['operationalCostRate']),
                    str(m['penaltyCostRate']),
                    str(m['totalCostRate'])
                ])
            csv_data = ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows)
            start_response('200 OK', [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f"attachment; filename=DYNRESDT_telemetry_hour_{state.current_sim_hour}.csv")
            ])
            return [csv_data.encode('utf-8')]
            
    elif method == 'POST':
        if path == '/api/step':
            state.step()
        elif path == '/api/play-toggle':
            state.is_playing = body.get('isPlaying', not state.is_playing)
        elif path == '/api/speed':
            state.speed = body.get('speed', 1500)
        elif path == '/api/reset':
            state.reset()
        elif path == '/api/block-bed':
            state.toggle_block_bed(body.get('roomId'), body.get('bedId'))
        elif path == '/api/inject':
            state.inject_patients(body.get('count', 3), body.get('isSevere', False))
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found"]
            
        p_map_serializable = {k: v.to_dict() for k, v in state.patients_map.items()}
        res = {
            'wardState': state.ward_state.to_dict(),
            'waitingQueue': [p.to_dict() for p in state.waiting_queue],
            'patientsMap': p_map_serializable,
            'currentSimHour': state.current_sim_hour,
            'isPlaying': state.is_playing,
            'speed': state.speed,
            'metrics': state.metrics,
            'metricsHistory': state.metrics_history,
            'historyLogs': state.history_logs,
            'operationalPhase': state.operational_phase,
            'analysisMessage': state.analysis_message,
            'currentAction': state.current_action
        }
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps(res).encode('utf-8')]

    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b"Not Found"]


def run():
    server_address = ('0.0.0.0', 3000)
    httpd = HTTPServer(server_address, PythonTwinServer)
    print("DYNRESDT Web App running on port 3000...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
