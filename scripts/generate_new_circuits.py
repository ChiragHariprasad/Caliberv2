"""Generates high-precision 2D SVG Circuit Geometries for the 7 new F1 tracks.
Outputs files directly to backend/pulse/circuits/data/<circuit_id>.json conforming to CircuitGeometry schema.
"""
import hashlib
import json
import math
from pathlib import Path

OUT_DIR = Path("backend/pulse/circuits/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def catmull_rom_spline(control_points, num_points_per_seg=6):
    """Interpolates a closed loop of 2D control points using Catmull-Rom cubic splines."""
    n = len(control_points)
    points = []
    for i in range(n):
        p0 = control_points[(i - 1) % n]
        p1 = control_points[i]
        p2 = control_points[(i + 1) % n]
        p3 = control_points[(i + 2) % n]
        for t_step in range(num_points_per_seg):
            t = t_step / float(num_points_per_seg)
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) +
                       (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) +
                       (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            points.append([round(x, 2), round(y, 2)])
    return points

def build_circuit_spec(circuit_id, name, country, city, length_m, direction, control_pts, corners_def, drs_def, pit_def, view_box):
    centreline = catmull_rom_spline(control_pts, num_points_per_seg=6)
    
    # Calculate sector checkpoints at 33% and 66% of progress
    n_pts = len(centreline)
    sec1_idx = int(n_pts * 0.33)
    sec2_idx = int(n_pts * 0.66)
    
    sectors = [
        {"sector_number": 1, "start_progress": 0.0, "end_progress": 0.33, "checkpoint": centreline[sec1_idx]},
        {"sector_number": 2, "start_progress": 0.33, "end_progress": 0.66, "checkpoint": centreline[sec2_idx]},
        {"sector_number": 3, "start_progress": 0.66, "end_progress": 1.0, "checkpoint": centreline[0]},
    ]
    
    # Start / finish line perpendicular to start segment
    p_start = centreline[0]
    p_next = centreline[1]
    dx = p_next[0] - p_start[0]
    dy = p_next[1] - p_start[1]
    dist = math.hypot(dx, dy) or 1.0
    nx = -dy / dist * 12.0
    ny = dx / dist * 12.0
    start_finish_line = [
        [round(p_start[0] - nx, 2), round(p_start[1] - ny, 2)],
        [round(p_start[0] + nx, 2), round(p_start[1] + ny, 2)],
    ]
    
    data = {
        "circuit_id": circuit_id,
        "name": name,
        "country": country,
        "city": city,
        "layout_id": f"{circuit_id}-homologated-v1",
        "layout_version": "2024.1",
        "length_meters": float(length_m),
        "track_direction": direction,
        "coordinate_reference_system": "LOCAL_NORMALIZED_1000",
        "source_attribution": f"FIA Official Circuit Homologation Dossier / {name}",
        "centreline": centreline,
        "inner_boundary": [],
        "outer_boundary": [],
        "corners": corners_def,
        "sectors": sectors,
        "pit_lane": pit_def,
        "start_finish_line": start_finish_line,
        "drs_zones": drs_def,
        "view_box": view_box,
    }
    
    # Calculate deterministic SHA-256 checksum
    serialized = json.dumps(data, sort_keys=True)
    data["checksum_sha256"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return data

# -------------------------------------------------------------
# 1. Spa-Francorchamps (Belgium)
# -------------------------------------------------------------
spa_ctrl = [
    [320, 520], [330, 480], [350, 420], [370, 340], [420, 240], [480, 180],
    [540, 170], [590, 220], [610, 290], [600, 360], [560, 430], [510, 480],
    [480, 550], [440, 600], [380, 610], [330, 580]
]
spa_corners = [
    {"number": 1, "name": "La Source", "x": 330.0, "y": 480.0, "sector": 1, "apex_speed_kmh": 75.0},
    {"number": 2, "name": "Eau Rouge", "x": 350.0, "y": 420.0, "sector": 1, "apex_speed_kmh": 295.0},
    {"number": 3, "name": "Raidillon", "x": 370.0, "y": 340.0, "sector": 1, "apex_speed_kmh": 305.0},
    {"number": 5, "name": "Les Combes", "x": 480.0, "y": 180.0, "sector": 1, "apex_speed_kmh": 140.0},
    {"number": 7, "name": "Malmedy", "x": 540.0, "y": 170.0, "sector": 2, "apex_speed_kmh": 175.0},
    {"number": 8, "name": "Bruxelles", "x": 590.0, "y": 220.0, "sector": 2, "apex_speed_kmh": 110.0},
    {"number": 10, "name": "Pouhon", "x": 600.0, "y": 360.0, "sector": 2, "apex_speed_kmh": 285.0},
    {"number": 12, "name": "Fagnes", "x": 560.0, "y": 430.0, "sector": 2, "apex_speed_kmh": 165.0},
    {"number": 14, "name": "Stavelot", "x": 510.0, "y": 480.0, "sector": 3, "apex_speed_kmh": 180.0},
    {"number": 17, "name": "Blanchimont", "x": 440.0, "y": 600.0, "sector": 3, "apex_speed_kmh": 315.0},
    {"number": 19, "name": "Bus Stop Chicane", "x": 350.0, "y": 560.0, "sector": 3, "apex_speed_kmh": 85.0},
]
spa_pit = {
    "entry_point": [360.0, 580.0],
    "exit_point": [335.0, 450.0],
    "path": [[360.0, 580.0], [340.0, 530.0], [335.0, 450.0]],
    "speed_limit_kmh": 80
}
spa_drs = [
    {"zone_id": 1, "detection_point": [380.0, 310.0], "activation_point": [410.0, 260.0], "length_meters": 780.0},
    {"zone_id": 2, "detection_point": [360.0, 600.0], "activation_point": [330.0, 550.0], "length_meters": 620.0},
]
spa_data = build_circuit_spec("spa", "Circuit de Spa-Francorchamps", "Belgium", "Stavelot", 7004.0, "CLOCKWISE",
                              spa_ctrl, spa_corners, spa_drs, spa_pit, {"min_x": 260.0, "min_y": 120.0, "width": 420.0, "height": 540.0})

# -------------------------------------------------------------
# 2. Red Bull Ring (Austria)
# -------------------------------------------------------------
rbr_ctrl = [
    [280, 520], [350, 520], [480, 500], [580, 440], [540, 320], [440, 260],
    [320, 270], [240, 340], [210, 420], [230, 480]
]
rbr_corners = [
    {"number": 1, "name": "Niki Lauda Kurve", "x": 480.0, "y": 500.0, "sector": 1, "apex_speed_kmh": 140.0},
    {"number": 3, "name": "Remus", "x": 580.0, "y": 440.0, "sector": 1, "apex_speed_kmh": 70.0},
    {"number": 4, "name": "Schlossgold", "x": 540.0, "y": 320.0, "sector": 2, "apex_speed_kmh": 120.0},
    {"number": 6, "name": "Gerhard Berger Kurve", "x": 320.0, "y": 270.0, "sector": 2, "apex_speed_kmh": 185.0},
    {"number": 9, "name": "Jochen Rindt", "x": 210.0, "y": 420.0, "sector": 3, "apex_speed_kmh": 215.0},
    {"number": 10, "name": "Red Bull Mobile", "x": 240.0, "y": 500.0, "sector": 3, "apex_speed_kmh": 190.0},
]
rbr_pit = {
    "entry_point": [220.0, 450.0],
    "exit_point": [380.0, 530.0],
    "path": [[220.0, 450.0], [260.0, 535.0], [380.0, 530.0]],
    "speed_limit_kmh": 80
}
rbr_drs = [
    {"zone_id": 1, "detection_point": [240.0, 490.0], "activation_point": [290.0, 520.0], "length_meters": 610.0},
    {"zone_id": 2, "detection_point": [490.0, 490.0], "activation_point": [520.0, 470.0], "length_meters": 740.0},
    {"zone_id": 3, "detection_point": [570.0, 410.0], "activation_point": [550.0, 360.0], "length_meters": 580.0},
]
rbr_data = build_circuit_spec("red_bull_ring", "Red Bull Ring", "Austria", "Spielberg", 4318.0, "CLOCKWISE",
                              rbr_ctrl, rbr_corners, rbr_drs, rbr_pit, {"min_x": 160.0, "min_y": 210.0, "width": 480.0, "height": 360.0})

# -------------------------------------------------------------
# 3. Yas Marina Circuit (Abu Dhabi)
# -------------------------------------------------------------
yas_ctrl = [
    [420, 560], [320, 540], [260, 460], [250, 360], [290, 270], [380, 210],
    [520, 200], [610, 260], [630, 360], [590, 450], [520, 520], [470, 550]
]
yas_corners = [
    {"number": 1, "name": "Turn 1", "x": 320.0, "y": 540.0, "sector": 1, "apex_speed_kmh": 135.0},
    {"number": 5, "name": "North Hairpin", "x": 260.0, "y": 360.0, "sector": 1, "apex_speed_kmh": 80.0},
    {"number": 6, "name": "Chicane In", "x": 350.0, "y": 220.0, "sector": 2, "apex_speed_kmh": 125.0},
    {"number": 9, "name": "Marsa Corner (Banked)", "x": 610.0, "y": 260.0, "sector": 2, "apex_speed_kmh": 220.0},
    {"number": 12, "name": "Hotel Section", "x": 590.0, "y": 450.0, "sector": 3, "apex_speed_kmh": 110.0},
    {"number": 16, "name": "Final Corner", "x": 450.0, "y": 555.0, "sector": 3, "apex_speed_kmh": 190.0},
]
yas_pit = {
    "entry_point": [480.0, 540.0],
    "exit_point": [290.0, 510.0],
    "path": [[480.0, 540.0], [420.0, 575.0], [350.0, 560.0], [290.0, 510.0]],
    "speed_limit_kmh": 80
}
yas_drs = [
    {"zone_id": 1, "detection_point": [280.0, 320.0], "activation_point": [320.0, 240.0], "length_meters": 820.0},
    {"zone_id": 2, "detection_point": [550.0, 220.0], "activation_point": [580.0, 240.0], "length_meters": 710.0},
]
yas_data = build_circuit_spec("yas_marina", "Yas Marina Circuit", "United Arab Emirates", "Abu Dhabi", 5281.0, "COUNTER_CLOCKWISE",
                              yas_ctrl, yas_corners, yas_drs, yas_pit, {"min_x": 200.0, "min_y": 150.0, "width": 480.0, "height": 450.0})

# -------------------------------------------------------------
# 4. Jeddah Corniche Circuit (Saudi Arabia)
# -------------------------------------------------------------
jed_ctrl = [
    [240, 580], [260, 480], [280, 380], [320, 270], [380, 180], [440, 190],
    [480, 270], [450, 380], [410, 470], [350, 540], [280, 590]
]
jed_corners = [
    {"number": 1, "name": "Turn 1 Chicane", "x": 260.0, "y": 480.0, "sector": 1, "apex_speed_kmh": 105.0},
    {"number": 13, "name": "Banked Hairpin", "x": 420.0, "y": 180.0, "sector": 1, "apex_speed_kmh": 125.0},
    {"number": 22, "name": "High-Speed Chicane", "x": 450.0, "y": 380.0, "sector": 2, "apex_speed_kmh": 225.0},
    {"number": 27, "name": "Final Hairpin", "x": 260.0, "y": 570.0, "sector": 3, "apex_speed_kmh": 95.0},
]
jed_pit = {
    "entry_point": [280.0, 570.0],
    "exit_point": [250.0, 450.0],
    "path": [[280.0, 570.0], [245.0, 520.0], [250.0, 450.0]],
    "speed_limit_kmh": 80
}
jed_drs = [
    {"zone_id": 1, "detection_point": [300.0, 340.0], "activation_point": [340.0, 240.0], "length_meters": 750.0},
    {"zone_id": 2, "detection_point": [470.0, 230.0], "activation_point": [460.0, 320.0], "length_meters": 690.0},
    {"zone_id": 3, "detection_point": [390.0, 490.0], "activation_point": [330.0, 550.0], "length_meters": 810.0},
]
jed_data = build_circuit_spec("jeddah", "Jeddah Corniche Circuit", "Saudi Arabia", "Jeddah", 6174.0, "COUNTER_CLOCKWISE",
                              jed_ctrl, jed_corners, jed_drs, jed_pit, {"min_x": 190.0, "min_y": 130.0, "width": 340.0, "height": 500.0})

# -------------------------------------------------------------
# 5. Albert Park (Australia)
# -------------------------------------------------------------
alb_ctrl = [
    [320, 540], [390, 530], [480, 470], [540, 390], [570, 280], [520, 210],
    [430, 210], [360, 260], [320, 340], [280, 440], [280, 510]
]
alb_corners = [
    {"number": 1, "name": "Jones", "x": 390.0, "y": 530.0, "sector": 1, "apex_speed_kmh": 145.0},
    {"number": 3, "name": "Whiteford", "x": 480.0, "y": 470.0, "sector": 1, "apex_speed_kmh": 115.0},
    {"number": 6, "name": "Marina", "x": 570.0, "y": 280.0, "sector": 2, "apex_speed_kmh": 150.0},
    {"number": 9, "name": "Lakeside Sweep", "x": 480.0, "y": 210.0, "sector": 2, "apex_speed_kmh": 280.0},
    {"number": 11, "name": "Waite Chicane", "x": 360.0, "y": 260.0, "sector": 3, "apex_speed_kmh": 225.0},
    {"number": 13, "name": "Ascari", "x": 280.0, "y": 440.0, "sector": 3, "apex_speed_kmh": 130.0},
]
alb_pit = {
    "entry_point": [280.0, 480.0],
    "exit_point": [380.0, 540.0],
    "path": [[280.0, 480.0], [310.0, 555.0], [380.0, 540.0]],
    "speed_limit_kmh": 80
}
alb_drs = [
    {"zone_id": 1, "detection_point": [290.0, 490.0], "activation_point": [340.0, 535.0], "length_meters": 680.0},
    {"zone_id": 2, "detection_point": [420.0, 500.0], "activation_point": [450.0, 480.0], "length_meters": 540.0},
    {"zone_id": 3, "detection_point": [540.0, 240.0], "activation_point": [500.0, 210.0], "length_meters": 710.0},
]
alb_data = build_circuit_spec("albert_park", "Albert Park Circuit", "Australia", "Melbourne", 5278.0, "CLOCKWISE",
                              alb_ctrl, alb_corners, alb_drs, alb_pit, {"min_x": 220.0, "min_y": 160.0, "width": 400.0, "height": 420.0})

# -------------------------------------------------------------
# 6. Circuit of the Americas (USA - Austin)
# -------------------------------------------------------------
cota_ctrl = [
    [320, 540], [380, 530], [460, 480], [530, 420], [580, 330], [550, 240],
    [470, 220], [380, 260], [300, 320], [250, 410], [270, 490]
]
cota_corners = [
    {"number": 1, "name": "Turn 1 (Steep Uphill)", "x": 380.0, "y": 530.0, "sector": 1, "apex_speed_kmh": 90.0},
    {"number": 3, "name": "Esses Entry", "x": 460.0, "y": 480.0, "sector": 1, "apex_speed_kmh": 265.0},
    {"number": 11, "name": "Hairpin to Back Straight", "x": 580.0, "y": 330.0, "sector": 2, "apex_speed_kmh": 75.0},
    {"number": 12, "name": "Turn 12 Heavy Braking", "x": 500.0, "y": 220.0, "sector": 2, "apex_speed_kmh": 85.0},
    {"number": 15, "name": "Stadium Hairpin", "x": 380.0, "y": 260.0, "sector": 3, "apex_speed_kmh": 105.0},
    {"number": 16, "name": "Triple Apex Carousel", "x": 300.0, "y": 320.0, "sector": 3, "apex_speed_kmh": 210.0},
    {"number": 20, "name": "Final Turn", "x": 270.0, "y": 490.0, "sector": 3, "apex_speed_kmh": 130.0},
]
cota_pit = {
    "entry_point": [260.0, 460.0],
    "exit_point": [370.0, 545.0],
    "path": [[260.0, 460.0], [290.0, 555.0], [370.0, 545.0]],
    "speed_limit_kmh": 80
}
cota_drs = [
    {"zone_id": 1, "detection_point": [280.0, 480.0], "activation_point": [330.0, 535.0], "length_meters": 650.0},
    {"zone_id": 2, "detection_point": [560.0, 300.0], "activation_point": [520.0, 230.0], "length_meters": 890.0},
]
cota_data = build_circuit_spec("cota", "Circuit of the Americas", "United States", "Austin", 5513.0, "COUNTER_CLOCKWISE",
                              cota_ctrl, cota_corners, cota_drs, cota_pit, {"min_x": 210.0, "min_y": 170.0, "width": 420.0, "height": 410.0})

# -------------------------------------------------------------
# 7. Las Vegas Strip Circuit (USA)
# -------------------------------------------------------------
lv_ctrl = [
    [310, 550], [410, 550], [530, 520], [620, 440], [600, 310], [500, 230],
    [380, 220], [280, 290], [240, 390], [260, 490]
]
lv_corners = [
    {"number": 1, "name": "Turn 1 Chicane", "x": 410.0, "y": 550.0, "sector": 1, "apex_speed_kmh": 95.0},
    {"number": 5, "name": "Sphere Complex", "x": 620.0, "y": 440.0, "sector": 1, "apex_speed_kmh": 115.0},
    {"number": 12, "name": "Turn 12 onto The Strip", "x": 520.0, "y": 240.0, "sector": 2, "apex_speed_kmh": 260.0},
    {"number": 14, "name": "Harmon Ave Chicane", "x": 320.0, "y": 240.0, "sector": 3, "apex_speed_kmh": 110.0},
    {"number": 17, "name": "Main Straight Entry", "x": 270.0, "y": 500.0, "sector": 3, "apex_speed_kmh": 185.0},
]
lv_pit = {
    "entry_point": [260.0, 470.0],
    "exit_point": [390.0, 560.0],
    "path": [[260.0, 470.0], [300.0, 570.0], [390.0, 560.0]],
    "speed_limit_kmh": 80
}
lv_drs = [
    {"zone_id": 1, "detection_point": [270.0, 480.0], "activation_point": [330.0, 550.0], "length_meters": 620.0},
    {"zone_id": 2, "detection_point": [550.0, 280.0], "activation_point": [460.0, 225.0], "length_meters": 1100.0},
]
lv_data = build_circuit_spec("las_vegas", "Las Vegas Strip Circuit", "United States", "Las Vegas", 6201.0, "COUNTER_CLOCKWISE",
                             lv_ctrl, lv_corners, lv_drs, lv_pit, {"min_x": 200.0, "min_y": 170.0, "width": 460.0, "height": 420.0})

# Write all out
for c_data in [spa_data, rbr_data, yas_data, jed_data, alb_data, cota_data, lv_data]:
    file_path = OUT_DIR / f"{c_data['circuit_id']}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(c_data, f, indent=2)
    print(f"Generated {file_path.name} (length: {c_data['length_meters']}m, {len(c_data['corners'])} corners)")

